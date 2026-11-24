package mqtt

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"strings"
	"time"

	"da-db-writer/internal/storage"

	paho "github.com/eclipse/paho.mqtt.golang"
)

type Consumer struct {
	client  paho.Client
	storage *storage.Storage
	logger  *slog.Logger
	ctx     context.Context
	cancel  context.CancelFunc
}

func NewConsumer(
	brokerURL, clientID, user, pass, sharedGroup, topicFilter string,
	store *storage.Storage,
	logger *slog.Logger,
) (*Consumer, error) {
	ctx, cancel := context.WithCancel(context.Background())

	c := &Consumer{
		storage: store,
		logger:  logger,
		ctx:     ctx,
		cancel:  cancel,
	}

	opts := paho.NewClientOptions()
	opts.AddBroker(brokerURL)
	opts.SetClientID(clientID)
	if user != "" {
		opts.SetUsername(user)
		opts.SetPassword(pass)
	}
	opts.SetAutoReconnect(true)
	opts.SetKeepAlive(30 * time.Second)
	opts.SetConnectTimeout(5 * time.Second)

	// Subscribe upon connection
	opts.SetOnConnectHandler(func(client paho.Client) {
		logger.Info("Connected to EMQX broker as consumer", "broker", brokerURL, "client_id", clientID)

		// Construct Shared Subscription topic e.g. $share/db_writers/smm/jetflow/#
		shareTopic := fmt.Sprintf("$share/%s/%s", sharedGroup, topicFilter)
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
		return nil, fmt.Errorf("connect consumer to mqtt broker %s: %w", brokerURL, token.Error())
	}

	c.client = client
	return c, nil
}

func (c *Consumer) handleIncomingMessage(_ paho.Client, msg paho.Message) {
	topic := msg.Topic()
	payload := msg.Payload()

	parts := strings.Split(topic, "/")
	if len(parts) < 4 {
		return
	}
	// e.g. smm/jetflow/{asset_id}/telemetry or status, batch_curve, alarms
	subType := parts[len(parts)-1]

	switch subType {
	case "telemetry":
		var p storage.TelemetryPayload
		if err := json.Unmarshal(payload, &p); err != nil {
			c.logger.Debug("Unmarshal telemetry failed", "topic", topic, "error", err)
			return
		}
		if err := c.storage.IngestTelemetry(c.ctx, p); err != nil {
			c.logger.Error("Failed to ingest telemetry", "topic", topic, "error", err)
		}

	case "status":
		var p storage.StatusPayload
		if err := json.Unmarshal(payload, &p); err != nil {
			c.logger.Debug("Unmarshal status failed", "topic", topic, "error", err)
			return
		}
		_ = c.storage.IngestStatus(c.ctx, p)

	case "batch_curve":
		var p storage.BatchCurvePayload
		if err := json.Unmarshal(payload, &p); err != nil {
			c.logger.Debug("Unmarshal batch curve failed", "topic", topic, "error", err)
			return
		}
		if err := c.storage.IngestBatchCurve(c.ctx, p); err != nil {
			c.logger.Error("Failed to ingest batch curve", "batch", p.BatchNo, "error", err)
		} else {
			c.logger.Info("Batch curve persisted to DB", "asset", p.AssetID, "batch", p.BatchNo, "points", len(p.Points))
		}

	case "alarms":
		var p storage.AlarmsPayload
		if err := json.Unmarshal(payload, &p); err != nil {
			c.logger.Debug("Unmarshal alarms failed", "topic", topic, "error", err)
			return
		}
		if err := c.storage.IngestAlarms(c.ctx, p); err != nil {
			c.logger.Error("Failed to ingest alarms", "asset", p.AssetID, "error", err)
		}
	}
}

func (c *Consumer) Close() {
	c.cancel()
	if c.client != nil && c.client.IsConnected() {
		c.client.Disconnect(250)
	}
}
