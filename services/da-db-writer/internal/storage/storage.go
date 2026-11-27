package storage

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"math"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type Storage struct {
	jetflowPool  *pgxpool.Pool
	scadaPool    *pgxpool.Pool
	logger       *slog.Logger
	knownAssets  sync.Map // map[string]bool (asset_id -> exists in pt_smm_scada.asset)
	knownTagDefs sync.Map // map[string]struct{} (tag_code already registered in tag_definition)
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

type ActInterventionEvent struct {
	Type          string  `json:"type"`
	DetectedAt    string  `json:"detected_at"`
	StepNo        int     `json:"step_no"`
	Slot          int     `json:"slot"`
	FuncID        int     `json:"func_id,omitempty"`
	Func          string  `json:"func,omitempty"`
	ParamIndex    int     `json:"param_index"`
	ParameterName string  `json:"parameter_name,omitempty"`
	Unit          string  `json:"unit,omitempty"`
	Before        float64 `json:"before"`
	After         float64 `json:"after"`
	Delta         float64 `json:"delta"`
	AlarmCode     int     `json:"alarm_code"`
	FromStep      int     `json:"from_step,omitempty"`
	ToStep        int     `json:"to_step,omitempty"`
}

type StatusPayload struct {
	Timestamp          time.Time              `json:"timestamp"`
	AssetID            string                 `json:"asset_id"`
	MachineID          string                 `json:"machine_id"`
	ConnectionStatus   string                 `json:"connection_status"`
	BatchNo            string                 `json:"batch_no"`
	StepNo             int                    `json:"step_no"`
	ProgramNo          string                 `json:"program_no"`
	ProgramCode        string                 `json:"program_code,omitempty"`
	ProgramName        string                 `json:"program_name,omitempty"`
	InterventionEvents []ActInterventionEvent `json:"intervention_events,omitempty"`
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

type BatchInfoMeta struct {
	ProgramCode  string `json:"program_code,omitempty"`
	CustomerName string `json:"customer_name,omitempty"`
	FabricType   string `json:"fabric_type,omitempty"`
	OrderNo      string `json:"order_no,omitempty"`
	ColorName    string `json:"color_name,omitempty"`
	ProgramName  string `json:"program_name,omitempty"`
	StartedAt    string `json:"started_at,omitempty"`
}

type BatchSummaryMeta struct {
	TotalWaitSec   int     `json:"total_wait_sec,omitempty"`
	TotalPauses    int     `json:"total_pauses,omitempty"`
	TotalJumps     int     `json:"total_jumps,omitempty"`
	TotalAlarms    int     `json:"total_alarms,omitempty"`
	TotalOverrides int     `json:"total_overrides,omitempty"`
	WaterL         float64 `json:"water_l,omitempty"`
	SteamKg        float64 `json:"steam_kg,omitempty"`
	PowerKwh       float64 `json:"power_kwh,omitempty"`
	BatchEnded     bool    `json:"batch_ended,omitempty"`
}

type OperatorEventItem struct {
	TS            string  `json:"ts"`
	Type          string  `json:"type"`
	StepNo        int     `json:"step_no,omitempty"`
	FromStep      int     `json:"from_step,omitempty"`
	ToStep        int     `json:"to_step,omitempty"`
	FuncID        int     `json:"func_id,omitempty"`
	Code          int     `json:"code,omitempty"`
	WaitSec       int     `json:"wait_sec,omitempty"`
	ParameterName string  `json:"parameter_name,omitempty"`
	Unit          string  `json:"unit,omitempty"`
	ValueBefore   float64 `json:"value_before,omitempty"`
	ValueAfter    float64 `json:"value_after,omitempty"`
	Delta         float64 `json:"delta,omitempty"`
	Detail        string  `json:"detail,omitempty"`
}

type BatchAlarmMeta struct {
	AlarmTimestamp string  `json:"alarm_timestamp"`
	AlarmCode      string  `json:"alarm_code"`
	AlarmText      string  `json:"alarm_text"`
	StepNo         int     `json:"step_no"`
	Severity       string  `json:"severity"`
	ClearedAt      *string `json:"cleared_at,omitempty"`
}

type BatchProgramPayload struct {
	AssetID           string              `json:"asset_id"`
	MachineNo         string              `json:"machine_no"`
	BatchNo           string              `json:"batch_no"`
	ProgramNo         string              `json:"program_no"`
	ProgramName       string              `json:"program_name"`
	ProgramFile       string              `json:"program_file"`
	ProgramSource     string              `json:"program_source"`
	CurrentStep       int                 `json:"current_step"`
	TotalSteps        int                 `json:"total_steps"`
	BatchInfo         *BatchInfoMeta      `json:"batch_info,omitempty"`
	OperatorTimeline  []OperatorEventItem `json:"operator_timeline,omitempty"`
	SetpointOverrides []OperatorEventItem `json:"setpoint_overrides,omitempty"`
	BatchAlarms       []BatchAlarmMeta    `json:"batch_alarms,omitempty"`
	BatchSummary      *BatchSummaryMeta   `json:"batch_summary,omitempty"`
	InterventActive   int                 `json:"intervent_active"`
	Program           json.RawMessage     `json:"program"`
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
			asset_id = EXCLUDED.asset_id,
			last_updated = EXCLUDED.last_updated,
			connection_status = 'ONLINE',
			batch_no = COALESCE(NULLIF(EXCLUDED.batch_no, ''), live_iw_telemetry.batch_no),
			step_no = CASE WHEN EXCLUDED.step_no > 0 THEN EXCLUDED.step_no ELSE live_iw_telemetry.step_no END,
			program_no = COALESCE(NULLIF(EXCLUDED.program_no, ''), live_iw_telemetry.program_no),
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

	// 3. Ensure tag definitions exist in pt_smm_scada.tag_definition (only for assets registered in pt_smm_scada.asset)
	var assetExists bool
	if len(p.Tags) > 0 && p.AssetID != "" {
		_ = s.scadaPool.QueryRow(ctx, "SELECT EXISTS(SELECT 1 FROM asset WHERE asset_id = $1);", p.AssetID).Scan(&assetExists)
	}
	if len(p.Tags) > 0 && assetExists {
		sortedTagNames := make([]string, 0, len(p.Tags))
		for tagName := range p.Tags {
			sortedTagNames = append(sortedTagNames, tagName)
		}
		sort.Strings(sortedTagNames)

		batchDef := &pgx.Batch{}
		queryDef := `
			INSERT INTO tag_definition (tag_code, asset_id, signal_role, engineering_unit, source_status, active, created_at, stale_after_seconds, freshness_mode, display_name)
			VALUES ($1, $2, $3, $4, 'LIVE', TRUE, NOW(), 60, 'TAG_TIMESTAMP', $1)
			ON CONFLICT (tag_code) DO UPDATE SET
				asset_id = EXCLUDED.asset_id;
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
				asset_id = EXCLUDED.asset_id,
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
			// Auto-promote asset from DUMMY to LIVE once live telemetry is persisted
			_, _ = s.scadaPool.Exec(ctx, "UPDATE asset SET data_source = 'LIVE', updated_at = NOW() WHERE asset_id = $1 AND data_source = 'DUMMY';", p.AssetID)
			// Trigger Jetflow asset snapshot calculation once per telemetry cycle
			_, _ = s.scadaPool.Exec(ctx, "SELECT sync_jetflow_asset_snapshot($1);", p.AssetID)
		}
	}

	// 3.1.1 Update SCADA asset_snapshot & batch_process_run so :8788 Digital Automation dashboard shows live batch
	if p.BatchNo != "" && p.AssetID != "" {
		s.ensureScadaBatchAndSnapshot(ctx, p.AssetID, p.BatchNo, p.ProgramNo)
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

// isKnownScadaAsset checks (with in-memory cache) whether asset_id exists in pt_smm_scada.asset.
func (s *Storage) isKnownScadaAsset(ctx context.Context, assetID string) bool {
	if assetID == "" {
		return false
	}
	if v, ok := s.knownAssets.Load(assetID); ok {
		return v.(bool)
	}
	var exists bool
	if err := s.scadaPool.QueryRow(ctx, "SELECT EXISTS(SELECT 1 FROM asset WHERE asset_id = $1);", assetID).Scan(&exists); err == nil {
		// Only permanently cache positive hits so newly registered assets are picked up
		if exists {
			s.knownAssets.Store(assetID, true)
		}
		return exists
	}
	return false
}

// IngestTelemetryBatch persists a batch of telemetry payloads efficiently:
//   - Bulk-copies ALL historian rows into datalog_iw_records via pgx.CopyFrom (1 round-trip)
//   - Deduplicates latest snapshot per machine for live_iw_telemetry, machines, and pt_smm_scada.tag_latest
//   - Caches asset existence and tag_definition registrations in memory to avoid redundant writes
func (s *Storage) IngestTelemetryBatch(ctx context.Context, payloads []TelemetryPayload) error {
	if len(payloads) == 0 {
		return nil
	}

	// 1. Collect all historian rows & keep latest payload per machine_id
	latestByMachine := make(map[string]TelemetryPayload, len(payloads))
	copyRows := make([][]interface{}, 0, len(payloads)*32)

	for _, p := range payloads {
		now := p.Timestamp
		if now.IsZero() {
			now = time.Now()
		}
		p.Timestamp = now

		if prev, ok := latestByMachine[p.MachineID]; !ok || !now.Before(prev.Timestamp) {
			latestByMachine[p.MachineID] = p
		}

		for tagName, metric := range p.Tags {
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
			copyRows = append(copyRows, []interface{}{
				now, p.MachineID, p.AssetID, p.BatchNo, p.StepNo, tagName, metric.Value, rawInt, metric.Quality,
			})
		}
	}

	// 2. Bulk COPY all historian rows into datalog_iw_records in 1 round-trip
	if len(copyRows) > 0 {
		_, err := s.jetflowPool.CopyFrom(
			ctx,
			pgx.Identifier{"datalog_iw_records"},
			[]string{"time", "machine_id", "asset_id", "batch_no", "step_no", "tag_name", "value", "raw_value", "quality"},
			pgx.CopyFromRows(copyRows),
		)
		if err != nil {
			s.logger.Warn("Error bulk copying datalog_iw_records", "rows", len(copyRows), "error", err)
		}
	}

	// 3. Batch upsert live_iw_telemetry & machines (deduplicated per machine, sorted deterministically)
	machineIDs := make([]string, 0, len(latestByMachine))
	for mID := range latestByMachine {
		machineIDs = append(machineIDs, mID)
	}
	sort.Strings(machineIDs)

	queryLive := `
		INSERT INTO live_iw_telemetry
		(machine_id, asset_id, last_updated, connection_status, batch_no, step_no, program_no, telemetry_json)
		VALUES ($1, $2, $3, 'ONLINE', $4, $5, $6, $7)
		ON CONFLICT (machine_id) DO UPDATE SET
			asset_id = EXCLUDED.asset_id,
			last_updated = EXCLUDED.last_updated,
			connection_status = 'ONLINE',
			batch_no = COALESCE(NULLIF(EXCLUDED.batch_no, ''), live_iw_telemetry.batch_no),
			step_no = CASE WHEN EXCLUDED.step_no > 0 THEN EXCLUDED.step_no ELSE live_iw_telemetry.step_no END,
			program_no = COALESCE(NULLIF(EXCLUDED.program_no, ''), live_iw_telemetry.program_no),
			telemetry_json = EXCLUDED.telemetry_json;
	`
	queryMachine := `
		UPDATE machines
		SET current_temp = $1,
		    current_batch = COALESCE(NULLIF($2, ''), current_batch),
		    current_step = CASE WHEN $3 > 0 THEN $3 ELSE current_step END,
		    last_ping_time = $4,
		    status = 'RUNNING'
		WHERE machine_no = $5;
	`

	liveBatch := &pgx.Batch{}
	for _, mID := range machineIDs {
		p := latestByMachine[mID]
		telemetryBytes, _ := json.Marshal(p.Tags)
		liveBatch.Queue(queryLive, p.MachineID, p.AssetID, p.Timestamp, p.BatchNo, p.StepNo, p.ProgramNo, telemetryBytes)

		var currentTemp float64
		for k, v := range p.Tags {
			if k == fmt.Sprintf("SMM.%s.MAIN_TANK.TEMPERATURE_PV", p.AssetID) || k == fmt.Sprintf("SMM.%s.CONTROLLER.IW_1_PV", p.AssetID) {
				currentTemp = v.Value
				break
			}
		}
		if currentTemp > 0 {
			liveBatch.Queue(queryMachine, currentTemp, p.BatchNo, p.StepNo, p.Timestamp, p.MachineID)
		}
	}
	if liveBatch.Len() > 0 {
		brLive := s.jetflowPool.SendBatch(ctx, liveBatch)
		if err := brLive.Close(); err != nil {
			s.logger.Warn("Error batch updating live_iw_telemetry/machines", "machines", len(machineIDs), "error", err)
		}
	}

	// 4. Batch upsert SCADA tag_definition (new tags only) & tag_latest (deduplicated per tag)
	queryDef := `
		INSERT INTO tag_definition (tag_code, asset_id, signal_role, engineering_unit, source_status, active, created_at, stale_after_seconds, freshness_mode, display_name)
		VALUES ($1, $2, $3, $4, 'LIVE', TRUE, NOW(), 60, 'TAG_TIMESTAMP', $1)
		ON CONFLICT (tag_code) DO UPDATE SET
			asset_id = EXCLUDED.asset_id;
	`
	queryScada := `
		INSERT INTO tag_latest (tag_code, asset_id, value_number, quality, source_ts, ingested_at, updated_at, message_id)
		VALUES ($1, $2, $3, 'GOOD', $4, NOW(), NOW(), gen_random_uuid())
		ON CONFLICT (tag_code) DO UPDATE SET
			asset_id = EXCLUDED.asset_id,
			value_number = EXCLUDED.value_number,
			quality = 'GOOD',
			source_ts = EXCLUDED.source_ts,
			ingested_at = NOW(),
			updated_at = NOW(),
			message_id = gen_random_uuid();
	`

	defBatch := &pgx.Batch{}
	newDefTags := make([]string, 0)
	scadaBatch := &pgx.Batch{}
	syncedAssets := make([]string, 0, len(machineIDs))

	for _, mID := range machineIDs {
		p := latestByMachine[mID]
		if len(p.Tags) == 0 || !s.isKnownScadaAsset(ctx, p.AssetID) {
			continue
		}
		syncedAssets = append(syncedAssets, p.AssetID)

		sortedTags := make([]string, 0, len(p.Tags))
		for tagName := range p.Tags {
			sortedTags = append(sortedTags, tagName)
		}
		sort.Strings(sortedTags)

		for _, tagName := range sortedTags {
			metric := p.Tags[tagName]
			if _, seen := s.knownTagDefs.Load(tagName); !seen {
				role := metric.Role
				if role == "" {
					role = "PV"
				}
				defBatch.Queue(queryDef, tagName, p.AssetID, role, metric.Unit)
				newDefTags = append(newDefTags, tagName)
			}
			scadaBatch.Queue(queryScada, tagName, p.AssetID, metric.Value, p.Timestamp)
		}
	}

	if defBatch.Len() > 0 {
		brDef := s.scadaPool.SendBatch(ctx, defBatch)
		if err := brDef.Close(); err == nil {
			for _, tn := range newDefTags {
				s.knownTagDefs.Store(tn, struct{}{})
			}
		} else {
			s.logger.Warn("Error batch upserting tag_definition", "count", len(newDefTags), "error", err)
		}
	}

	if scadaBatch.Len() > 0 {
		brScada := s.scadaPool.SendBatch(ctx, scadaBatch)
		if err := brScada.Close(); err != nil {
			s.logger.Warn("Error batch updating tag_latest in pt_smm_scada", "error", err)
		} else if len(syncedAssets) > 0 {
			snapBatch := &pgx.Batch{}
			for _, aid := range syncedAssets {
				snapBatch.Queue("UPDATE asset SET data_source = 'LIVE', updated_at = NOW() WHERE asset_id = $1 AND data_source = 'DUMMY';", aid)
				snapBatch.Queue("SELECT sync_jetflow_asset_snapshot($1);", aid)
			}
			brSnap := s.scadaPool.SendBatch(ctx, snapBatch)
			_ = brSnap.Close()
		}
	}

	// 5. Sync SCADA batch_process_run & asset_snapshot for active batches in this flush
	for _, mID := range machineIDs {
		p := latestByMachine[mID]
		if p.BatchNo != "" && p.AssetID != "" {
			s.ensureScadaBatchAndSnapshot(ctx, p.AssetID, p.BatchNo, p.ProgramNo)
		}
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
			$1, $2, $3::varchar, $4, $5, 'RUNNING',
			COALESCE((SELECT capacity_kg FROM machines WHERE machine_no = $3::varchar), 350.0),
			COALESCE((SELECT default_liquor_ratio FROM machines WHERE machine_no = $3::varchar), 8.0),
			'PT. SMM JETFLOW'
		)
		ON CONFLICT (batch_ref_no) DO NOTHING;
	`
	if _, err := s.jetflowPool.Exec(ctx, query, ref, batchNo, mach, progNum, recipeName); err != nil {
		s.logger.Warn("Error ensuring batch_headers entry", "batch", ref, "machine", mach, "error", err)
	}
}

// ensureScadaBatchAndSnapshot syncs active batch & state into pt_smm_scada (production_batch, batch_process_run, asset_snapshot)
// so the Digital Automation (:8788) dashboard automatically detects new batches and records run history.
func (s *Storage) ensureScadaBatchAndSnapshot(ctx context.Context, assetID, batchNo, programNo string) {
	aid := strings.TrimSpace(assetID)
	bno := strings.TrimSpace(batchNo)
	if aid == "" || bno == "" || bno == "000000" {
		return
	}

	// 1. Ensure production_batch exists (FK requirement for batch_process_run)
	_, err := s.scadaPool.Exec(ctx, `
		INSERT INTO production_batch (batch_no, batch_status, source_system, created_at, updated_at)
		VALUES ($1, 'RUNNING', 'SETEX_COLLECTOR', NOW(), NOW())
		ON CONFLICT (batch_no) DO UPDATE SET updated_at = NOW();
	`, bno)
	if err != nil {
		s.logger.Debug("Error upserting production_batch", "batch", bno, "error", err)
		return
	}

	// 2. Complete any previous RUNNING batch on this asset when a new batch starts
	_, _ = s.scadaPool.Exec(ctx, `
		UPDATE batch_process_run
		SET run_status = 'COMPLETED',
		    ended_at = COALESCE(ended_at, NOW()),
		    updated_at = NOW()
		WHERE asset_id = $1 AND run_status = 'RUNNING' AND batch_no <> $2;
	`, aid, bno)

	// 3. Upsert current RUNNING batch_process_run for (asset_id, batch_no)
	progStr := strings.TrimSpace(programNo)
	if progStr == "" {
		progStr = "1"
	}
	recipeCode := "PROGRAM " + progStr
	_, err = s.scadaPool.Exec(ctx, `
		WITH updated AS (
			UPDATE batch_process_run
			SET run_status = 'RUNNING',
			    recipe_code = COALESCE(NULLIF($3, ''), recipe_code),
			    source_updated_at = NOW(),
			    updated_at = NOW()
			WHERE asset_id = $1 AND batch_no = $2
			RETURNING process_run_id
		)
		INSERT INTO batch_process_run
		(process_run_id, batch_no, asset_id, process_type, recipe_code, run_status, started_at, source_system, source_updated_at, created_at, updated_at, payload_json)
		SELECT gen_random_uuid(), $2, $1, 'jetflow', $3, 'RUNNING', NOW(), 'SETEX_COLLECTOR', NOW(), NOW(), NOW(),
		       jsonb_build_object('program_no', $4::text)
		WHERE NOT EXISTS (SELECT 1 FROM updated)
		  AND EXISTS (SELECT 1 FROM asset WHERE asset_id = $1);
	`, aid, bno, recipeCode, progStr)
	if err != nil {
		s.logger.Debug("Error upserting batch_process_run", "asset", aid, "batch", bno, "error", err)
	}

	// 4. Update asset_snapshot.batch_no & machine_state so :8788 UI shows active batch immediately
	_, _ = s.scadaPool.Exec(ctx, `
		UPDATE asset_snapshot
		SET batch_no = $2,
		    machine_state = 'running',
		    connected = TRUE,
		    updated_at = NOW()
		WHERE asset_id = $1;
	`, aid, bno)
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
			asset_id = EXCLUDED.asset_id,
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

	// Auto-register new batch in batch_headers (pt_smm_jetflow) and SCADA tables (pt_smm_scada)
	s.ensureBatchHeader(ctx, p.MachineID, p.BatchNo, p.ProgramNo)
	if p.ConnectionStatus == "ONLINE" {
		s.ensureScadaBatchAndSnapshot(ctx, p.AssetID, p.BatchNo, p.ProgramNo)
	}

	// Update lightweight SCADA step tags (SMM.<ASSET>.MACHINE.PROCESS_STEP_CODE & PROCESS.STEP_CODE)
	if p.StepNo > 0 && p.AssetID != "" {
		s.upsertScadaStepTag(ctx, p.AssetID, p.StepNo, now)
	}

	// Update batch_process_run.payload_json with program_code/program_name and embed operator interventions into program[]
	if p.ConnectionStatus == "ONLINE" && p.AssetID != "" && p.BatchNo != "" {
		s.syncScadaBatchMetaAndInterventions(ctx, p, now)
	}

	return nil
}

func formatScadaParamValue(val float64, unit string) string {
	var numStr string
	if math.Abs(val-math.Round(val)) < 1e-6 {
		numStr = strconv.FormatInt(int64(math.Round(val)), 10)
	} else {
		numStr = strconv.FormatFloat(math.Round(val*100)/100, 'f', -1, 64)
	}
	u := strings.TrimSpace(unit)
	if u != "" {
		return numStr + " " + u
	}
	return numStr
}

func toIntVal(v interface{}) int {
	switch x := v.(type) {
	case float64:
		return int(math.Round(x))
	case int:
		return x
	case int64:
		return int(x)
	case json.Number:
		if i, err := x.Int64(); err == nil {
			return int(i)
		}
	}
	return 0
}

func toFloatVal(v interface{}) float64 {
	switch x := v.(type) {
	case float64:
		return x
	case int:
		return float64(x)
	case int64:
		return float64(x)
	}
	return 0
}

// mergeInterventionsIntoProgram embeds detected STATUS.ACT operator interventions directly into
// program[].slots[].params[].interventions (and program[].step_interventions for step jumps).
// Returns updated JSON, total intervention count across the program, and whether any new event was appended.
func mergeInterventionsIntoProgram(programRaw json.RawMessage, events []ActInterventionEvent) (json.RawMessage, int, bool) {
	if len(programRaw) == 0 || len(events) == 0 {
		return programRaw, 0, false
	}

	var steps []map[string]interface{}
	if err := json.Unmarshal(programRaw, &steps); err != nil || len(steps) == 0 {
		return programRaw, 0, false
	}

	changedAny := false

	for _, ev := range events {
		// Find target step by step["no"] == ev.StepNo
		var targetStep map[string]interface{}
		for _, st := range steps {
			if toIntVal(st["no"]) == ev.StepNo {
				targetStep = st
				break
			}
		}
		if targetStep == nil {
			continue
		}

		// Step-level intervention (jump / skip)
		if ev.Type == "STEP_JUMP_BACK" || ev.Type == "STEP_SKIP_FORWARD" {
			existingList, _ := targetStep["step_interventions"].([]interface{})
			// Deduplicate against last step intervention
			if len(existingList) > 0 {
				if last, ok := existingList[len(existingList)-1].(map[string]interface{}); ok {
					if last["type"] == ev.Type && toIntVal(last["from_step"]) == ev.FromStep && toIntVal(last["to_step"]) == ev.ToStep && last["detected_at"] == ev.DetectedAt {
						continue
					}
				}
			}
			entry := map[string]interface{}{
				"type":        ev.Type,
				"detected_at": ev.DetectedAt,
				"from_step":   ev.FromStep,
				"to_step":     ev.ToStep,
				"alarm_code":  ev.AlarmCode,
			}
			targetStep["step_interventions"] = append(existingList, entry)
			targetStep["has_intervention"] = true
			changedAny = true
			continue
		}

		// Parameter-level intervention -> match program[].slots[] & params[]
		slotsRaw, _ := targetStep["slots"].([]interface{})
		var targetSlot map[string]interface{}
		targetSlotNo := ev.Slot
		if targetSlotNo <= 0 {
			targetSlotNo = 1
		}
		for _, sObj := range slotsRaw {
			sm, ok := sObj.(map[string]interface{})
			if !ok {
				continue
			}
			if toIntVal(sm["slot"]) == targetSlotNo {
				targetSlot = sm
				break
			}
		}
		if targetSlot == nil && len(slotsRaw) > 0 {
			if sm, ok := slotsRaw[0].(map[string]interface{}); ok {
				targetSlot = sm
			}
		}
		if targetSlot == nil {
			continue
		}

		paramsRaw, _ := targetSlot["params"].([]interface{})
		var targetParam map[string]interface{}

		// 1. Prefer exact name match (case-insensitive)
		evNameLow := strings.ToLower(strings.TrimSpace(ev.ParameterName))
		if evNameLow != "" {
			for _, pObj := range paramsRaw {
				pm, ok := pObj.(map[string]interface{})
				if !ok {
					continue
				}
				pNameLow := strings.ToLower(strings.TrimSpace(fmt.Sprint(pm["name"])))
				if pNameLow == evNameLow {
					targetParam = pm
					break
				}
			}
		}
		// 2. Fallback to param_index
		if targetParam == nil && ev.ParamIndex >= 0 && ev.ParamIndex < len(paramsRaw) {
			if pm, ok := paramsRaw[ev.ParamIndex].(map[string]interface{}); ok {
				targetParam = pm
			}
		}
		if targetParam == nil {
			continue
		}

		existingIv, _ := targetParam["interventions"].([]interface{})
		// Deduplicate against last recorded intervention on this param
		if len(existingIv) > 0 {
			if last, ok := existingIv[len(existingIv)-1].(map[string]interface{}); ok {
				if math.Abs(toFloatVal(last["after"])-ev.After) < 0.01 &&
					math.Abs(toFloatVal(last["before"])-ev.Before) < 0.01 &&
					toIntVal(last["alarm_code"]) == ev.AlarmCode {
					continue
				}
			}
		}

		entry := map[string]interface{}{
			"detected_at": ev.DetectedAt,
			"before":      ev.Before,
			"after":       ev.After,
			"delta":       ev.Delta,
			"unit":        ev.Unit,
			"alarm_code":  ev.AlarmCode,
		}
		targetParam["interventions"] = append(existingIv, entry)
		targetParam["changed"] = true
		targetParam["actual_value"] = formatScadaParamValue(ev.After, ev.Unit)
		targetStep["has_intervention"] = true
		changedAny = true
	}

	if !changedAny {
		return programRaw, countProgramInterventions(steps), false
	}

	outBytes, err := json.Marshal(steps)
	if err != nil {
		return programRaw, 0, false
	}
	return json.RawMessage(outBytes), countProgramInterventions(steps), true
}

func countProgramInterventions(steps []map[string]interface{}) int {
	total := 0
	for _, st := range steps {
		if si, ok := st["step_interventions"].([]interface{}); ok {
			total += len(si)
		}
		if slots, ok := st["slots"].([]interface{}); ok {
			for _, sObj := range slots {
				if sm, ok := sObj.(map[string]interface{}); ok {
					if params, ok := sm["params"].([]interface{}); ok {
						for _, pObj := range params {
							if pm, ok := pObj.(map[string]interface{}); ok {
								if iv, ok := pm["interventions"].([]interface{}); ok {
									total += len(iv)
								}
							}
						}
					}
				}
			}
		}
	}
	return total
}

// preserveProgramInterventions copies any existing param/step interventions from existingProgramRaw
// into incomingProgramRaw so periodic IngestBatchProgram refreshes never wipe operator intervention history.
func preserveProgramInterventions(existingProgramRaw, incomingProgramRaw json.RawMessage) (json.RawMessage, int) {
	if len(existingProgramRaw) == 0 || len(incomingProgramRaw) == 0 {
		return incomingProgramRaw, 0
	}
	var existingSteps, incomingSteps []map[string]interface{}
	if err := json.Unmarshal(existingProgramRaw, &existingSteps); err != nil || len(existingSteps) == 0 {
		return incomingProgramRaw, 0
	}
	if err := json.Unmarshal(incomingProgramRaw, &incomingSteps); err != nil || len(incomingSteps) == 0 {
		return incomingProgramRaw, 0
	}

	existingByNo := make(map[int]map[string]interface{}, len(existingSteps))
	for _, st := range existingSteps {
		if no := toIntVal(st["no"]); no > 0 {
			existingByNo[no] = st
		}
	}

	mergedAny := false
	for _, incSt := range incomingSteps {
		no := toIntVal(incSt["no"])
		exSt, ok := existingByNo[no]
		if !ok {
			continue
		}
		if si, ok := exSt["step_interventions"].([]interface{}); ok && len(si) > 0 {
			incSt["step_interventions"] = si
			incSt["has_intervention"] = true
			mergedAny = true
		}

		// Index existing slots by slot number
		exSlotsRaw, _ := exSt["slots"].([]interface{})
		exSlotMap := make(map[int]map[string]interface{}, len(exSlotsRaw))
		for _, sObj := range exSlotsRaw {
			if sm, ok := sObj.(map[string]interface{}); ok {
				exSlotMap[toIntVal(sm["slot"])] = sm
			}
		}

		incSlotsRaw, _ := incSt["slots"].([]interface{})
		for _, sObj := range incSlotsRaw {
			incSlot, ok := sObj.(map[string]interface{})
			if !ok {
				continue
			}
			exSlot, ok := exSlotMap[toIntVal(incSlot["slot"])]
			if !ok {
				continue
			}
			exParamsRaw, _ := exSlot["params"].([]interface{})
			exParamByName := make(map[string]map[string]interface{}, len(exParamsRaw))
			for _, pObj := range exParamsRaw {
				if pm, ok := pObj.(map[string]interface{}); ok {
					exParamByName[strings.ToLower(strings.TrimSpace(fmt.Sprint(pm["name"])))] = pm
				}
			}

			incParamsRaw, _ := incSlot["params"].([]interface{})
			for pIdx, pObj := range incParamsRaw {
				incP, ok := pObj.(map[string]interface{})
				if !ok {
					continue
				}
				pKey := strings.ToLower(strings.TrimSpace(fmt.Sprint(incP["name"])))
				exP := exParamByName[pKey]
				if exP == nil && pIdx < len(exParamsRaw) {
					exP, _ = exParamsRaw[pIdx].(map[string]interface{})
				}
				if exP == nil {
					continue
				}
				if iv, ok := exP["interventions"].([]interface{}); ok && len(iv) > 0 {
					incP["interventions"] = iv
					incP["changed"] = true
					if av, ok := exP["actual_value"]; ok {
						incP["actual_value"] = av
					}
					incSt["has_intervention"] = true
					mergedAny = true
				}
			}
		}
	}

	totalCount := countProgramInterventions(incomingSteps)
	if !mergedAny {
		return incomingProgramRaw, totalCount
	}
	outBytes, err := json.Marshal(incomingSteps)
	if err != nil {
		return incomingProgramRaw, totalCount
	}
	return json.RawMessage(outBytes), totalCount
}

// syncScadaBatchMetaAndInterventions updates batch_process_run.payload_json with program_code/program_name
// and embeds operator intervention events directly inside program[].slots[].params[] ONLY when changes occur.
func (s *Storage) syncScadaBatchMetaAndInterventions(ctx context.Context, p StatusPayload, now time.Time) {
	aid := strings.TrimSpace(p.AssetID)
	bno := strings.TrimSpace(p.BatchNo)
	if aid == "" || bno == "" || bno == "000000" {
		return
	}

	pCode := strings.TrimSpace(p.ProgramCode)
	pName := strings.TrimSpace(p.ProgramName)
	hasIntervents := len(p.InterventionEvents) > 0

	if pCode == "" && pName == "" && !hasIntervents {
		return
	}

	var existingCode, existingName string
	var existingProgRaw []byte
	err := s.scadaPool.QueryRow(ctx, `
		SELECT COALESCE(payload_json->>'program_code', ''),
		       COALESCE(payload_json->>'program_name', ''),
		       payload_json->'program'
		FROM batch_process_run
		WHERE asset_id = $1 AND batch_no = $2
		LIMIT 1;
	`, aid, bno).Scan(&existingCode, &existingName, &existingProgRaw)
	if err != nil {
		return
	}

	patch := make(map[string]interface{})
	if pCode != "" && pCode != existingCode {
		patch["program_code"] = pCode
	}
	if pName != "" && pName != existingName {
		patch["program_name"] = pName
	}

	newInterventAdded := false
	if hasIntervents && len(existingProgRaw) > 0 {
		updatedProg, totalCount, changed := mergeInterventionsIntoProgram(json.RawMessage(existingProgRaw), p.InterventionEvents)
		if changed {
			patch["program"] = updatedProg
			patch["intervent_active"] = 1
			patch["intervention_count"] = totalCount
			newInterventAdded = true
		}
	}

	if len(patch) == 0 {
		return
	}

	patchBytes, err := json.Marshal(patch)
	if err != nil {
		return
	}

	_, err = s.scadaPool.Exec(ctx, `
		UPDATE batch_process_run
		SET payload_json = COALESCE(payload_json, '{}'::jsonb) || $3::jsonb,
		    source_updated_at = NOW(),
		    updated_at = NOW()
		WHERE asset_id = $1 AND batch_no = $2;
	`, aid, bno, patchBytes)
	if err != nil {
		s.logger.Warn("Error updating batch_process_run payload_json from STATUS.ACT", "asset", aid, "batch", bno, "error", err)
		return
	}

	if newInterventAdded {
		s.upsertScadaInterventTag(ctx, aid, 1, now)
	}
}

// upsertScadaStepTag writes live step_no from da-batch-worker into pt_smm_scada.tag_latest
// for both MACHINE.PROCESS_STEP_CODE and PROCESS.STEP_CODE, then refreshes asset_snapshot.
func (s *Storage) upsertScadaStepTag(ctx context.Context, assetID string, stepNo int, ts time.Time) {
	aid := strings.TrimSpace(assetID)
	if aid == "" || stepNo <= 0 {
		return
	}
	var assetExists bool
	_ = s.scadaPool.QueryRow(ctx, "SELECT EXISTS(SELECT 1 FROM asset WHERE asset_id = $1);", aid).Scan(&assetExists)
	if !assetExists {
		return
	}
	stepTags := []string{
		fmt.Sprintf("SMM.%s.MACHINE.PROCESS_STEP_CODE", aid),
		fmt.Sprintf("SMM.%s.PROCESS.STEP_CODE", aid),
	}
	for _, tc := range stepTags {
		_, _ = s.scadaPool.Exec(ctx, `
			INSERT INTO tag_definition (tag_code, asset_id, signal_role, engineering_unit, source_status, active, created_at, stale_after_seconds, freshness_mode, display_name)
			VALUES ($1, $2, 'PV', 'step', 'LIVE', TRUE, NOW(), 600, 'TAG_TIMESTAMP', $1)
			ON CONFLICT (tag_code) DO UPDATE SET asset_id = EXCLUDED.asset_id;
		`, tc, aid)
		_, _ = s.scadaPool.Exec(ctx, `
			INSERT INTO tag_latest (tag_code, asset_id, value_number, quality, source_ts, ingested_at, updated_at, message_id)
			VALUES ($1, $2, $3, 'GOOD', $4, NOW(), NOW(), gen_random_uuid())
			ON CONFLICT (tag_code) DO UPDATE SET
				value_number = EXCLUDED.value_number,
				quality = 'GOOD',
				source_ts = EXCLUDED.source_ts,
				ingested_at = NOW(),
				updated_at = NOW(),
				message_id = gen_random_uuid();
		`, tc, aid, float64(stepNo), ts)
	}
	_, _ = s.scadaPool.Exec(ctx, "SELECT sync_jetflow_asset_snapshot($1);", aid)
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

// IngestBatchProgram stores parsed PRG recipe steps into pt_smm_scada.batch_process_run.payload_json
// and refreshes asset_snapshot so "Tabel proses" on /process/jetflow/:assetId renders the live recipe.
func (s *Storage) IngestBatchProgram(ctx context.Context, p BatchProgramPayload) error {
	aid := strings.TrimSpace(p.AssetID)
	bno := strings.TrimSpace(p.BatchNo)
	if aid == "" || bno == "" || bno == "000000" || len(p.Program) == 0 {
		return nil
	}

	// Ensure parent production_batch and batch_process_run rows exist
	s.ensureScadaBatchAndSnapshot(ctx, aid, bno, p.ProgramNo)

	// Persist BatchInfo metadata (customer, fabric, color, order_no) into pt_smm_scada.production_batch & pt_smm_jetflow.batch_headers
	if p.BatchInfo != nil {
		bi := p.BatchInfo
		biBytes, _ := json.Marshal(bi)
		_, _ = s.scadaPool.Exec(ctx, `
			UPDATE production_batch
			SET customer_name = COALESCE(NULLIF($2, ''), customer_name),
			    fabric_type = COALESCE(NULLIF($3, ''), fabric_type),
			    external_reference = COALESCE(NULLIF($4, ''), external_reference),
			    payload_json = COALESCE(payload_json, '{}'::jsonb) || $5::jsonb,
			    source_updated_at = NOW(),
			    updated_at = NOW()
			WHERE batch_no = $1;
		`, bno, bi.CustomerName, bi.FabricType, bi.OrderNo, biBytes)

		_, _ = s.jetflowPool.Exec(ctx, `
			UPDATE batch_headers
			SET customer = COALESCE(NULLIF($2, ''), customer),
			    article = COALESCE(NULLIF($3, ''), article),
			    color_name = COALESCE(NULLIF($4, ''), color_name),
			    color_shade = COALESCE(NULLIF($4, ''), color_shade),
			    recipe_name = COALESCE(NULLIF($5, ''), recipe_name)
			WHERE batch_ref_no = $1 OR batch_no = $1;
		`, bno, bi.CustomerName, bi.FabricType, bi.ColorName, bi.ProgramName)
	}

	var progress float64
	if p.TotalSteps > 0 && p.CurrentStep > 0 {
		progress = float64(p.CurrentStep) / float64(p.TotalSteps) * 100.0
		if progress > 100.0 {
			progress = 100.0
		}
	}

	recipeCode := strings.TrimSpace(p.ProgramName)
	if recipeCode == "" {
		recipeCode = "PROGRAM " + strings.TrimSpace(p.ProgramNo)
	}

	// Preserve any STATUS.ACT operator interventions already embedded in batch_process_run.payload_json->'program'
	var existingProgRaw []byte
	_ = s.scadaPool.QueryRow(ctx, `
		SELECT payload_json->'program'
		FROM batch_process_run
		WHERE asset_id = $1 AND batch_no = $2
		LIMIT 1;
	`, aid, bno).Scan(&existingProgRaw)

	mergedProgram, preservedIvCount := preserveProgramInterventions(json.RawMessage(existingProgRaw), p.Program)
	effectiveInterventActive := p.InterventActive
	if preservedIvCount > 0 {
		effectiveInterventActive = 1
	}

	payloadObj := map[string]interface{}{
		"program":         mergedProgram,
		"program_no":      p.ProgramNo,
		"program_file":    p.ProgramFile,
		"program_source":  p.ProgramSource,
		"total_steps":     p.TotalSteps,
		"current_step":    p.CurrentStep,
		"progress_basis":  "step_ratio",
		"program_read_at": time.Now().UTC().Format(time.RFC3339),
	}
	if strings.TrimSpace(p.ProgramName) != "" {
		payloadObj["program_name"] = strings.TrimSpace(p.ProgramName)
	}
	if p.BatchInfo != nil && strings.TrimSpace(p.BatchInfo.ProgramCode) != "" {
		payloadObj["program_code"] = strings.TrimSpace(p.BatchInfo.ProgramCode)
	}
	if preservedIvCount > 0 {
		payloadObj["intervention_count"] = preservedIvCount
	}
	if len(p.OperatorTimeline) > 0 {
		payloadObj["operator_timeline"] = p.OperatorTimeline
	}
	if len(p.SetpointOverrides) > 0 {
		payloadObj["setpoint_overrides"] = p.SetpointOverrides
	}
	if len(p.BatchAlarms) > 0 {
		payloadObj["batch_alarms"] = p.BatchAlarms
	}
	if p.BatchSummary != nil {
		payloadObj["batch_summary"] = p.BatchSummary
	}
	payloadObj["intervent_active"] = effectiveInterventActive
	payloadBytes, err := json.Marshal(payloadObj)
	if err != nil {
		return err
	}

	_, err = s.scadaPool.Exec(ctx, `
		UPDATE batch_process_run
		SET recipe_code = COALESCE(NULLIF($3, ''), recipe_code),
		    progress_percent = ROUND($4::numeric, 2),
		    payload_json = COALESCE(payload_json, '{}'::jsonb) || $5::jsonb,
		    source_updated_at = NOW(),
		    updated_at = NOW()
		WHERE asset_id = $1 AND batch_no = $2;
	`, aid, bno, recipeCode, progress, payloadBytes)
	if err != nil {
		return err
	}

	// Upsert SMM.<ASSET_ID>.HMI.INTERVENT_ST (1 = ada intervensi, 0 = normal) ke pt_smm_scada
	s.upsertScadaInterventTag(ctx, aid, p.InterventActive, time.Now())

	// Persist operator interventions, PR alarms, and batch consumptions into pt_smm_jetflow
	s.persistBatchAuditToJetflow(ctx, p)

	_, _ = s.scadaPool.Exec(ctx, `
		UPDATE asset_snapshot
		SET progress_percent = ROUND($2::numeric, 2),
		    updated_at = NOW()
		WHERE asset_id = $1;
	`, aid, progress)

	if p.CurrentStep > 0 {
		s.upsertScadaStepTag(ctx, aid, p.CurrentStep, time.Now())
	} else {
		_, _ = s.scadaPool.Exec(ctx, "SELECT sync_jetflow_asset_snapshot($1);", aid)
	}
	return nil
}

// upsertScadaInterventTag writes SMM.<ASSET_ID>.HMI.INTERVENT_ST (1 or 0) into pt_smm_scada tag_definition & tag_latest.
func (s *Storage) upsertScadaInterventTag(ctx context.Context, assetID string, interventActive int, ts time.Time) {
	aid := strings.TrimSpace(assetID)
	if aid == "" {
		return
	}
	var assetExists bool
	_ = s.scadaPool.QueryRow(ctx, "SELECT EXISTS(SELECT 1 FROM asset WHERE asset_id = $1);", aid).Scan(&assetExists)
	if !assetExists {
		return
	}
	tagCode := fmt.Sprintf("SMM.%s.HMI.INTERVENT_ST", aid)
	val := 0.0
	if interventActive > 0 {
		val = 1.0
	}
	_, _ = s.scadaPool.Exec(ctx, `
		INSERT INTO tag_definition (tag_code, asset_id, signal_role, engineering_unit, source_status, active, created_at, stale_after_seconds, freshness_mode, display_name)
		VALUES ($1, $2, 'ST', '', 'LIVE', TRUE, NOW(), 600, 'TAG_TIMESTAMP', 'Intervensi HMI Operator')
		ON CONFLICT (tag_code) DO UPDATE SET asset_id = EXCLUDED.asset_id, signal_role = 'ST';
	`, tagCode, aid)
	_, _ = s.scadaPool.Exec(ctx, `
		INSERT INTO tag_latest (tag_code, asset_id, value_number, quality, source_ts, ingested_at, updated_at, message_id)
		VALUES ($1, $2, $3, 'GOOD', $4, NOW(), NOW(), gen_random_uuid())
		ON CONFLICT (tag_code) DO UPDATE SET
			value_number = EXCLUDED.value_number,
			quality = 'GOOD',
			source_ts = EXCLUDED.source_ts,
			ingested_at = NOW(),
			updated_at = NOW(),
			message_id = gen_random_uuid();
	`, tagCode, aid, val, ts)
}

// persistBatchAuditToJetflow stores PR.LOG operator interventions, alarms, and batch consumption totals idempotently.
func (s *Storage) persistBatchAuditToJetflow(ctx context.Context, p BatchProgramPayload) {
	mNo := strings.TrimSpace(p.MachineNo)
	bNo := strings.TrimSpace(p.BatchNo)
	if mNo == "" || bNo == "" {
		return
	}

	// 1. Operator interventions (pauses, manual stops, step jumps/skips, call-off waits, setpoint overrides)
	for _, ev := range p.OperatorTimeline {
		if ev.Type == "ALARM_ACTIVE" {
			continue
		}
		evTS, err := time.Parse("2006-01-02T15:04:05", ev.TS)
		if err != nil {
			evTS = time.Now()
		}
		paramName := ev.ParameterName
		if paramName == "" {
			paramName = ev.Type
		}
		unit := ev.Unit
		vBefore := ev.ValueBefore
		vAfter := ev.ValueAfter
		delta := ev.Delta
		if ev.Type == "STEP_JUMP_BACK" || ev.Type == "STEP_SKIP_FORWARD" {
			unit = "step"
			vBefore = float64(ev.FromStep)
			vAfter = float64(ev.ToStep)
			delta = vAfter - vBefore
		} else if ev.Type == "CALL_OFF_WAIT" {
			unit = "s"
			vAfter = float64(ev.WaitSec)
			delta = float64(ev.WaitSec)
		}
		rawJSON, _ := json.Marshal(ev)
		_, _ = s.jetflowPool.Exec(ctx, `
			INSERT INTO operator_interventions
			(machine_no, batch_no, step_no, timestamp, trigger_source, function_id, parameter_name, unit, value_before, value_after, delta, notes, raw_details)
			SELECT $1, $2, $3, $4, 'PR_LOG', $5, $6, $7, $8, $9, $10, $11, $12
			WHERE NOT EXISTS (
				SELECT 1 FROM operator_interventions
				WHERE machine_no = $1 AND batch_no = $2 AND timestamp = $4 AND parameter_name = $6
			);
		`, mNo, bNo, ev.StepNo, evTS, ev.FuncID, paramName, unit, vBefore, vAfter, delta, ev.Detail, string(rawJSON))
	}

	// 2. Alarms from PR.LOG evt=4
	for _, al := range p.BatchAlarms {
		alTS, err := time.Parse("2006-01-02T15:04:05", al.AlarmTimestamp)
		if err != nil {
			continue
		}
		var clearedPtr *time.Time
		if al.ClearedAt != nil && *al.ClearedAt != "" {
			if ct, err2 := time.Parse("2006-01-02T15:04:05", *al.ClearedAt); err2 == nil {
				clearedPtr = &ct
			}
		}
		_, _ = s.jetflowPool.Exec(ctx, `
			INSERT INTO datalog_alarms
			(batch_ref_no, machine_no, alarm_timestamp, alarm_code, alarm_text, step_no, operator_id, severity, cleared_at)
			SELECT $1, $2, $3, $4, $5, $6, 0, $7, $8
			WHERE NOT EXISTS (
				SELECT 1 FROM datalog_alarms
				WHERE batch_ref_no = $1 AND machine_no = $2 AND alarm_timestamp = $3 AND alarm_code = $4
			);
		`, bNo, mNo, alTS, al.AlarmCode, al.AlarmText, al.StepNo, al.Severity, clearedPtr)
	}

	// 3. Batch consumption summary from PR.LOG evt=10 (when water/steam/power totals are present)
	if p.BatchSummary != nil && (p.BatchSummary.WaterL > 0 || p.BatchSummary.SteamKg > 0 || p.BatchSummary.PowerKwh > 0) {
		rawSum, _ := json.Marshal(p.BatchSummary)
		res, err := s.jetflowPool.Exec(ctx, `
			UPDATE batch_consumptions
			SET water_liters = $3, power_kwh = $4, steam_kg = $5, recorded_at = NOW(), raw_counters = $6
			WHERE batch_ref_no = $1 AND machine_no = $2;
		`, bNo, mNo, p.BatchSummary.WaterL, p.BatchSummary.PowerKwh, p.BatchSummary.SteamKg, string(rawSum))
		if err == nil && res.RowsAffected() == 0 {
			_, _ = s.jetflowPool.Exec(ctx, `
				INSERT INTO batch_consumptions (batch_ref_no, machine_no, recorded_at, water_liters, power_kwh, steam_kg, runtime_minutes, raw_counters)
				VALUES ($1, $2, NOW(), $3, $4, $5, 0, $6);
			`, bNo, mNo, p.BatchSummary.WaterL, p.BatchSummary.PowerKwh, p.BatchSummary.SteamKg, string(rawSum))
		}
	}
}

// IngestAlarms stores parsed alarm records into datalog_alarms.
func (s *Storage) IngestAlarms(ctx context.Context, p AlarmsPayload) error {
	if len(p.Alarms) == 0 {
		return nil
	}

	query := `
		INSERT INTO datalog_alarms 
		(batch_ref_no, machine_no, alarm_timestamp, alarm_code, alarm_text, step_no, operator_id, severity, cleared_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
		ON CONFLICT DO NOTHING;
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
