CREATE OR REPLACE FUNCTION public.sync_jetflow_asset_snapshot(target_asset_id text)
 RETURNS void
 LANGUAGE plpgsql
AS $function$
DECLARE
  v_source_ts TIMESTAMPTZ;
  v_values JSONB;
  v_run JSONB;
BEGIN
  SELECT
    MAX(source_ts),
    jsonb_object_agg(metric_key, metric_val) FILTER (WHERE metric_key IS NOT NULL)
  INTO v_source_ts, v_values
  FROM (
    SELECT
      source_ts,
      CASE substring(tag_code FROM length('SMM.' || target_asset_id || '.') + 1)
        WHEN 'MAIN_TANK.TEMPERATURE_PV' THEN 'main_temp'
        WHEN 'MAIN_TANK.TEMPERATURE_SV' THEN 'main_temp_sp'
        WHEN 'MAIN_TANK.LEVEL_PV' THEN 'main_level'
        WHEN 'MAIN_TANK.LEVEL_SV' THEN 'main_level_sp'
        WHEN 'MACHINE.PROCESS_STEP_CODE' THEN 'step_no'
        WHEN 'DOSING_TANK_01.TEMPERATURE_PV' THEN 'dosing_tank_1_temp'
        WHEN 'DOSING_TANK_01.LEVEL_PV' THEN 'dosing_tank_1_level'
        WHEN 'DOSING_TANK_02.TEMPERATURE_PV' THEN 'dosing_tank_2_temp'
        WHEN 'DOSING_TANK_02.LEVEL_PV' THEN 'dosing_tank_2_level'
        WHEN 'WATER_INLET.FLOW_PV' THEN 'water_flow'
        WHEN 'WATER_INLET.FLOW_TOTAL' THEN 'total_water_m3'
        WHEN 'PRODUCTION.OUTPUT_TOTAL_M' THEN 'output_total_m'
        ELSE NULL
      END AS metric_key,
      CASE WHEN value_number IS NOT NULL THEN to_jsonb(value_number) ELSE to_jsonb(value_text) END AS metric_val
    FROM tag_latest
    WHERE asset_id = target_asset_id
      AND tag_code LIKE 'SMM.' || target_asset_id || '.%'
      AND upper(COALESCE(quality, 'GOOD')) = 'GOOD'
  ) mapped;

  IF v_source_ts IS NULL OR v_values IS NULL THEN
    RETURN;
  END IF;

  -- Program asli batch yang sedang berjalan (dibaca dari controller oleh pengirim, disimpan di
  -- payload_json run). Tanpa program, tabel proses menampilkan "belum terkoneksi", bukan resep contoh.
  SELECT jsonb_strip_nulls(jsonb_build_object(
           'program', run.payload_json -> 'program',
           'program_no', run.payload_json -> 'program_no',
           'program_file', run.payload_json -> 'program_file',
           'program_source', run.payload_json -> 'program_source',
           'run_started_at', to_jsonb(run.started_at)))
    INTO v_run
  FROM batch_process_run run
  WHERE run.asset_id = target_asset_id AND run.run_status IN ('RUNNING', 'HOLD')
  ORDER BY run.source_updated_at DESC NULLS LAST, run.updated_at DESC
  LIMIT 1;
  v_values := v_values || COALESCE(v_run, '{}'::jsonb);

  INSERT INTO asset_snapshot (asset_id, machine_state, batch_no, progress_percent, connected, source_ts, quality, values_json, updated_at)
  VALUES (target_asset_id, 'idle', chr(8212), 0, TRUE, v_source_ts, 'GOOD', v_values, clock_timestamp())
  ON CONFLICT (asset_id) DO UPDATE SET
    -- Kunci program lama dibuang dulu supaya batch berikutnya tidak mewarisi program batch sebelumnya.
    values_json = (COALESCE(asset_snapshot.values_json, '{}'::jsonb)
                   - 'program' - 'program_no' - 'program_file' - 'program_source' - 'run_started_at') || EXCLUDED.values_json,
    source_ts = GREATEST(asset_snapshot.source_ts, EXCLUDED.source_ts),
    updated_at = EXCLUDED.updated_at;
END;
$function$
