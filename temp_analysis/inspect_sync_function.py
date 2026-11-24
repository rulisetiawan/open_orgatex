import psycopg2

conn = psycopg2.connect("postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_scada")
cur = conn.cursor()

cur.execute("""
    SELECT pg_get_functiondef(oid) 
    FROM pg_proc 
    WHERE proname = 'sync_jetflow_asset_snapshot';
""")
row = cur.fetchone()
if row:
    print(row[0])
else:
    print("Function sync_jetflow_asset_snapshot not found!")

conn.close()
