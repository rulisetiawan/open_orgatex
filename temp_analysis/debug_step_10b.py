import psycopg2

c1 = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_scada', connect_timeout=5)
cur1 = c1.cursor()
cur1.execute("SELECT tag_code, value_number, source_ts, updated_at FROM tag_latest WHERE asset_id='JF-LB-10' AND tag_code LIKE '%STEP%'")
print("=== pt_smm_scada.tag_latest (STEP) ===")
for r in cur1.fetchall(): print(" ", r)

cur1.execute("SELECT batch_no, machine_state, updated_at, values_json->>'step_no', values_json->>'program_file', values_json->>'program_no' FROM asset_snapshot WHERE asset_id='JF-LB-10'")
print("=== pt_smm_scada.asset_snapshot ===")
for r in cur1.fetchall(): print(" ", r)

cur1.execute("SELECT batch_no, run_status, recipe_code, started_at, updated_at, payload_json->>'program_file' FROM batch_process_run WHERE asset_id='JF-LB-10' ORDER BY updated_at DESC LIMIT 3")
print("=== pt_smm_scada.batch_process_run ===")
for r in cur1.fetchall(): print(" ", r)
c1.close()

c2 = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow', connect_timeout=5)
cur2 = c2.cursor()
cur2.execute("SELECT machine_id, batch_no, step_no, program_no, last_updated FROM live_iw_telemetry WHERE machine_id IN ('10B','1F')")
print("=== pt_smm_jetflow.live_iw_telemetry ===")
for r in cur2.fetchall(): print(" ", r)

cur2.execute("SELECT machine_no, current_batch, current_step, last_ping_time FROM machines WHERE machine_no IN ('10B','1F')")
print("=== pt_smm_jetflow.machines ===")
for r in cur2.fetchall(): print(" ", r)
c2.close()
