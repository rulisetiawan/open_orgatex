import psycopg2, json

c1 = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow', connect_timeout=5)
cur1 = c1.cursor()
cur1.execute("SELECT machine_id, asset_id, last_updated, connection_status, batch_no, step_no, jsonb_object_keys(telemetry_json) FROM live_iw_telemetry WHERE machine_id IN ('10B','1F') LIMIT 5")
cur1.execute("SELECT machine_id, asset_id, last_updated, connection_status, batch_no, step_no, (SELECT count(*) FROM jsonb_object_keys(telemetry_json)) AS tag_cnt, telemetry_json->'SMM.JF-LB-10.MAIN_TANK.TEMPERATURE_PV' AS t10b, telemetry_json->'SMM.JF-LF-01.MAIN_TANK.TEMPERATURE_PV' AS t1f FROM live_iw_telemetry WHERE machine_id IN ('10B','1F')")
print("=== pt_smm_jetflow.live_iw_telemetry ===")
for r in cur1.fetchall():
    print(" ", r)
c1.close()

c2 = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_scada', connect_timeout=5)
cur2 = c2.cursor()
cur2.execute("SELECT asset_id, COUNT(*), MAX(source_ts), MAX(updated_at) FROM tag_latest WHERE asset_id IN ('JF-LB-10','JF-LF-01') GROUP BY asset_id")
print("=== pt_smm_scada.tag_latest summary ===")
for r in cur2.fetchall():
    print(" ", r)
c2.close()
