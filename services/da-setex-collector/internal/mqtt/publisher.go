package mqtt

import (
	"encoding/json"
	"fmt"
	"log/slog"
	"time"

	paho "github.com/eclipse/paho.mqtt.golang"
)

type Publisher struct {
	client paho.Client
	logger *slog.Logger
}

type TagMetric struct {
	Value   float64 `json:"value"`
	Raw     uint16  `json:"raw"`
	Unit    string  `json:"unit"`
	Role    string  `json:"role"`
	Quality int     `json:"quality"`
}

type TelemetryPayload struct {
	Timestamp time.Time             `json:"timestamp"`
	AssetID   string                `json:"asset_id"`
	MachineID string                `json:"machine_id"`
	BatchNo   string                `json:"batch_no,omitempty"`
	StepNo    int                   `json:"step_no,omitempty"`
	ProgramNo string                `json:"program_no,omitempty"`
	Tags      map[string]TagMetric  `json:"tags"`
}

type StatusPayload struct {
	Timestamp        time.Time `json:"timestamp"`
	AssetID          string    `json:"asset_id"`
	MachineID        string    `json:"machine_id"`
	ConnectionStatus string    `json:"connection_status"`
	BatchNo          string    `json:"batch_no"`
	StepNo           int       `json:"step_no"`
	ProgramNo        string    `json:"program_no"`
}

func NewPublisher(brokerURL, clientID, user, pass string, logger *slog.Logger) (*Publisher, error) {
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

	opts.SetOnConnectHandler(func(c paho.Client) {
		logger.Info("Connected to EMQX broker", "broker", brokerURL, "client_id", clientID)
	})
	opts.SetConnectionLostHandler(func(c paho.Client, err error) {
		logger.Warn("Connection lost to EMQX broker", "error", err)
	})

	client := paho.NewClient(opts)
	token := client.Connect()
	if token.Wait() && token.Error() != nil {
		return nil, fmt.Errorf("connect to mqtt broker %s: %w", brokerURL, token.Error())
	}

	return &Publisher{
		client: client,
		logger: logger,
	}, nil
}

func (p *Publisher) PublishTelemetry(topic string, payload TelemetryPayload) error {
	bytes, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("marshal telemetry payload: %w", err)
	}

	token := p.client.Publish(topic, 0, false, bytes)
	if token.Wait() && token.Error() != nil {
		return fmt.Errorf("publish to topic %s: %w", topic, token.Error())
	}
	return nil
}

func (p *Publisher) PublishStatus(topic string, payload StatusPayload) error {
	bytes, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("marshal status payload: %w", err)
	}

	token := p.client.Publish(topic, 1, true, bytes)
	if token.Wait() && token.Error() != nil {
		return fmt.Errorf("publish status to topic %s: %w", topic, token.Error())
	}
	return nil
}

func (p *Publisher) Close() {
	if p.client != nil && p.client.IsConnected() {
		p.client.Disconnect(250)
	}
}
