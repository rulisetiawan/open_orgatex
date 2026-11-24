import psycopg2
import json

conn = psycopg2.connect("postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_scada")
cur = conn.cursor()

# 1. Update tag_latest with step 5
cur.execute("""
    INSERT INTO tag_latest (tag_code, asset_id, value_number, quality, source_ts, ingested_at, updated_at, message_id)
    VALUES ('SMM.JF-LB-10.MACHINE.PROCESS_STEP_CODE', 'JF-LB-10', 5, 'GOOD', NOW(), NOW(), NOW(), gen_random_uuid())
    ON CONFLICT (tag_code) DO UPDATE SET
        value_number = 5,
        quality = 'GOOD',
        source_ts = NOW(),
        updated_at = NOW();
""")

# 2. Trigger sync_jetflow_asset_snapshot
cur.execute("SELECT sync_jetflow_asset_snapshot('JF-LB-10');")
conn.commit()

# 3. Check asset_snapshot values
cur.execute("SELECT values_json->'step_no', updated_at FROM asset_snapshot WHERE asset_id = 'JF-LB-10';")
row = cur.fetchone()
print("Updated asset_snapshot step_no:", row)

conn.close()
