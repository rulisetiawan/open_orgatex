package mqtt

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"da-db-writer/internal/storage"

	paho "github.com/eclipse/paho.mqtt.golang"
)

type ConsumerOptions struct {
	BrokerURL          string
	ClientID           string
	Username           string
	Password           string
	SharedGroup        string
	TopicFilter        string
	BatchMaxSize       int
	BatchFlushInterval time.Duration
	WorkerCount        int
	QueueSize          int
}

type rawMessage struct {
	topic   string
	subType string
	payload []byte
}

type Consumer struct {
	client             paho.Client
	storage            *storage.Storage
	logger             *slog.Logger
	ctx                context.Context
	cancel             context.CancelFunc
	wg                 sync.WaitGroup
	telemetryCh        chan rawMessage
	telemetryBatchCh   chan []storage.TelemetryPayload
	eventCh            chan rawMessage
	batchMaxSize       int
	batchFlushInterval time.Duration
	workerCount        int

	receivedCount atomic.Uint64
	droppedCount  atomic.Uint64
	flushedCount  atomic.Uint64
}

func NewConsumer(
	optsCfg ConsumerOptions,
	store *storage.Storage,
	logger *slog.Logger,
) (*Consumer, error) {
	if optsCfg.BatchMaxSize <= 0 {
		optsCfg.BatchMaxSize = 500
	}
	if optsCfg.BatchFlushInterval <= 0 {
		optsCfg.BatchFlushInterval = 500 * time.Millisecond
	}
	if optsCfg.WorkerCount <= 0 {
		optsCfg.WorkerCount = 8
	}
	if optsCfg.QueueSize <= 0 {
		optsCfg.QueueSize = 50000
	}

	ctx, cancel := context.WithCancel(context.Background())

	eventQueueSize := optsCfg.QueueSize / 5
	if eventQueueSize < 4096 {
		eventQueueSize = 4096
	}

	c := &Consumer{
		storage:            store,
		logger:             logger,
		ctx:                ctx,
		cancel:             cancel,
		telemetryCh:        make(chan rawMessage, optsCfg.QueueSize),
		telemetryBatchCh:   make(chan []storage.TelemetryPayload, optsCfg.WorkerCount*4),
		eventCh:            make(chan rawMessage, eventQueueSize),
		batchMaxSize:       optsCfg.BatchMaxSize,
		batchFlushInterval: optsCfg.BatchFlushInterval,
		workerCount:        optsCfg.WorkerCount,
	}

	// Start async workers BEFORE connecting to EMQX so incoming messages are drained immediately
	c.startWorkers()

	opts := paho.NewClientOptions()
	opts.AddBroker(optsCfg.BrokerURL)
	opts.SetClientID(optsCfg.ClientID)
	if optsCfg.Username != "" {
		opts.SetUsername(optsCfg.Username)
		opts.SetPassword(optsCfg.Password)
	}
	// CRITICAL: Prevent Paho Go from blocking the TCP socket reader goroutine
	opts.SetOrderMatters(false)
	opts.SetCleanSession(true)
	opts.SetAutoReconnect(true)
	opts.SetKeepAlive(30 * time.Second)
	opts.SetPingTimeout(10 * time.Second)
	opts.SetConnectTimeout(5 * time.Second)
	opts.SetWriteTimeout(10 * time.Second)

	// Subscribe upon connection
	opts.SetOnConnectHandler(func(client paho.Client) {
		logger.Info("Connected to EMQX broker as consumer",
			"broker", optsCfg.BrokerURL,
			"client_id", optsCfg.ClientID,
			"order_matters", false,
			"workers", optsCfg.WorkerCount,
			"queue_size", optsCfg.QueueSize,
			"batch_max_size", optsCfg.BatchMaxSize,
		)

		// Construct Shared Subscription topic e.g. $share/db_writers/smm/jetflow/#
		shareTopic := fmt.Sprintf("$share/%s/%s", optsCfg.SharedGroup, optsCfg.TopicFilter)
		token := client.Subscribe(shareTopic, 1, c.handleIncomingMessage)
		if token.Wait() && token.Error() != nil {
			logger.Error("Failed to subscribe to shared topic", "topic", shareTopic, "error", token.Error())
		} else {
			logger.Info("Subscribed to shared topic successfully", "shared_topic", shareTopic)
		}
	})

	opts.SetConnectionLostHandler(func(client paho.Client, err error) {
		logger.Warn("Consumer connection lost to EMQX broker", "error", err)
	})

	client := paho.NewClient(opts)
	token := client.Connect()
	if token.Wait() && token.Error() != nil {
		cancel()
		c.wg.Wait()
		return nil, fmt.Errorf("connect consumer to mqtt broker %s: %w", optsCfg.BrokerURL, token.Error())
	}

	c.client = client
	return c, nil
}

