import psycopg2
import json

conn = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_scada')
cur = conn.cursor()

cur.execute("SELECT process_run_id, batch_no, asset_id, payload_json FROM batch_process_run WHERE asset_id = 'JF-LB-10';")
row = cur.fetchone()
if row:
    payload = row[3]
    print("Keys in payload_json:", list(payload.keys()))
    print("program_file:", payload.get("program_file"))
    print("program_source:", payload.get("program_source"))
    print("program_no:", payload.get("program_no"))
    prog = payload.get("program", [])
    print(f"Total steps in payload['program']: {len(prog)}")
    for s in prog[:8]:
        print(f"  Step {s.get('no')}: {s.get('step')} | sv={s.get('sv')} | min={s.get('min')}")

conn.close()
