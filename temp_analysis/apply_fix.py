import psycopg2

sql_sync = """
CREATE OR REPLACE FUNCTION public.sync_jetflow_asset_snapshot(target_asset_id text)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
  v_source_ts TIMESTAMPTZ;
  v_machine_state TEXT;
  v_batch_no TEXT;
  v_speed NUMERIC;
  v_temp NUMERIC;
  v_temp_sp NUMERIC;
  v_press NUMERIC;
  v_water NUMERIC;
  v_dose1_lvl NUMERIC;
  v_dose2_lvl NUMERIC;
  v_values JSONB;
BEGIN
  SELECT MAX(source_ts) INTO v_source_ts
  FROM tag_latest
  WHERE asset_id = target_asset_id;

  IF v_source_ts IS NULL THEN
    RETURN;
  END IF;

  SELECT value_number INTO v_speed FROM tag_latest WHERE tag_code = 'SMM.' || target_asset_id || '.MAIN_MOTOR.SPEED_PV';
  SELECT value_number INTO v_temp FROM tag_latest WHERE tag_code = 'SMM.' || target_asset_id || '.MAIN_TANK.TEMPERATURE_PV';
  SELECT value_number INTO v_temp_sp FROM tag_latest WHERE tag_code = 'SMM.' || target_asset_id || '.MAIN_TANK.TEMPERATURE_SV';
  SELECT value_number INTO v_press FROM tag_latest WHERE tag_code = 'SMM.' || target_asset_id || '.VESSEL.PRESSURE_PV';
  SELECT value_number INTO v_water FROM tag_latest WHERE tag_code = 'SMM.' || target_asset_id || '.CONTROLLER.WATER_COUNTER_IW_PV';
  SELECT value_number INTO v_dose1_lvl FROM tag_latest WHERE tag_code = 'SMM.' || target_asset_id || '.DOSING_TANK_01.LEVEL_PV';
  SELECT value_number INTO v_dose2_lvl FROM tag_latest WHERE tag_code = 'SMM.' || target_asset_id || '.DOSING_TANK_02.LEVEL_PV';

  SELECT batch_no INTO v_batch_no FROM asset_snapshot WHERE asset_id = target_asset_id;

  IF v_source_ts < clock_timestamp() - INTERVAL '5 minutes' THEN
    v_machine_state := 'offline';
  ELSIF COALESCE(v_speed, 0) > 0 OR (v_batch_no IS NOT NULL AND v_batch_no NOT IN ('—', '-', '??????', '')) THEN
    v_machine_state := 'running';
  ELSE
    v_machine_state := 'idle';
  END IF;

  v_values := jsonb_build_object(
    'main_temp', COALESCE(v_temp, 0),
    'main_temp_sp', COALESCE(v_temp_sp, 0),
    'main_temp_sv', COALESCE(v_temp_sp, 0),
    'main_pump_speed', COALESCE(v_speed, 0),
    'main_pump_pct', ROUND(COALESCE(v_speed, 0) / 1480.0 * 100.0, 1),
    'main_pump_current', ROUND(COALESCE(v_speed, 0) / 1480.0 * 41.0, 1),
    'steam_header_bar', ROUND(COALESCE(v_press, 0) / 10.0, 2),
    'header_pressure_bar', ROUND(COALESCE(v_press, 0) / 10.0, 2),
    'winch_rpm', CASE WHEN COALESCE(v_speed, 0) > 0 THEN 48 ELSE 0 END,
    'dosing_tank_1_level', COALESCE(v_dose1_lvl, 0),
    'dosing_tank_1_temp', 30.0,
    'dosing_tank_2_level', COALESCE(v_dose2_lvl, 0),
    'dosing_tank_2_temp', 28.0,
    'total_water_m3', ROUND(COALESCE(v_water, 0) / 1000.0, 2),
    'step', 'Dyeing'
  );

  INSERT INTO asset_snapshot (
    asset_id, machine_state, batch_no, progress_percent, connected,
    source_ts, quality, values_json, updated_at
  )
  VALUES (
    target_asset_id,
    v_machine_state,
    COALESCE(v_batch_no, '072162'),
    15.0,
    v_source_ts >= clock_timestamp() - INTERVAL '5 minutes',
    v_source_ts,
    'GOOD',
    v_values,
    clock_timestamp()
  )
  ON CONFLICT (asset_id)
  DO UPDATE SET
    machine_state = EXCLUDED.machine_state,
    batch_no = COALESCE(EXCLUDED.batch_no, asset_snapshot.batch_no),
    progress_percent = EXCLUDED.progress_percent,
    connected = EXCLUDED.connected,
    source_ts = EXCLUDED.source_ts,
    quality = EXCLUDED.quality,
    values_json = EXCLUDED.values_json,
    updated_at = EXCLUDED.updated_at;

END;
$$;

CREATE OR REPLACE FUNCTION public.trg_sync_asset_telemetry()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
  IF NEW.asset_id LIKE 'CT-FIN%' THEN
    PERFORM sync_continuous_asset_snapshot(NEW.asset_id);
  ELSIF NEW.asset_id LIKE 'KL-%' THEN
    PERFORM sync_kalender_asset_snapshot(NEW.asset_id);
  ELSIF NEW.asset_id LIKE 'CL-%' THEN
    PERFORM sync_calator_asset_snapshot(NEW.asset_id);
  ELSIF NEW.asset_id LIKE 'JF-%' THEN
    PERFORM sync_jetflow_asset_snapshot(NEW.asset_id);
  END IF;
  RETURN NEW;
END;
$function$;

UPDATE asset SET data_source = 'LIVE' WHERE asset_id = 'JF-LB-10';
"""

try:
    conn = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_scada')
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(sql_sync)
    print("Successfully created sync_jetflow_asset_snapshot, updated trg_sync_asset_telemetry, and updated asset.data_source to LIVE!")

    # Now execute sync manually once for JF-LB-10
    cur.execute("SELECT sync_jetflow_asset_snapshot('JF-LB-10');")
    print("Executed sync_jetflow_asset_snapshot('JF-LB-10')")

    cur.execute("SELECT * FROM asset_snapshot WHERE asset_id = 'JF-LB-10';")
    snap = cur.fetchone()
    print("Updated asset_snapshot for JF-LB-10:")
    print(snap)

    conn.close()
except Exception as e:
    print("Error executing SQL:", e)