// handleIncomingMessage MUST NEVER BLOCK so the Paho TCP reader goroutine
// continuously drains the OS socket buffer and never triggers EMQX send_timeout.
func (c *Consumer) handleIncomingMessage(_ paho.Client, msg paho.Message) {
	topic := msg.Topic()
	parts := strings.Split(topic, "/")
	if len(parts) < 4 {
		return
	}
	subType := parts[len(parts)-1]

	// Copy payload because Paho may reuse underlying buffers
	src := msg.Payload()
	buf := make([]byte, len(src))
	copy(buf, src)

	rm := rawMessage{
		topic:   topic,
		subType: subType,
		payload: buf,
	}

	c.receivedCount.Add(1)

	if subType == "telemetry" {
		select {
		case c.telemetryCh <- rm:
		default:
			c.droppedCount.Add(1)
		}
		return
	}

	select {
	case c.eventCh <- rm:
	default:
		c.droppedCount.Add(1)
	}
}

func (c *Consumer) startWorkers() {
	// 1. Telemetry Batcher goroutine: collects messages from telemetryCh and flushes by size or interval
	c.wg.Add(1)
	go c.runTelemetryBatcher()

	// 2. Telemetry DB Worker Pool: executes bulk COPY + batch upserts concurrently
	for i := 0; i < c.workerCount; i++ {
		c.wg.Add(1)
		go c.runTelemetryWorker(i + 1)
	}

	// 3. Event Worker Pool (status, batch_curve, batch_program, alarms)
	eventWorkers := c.workerCount / 2
	if eventWorkers < 2 {
		eventWorkers = 2
	}
	for i := 0; i < eventWorkers; i++ {
		c.wg.Add(1)
		go c.runEventWorker(i + 1)
	}

	// 4. Periodic Queue & Drop Health Reporter
	c.wg.Add(1)
	go c.runMetricsLogger()
}

func (c *Consumer) runTelemetryBatcher() {
	defer c.wg.Done()
	defer close(c.telemetryBatchCh)

	ticker := time.NewTicker(c.batchFlushInterval)
	defer ticker.Stop()

	batch := make([]storage.TelemetryPayload, 0, c.batchMaxSize)
	flush := func() {
		if len(batch) == 0 {
			return
		}
		toSend := batch
		batch = make([]storage.TelemetryPayload, 0, c.batchMaxSize)
		select {
		case c.telemetryBatchCh <- toSend:
		case <-c.ctx.Done():
		}
	}

	for {
		select {
		case <-c.ctx.Done():
			flush()
			return

		case rm := <-c.telemetryCh:
			var p storage.TelemetryPayload
			if err := json.Unmarshal(rm.payload, &p); err != nil {
				c.logger.Debug("Unmarshal telemetry failed", "topic", rm.topic, "error", err)
				continue
			}
			batch = append(batch, p)
			if len(batch) >= c.batchMaxSize {
				flush()
			}

		case <-ticker.C:
			flush()
		}
	}
}

