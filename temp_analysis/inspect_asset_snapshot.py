import psycopg2

conn = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_scada')
cur = conn.cursor()
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'asset_snapshot';")
cols = [r[0] for r in cur.fetchall()]
print("Columns in asset_snapshot:", cols)

cur.execute("SELECT * FROM asset_snapshot WHERE asset_id = 'JF-LB-10';")
row = cur.fetchone()
print("Data JF-LB-10:")
for c, val in zip(cols, row):
    if val is not None:
        print(f"  {c}: {val}")

conn.close()
