package storage

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type Storage struct {
	jetflowPool *pgxpool.Pool
	scadaPool   *pgxpool.Pool
	logger      *slog.Logger
}

type TagMetric struct {
	Value   float64     `json:"value"`
	Raw     interface{} `json:"raw"`
	Unit    string      `json:"unit"`
	Role    string      `json:"role"`
	Quality int         `json:"quality"`
}

type TelemetryPayload struct {
	Timestamp time.Time            `json:"timestamp"`
	AssetID   string               `json:"asset_id"`
	MachineID string               `json:"machine_id"`
	BatchNo   string               `json:"batch_no,omitempty"`
	StepNo    int                  `json:"step_no,omitempty"`
	ProgramNo string               `json:"program_no,omitempty"`
	Tags      map[string]TagMetric `json:"tags"`
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

type CyclicPoint struct {
	LogTimestamp      time.Time `json:"log_timestamp"`
	MachineNo         string    `json:"machine_no"`
	BatchRefNo        string    `json:"batch_ref_no"`
	TempPV            float64   `json:"temp_pv"`
	TempSP            float64   `json:"temp_sp"`
	TempPT100T2       float64   `json:"temp_pt100_t2"`
	PumpSpeedPercent  float64   `json:"pump_speed_percent"`
	ReelSpeedMPM      float64   `json:"reel_speed_mpm"`
	VesselPressureBar float64   `json:"vessel_pressure_bar"`
	StepNo            int       `json:"step_no"`
	RawDigitalBits    int       `json:"raw_digital_bits"`
}

type BatchCurvePayload struct {
	AssetID   string        `json:"asset_id"`
	MachineID string        `json:"machine_id"`
	BatchNo   string        `json:"batch_no"`
	Points    []CyclicPoint `json:"points"`
}

type AlarmItem struct {
	BatchRefNo     string     `json:"batch_ref_no"`
	MachineNo      string     `json:"machine_no"`
	AlarmTimestamp time.Time  `json:"alarm_timestamp"`
	AlarmCode      string     `json:"alarm_code"`
	AlarmText      string     `json:"alarm_text"`
	StepNo         int        `json:"step_no"`
	OperatorID     int        `json:"operator_id"`
	Severity       string     `json:"severity"`
	ClearedAt      *time.Time `json:"cleared_at,omitempty"`
}

type AlarmsPayload struct {
	AssetID   string      `json:"asset_id"`
	MachineID string      `json:"machine_id"`
	Alarms    []AlarmItem `json:"alarms"`
}

func NewStorage(ctx context.Context, jetflowURL, scadaURL string, maxConns, minConns int32, logger *slog.Logger) (*Storage, error) {
	jfCfg, err := pgxpool.ParseConfig(jetflowURL)
	if err != nil {
		return nil, fmt.Errorf("parse jetflow url: %w", err)
	}
	if maxConns > 0 {
		jfCfg.MaxConns = maxConns
	}
	if minConns > 0 {
		jfCfg.MinConns = minConns
	}

	jfPool, err := pgxpool.NewWithConfig(ctx, jfCfg)
	if err != nil {
		return nil, fmt.Errorf("connect jetflow pool: %w", err)
	}

	scadaCfg, err := pgxpool.ParseConfig(scadaURL)
	if err != nil {
		jfPool.Close()
		return nil, fmt.Errorf("parse scada url: %w", err)
	}
	if maxConns > 0 {
		scadaCfg.MaxConns = maxConns
	}
	if minConns > 0 {
		scadaCfg.MinConns = minConns
	}

	scadaPool, err := pgxpool.NewWithConfig(ctx, scadaCfg)
	if err != nil {
		jfPool.Close()
		return nil, fmt.Errorf("connect scada pool: %w", err)
	}

	return &Storage{
		jetflowPool: jfPool,
		scadaPool:   scadaPool,
		logger:      logger,
	}, nil
}

// IngestTelemetry processes multi-object telemetry payload into live, SCADA, and historian tables.
func (s *Storage) IngestTelemetry(ctx context.Context, p TelemetryPayload) error {
	now := p.Timestamp
	if now.IsZero() {
		now = time.Now()
	}

	// Extract primary temp if available
	var currentTemp float64
	for k, v := range p.Tags {
		if k == fmt.Sprintf("SMM.%s.MAIN_TANK.TEMPERATURE_PV", p.AssetID) || k == fmt.Sprintf("SMM.%s.CONTROLLER.IW_1_PV", p.AssetID) {
			currentTemp = v.Value
			break
		}
	}

	// 1. JSON Snapshot for live_iw_telemetry
	telemetryBytes, _ := json.Marshal(p.Tags)
	queryLive := `
		INSERT INTO live_iw_telemetry 
		(machine_id, asset_id, last_updated, connection_status, batch_no, step_no, program_no, telemetry_json)
		VALUES ($1, $2, $3, 'ONLINE', $4, $5, $6, $7)
		ON CONFLICT (machine_id) DO UPDATE SET
			last_updated = EXCLUDED.last_updated,
			connection_status = 'ONLINE',
			batch_no = EXCLUDED.batch_no,
			step_no = EXCLUDED.step_no,
			program_no = EXCLUDED.program_no,
			telemetry_json = EXCLUDED.telemetry_json;
	`
	_, err := s.jetflowPool.Exec(ctx, queryLive, p.MachineID, p.AssetID, now, p.BatchNo, p.StepNo, p.ProgramNo, telemetryBytes)
	if err != nil {
		s.logger.Error("Error updating live_iw_telemetry", "machine", p.MachineID, "error", err)
	}

	// 2. Update machine status & temp in machines
	if currentTemp > 0 {
		queryMachine := `
			UPDATE machines 
			SET current_temp = $1, 
			    current_batch = COALESCE(NULLIF($2, ''), current_batch),
			    current_step = CASE WHEN $3 > 0 THEN $3 ELSE current_step END,
			    last_ping_time = $4,
			    status = 'RUNNING'
			WHERE machine_no = $5;
		`
		_, _ = s.jetflowPool.Exec(ctx, queryMachine, currentTemp, p.BatchNo, p.StepNo, now, p.MachineID)
	}

	// 3. Ensure tag definitions exist in pt_smm_scada.tag_definition (Auto-register new SV/PV/TOTALIZER tags)
	if len(p.Tags) > 0 {
		sortedTagNames := make([]string, 0, len(p.Tags))
		for tagName := range p.Tags {
			sortedTagNames = append(sortedTagNames, tagName)
		}
		sort.Strings(sortedTagNames)

		batchDef := &pgx.Batch{}
		queryDef := `
			INSERT INTO tag_definition (tag_code, asset_id, signal_role, engineering_unit, source_status, active, created_at, stale_after_seconds, freshness_mode, display_name)
			VALUES ($1, $2, $3, $4, 'LIVE', TRUE, NOW(), 60, 'TAG_TIMESTAMP', $1)
			ON CONFLICT (tag_code) DO NOTHING;
		`
		for _, tagName := range sortedTagNames {
			metric := p.Tags[tagName]
			role := metric.Role
			if role == "" {
				role = "PV"
			}
			batchDef.Queue(queryDef, tagName, p.AssetID, role, metric.Unit)
		}
		brDef := s.scadaPool.SendBatch(ctx, batchDef)
		for range sortedTagNames {
			_, _ = brDef.Exec()
		}
		_ = brDef.Close()

		// 3.1 Batch upsert into pt_smm_scada.tag_latest (Sorted keys for deterministic locking)
		batchScada := &pgx.Batch{}
		queryScada := `
			INSERT INTO tag_latest (tag_code, asset_id, value_number, quality, source_ts, ingested_at, updated_at, message_id)
			VALUES ($1, $2, $3, 'GOOD', $4, NOW(), NOW(), gen_random_uuid())
			ON CONFLICT (tag_code) DO UPDATE SET
				value_number = EXCLUDED.value_number,
				quality = 'GOOD',
				source_ts = EXCLUDED.source_ts,
				ingested_at = NOW(),
				updated_at = NOW(),
				message_id = gen_random_uuid();
		`
		for _, tagName := range sortedTagNames {
			metric := p.Tags[tagName]
			batchScada.Queue(queryScada, tagName, p.AssetID, metric.Value, now)
		}

		br := s.scadaPool.SendBatch(ctx, batchScada)
		if err := br.Close(); err != nil {
			s.logger.Warn("Error batch updating tag_latest in pt_smm_scada", "error", err)
		} else {
			// Trigger Jetflow asset snapshot calculation once per telemetry cycle
			_, _ = s.scadaPool.Exec(ctx, "SELECT sync_jetflow_asset_snapshot($1);", p.AssetID)
		}
	}

	// 4. Historian insertion to datalog_iw_records for key process metrics
	if len(p.Tags) > 0 {
		batchJf := &pgx.Batch{}
		queryDatalog := `
			INSERT INTO datalog_iw_records (time, machine_id, asset_id, batch_no, step_no, tag_name, value, raw_value, quality)
			VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9);
		`
		for tagName, metric := range p.Tags {
			// Save key PV, SV, and Totalizers to historian
			var rawInt int
			switch v := metric.Raw.(type) {
			case float64:
				rawInt = int(v)
			case int:
				rawInt = v
			case uint16:
				rawInt = int(v)
			case uint32:
				rawInt = int(v)
			default:
				rawInt = int(metric.Value)
			}
			batchJf.Queue(queryDatalog, now, p.MachineID, p.AssetID, p.BatchNo, p.StepNo, tagName, metric.Value, rawInt, metric.Quality)
		}
		brJf := s.jetflowPool.SendBatch(ctx, batchJf)
		_ = brJf.Close()
	}

	return nil
}

// ensureBatchHeader auto-registers newly detected batches in batch_headers so they appear on the dashboard.
func (s *Storage) ensureBatchHeader(ctx context.Context, machineNo, batchRefNo, programNo string) {
	ref := strings.TrimSpace(batchRefNo)
	mach := strings.TrimSpace(machineNo)
	if ref == "" || mach == "" {
		return
	}

	progNum := 1
	if pVal, err := strconv.Atoi(strings.TrimSpace(programNo)); err == nil && pVal > 0 {
		progNum = pVal
	}

	batchNo := ref
	if !strings.HasPrefix(batchNo, "LOT-") {
		batchNo = "LOT-" + ref
	}
	recipeName := fmt.Sprintf("Program %d", progNum)

	query := `
		INSERT INTO batch_headers
		(batch_ref_no, batch_no, machine_no, program_no, recipe_name, status, fabric_weight_kg, liquor_ratio, customer)
		VALUES (
			$1, $2, $3, $4, $5, 'RUNNING',
			COALESCE((SELECT capacity_kg FROM machines WHERE machine_no = $3), 350.0),
			COALESCE((SELECT default_liquor_ratio FROM machines WHERE machine_no = $3), 8.0),
			'PT. SMM JETFLOW'
		)
		ON CONFLICT (batch_ref_no) DO NOTHING;
	`
	if _, err := s.jetflowPool.Exec(ctx, query, ref, batchNo, mach, progNum, recipeName); err != nil {
		s.logger.Warn("Error ensuring batch_headers entry", "batch", ref, "machine", mach, "error", err)
	}
}

// IngestStatus updates machine status across tables.
func (s *Storage) IngestStatus(ctx context.Context, p StatusPayload) error {
	now := p.Timestamp
	if now.IsZero() {
		now = time.Now()
	}

	queryLive := `
		INSERT INTO live_iw_telemetry 
		(machine_id, asset_id, last_updated, connection_status, batch_no, step_no, program_no)
		VALUES ($1, $2, $3, $4, $5, $6, $7)
		ON CONFLICT (machine_id) DO UPDATE SET
			last_updated = EXCLUDED.last_updated,
			connection_status = EXCLUDED.connection_status,
			batch_no = COALESCE(NULLIF(EXCLUDED.batch_no, ''), live_iw_telemetry.batch_no),
			step_no = CASE WHEN EXCLUDED.step_no > 0 THEN EXCLUDED.step_no ELSE live_iw_telemetry.step_no END,
			program_no = COALESCE(NULLIF(EXCLUDED.program_no, ''), live_iw_telemetry.program_no);
	`
	_, _ = s.jetflowPool.Exec(ctx, queryLive, p.MachineID, p.AssetID, now, p.ConnectionStatus, p.BatchNo, p.StepNo, p.ProgramNo)

	// Update machine current_batch & step in machines table
	queryMachine := `
		UPDATE machines
		SET current_batch = COALESCE(NULLIF($1, ''), current_batch),
		    current_step = CASE WHEN $2 > 0 THEN $2 ELSE current_step END,
		    last_ping_time = $3,
		    status = CASE WHEN $4 = 'ONLINE' THEN 'RUNNING' ELSE status END
		WHERE machine_no = $5;
	`
	_, _ = s.jetflowPool.Exec(ctx, queryMachine, p.BatchNo, p.StepNo, now, p.ConnectionStatus, p.MachineID)

	// Auto-register new batch in batch_headers
	s.ensureBatchHeader(ctx, p.MachineID, p.BatchNo, p.ProgramNo)

	// Update asset table
	queryAsset := `
		UPDATE asset 
		SET connected = ($1 = 'ONLINE'),
		    batch_ref_no = COALESCE(NULLIF($2, ''), batch_ref_no),
		    step_no = CASE WHEN $3 > 0 THEN $3 ELSE step_no END,
		    updated_at = NOW()
		WHERE asset_id = $4;
	`
	_, _ = s.scadaPool.Exec(ctx, queryAsset, p.ConnectionStatus, p.BatchNo, p.StepNo, p.AssetID)

	return nil
}

// IngestBatchCurve stores parsed PR<batch>.LOG curve points into datalog_cyclic_records.
func (s *Storage) IngestBatchCurve(ctx context.Context, p BatchCurvePayload) error {
	if len(p.Points) == 0 {
		return nil
	}

	machineNo := p.MachineID
	if machineNo == "" && len(p.Points) > 0 {
		machineNo = p.Points[0].MachineNo
	}
	s.ensureBatchHeader(ctx, machineNo, p.BatchNo, "")

	// Chunk points in batches of 200 to prevent oversized SQL statements
	chunkSize := 200
	query := `
		INSERT INTO datalog_cyclic_records 
		(log_timestamp, machine_no, batch_ref_no, temp_pv, temp_sp, temp_pt100_t2, pump_speed_percent, reel_speed_mpm, vessel_pressure_bar, step_no, raw_digital_bits)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
		ON CONFLICT (log_timestamp, machine_no, batch_ref_no) DO UPDATE SET
			temp_pv = EXCLUDED.temp_pv,
			temp_sp = EXCLUDED.temp_sp,
			temp_pt100_t2 = EXCLUDED.temp_pt100_t2,
			pump_speed_percent = EXCLUDED.pump_speed_percent,
			reel_speed_mpm = EXCLUDED.reel_speed_mpm,
			vessel_pressure_bar = EXCLUDED.vessel_pressure_bar,
			step_no = EXCLUDED.step_no,
			raw_digital_bits = EXCLUDED.raw_digital_bits;
	`

	for i := 0; i < len(p.Points); i += chunkSize {
		end := i + chunkSize
		if end > len(p.Points) {
			end = len(p.Points)
		}
		chunk := p.Points[i:end]

		batch := &pgx.Batch{}
		for _, pt := range chunk {
			batch.Queue(query,
				pt.LogTimestamp, pt.MachineNo, pt.BatchRefNo,
				pt.TempPV, pt.TempSP, pt.TempPT100T2,
				pt.PumpSpeedPercent, pt.ReelSpeedMPM, pt.VesselPressureBar,
				pt.StepNo, pt.RawDigitalBits,
			)
		}
		br := s.jetflowPool.SendBatch(ctx, batch)
		if err := br.Close(); err != nil {
			s.logger.Error("Failed inserting batch curve chunk", "error", err)
			return err
		}
	}

	return nil
}

// IngestAlarms stores parsed alarm records into datalog_alarms.
func (s *Storage) IngestAlarms(ctx context.Context, p AlarmsPayload) error {
	if len(p.Alarms) == 0 {
		return nil
	}

	query := `
		INSERT INTO datalog_alarms 
		(batch_ref_no, machine_no, alarm_timestamp, alarm_code, alarm_text, step_no, operator_id, severity, cleared_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9);
	`
	batch := &pgx.Batch{}
	for _, a := range p.Alarms {
		batch.Queue(query,
			a.BatchRefNo, a.MachineNo, a.AlarmTimestamp,
			a.AlarmCode, a.AlarmText, a.StepNo, a.OperatorID, a.Severity, a.ClearedAt,
		)
	}

	br := s.jetflowPool.SendBatch(ctx, batch)
	return br.Close()
}

func (s *Storage) Close() {
	if s.jetflowPool != nil {
		s.jetflowPool.Close()
	}
	if s.scadaPool != nil {
		s.scadaPool.Close()
	}
}
