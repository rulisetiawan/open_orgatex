package main

import (
	"context"
	"fmt"
	"log/slog"
	"math"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"da-setex-collector/internal/config"
	"da-setex-collector/internal/mqtt"
	"da-setex-collector/internal/setex"
)

func main() {
	// 1. Structured Logging
	logger := slog.New(slog.NewTextHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelInfo,
	}))
	slog.SetDefault(logger)

	logger.Info("Starting DA-SETEX Multi-Object Telemetry Collector (Pure MQTT Producer)", "version", "2.0.0")

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
		"machine_id", cfg.PilotMachine.MachineID,
		"asset_id", cfg.PilotMachine.AssetID,
		"ip", cfg.PilotMachine.ControllerIP,
		"tcp_port", cfg.PilotMachine.TCPPort,
		"emqx", cfg.EMQX.BrokerURL,
	)

	// 3. Dynamic Machine-Aware Configuration Loader (02_CONFIG_SIAP_PAKAI)
	bundle, err := setex.LoadMachineConfig(cfg.PilotMachine.ConfigBaseDir, cfg.PilotMachine.MachineID)
	if err != nil {
		logger.Warn("Failed to load machine configuration bundle; using defaults", "error", err)
		bundle = &setex.MachineConfigBundle{
			MachineID:  cfg.PilotMachine.MachineID,
			AssetID:    cfg.PilotMachine.AssetID,
			IWMap:      make(map[int]*setex.RegisterMapping),
			Parameters: make(map[int]*setex.ParameterConfig),
			Functions:  make(map[int]*setex.FunctionConfig),
		}
	} else {
		logger.Info("Loaded machine configuration bundle successfully",
			"machine", bundle.MachineID,
			"iw_registers", len(bundle.IWMap),
			"parameters", len(bundle.Parameters),
			"functions", len(bundle.Functions),
		)
		if bundle.AssetID != "" && cfg.PilotMachine.AssetID == "" {
			cfg.PilotMachine.AssetID = bundle.AssetID
		}
	}

	// 4. Initialize EMQX MQTT Publisher
	clientID := fmt.Sprintf("%s_%d", cfg.EMQX.ClientID, os.Getpid())
	mqttPub, err := mqtt.NewPublisher(
		cfg.EMQX.BrokerURL,
		clientID,
		cfg.EMQX.Username,
		cfg.EMQX.Password,
		logger,
	)
	if err != nil {
		logger.Error("Failed to connect to EMQX broker", "url", cfg.EMQX.BrokerURL, "error", err)
		os.Exit(1)
	}
	defer mqttPub.Close()

	// 5. Initialize Controller Clients
	tcpClient := setex.NewTCPClient(cfg.PilotMachine.ControllerIP, cfg.PilotMachine.TCPPort, 3*time.Second)
	ftpClient := setex.NewFTPClient(
		cfg.PilotMachine.ControllerIP,
		cfg.PilotMachine.FTPPort,
		cfg.PilotMachine.FTPUser,
		cfg.PilotMachine.FTPPassword,
		4*time.Second,
	)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Shared machine state
	var stateMu sync.RWMutex
	currentBatchNo := "000000"
	currentStepNo := 0
	currentProgramNo := "0000"

	// 6. Poller 1: STATUS.ACT via FTP (every 5 seconds)
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
					logger.Debug("FTP STATUS.ACT probe error (controller busy)", "error", err)
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

	// 7. Poller 2: Multi-Object Telemetry via TCP Port 50000 (every 2 seconds)
	telemetryTopic := fmt.Sprintf("%s/%s/telemetry", cfg.EMQX.TopicTelemetryPrefix, cfg.PilotMachine.AssetID)
	telemetryTicker := time.NewTicker(time.Duration(cfg.PilotMachine.TelemetryIntervalSec) * time.Second)
	defer telemetryTicker.Stop()

	cycleCount := 0
	logger.Info("Starting multi-object telemetry stream to EMQX",
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

			stateMu.RLock()
			bNo := currentBatchNo
			sNo := currentStepNo
			pNo := currentProgramNo
			stateMu.RUnlock()

			tagsMap := make(map[string]mqtt.TagMetric)
			var currentTempPV float64

			// ==========================================
			// 1. OBJECT 1025: Info Words (Sensor PV)
			// ==========================================
			if cfg.PilotMachine.Objects.EnableIW1025 {
				words, _, err := tcpClient.ReadBlock(1025, 1, 94)
				if err != nil {
					logger.Warn("Failed to read Object 1025 (IW)", "host", cfg.PilotMachine.ControllerIP, "error", err)
				} else {
					for offset, rawVal := range words {
						regNum := offset + 1
						mapping, exists := bundle.IWMap[regNum]
						if exists {
							calibrated := mapping.Calibrate(rawVal)
							tagName := mapping.TagName
							if tagName == "" {
								tagName = fmt.Sprintf("SMM.%s.IW_%d_PV", cfg.PilotMachine.AssetID, regNum)
							}
							if regNum == 1 {
								currentTempPV = calibrated
							}
							tagsMap[tagName] = mqtt.TagMetric{
								Value:   calibrated,
								Raw:     rawVal,
								Unit:    mapping.Unit,
								Role:    "PV",
								Quality: 192,
							}
						}
					}
				}
			}

			// ==========================================
			// 2. OBJECT 1009: Recipe Setpoints (SV)
			// ==========================================
			if cfg.PilotMachine.Objects.EnableSET1009 {
				setWords, err := tcpClient.ReadSETBlock(1, 40)
				if err != nil {
					logger.Debug("Failed to read Object 1009 (SET)", "error", err)
				} else {
					for offset, rawVal := range setWords {
						paramID := offset + 1
						param, exists := bundle.Parameters[paramID]
						var val float64
						var unit string
						tagName := fmt.Sprintf("SMM.%s.SET_%d_SV", cfg.PilotMachine.AssetID, paramID)

						if exists {
							val = param.Calibrate(rawVal)
							unit = param.Unit
							if param.TagName != "" {
								tagName = param.TagName
							}
						} else {
							val = float64(rawVal) / 10.0
						}

						// Standard known setpoint overrides
						if paramID == 1 { // Temperature Setpoint
							tagName = fmt.Sprintf("SMM.%s.MAIN_TANK.TEMPERATURE_SV", cfg.PilotMachine.AssetID)
							unit = "°C"
						} else if paramID == 5 { // Speed Setpoint
							tagName = fmt.Sprintf("SMM.%s.MAIN_MOTOR.SPEED_SV", cfg.PilotMachine.AssetID)
							unit = "%"
						} else if paramID == 9 { // Level Setpoint
							tagName = fmt.Sprintf("SMM.%s.MAIN_TANK.LEVEL_SV", cfg.PilotMachine.AssetID)
							unit = "L"
						}

						tagsMap[tagName] = mqtt.TagMetric{
							Value:   math.Round(val*10) / 10,
							Raw:     rawVal,
							Unit:    unit,
							Role:    "SV",
							Quality: 192,
						}
					}
				}
			}

			// ==========================================
			// 3. OBJECT 6: Active Step Recipe Function (SV)
			// ==========================================
			if cfg.PilotMachine.Objects.EnableFunction6 {
				// Func 141: Temperature Control (Target Temp, Gradient, Holding Time)
				if f141Vals, _, err := tcpClient.ReadActiveFunction(141); err == nil && len(f141Vals) >= 3 {
					if f141Vals[0] > 0 {
						tagsMap[fmt.Sprintf("SMM.%s.MAIN_TANK.TEMPERATURE_SV", cfg.PilotMachine.AssetID)] = mqtt.TagMetric{
							Value:   math.Round(float64(f141Vals[0])*10) / 10,
							Raw:     f141Vals[0],
							Unit:    "°C",
							Role:    "SV",
							Quality: 192,
						}
					}
					if f141Vals[1] >= 0 {
						tagsMap[fmt.Sprintf("SMM.%s.PROCESS.GRADIENT_SV", cfg.PilotMachine.AssetID)] = mqtt.TagMetric{
							Value:   math.Round(float64(f141Vals[1])*10) / 10,
							Raw:     f141Vals[1],
							Unit:    "°C/min",
							Role:    "SV",
							Quality: 192,
						}
					}
					if f141Vals[2] > 0 {
						tagsMap[fmt.Sprintf("SMM.%s.PROCESS.HOLDING_TIME_SV", cfg.PilotMachine.AssetID)] = mqtt.TagMetric{
							Value:   math.Round(float64(f141Vals[2])*10) / 10,
							Raw:     f141Vals[2],
							Unit:    "min",
							Role:    "SV",
							Quality: 192,
						}
					}
				}

				// Func 713: Fill Level
				if f713Vals, _, err := tcpClient.ReadActiveFunction(713); err == nil && len(f713Vals) >= 2 {
					if f713Vals[1] > 0 {
						tagsMap[fmt.Sprintf("SMM.%s.MAIN_TANK.FILL_VOLUME_SV", cfg.PilotMachine.AssetID)] = mqtt.TagMetric{
							Value:   float64(f713Vals[1]),
							Raw:     f713Vals[1],
							Unit:    "L",
							Role:    "SV",
							Quality: 192,
						}
					}
				}
			}

			// ==========================================
			// 4. OBJECT 1010: Loop Control Actuals (PV)
			// ==========================================
			if cfg.PilotMachine.Objects.EnableACT1010 {
				if actWords, err := tcpClient.ReadACTBlock(1, 20); err == nil {
					for offset, rawVal := range actWords {
						idx := offset + 1
						tagName := fmt.Sprintf("SMM.%s.PID_LOOP.ACT_%d_PV", cfg.PilotMachine.AssetID, idx)
						tagsMap[tagName] = mqtt.TagMetric{
							Value:   float64(rawVal),
							Raw:     rawVal,
							Unit:    "raw",
							Role:    "PV",
							Quality: 192,
						}
					}
				}
			}

			// ==========================================
			// 5. OBJECT 1035: Batch Consumption Counters (TOTALIZER)
			// ==========================================
			if cfg.PilotMachine.Objects.EnableBATCH1035 {
				if dwords, _, err := tcpClient.ReadDWordBlock(1035, 1, 10); err == nil && len(dwords) >= 4 {
					tagsMap[fmt.Sprintf("SMM.%s.CONSUMPTION.WATER_L", cfg.PilotMachine.AssetID)] = mqtt.TagMetric{
						Value:   float64(dwords[0]),
						Raw:     dwords[0],
						Unit:    "L",
						Role:    "TOTALIZER",
						Quality: 192,
					}
					tagsMap[fmt.Sprintf("SMM.%s.CONSUMPTION.CYCLE_COUNT", cfg.PilotMachine.AssetID)] = mqtt.TagMetric{
						Value:   float64(dwords[1]),
						Raw:     dwords[1],
						Unit:    "cycle",
						Role:    "TOTALIZER",
						Quality: 192,
					}
					tagsMap[fmt.Sprintf("SMM.%s.CONSUMPTION.STEAM_KG", cfg.PilotMachine.AssetID)] = mqtt.TagMetric{
						Value:   float64(dwords[2]),
						Raw:     dwords[2],
						Unit:    "kg",
						Role:    "TOTALIZER",
						Quality: 192,
					}
					tagsMap[fmt.Sprintf("SMM.%s.CONSUMPTION.POWER_KWH", cfg.PilotMachine.AssetID)] = mqtt.TagMetric{
						Value:   float64(dwords[3]),
						Raw:     dwords[3],
						Unit:    "kWh",
						Role:    "TOTALIZER",
						Quality: 192,
					}
					if len(dwords) >= 6 && dwords[5] > 0 {
						tagsMap[fmt.Sprintf("SMM.%s.CONSUMPTION.RUN_TIME_SEC", cfg.PilotMachine.AssetID)] = mqtt.TagMetric{
							Value:   float64(dwords[5]),
							Raw:     dwords[5],
							Unit:    "s",
							Role:    "TOTALIZER",
							Quality: 192,
						}
					}
				}
			}

			// ==========================================
			// Publish Telemetry Payload to EMQX MQTT
			// ==========================================
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

			// Log periodic summary every 10 cycles (~20s)
			if cycleCount%10 == 1 {
				logger.Info("Multi-object cycle published to EMQX",
					"cycle", cycleCount,
					"batch", bNo,
					"step", sNo,
					"temp_pv", fmt.Sprintf("%.1f°C", currentTempPV),
					"total_tags", len(tagsMap),
					"mqtt_topic", telemetryTopic,
				)
			}
		}
	}
}

func init() {
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)
	go func() {
		<-sigChan
		slog.Info("Interrupt received, terminating collector...")
		os.Exit(0)
	}()
}
