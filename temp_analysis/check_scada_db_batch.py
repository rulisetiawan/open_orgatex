import psycopg2

conn = psycopg2.connect("postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_scada")
cur = conn.cursor()

# Check table structure of asset_snapshot
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'asset_snapshot'")
print("Columns in asset_snapshot:", [r[0] for r in cur.fetchall()])

cur.execute("SELECT * FROM asset_snapshot WHERE asset_id = 'JF-LB-10'")
snap = cur.fetchone()
print("\nasset_snapshot for JF-LB-10:")
print(snap)

# Check telemetry_sample or tag_latest for batch / step
cur.execute("SELECT tag_code, value_number, value_text, updated_at FROM tag_latest WHERE asset_id = 'JF-LB-10' AND (tag_code LIKE '%BATCH%' OR tag_code LIKE '%STEP%' OR tag_code LIKE '%PROGRAM%')")
for r in cur.fetchall():
    print("  Tag:", r)

conn.close()