func (c *Consumer) runTelemetryWorker(workerID int) {
	defer c.wg.Done()

	for batch := range c.telemetryBatchCh {
		if len(batch) == 0 {
			continue
		}
		wCtx, cancel := context.WithTimeout(c.ctx, 15*time.Second)
		if err := c.storage.IngestTelemetryBatch(wCtx, batch); err != nil {
			c.logger.Error("Failed to ingest telemetry batch", "worker", workerID, "size", len(batch), "error", err)
		} else {
			c.flushedCount.Add(uint64(len(batch)))
		}
		cancel()
	}
}

func (c *Consumer) runEventWorker(workerID int) {
	defer c.wg.Done()

	for {
		select {
		case <-c.ctx.Done():
			return
		case rm := <-c.eventCh:
			c.processEvent(workerID, rm)
		}
	}
}

func (c *Consumer) processEvent(workerID int, rm rawMessage) {
	wCtx, cancel := context.WithTimeout(c.ctx, 15*time.Second)
	defer cancel()

	switch rm.subType {
	case "status":
		var p storage.StatusPayload
		if err := json.Unmarshal(rm.payload, &p); err != nil {
			c.logger.Debug("Unmarshal status failed", "topic", rm.topic, "error", err)
			return
		}
		if err := c.storage.IngestStatus(wCtx, p); err != nil {
			c.logger.Warn("Failed to ingest status", "worker", workerID, "topic", rm.topic, "error", err)
		}

	case "batch_curve":
		var p storage.BatchCurvePayload
		if err := json.Unmarshal(rm.payload, &p); err != nil {
			c.logger.Debug("Unmarshal batch curve failed", "topic", rm.topic, "error", err)
			return
		}
		if err := c.storage.IngestBatchCurve(wCtx, p); err != nil {
			c.logger.Error("Failed to ingest batch curve", "worker", workerID, "batch", p.BatchNo, "error", err)
		} else {
			c.logger.Info("Batch curve persisted to DB", "asset", p.AssetID, "batch", p.BatchNo, "points", len(p.Points))
		}

	case "batch_program":
		var p storage.BatchProgramPayload
		if err := json.Unmarshal(rm.payload, &p); err != nil {
			c.logger.Debug("Unmarshal batch program failed", "topic", rm.topic, "error", err)
			return
		}
		if err := c.storage.IngestBatchProgram(wCtx, p); err != nil {
			c.logger.Error("Failed to ingest batch program", "worker", workerID, "asset", p.AssetID, "batch", p.BatchNo, "error", err)
		} else {
			c.logger.Info("Batch program persisted to SCADA", "asset", p.AssetID, "batch", p.BatchNo, "steps", p.TotalSteps)
		}

	case "alarms":
		var p storage.AlarmsPayload
		if err := json.Unmarshal(rm.payload, &p); err != nil {
			c.logger.Debug("Unmarshal alarms failed", "topic", rm.topic, "error", err)
			return
		}
		if err := c.storage.IngestAlarms(wCtx, p); err != nil {
			c.logger.Error("Failed to ingest alarms", "worker", workerID, "asset", p.AssetID, "error", err)
		}
	}
}

func (c *Consumer) runMetricsLogger() {
	defer c.wg.Done()
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	var lastDropped uint64
	for {
		select {
		case <-c.ctx.Done():
			return
		case <-ticker.C:
			dropped := c.droppedCount.Load()
			if dropped > lastDropped {
				c.logger.Warn("MQTT consumer dropped messages due to full channel buffer",
					"dropped_total", dropped,
					"dropped_delta", dropped-lastDropped,
					"telemetry_queue_len", len(c.telemetryCh),
					"event_queue_len", len(c.eventCh),
					"received_total", c.receivedCount.Load(),
					"flushed_telemetry", c.flushedCount.Load(),
				)
				lastDropped = dropped
			}
		}
	}
}

func (c *Consumer) Close() {
	if c.client != nil && c.client.IsConnected() {
		c.client.Disconnect(250)
	}
	c.cancel()
	c.wg.Wait()
}
