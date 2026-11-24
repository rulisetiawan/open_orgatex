import psycopg2
from psycopg2.extras import RealDictCursor

try:
    conn = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow')
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT MAX(time) as max_time_iw, COUNT(*) as cnt_iw FROM datalog_iw_records WHERE batch_no = '072162';")
    print("datalog_iw_records for 072162:", cur.fetchone())

    cur.execute("SELECT MAX(timestamp) as max_time_cyc, COUNT(*) as cnt_cyc FROM datalog_cyclic_records WHERE batch_no = '072162';")
    print("datalog_cyclic_records for 072162:", cur.fetchone())

    cur.execute("SELECT MAX(timestamp) as max_time_cyc_all FROM datalog_cyclic_records;")
    print("datalog_cyclic_records latest overall:", cur.fetchone())

    conn.close()
except Exception as e:
    print('DB Error:', e)
