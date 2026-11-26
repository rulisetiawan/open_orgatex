package main

import (
	"context"
	"fmt"
	"log/slog"
	"math"
	"net"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"
	"unicode"

	"da-setex-collector/internal/config"
	"da-setex-collector/internal/mqtt"
	"da-setex-collector/internal/setex"

	"github.com/jackc/pgx/v5"
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
	if envCfg := os.Getenv("CONFIG_PATH"); envCfg != "" {
		cfgPath = envCfg
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
		"multi_machine", cfg.Collector.MultiMachine,
		"emqx", cfg.EMQX.BrokerURL,
	)

	// 3. Initialize EMQX MQTT Publisher (shared across all machine workers)
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

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// 4. Resolve target machines (all active machines from DB when multi_machine=true, else pilot_machine)
	var targets []config.PilotMachineConfig
	if cfg.Collector.MultiMachine && cfg.Database.URL != "" {
		dbMachines, dbErr := loadMachinesFromDB(ctx, cfg.Database.URL, cfg.PilotMachine, logger)
		if dbErr != nil {
			logger.Warn("Failed loading machines from DB; falling back to pilot_machine", "error", dbErr)
		} else {
			targets = dbMachines
		}
	}
	if len(targets) == 0 && cfg.PilotMachine.ControllerIP != "" {
		targets = append(targets, cfg.PilotMachine)
	}

	// Filter by target_machines (env TARGET_MACHINES or config.yaml collector.target_machines)
	filterList := cfg.Collector.TargetMachines
	if envTargets := strings.TrimSpace(os.Getenv("TARGET_MACHINES")); envTargets != "" {
		filterList = nil
		for _, part := range strings.Split(envTargets, ",") {
			if p := strings.TrimSpace(part); p != "" {
				filterList = append(filterList, p)
			}
		}
	}
	if len(filterList) > 0 {
		allowed := make(map[string]bool, len(filterList))
		for _, m := range filterList {
			allowed[strings.ToUpper(strings.TrimSpace(m))] = true
		}
		var filtered []config.PilotMachineConfig
		for _, t := range targets {
			if allowed[strings.ToUpper(strings.TrimSpace(t.MachineID))] {
				filtered = append(filtered, t)
			}
		}
		targets = filtered
	}

	if len(targets) == 0 {
		logger.Error("No target machines configured or found in database")
		os.Exit(1)
	}

	var targetNames []string
	for _, t := range targets {
		targetNames = append(targetNames, fmt.Sprintf("%s(%s)", t.MachineID, t.ControllerIP))
	}
	logger.Info("Starting multi-machine collector workers", "total_machines", len(targets), "targets", strings.Join(targetNames, ", "))

	var wg sync.WaitGroup
	for idx, mCfg := range targets {
		wg.Add(1)
		stagger := time.Duration((idx%20)*150) * time.Millisecond
		go func(mc config.PilotMachineConfig, delay time.Duration) {
			defer wg.Done()
			runMachineCollector(ctx, mc, cfg, mqttPub, logger, delay)
		}(mCfg, stagger)
	}

	wg.Wait()
}

func resolveAssetID(machineNo string) string {
	var digits, letters strings.Builder
	for _, r := range strings.ToUpper(strings.TrimSpace(machineNo)) {
		if unicode.IsDigit(r) {
			digits.WriteRune(r)
		} else if unicode.IsLetter(r) {
			letters.WriteRune(r)
		}
	}
	if digits.Len() > 0 {
		if n, err := strconv.Atoi(digits.String()); err == nil {
			line := "B"
			if letters.Len() == 1 {
				line = letters.String()
			}
			return fmt.Sprintf("JF-L%s-%02d", line, n)
		}
	}
	return fmt.Sprintf("JF-LB-%s", machineNo)
}

