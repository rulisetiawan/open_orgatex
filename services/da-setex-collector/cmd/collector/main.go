package main

import (
	"context"
	"fmt"
	"log/slog"
	"math"
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

			// Read 94 words from Object 1025 (IW) starting at address 1 (SETEX IW is 1-based)
			words, rawFrame, err := tcpClient.ReadBlock(1025, 1, 94)
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

			for offset, rawVal := range words {
				regNum := offset + 1 // 1-based IW register number (IW 1 = words[0])
				mapping, exists := tcMap[regNum]
				if !exists {
					continue
				}

				calibrated := mapping.Calibrate(rawVal)
				tagName := mapping.TagName
				if tagName == "" {
					tagName = fmt.Sprintf("SMM.%s.CONTROLLER.IW_%d_PV", cfg.PilotMachine.AssetID, regNum)
				}

				role := mapping.TagRole
				if role == "" {
					role = "PV"
				}

				// Check primary temperature PV (IW 1)
				if regNum == 1 {
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

			// Read Dedicated Setpoints from Object 1009 (SET) and Object 6 (Active Step Parameters)
			var tempSP, holdingTimeSP, gradientSP, levelSP, speedSP float64
			setWords, errSet := tcpClient.ReadSETBlock(1, 20)
			if errSet == nil && len(setWords) > 0 {
				if setWords[0] > 0 {
					tempSP = float64(setWords[0]) / 10.0
				}
				if len(setWords) > 4 && setWords[4] > 0 {
					speedSP = float64(setWords[4]) / 10.0
				}
				if len(setWords) > 8 && setWords[8] > 0 {
					levelSP = float64(setWords[8])
				}
			}

			// Read Active Function 141 (Temperature Control: Target Temp, Gradient, Holding Time)
			f141Vals, _, errF141 := tcpClient.ReadActiveFunction(141)
			if errF141 == nil && len(f141Vals) >= 3 {
				if f141Vals[0] > 0 {
					tempSP = float64(f141Vals[0])
				}
				if f141Vals[1] >= 0 {
					gradientSP = float64(f141Vals[1])
				}
				if f141Vals[2] > 0 {
					holdingTimeSP = float64(f141Vals[2])
				}
			}

			// Read Active Function 713 (Fill Level: Target Fill Volume)
			f713Vals, _, errF713 := tcpClient.ReadActiveFunction(713)
			if errF713 == nil && len(f713Vals) >= 2 {
				if f713Vals[1] > 0 {
					levelSP = float64(f713Vals[1])
				}
			}

			// Register SV Setpoint Tags into Telemetry and SCADA
			svItems := []struct {
				TagName string
				Value   float64
				Unit    string
				Raw     uint16
				Role    string
				Field   string
				Note    string
			}{
				{
					TagName: fmt.Sprintf("SMM.%s.MAIN_TANK.TEMPERATURE_SV", cfg.PilotMachine.AssetID),
					Value:   math.Round(tempSP*10) / 10,
					Unit:    "°C",
					Raw:     uint16(tempSP * 10),
					Role:    "SV",
					Field:   "temp_setpoint",
					Note:    "Target Temperature Setpoint (Obj 1009 / Func 141)",
				},
				{
					TagName: fmt.Sprintf("SMM.%s.MAIN_TANK.LEVEL_SV", cfg.PilotMachine.AssetID),
					Value:   levelSP,
					Unit:    "L",
					Raw:     uint16(levelSP),
					Role:    "SV",
					Field:   "level_setpoint",
					Note:    "Target Fill Volume / Level Setpoint (Obj 1009 / Func 713)",
				},
				{
					TagName: fmt.Sprintf("SMM.%s.MAIN_MOTOR.SPEED_SV", cfg.PilotMachine.AssetID),
					Value:   speedSP,
					Unit:    "%",
					Raw:     uint16(speedSP * 10),
					Role:    "SV",
					Field:   "speed_setpoint",
					Note:    "Target Pump / Winch Speed Setpoint (Obj 1009)",
				},
				{
					TagName: fmt.Sprintf("SMM.%s.PROCESS.HOLDING_TIME_SV", cfg.PilotMachine.AssetID),
					Value:   holdingTimeSP,
					Unit:    "min",
					Raw:     uint16(holdingTimeSP),
					Role:    "SV",
					Field:   "holding_time_setpoint",
					Note:    "Target Holding Time Setpoint (Func 141 P3)",
				},
				{
					TagName: fmt.Sprintf("SMM.%s.PROCESS.GRADIENT_SV", cfg.PilotMachine.AssetID),
					Value:   gradientSP,
					Unit:    "°C/min",
					Raw:     uint16(gradientSP * 10),
					Role:    "SV",
					Field:   "gradient_setpoint",
					Note:    "Target Temperature Gradient Setpoint (Func 141 P2)",
				},
			}

			for _, sv := range svItems {
				tagsMap[sv.TagName] = mqtt.TagMetric{
					Value:   sv.Value,
					Raw:     sv.Raw,
					Unit:    sv.Unit,
					Role:    sv.Role,
					Quality: 192,
				}
				jsonTelemetry[sv.TagName] = map[string]interface{}{
					"value":      sv.Value,
					"raw":        sv.Raw,
					"unit":       sv.Unit,
					"role":       sv.Role,
					"quality":    192,
					"field_name": sv.Field,
					"notes":      sv.Note,
				}
				tagRecords = append(tagRecords, storage.TagValueRecord{
					TagName:   sv.TagName,
					Value:     sv.Value,
					Raw:       sv.Raw,
					Unit:      sv.Unit,
					Role:      sv.Role,
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
