import psycopg2
from psycopg2.extras import RealDictCursor

try:
    conn = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow')
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'datalog_cyclic_records';
    """)
    cols = cur.fetchall()
    print("Columns in datalog_cyclic_records:")
    for c in cols:
        print(f"  {c['column_name']} ({c['data_type']})")

    cur.execute("SELECT * FROM datalog_cyclic_records ORDER BY time DESC LIMIT 3;")
    print("\nLatest rows in datalog_cyclic_records:")
    for r in cur.fetchall():
        print(dict(r))

    conn.close()
except Exception as e:
    print('DB Error:', e)
