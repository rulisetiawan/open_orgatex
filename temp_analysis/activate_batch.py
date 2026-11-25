import psycopg2
import json
import uuid

conn = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_scada')
cur = conn.cursor()

# Insert active batch 072453
run_id = str(uuid.uuid4())
payload = {
    'program_file': 'PKO838.PRG',
    'program_no': 4,
    'program_code': 'PKO838',
    'program_name': 'TOP VINYL MD F',
    'program_source': 'CONTROLLER_FTP'
}

cur.execute('''
    INSERT INTO batch_process_run 
    (process_run_id, batch_no, asset_id, run_status, started_at, updated_at, recipe_code, payload_json)
    VALUES (%s, %s, %s, 'RUNNING', NOW() - interval '45 minutes', NOW(), %s, %s);
''', (run_id, '072453', 'JF-LB-10', 'TOP VINYL MD F', json.dumps(payload)))

# Update tag_latest with step 4
cur.execute('''
    INSERT INTO tag_latest (tag_code, asset_id, value_number, quality, source_ts, ingested_at, updated_at, message_id)
    VALUES ('SMM.JF-LB-10.MACHINE.PROCESS_STEP_CODE', 'JF-LB-10', 4, 'GOOD', NOW(), NOW(), NOW(), gen_random_uuid())
    ON CONFLICT (tag_code) DO UPDATE SET value_number = 4, updated_at = NOW();
''')

# Update asset_snapshot batch_no
cur.execute('''
    UPDATE asset_snapshot 
    SET batch_no = '072453', machine_state = 'running', updated_at = NOW() 
    WHERE asset_id = 'JF-LB-10';
''')

# Run sync_jetflow_asset_snapshot
cur.execute("SELECT sync_jetflow_asset_snapshot('JF-LB-10');")

conn.commit()
print('Batch 072453 activated and synced successfully!')
conn.close()
