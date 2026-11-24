import psycopg2
from psycopg2.extras import RealDictCursor

try:
    conn = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow')
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name;
    """)
    tables = [t['table_name'] for t in cur.fetchall()]
    print("Tables in pt_smm_jetflow:", tables)

    for t in ['datalog_cyclic_records', 'datalog_iw_records', 'batch_headers', 'live_iw_telemetry', 'datalog_alarms']:
        if t in tables:
            cur.execute(f"SELECT COUNT(*) as count FROM {t};")
            cnt = cur.fetchone()['count']
            print(f"Count in {t}: {cnt}")

    conn.close()
except Exception as e:
    print('DB Error:', e)
