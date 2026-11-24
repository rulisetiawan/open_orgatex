import psycopg2
from psycopg2.extras import RealDictCursor

try:
    conn = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow')
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("SELECT * FROM datalog_cyclic_records WHERE batch_ref_no = '072162' ORDER BY log_timestamp DESC LIMIT 5;")
    rows = cur.fetchall()
    print("Latest 5 records in datalog_cyclic_records for 072162:")
    for r in rows:
        print(dict(r))

    conn.close()
except Exception as e:
    print('DB Error:', e)
