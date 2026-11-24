package main

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"syscall"

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
	cfgPath := "config.yaml"
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

	// 3. Initialize EMQX Consumer with Shared Subscription
	clientID := fmt.Sprintf("%s_%d", cfg.EMQX.ClientID, os.Getpid())
	consumer, err := mqtt.NewConsumer(
		cfg.EMQX.BrokerURL,
		clientID,
		cfg.EMQX.Username,
		cfg.EMQX.Password,
		cfg.EMQX.SharedGroup,
		cfg.EMQX.TopicFilter,
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
