package main

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"da-db-writer/internal/config"
	"da-db-writer/internal/mqtt"
	"da-db-writer/internal/storage"
)

func main() {
	logger := slog.New(slog.NewTextHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelInfo,
	}))
	slog.SetDefault(logger)

	logger.Info("Starting DA-DB-Writer Enterprise Database Consumer (Go Edition)", "version", "1.0.0")

	// 1. Load Config
	cfgPath := os.Getenv("CONFIG_PATH")
	if cfgPath == "" {
		cfgPath = "config.yaml"
	}
	if len(os.Args) > 1 {
		cfgPath = os.Args[1]
	}
	cfg, err := config.LoadConfig(cfgPath)
	if err != nil {
		logger.Error("Failed to load config file", "path", cfgPath, "error", err)
		os.Exit(1)
	}

	logger.Info("Config loaded successfully",
		"emqx", cfg.EMQX.BrokerURL,
		"shared_group", cfg.EMQX.SharedGroup,
		"topic_filter", cfg.EMQX.TopicFilter,
	)

	// 2. Initialize PostgreSQL Storage
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	store, err := storage.NewStorage(
		ctx,
		cfg.Database.JetflowURL,
		cfg.Database.ScadaURL,
		cfg.Database.MaxConns,
		cfg.Database.MinConns,
		logger,
	)
	if err != nil {
		logger.Error("Failed to connect to PostgreSQL pools", "error", err)
		os.Exit(1)
	}
	defer store.Close()
	logger.Info("Connected to PostgreSQL databases (pt_smm_jetflow & pt_smm_scada)")

	// 3. Initialize EMQX Consumer with Shared Subscription (unique client_id per replica)
	clientID := strings.TrimSpace(os.Getenv("CLIENT_ID"))
	if clientID == "" {
		host, _ := os.Hostname()
		if host == "" {
			host = "node"
		}
		clientID = fmt.Sprintf("%s_%s_%d", cfg.EMQX.ClientID, host, os.Getpid())
	}
	consumer, err := mqtt.NewConsumer(
		mqtt.ConsumerOptions{
			BrokerURL:          cfg.EMQX.BrokerURL,
			ClientID:           clientID,
			Username:           cfg.EMQX.Username,
			Password:           cfg.EMQX.Password,
			SharedGroup:        cfg.EMQX.SharedGroup,
			TopicFilter:        cfg.EMQX.TopicFilter,
			BatchMaxSize:       cfg.Writer.BatchMaxSize,
			BatchFlushInterval: time.Duration(cfg.Writer.BatchFlushIntervalMs) * time.Millisecond,
			WorkerCount:        cfg.Writer.WorkerCount,
			QueueSize:          cfg.Writer.QueueSize,
		},
		store,
		logger,
	)
	if err != nil {
		logger.Error("Failed to start MQTT consumer", "error", err)
		os.Exit(1)
	}
	defer consumer.Close()

	logger.Info("DA-DB-Writer active. Waiting for events from EMQX message broker...")

	// 4. Wait for OS Termination Signal
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)
	<-sigChan

	logger.Info("Termination signal received. Shutting down DA-DB-Writer gracefully...")
}
