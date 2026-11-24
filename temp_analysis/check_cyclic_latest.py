import psycopg2
from psycopg2.extras import RealDictCursor

try:
    conn = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow')
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("SELECT MAX(log_timestamp) as latest_ts, COUNT(*) as cnt FROM datalog_cyclic_records WHERE batch_ref_no = '072162';")
    print("datalog_cyclic_records for 072162:", cur.fetchone())

    cur.execute("SELECT MAX(log_timestamp) as latest_overall FROM datalog_cyclic_records;")
    print("datalog_cyclic_records latest overall:", cur.fetchone())

    conn.close()
except Exception as e:
    print('DB Error:', e)
