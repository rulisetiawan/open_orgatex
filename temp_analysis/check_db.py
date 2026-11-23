import psycopg2
from psycopg2.extras import RealDictCursor

try:
    conn = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_scada')
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT * FROM asset_communication_state WHERE asset_id = 'JF-LB-10';")
    print("asset_communication_state:", cur.fetchall())

    cur.execute("SELECT asset_id, data_source FROM asset WHERE asset_id = 'JF-LB-10';")
    print("asset:", cur.fetchall())

    conn.close()
except Exception as e:
    print('DB Error:', e)