func loadMachinesFromDB(ctx context.Context, dbURL string, template config.PilotMachineConfig, logger *slog.Logger) ([]config.PilotMachineConfig, error) {
	connCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()

	conn, err := pgx.Connect(connCtx, dbURL)
	if err != nil {
		return nil, err
	}
	defer conn.Close(context.Background())

	rows, err := conn.Query(connCtx, `
		SELECT machine_no, ip_address, COALESCE(ftp_port, 21), COALESCE(tcp_port, 50000)
		FROM machines
		WHERE is_active = TRUE
		  AND ip_address IS NOT NULL AND ip_address != ''
		  AND ip_address NOT IN ('127.0.0.1', 'localhost', '0.0.0.0')
		ORDER BY machine_no;
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var machines []config.PilotMachineConfig
	for rows.Next() {
		var mNo, ip string
		var ftpPort, tcpPort int
		if err := rows.Scan(&mNo, &ip, &ftpPort, &tcpPort); err != nil {
			continue
		}
		if ftpPort <= 0 {
			ftpPort = 21
		}
		if tcpPort <= 0 {
			tcpPort = 50000
		}
		assetID := resolveAssetID(mNo)
		mc := template
		mc.MachineID = mNo
		mc.AssetID = assetID
		mc.ControllerIP = ip
		mc.FTPPort = ftpPort
		mc.TCPPort = tcpPort
		machines = append(machines, mc)
	}
	logger.Info("Loaded active machines from PostgreSQL", "count", len(machines))
	return machines, rows.Err()
}

func isPortReachable(ip string, port int, timeout time.Duration) bool {
	conn, err := net.DialTimeout("tcp", fmt.Sprintf("%s:%d", ip, port), timeout)
	if err != nil {
		return false
	}
	_ = conn.Close()
	return true
}

func runMachineCollector(ctx context.Context, mCfg config.PilotMachineConfig, globalCfg *config.Config, mqttPub *mqtt.Publisher, logger *slog.Logger, stagger time.Duration) {
	if stagger > 0 {
		select {
		case <-ctx.Done():
			return
		case <-time.After(stagger):
		}
	}

	// Dynamic Machine-Aware Configuration Loader (02_CONFIG_SIAP_PAKAI)
	bundle, err := setex.LoadMachineConfig(mCfg.ConfigBaseDir, mCfg.MachineID)
	if err != nil {
		logger.Warn("Machine config not found; using defaults", "machine", mCfg.MachineID, "error", err)
		bundle = &setex.MachineConfigBundle{
			MachineID:  mCfg.MachineID,
			AssetID:    mCfg.AssetID,
			IWMap:      make(map[int]*setex.RegisterMapping),
			Parameters: make(map[int]*setex.ParameterConfig),
			Functions:  make(map[int]*setex.FunctionConfig),
		}
	} else {
		if bundle.AssetID != "" {
			mCfg.AssetID = bundle.AssetID
		}
		logger.Debug("Loaded machine config",
			"machine", mCfg.MachineID,
			"asset_id", mCfg.AssetID,
			"iw_registers", len(bundle.IWMap),
			"parameters", len(bundle.Parameters),
			"functions", len(bundle.Functions),
		)
	}

	tcpClient := setex.NewTCPClient(mCfg.ControllerIP, mCfg.TCPPort, 2500*time.Millisecond)
	ftpClient := setex.NewFTPClient(
		mCfg.ControllerIP,
		mCfg.FTPPort,
		mCfg.FTPUser,
		mCfg.FTPPassword,
		3500*time.Millisecond,
	)

	// Shared machine state
	var stateMu sync.RWMutex
	currentBatchNo := ""
	currentStepNo := 0
	currentProgramNo := ""

	pollStatusAct := func() {
		if !isPortReachable(mCfg.ControllerIP, mCfg.FTPPort, 400*time.Millisecond) {
			return
		}
		st, _, err := ftpClient.FetchStatusAct()
		if err != nil {
			logger.Warn("FTP STATUS.ACT probe error", "machine", mCfg.MachineID, "host", mCfg.ControllerIP, "error", err)
			return
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
		topicStatus := fmt.Sprintf("%s/%s/status", globalCfg.EMQX.TopicStatusPrefix, mCfg.AssetID)
		_ = mqttPub.PublishStatus(topicStatus, mqtt.StatusPayload{
			Timestamp:        time.Now(),
			AssetID:          mCfg.AssetID,
			MachineID:        mCfg.MachineID,
			ConnectionStatus: "ONLINE",
			BatchNo:          bNo,
			StepNo:           sNo,
			ProgramNo:        pNo,
		})
	}

	// Poller 1: STATUS.ACT via FTP (Optional - only if enable_status_act is true and interval > 0)
	if mCfg.Objects.EnableStatusAct && mCfg.StatusActIntervalSec > 0 {
		go func() {
			pollStatusAct()
			ticker := time.NewTicker(time.Duration(mCfg.StatusActIntervalSec) * time.Second)
			defer ticker.Stop()

			for {
				select {
				case <-ctx.Done():
					return
				case <-ticker.C:
					pollStatusAct()
				}
			}
		}()
	} else {
		logger.Info("STATUS.ACT pulling via FTP is disabled", "machine", mCfg.MachineID)
	}

	// Poller 2: Multi-Object Telemetry via TCP Port 50000
	telemetryTopic := fmt.Sprintf("%s/%s/telemetry", globalCfg.EMQX.TopicTelemetryPrefix, mCfg.AssetID)
	telemetryTicker := time.NewTicker(time.Duration(mCfg.TelemetryIntervalSec) * time.Second)
	defer telemetryTicker.Stop()

	cycleCount := 0
	wasOffline := false

	for {
		select {
		case <-ctx.Done():
			return
		case <-telemetryTicker.C:
			if !isPortReachable(mCfg.ControllerIP, mCfg.TCPPort, 350*time.Millisecond) {
				if !wasOffline {
					wasOffline = true
					logger.Debug("Controller TCP offline", "machine", mCfg.MachineID, "host", mCfg.ControllerIP)
				}
				continue
			}
			wasOffline = false
			cycleCount++
			now := time.Now()

			stateMu.RLock()
			bNo := currentBatchNo
			sNo := currentStepNo
			pNo := currentProgramNo
			stateMu.RUnlock()

			tagsMap := make(map[string]mqtt.TagMetric)
			var currentTempPV float64

			// 1. OBJECT 1025: Info Words
			if mCfg.Objects.EnableIW1025 {
				words, _, err := tcpClient.ReadBlock(1025, 1, 200)
				if err == nil {
					for offset, rawVal := range words {
						regNum := offset + 1
						mapping, exists := bundle.IWMap[regNum]
						if exists {
							if mapping.Name == "---" || strings.HasSuffix(mapping.TagName, "._PV") {
								continue
							}
							calibrated := mapping.Calibrate(rawVal)
							tagName := mapping.TagName
							if tagName == "" {
								tagName = fmt.Sprintf("SMM.%s.IW_%d_PV", mCfg.AssetID, regNum)
							}
							if regNum == 70 && strings.HasSuffix(tagName, "_ALARM") {
								tagName = strings.TrimSuffix(tagName, "_ALARM") + "_ALM"
							}
							if regNum == 1 {
								currentTempPV = calibrated
							}
							role := mapping.TagRole
							if role == "" || role == "ACTUAL" {
								role = "PV"
							} else if role == "SETPOINT" {
								role = "SV"
							} else if role == "ALARM" {
								role = "ALM"
							}
							tagsMap[tagName] = mqtt.TagMetric{
								Value:   calibrated,
								Raw:     rawVal,
								Unit:    mapping.Unit,
								Role:    role,
								Quality: 192,
							}
						}
					}
				}
			}

			// 2. OBJECT 1009: Recipe Setpoints (SV)
			if mCfg.Objects.EnableSET1009 {
				if setWords, err := tcpClient.ReadSETBlock(1, 40); err == nil {
					for offset, rawVal := range setWords {
						paramID := offset + 1
						param, exists := bundle.Parameters[paramID]
						var val float64
						var unit string
						tagName := fmt.Sprintf("SMM.%s.SET_%d_SV", mCfg.AssetID, paramID)
						if exists {
							val = param.Calibrate(rawVal)
							unit = param.Unit
							if param.TagName != "" {
								tagName = param.TagName
							}
						} else {
							val = float64(rawVal) / 10.0
						}
						if paramID == 1 {
							tagName = fmt.Sprintf("SMM.%s.MAIN_TANK.TEMPERATURE_SV", mCfg.AssetID)
							unit = "°C"
						} else if paramID == 5 {
							tagName = fmt.Sprintf("SMM.%s.MAIN_MOTOR.SPEED_SV", mCfg.AssetID)
							unit = "%"
						} else if paramID == 9 {
							tagName = fmt.Sprintf("SMM.%s.MAIN_TANK.LEVEL_SV", mCfg.AssetID)
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

			// 3. OBJECT 6: Active Step Recipe Function (SV)
			if mCfg.Objects.EnableFunction6 {
				if f141Vals, _, err := tcpClient.ReadActiveFunction(141); err == nil && len(f141Vals) >= 3 {
					if f141Vals[0] > 0 {
						tagsMap[fmt.Sprintf("SMM.%s.MAIN_TANK.TEMPERATURE_SV", mCfg.AssetID)] = mqtt.TagMetric{
							Value:   math.Round(float64(f141Vals[0])*10) / 10,
							Raw:     f141Vals[0],
							Unit:    "°C",
							Role:    "SV",
							Quality: 192,
						}
					}
					if f141Vals[1] >= 0 {
						tagsMap[fmt.Sprintf("SMM.%s.PROCESS.GRADIENT_SV", mCfg.AssetID)] = mqtt.TagMetric{
							Value:   math.Round(float64(f141Vals[1])*10) / 10,
							Raw:     f141Vals[1],
							Unit:    "°C/min",
							Role:    "SV",
							Quality: 192,
						}
					}
					if f141Vals[2] > 0 {
						tagsMap[fmt.Sprintf("SMM.%s.PROCESS.HOLDING_TIME_SV", mCfg.AssetID)] = mqtt.TagMetric{
							Value:   math.Round(float64(f141Vals[2])*10) / 10,
							Raw:     f141Vals[2],
							Unit:    "min",
							Role:    "SV",
							Quality: 192,
						}
					}
				}
				if f713Vals, _, err := tcpClient.ReadActiveFunction(713); err == nil && len(f713Vals) >= 2 {
					if f713Vals[1] > 0 {
						tagsMap[fmt.Sprintf("SMM.%s.MAIN_TANK.FILL_VOLUME_SV", mCfg.AssetID)] = mqtt.TagMetric{
							Value:   float64(f713Vals[1]),
							Raw:     f713Vals[1],
							Unit:    "L",
							Role:    "SV",
							Quality: 192,
						}
					}
				}
			}

			// 4. OBJECT 1010: Loop Control Actuals (PV)
			if mCfg.Objects.EnableACT1010 {
				if actWords, err := tcpClient.ReadACTBlock(1, 20); err == nil {
					for offset, rawVal := range actWords {
						idx := offset + 1
						tagName := fmt.Sprintf("SMM.%s.PID_LOOP.ACT_%d_PV", mCfg.AssetID, idx)
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

			// 5. OBJECT 1035: Batch Consumption Counters (TOTALIZER)
			if mCfg.Objects.EnableBATCH1035 {
				if dwords, _, err := tcpClient.ReadDWordBlock(1035, 1, 10); err == nil && len(dwords) >= 4 {
					tagsMap[fmt.Sprintf("SMM.%s.CONSUMPTION.WATER_L", mCfg.AssetID)] = mqtt.TagMetric{
						Value:   float64(dwords[0]),
						Raw:     dwords[0],
						Unit:    "L",
						Role:    "TOTALIZER",
						Quality: 192,
					}
					tagsMap[fmt.Sprintf("SMM.%s.CONSUMPTION.CYCLE_COUNT", mCfg.AssetID)] = mqtt.TagMetric{
						Value:   float64(dwords[1]),
						Raw:     dwords[1],
						Unit:    "cycle",
						Role:    "TOTALIZER",
						Quality: 192,
					}
					tagsMap[fmt.Sprintf("SMM.%s.CONSUMPTION.STEAM_KG", mCfg.AssetID)] = mqtt.TagMetric{
						Value:   float64(dwords[2]),
						Raw:     dwords[2],
						Unit:    "kg",
						Role:    "TOTALIZER",
						Quality: 192,
					}
					tagsMap[fmt.Sprintf("SMM.%s.CONSUMPTION.POWER_KWH", mCfg.AssetID)] = mqtt.TagMetric{
						Value:   float64(dwords[3]),
						Raw:     dwords[3],
						Unit:    "kWh",
						Role:    "TOTALIZER",
						Quality: 192,
					}
					if len(dwords) >= 6 && dwords[5] > 0 {
						tagsMap[fmt.Sprintf("SMM.%s.CONSUMPTION.RUN_TIME_SEC", mCfg.AssetID)] = mqtt.TagMetric{
							Value:   float64(dwords[5]),
							Raw:     dwords[5],
							Unit:    "s",
							Role:    "TOTALIZER",
							Quality: 192,
						}
					}
				}
			}

			// 6. PROCESS STEP CODE (from STATUS.ACT)
			if sNo > 0 {
				tagsMap[fmt.Sprintf("SMM.%s.MACHINE.PROCESS_STEP_CODE", mCfg.AssetID)] = mqtt.TagMetric{
					Value:   float64(sNo),
					Raw:     sNo,
					Unit:    "step",
					Role:    "PV",
					Quality: 192,
				}
				tagsMap[fmt.Sprintf("SMM.%s.PROCESS.STEP_CODE", mCfg.AssetID)] = mqtt.TagMetric{
					Value:   float64(sNo),
					Raw:     sNo,
					Unit:    "step",
					Role:    "PV",
					Quality: 192,
				}
			}

			telPayload := mqtt.TelemetryPayload{
				Timestamp: now,
				AssetID:   mCfg.AssetID,
				MachineID: mCfg.MachineID,
				BatchNo:   bNo,
				StepNo:    sNo,
				ProgramNo: pNo,
				Tags:      tagsMap,
			}

			if err := mqttPub.PublishTelemetry(telemetryTopic, telPayload); err != nil {
				logger.Warn("Failed to publish telemetry to EMQX", "machine", mCfg.MachineID, "error", err)
			}

			if cycleCount%20 == 1 {
				logger.Info("Telemetry cycle published",
					"machine", mCfg.MachineID,
					"batch", bNo,
					"step", sNo,
					"temp_pv", fmt.Sprintf("%.1f°C", currentTempPV),
					"tags", len(tagsMap),
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
