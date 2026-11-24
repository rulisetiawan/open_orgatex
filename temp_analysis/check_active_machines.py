import psycopg2
from psycopg2.extras import RealDictCursor

try:
    conn = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow')
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT machine_no, display_name, ip_address, ftp_port, tcp_port, is_active FROM machines WHERE is_active = TRUE;")
    active_m = cur.fetchall()
    print(f"Active machines: {len(active_m)}")
    for m in active_m:
        print(dict(m))
    conn.close()
except Exception as e:
    print('DB Error:', e)
