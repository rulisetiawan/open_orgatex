import psycopg2
import json

conn = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_scada')
cur = conn.cursor()

# 1. Check asset table
cur.execute("SELECT asset_id, process_type, display_name, data_source FROM asset WHERE asset_id = 'JF-LB-10';")
print('Asset row:', cur.fetchone())

# 2. Check asset_snapshot table
cur.execute("SELECT asset_id, machine_state, batch_no, connected, values_json, updated_at FROM asset_snapshot WHERE asset_id = 'JF-LB-10';")
row = cur.fetchone()
if row:
    print('Snapshot row:', row[0], row[1], row[2], row[3], row[5])
    v = row[4] or {}
    print('Values JSON keys:', list(v.keys()))
    print('Sample values:', {k: v[k] for k in list(v.keys())[:10]})
    if 'program' in v:
        prog = v['program']
        print(f"Program found in values_json! Total steps: {len(prog)}")
        for s in prog[:5]:
            print("  Step:", s.get('no'), s.get('step'), "SV:", s.get('sv'), "Min:", s.get('min'))
    else:
        print("Program key NOT in values_json")

# 3. Check batch_process_run table
cur.execute("SELECT process_run_id, batch_no, run_status, payload_json FROM batch_process_run WHERE asset_id = 'JF-LB-10' ORDER BY updated_at DESC LIMIT 1;")
run_row = cur.fetchone()
if run_row:
    print('Active batch_process_run:', run_row[0], run_row[1], run_row[2])
    p_json = run_row[3] or {}
    print('Has program in payload_json?', 'program' in p_json)
    if 'program' in p_json:
        prog = p_json['program']
        print(f"Program has {len(prog)} steps! Sample step 1:", prog[0] if prog else None)
else:
    print('No batch_process_run found for JF-LB-10')

conn.close()
