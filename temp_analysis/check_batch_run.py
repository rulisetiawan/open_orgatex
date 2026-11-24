import psycopg2

conn = psycopg2.connect("postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_scada")
cur = conn.cursor()

cur.execute("SELECT process_run_id, batch_no, asset_id, run_status, started_at, updated_at FROM batch_process_run WHERE asset_id = 'JF-LB-10' ORDER BY updated_at DESC LIMIT 5;")
for r in cur.fetchall():
    print(r)

conn.close()
