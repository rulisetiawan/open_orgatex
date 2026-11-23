package main

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"path/filepath"
	"sync"
	"syscall"
	"time"

	"da-setex-collector/internal/config"
	"da-setex-collector/internal/mqtt"
	"da-setex-collector/internal/setex"
	"da-setex-collector/internal/storage"
)

func main() {
	// 1. Structured Logging
	logger := slog.New(slog.NewTextHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelInfo,
	}))
	slog.SetDefault(logger)

	logger.Info("Starting DA-SETEX Industrial Telemetry Collector (Go Edition)", "version", "1.0.0")

	// 2. Load Configuration
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
		"pilot_machine", cfg.PilotMachine.MachineID,
		"asset_id", cfg.PilotMachine.AssetID,
		"ip", cfg.PilotMachine.ControllerIP,
		"tcp_port", cfg.PilotMachine.TCPPort,
		"emqx", cfg.EMQX.BrokerURL,
	)

	// 5. Initialize PostgreSQL Storage
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	pgWriter, err := storage.NewPGWriter(
		ctx,
		cfg.Database.JetflowURL,
		cfg.Database.ScadaURL,
		cfg.Database.MaxConns,
		cfg.Database.MinConns,
		logger,
	)
	if err != nil {
		logger.Error("Failed to connect to PostgreSQL", "error", err)
		os.Exit(1)
	}
	defer pgWriter.Close()
	logger.Info("PostgreSQL connection pools initialized successfully")

	// 6. Load Tag Mappings from PostgreSQL (pt_smm_jetflow.cfg_machine_iw_tag_mapping)
	tcMap, err := pgWriter.LoadMachineTagMappings(ctx, cfg.PilotMachine.MachineID)
	if err != nil || len(tcMap) == 0 {
		logger.Warn("Falling back to local typeconf JSON file", "reason", err)
		typeconfPath := cfg.PilotMachine.TypeconfJSONPath
		if !filepath.IsAbs(typeconfPath) {
			candidates := []string{
				typeconfPath,
				filepath.Join("..", "..", typeconfPath),
				filepath.Join("c:", "Users", "ruli_smm", "DA-TEX", typeconfPath),
			}
			for _, c := range candidates {
				if _, err := os.Stat(c); err == nil {
					typeconfPath = c
					break
				}
			}
		}
		tcMap, err = setex.LoadTypeconfFromFile(typeconfPath)
		if err != nil {
			logger.Error("Failed to load TYPECONF calibration map", "path", typeconfPath, "error", err)
			os.Exit(1)
		}
	}
	logger.Info("Loaded tag calibration map", "total_registers", len(tcMap), "machine", cfg.PilotMachine.MachineID)

	// 7. Initialize MQTT Publisher (EMQX)
	mqttPub, err := mqtt.NewPublisher(
		cfg.EMQX.BrokerURL,
		cfg.EMQX.ClientID,
		cfg.EMQX.Username,
		cfg.EMQX.Password,
		logger,
	)
	if err != nil {
		logger.Error("Failed to connect to EMQX broker", "url", cfg.EMQX.BrokerURL, "error", err)
		os.Exit(1)
	}
	defer mqttPub.Close()

	// 8. Initialize Controller Clients
	tcpClient := setex.NewTCPClient(cfg.PilotMachine.ControllerIP, cfg.PilotMachine.TCPPort, 3*time.Second)
	ftpClient := setex.NewFTPClient(
		cfg.PilotMachine.ControllerIP,
		cfg.PilotMachine.FTPPort,
		cfg.PilotMachine.FTPUser,
		cfg.PilotMachine.FTPPassword,
		4*time.Second,
	)

	// Shared state across pollers
	var stateMu sync.RWMutex
	currentBatchNo := "072162"
	currentStepNo := 9
	currentProgramNo := "0342"

	// 7. Poller 1: STATUS.ACT via FTP (5 seconds)
	go func() {
		ticker := time.NewTicker(time.Duration(cfg.PilotMachine.StatusActIntervalSec) * time.Second)
		defer ticker.Stop()

		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				st, _, err := ftpClient.FetchStatusAct()
				if err != nil {
					// Non-fatal, controller might be busy
					logger.Debug("FTP STATUS.ACT probe", "error", err)
					continue
				}

				stateMu.Lock()
				if st.BatchNo != "" {
					currentBatchNo = st.BatchNo
				}
				if st.StepNo > 0 {
					currentStepNo = st.StepNo
				}
				if st.ProgramNo != "" {
					currentProgramNo = st.ProgramNo
				}
				bNo := currentBatchNo
				sNo := currentStepNo
				pNo := currentProgramNo
				stateMu.Unlock()

				// Publish status to EMQX
				topicStatus := fmt.Sprintf("%s/%s/status", cfg.EMQX.TopicStatusPrefix, cfg.PilotMachine.AssetID)
				_ = mqttPub.PublishStatus(topicStatus, mqtt.StatusPayload{
					Timestamp:        time.Now(),
					AssetID:          cfg.PilotMachine.AssetID,
					MachineID:        cfg.PilotMachine.MachineID,
					ConnectionStatus: "ONLINE",
					BatchNo:          bNo,
					StepNo:           sNo,
					ProgramNo:        pNo,
				})
			}
		}
	}()

	// 8. Poller 2: Realtime IW Telemetry via TCP Port 50000 (2 seconds)
	telemetryTopic := fmt.Sprintf("%s/%s/telemetry", cfg.EMQX.TopicTelemetryPrefix, cfg.PilotMachine.AssetID)
	telemetryTicker := time.NewTicker(time.Duration(cfg.PilotMachine.TelemetryIntervalSec) * time.Second)
	defer telemetryTicker.Stop()

	cycleCount := 0

	logger.Info("Starting realtime IW polling stream",
		"interval", fmt.Sprintf("%ds", cfg.PilotMachine.TelemetryIntervalSec),
		"topic", telemetryTopic,
	)

	for {
		select {
		case <-ctx.Done():
			logger.Info("Collector shutting down gracefully...")
			return
		case <-telemetryTicker.C:
			cycleCount++
			now := time.Now()

			// Read 94 words from Object 1025 (IW) starting at address 0
			words, rawFrame, err := tcpClient.ReadBlock(1025, 0, 94)
			if err != nil {
				logger.Warn("Failed to read IW block from controller",
					"host", cfg.PilotMachine.ControllerIP,
					"error", err,
				)
				continue
			}

			stateMu.RLock()
			bNo := currentBatchNo
			sNo := currentStepNo
			pNo := currentProgramNo
			stateMu.RUnlock()

			// Calibrate all registers
			tagsMap := make(map[string]mqtt.TagMetric)
			jsonTelemetry := make(map[string]interface{})
			tagRecords := make([]storage.TagValueRecord, 0, len(words))

			var currentTemp float64

			for idx, rawVal := range words {
				mapping, exists := tcMap[idx]
				if !exists {
					continue
				}

				calibrated := mapping.Calibrate(rawVal)
				tagName := mapping.TagName
				if tagName == "" {
					tagName = fmt.Sprintf("SMM.%s.CONTROLLER.IW_%d_PV", cfg.PilotMachine.AssetID, idx)
				}

				role := mapping.TagRole
				if role == "" {
					role = "PV"
				}

				// Check primary temperature PV
				if idx == 1 {
					currentTemp = calibrated
				}

				metric := mqtt.TagMetric{
					Value:   calibrated,
					Raw:     rawVal,
					Unit:    mapping.Unit,
					Role:    role,
					Quality: 192,
				}

				tagsMap[tagName] = metric
				jsonTelemetry[tagName] = map[string]interface{}{
					"value":      calibrated,
					"raw":        rawVal,
					"unit":       mapping.Unit,
					"role":       role,
					"quality":    192,
					"field_name": mapping.FieldName,
					"notes":      mapping.Name,
				}

				tagRecords = append(tagRecords, storage.TagValueRecord{
					TagName:   tagName,
					Value:     calibrated,
					Raw:       rawVal,
					Unit:      mapping.Unit,
					Role:      role,
					Quality:   192,
					Timestamp: now,
				})
			}

			// 1. Publish to EMQX MQTT Broker
			telPayload := mqtt.TelemetryPayload{
				Timestamp: now,
				AssetID:   cfg.PilotMachine.AssetID,
				MachineID: cfg.PilotMachine.MachineID,
				BatchNo:   bNo,
				StepNo:    sNo,
				ProgramNo: pNo,
				Tags:      tagsMap,
			}

			if err := mqttPub.PublishTelemetry(telemetryTopic, telPayload); err != nil {
				logger.Warn("Failed to publish telemetry to EMQX", "error", err)
			}

			// 2. Persist to PostgreSQL (pt_smm_jetflow & pt_smm_scada)
			_ = pgWriter.WriteLiveTelemetry(
				ctx,
				cfg.PilotMachine.MachineID,
				cfg.PilotMachine.AssetID,
				bNo, sNo, pNo,
				rawFrame,
				jsonTelemetry,
				tagRecords,
				currentTemp,
			)

			// Log every 10 cycles (~20s)
			if cycleCount%10 == 1 {
				logger.Info("Telemetry cycle ok",
					"cycle", cycleCount,
					"batch", bNo,
					"step", sNo,
					"temp_pv", fmt.Sprintf("%.1f°C", currentTemp),
					"total_tags", len(tagsMap),
					"mqtt_topic", telemetryTopic,
				)
			}
		}
	}
}

func init() {
	// Handle OS Signals for clean exit
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)
	go func() {
		<-sigChan
		slog.Info("Interrupt received, terminating collector...")
		os.Exit(0)
	}()
}
