import psycopg2
from psycopg2.extras import RealDictCursor

try:
    conn = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_scada')
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM batch_process_run WHERE asset_id = 'JF-LB-10' ORDER BY started_at DESC LIMIT 5;")
    runs = cur.fetchall()
    print(f"batch_process_run for JF-LB-10: {len(runs)}")
    for r in runs:
        print(dict(r))
    conn.close()
except Exception as e:
    print('DB Error:', e)
