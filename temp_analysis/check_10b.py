import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow')
cur = conn.cursor(cursor_factory=RealDictCursor)
cur.execute("SELECT machine_no, display_name, controller_type, share_folder_path FROM machines WHERE machine_no = '10B';")
print(dict(cur.fetchone()))
conn.close()
