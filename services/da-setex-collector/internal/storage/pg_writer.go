package storage

import (
	"context"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log/slog"
	"time"

	"da-setex-collector/internal/setex"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type PGWriter struct {
	jetflowPool *pgxpool.Pool
	scadaPool   *pgxpool.Pool
	logger      *slog.Logger
}

type TagValueRecord struct {
	TagName   string
	Value     float64
	Raw       uint16
	Unit      string
	Role      string
	Quality   int
	Timestamp time.Time
}

func NewPGWriter(ctx context.Context, jetflowURL, scadaURL string, maxConns, minConns int32, logger *slog.Logger) (*PGWriter, error) {
	// Configure Jetflow pool
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

	// Configure SCADA pool
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

	return &PGWriter{
		jetflowPool: jfPool,
		scadaPool:   scadaPool,
		logger:      logger,
	}, nil
}

// WriteLiveTelemetry updates live_iw_telemetry in pt_smm_jetflow and tag_latest in pt_smm_scada.
func (w *PGWriter) WriteLiveTelemetry(
	ctx context.Context,
	machineID, assetID string,
	batchNo string, stepNo int, programNo string,
	rawFrame []byte,
	telemetryMap map[string]interface{},
	tagRecords []TagValueRecord,
	currentTemp float64,
) error {
	now := time.Now()
	rawHex := ""
	if len(rawFrame) > 0 {
		rawHex = hex.EncodeToString(rawFrame)
	}

	telemetryBytes, err := json.Marshal(telemetryMap)
	if err != nil {
		return fmt.Errorf("marshal telemetry map: %w", err)
	}

	// 1. Upsert live_iw_telemetry in pt_smm_jetflow
	queryJetflow := `
		INSERT INTO live_iw_telemetry 
		(machine_id, asset_id, last_updated, connection_status, batch_no, step_no, program_no, raw_buffer_hex, telemetry_json)
		VALUES ($1, $2, $3, 'ONLINE', $4, $5, $6, $7, $8)
		ON CONFLICT (machine_id) DO UPDATE SET
			last_updated = EXCLUDED.last_updated,
			connection_status = 'ONLINE',
			batch_no = EXCLUDED.batch_no,
			step_no = EXCLUDED.step_no,
			program_no = EXCLUDED.program_no,
			raw_buffer_hex = EXCLUDED.raw_buffer_hex,
			telemetry_json = EXCLUDED.telemetry_json;
	`
	_, err = w.jetflowPool.Exec(ctx, queryJetflow, machineID, assetID, now, batchNo, stepNo, programNo, rawHex, telemetryBytes)
	if err != nil {
		w.logger.Error("Error upserting live_iw_telemetry", "machine", machineID, "error", err)
	}

	// 2. Update machine status & temperature in pt_smm_jetflow.machines
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
		_, _ = w.jetflowPool.Exec(ctx, queryMachine, currentTemp, batchNo, stepNo, now, machineID)
	}

	// 3. Batch upsert into pt_smm_scada.tag_latest
	if len(tagRecords) > 0 {
		batch := &pgx.Batch{}
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
		for _, tr := range tagRecords {
			batch.Queue(queryScada, tr.TagName, assetID, tr.Value, tr.Timestamp)
		}

		br := w.scadaPool.SendBatch(ctx, batch)
		if err := br.Close(); err != nil {
			w.logger.Warn("Error batch updating tag_latest in pt_smm_scada", "error", err)
		}
	}

	// 4. Batch insert into pt_smm_jetflow.datalog_iw_records (Historical Hypertable)
	if len(tagRecords) > 0 {
		batchJf := &pgx.Batch{}
		queryDatalog := `
			INSERT INTO datalog_iw_records (time, machine_id, asset_id, batch_no, step_no, tag_name, value, raw_value, quality)
			VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9);
		`
		for _, tr := range tagRecords {
			batchJf.Queue(queryDatalog, tr.Timestamp, machineID, assetID, batchNo, stepNo, tr.TagName, tr.Value, int(tr.Raw), tr.Quality)
		}
		brJf := w.jetflowPool.SendBatch(ctx, batchJf)
		if err := brJf.Close(); err != nil {
			w.logger.Debug("Error inserting datalog_iw_records", "error", err)
		}
	}

	return nil
}

// LoadMachineTagMappings loads active register tag mappings from public.cfg_machine_iw_tag_mapping.
func (w *PGWriter) LoadMachineTagMappings(ctx context.Context, machineID string) (map[int]*setex.RegisterMapping, error) {
	query := `
		SELECT register_index, iw_number, tag_name, tag_role, field_name, COALESCE(unit, ''),
		       raw_min, raw_max, eng_min, eng_max, scale_factor, COALESCE(notes, '')
		FROM cfg_machine_iw_tag_mapping
		WHERE machine_id = $1 AND is_active = TRUE
		ORDER BY register_index ASC;
	`
	rows, err := w.jetflowPool.Query(ctx, query, machineID)
	if err != nil {
		return nil, fmt.Errorf("query cfg_machine_iw_tag_mapping: %w", err)
	}
	defer rows.Close()

	result := make(map[int]*setex.RegisterMapping)
	for rows.Next() {
		var (
			regIdx  int
			iwNum   int
			tagName string
			tagRole string
			field   string
			unit    string
			rawMin  float64
			rawMax  float64
			engMin  float64
			engMax  float64
			factor  float64
			notes   string
		)
		if err := rows.Scan(&regIdx, &iwNum, &tagName, &tagRole, &field, &unit, &rawMin, &rawMax, &engMin, &engMax, &factor, &notes); err != nil {
			return nil, fmt.Errorf("scan tag mapping: %w", err)
		}

		result[regIdx] = &setex.RegisterMapping{
			Index:        regIdx,
			IWNumber:     iwNum,
			Name:         notes,
			Unit:         unit,
			DigitsBefore: 3,
			DigitsAfter:  1,
			X1:           engMin,
			X2:           engMax,
			Y1:           rawMin,
			Y2:           rawMax,
			Factor:       factor,
			TagName:      tagName,
			TagRole:      tagRole,
			FieldName:    field,
		}
	}

	return result, nil
}

func (w *PGWriter) Close() {
	if w.jetflowPool != nil {
		w.jetflowPool.Close()
	}
	if w.scadaPool != nil {
		w.scadaPool.Close()
	}
}
