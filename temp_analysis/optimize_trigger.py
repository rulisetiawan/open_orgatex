import psycopg2

sql = """
CREATE OR REPLACE FUNCTION trg_sync_asset_telemetry()
RETURNS trigger AS $$
BEGIN
  -- Hanya jalankan sync jika tag adalah metrik utama untuk menghindari deadlock saat batch update 100+ tags
  IF NEW.tag_code LIKE '%TEMPERATURE_PV' 
     OR NEW.tag_code LIKE '%LEVEL_PV' 
     OR NEW.tag_code LIKE '%PROCESS_STEP_CODE' 
     OR NEW.tag_code LIKE '%TEMPERATURE_SV' THEN
    IF NEW.asset_id LIKE 'CT-FIN%' THEN
      PERFORM sync_continuous_asset_snapshot(NEW.asset_id);
    ELSIF NEW.asset_id LIKE 'KL-%' THEN
      PERFORM sync_kalender_asset_snapshot(NEW.asset_id);
    ELSIF NEW.asset_id LIKE 'CL-%' THEN
      PERFORM sync_calator_asset_snapshot(NEW.asset_id);
    ELSIF NEW.asset_id LIKE 'JF-%' THEN
      PERFORM sync_jetflow_asset_snapshot(NEW.asset_id);
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

conn = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_scada')
cur = conn.cursor()
cur.execute(sql)
conn.commit()
conn.close()
print("Trigger trg_sync_asset_telemetry optimized successfully!")
