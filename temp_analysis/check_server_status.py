import psycopg2
import requests
import json
from datetime import datetime

print("=== 1. CHECK API SCADA (http://192.168.100.30:8788) ===")
try:
    r = requests.get("http://192.168.100.30:8788/api/v1/assets?process=jetflow", timeout=5)
    data = r.json()
    assets = data.get("assets", [])
    m10b = next((a for a in assets if a.get("id") == "JF-LB-10"), None)
    if m10b:
        vals = m10b.get("values", {})
        prog = vals.get("program", [])
        print(f"[API OK] JF-LB-10:")
        print(f"  - State: {m10b.get('state')}")
        print(f"  - Batch: {m10b.get('batch')}")
        print(f"  - Temp PV: {vals.get('main_temp')} C")
        print(f"  - Temp SP: {vals.get('main_temp_sp')} C")
        print(f"  - Step No: {vals.get('step_no')}")
        print(f"  - Total Program Steps: {len(prog)}")
        if prog:
            active_step = next((s for s in prog if s.get("status") == "running" or s.get("step_no") == vals.get("step_no")), None)
            print(f"  - Active Step Details: {active_step}")
    else:
        print("[API WARN] JF-LB-10 not found in assets list")
except Exception as e:
    print(f"[API ERR] {e}")

print("\n=== 2. CHECK DATABASE pt_smm_scada (192.168.100.30:5433) ===")
try:
    conn = psycopg2.connect("postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_scada")
    cur = conn.cursor()
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'tag_latest';
    """)
    cols = cur.fetchall()
    print("Columns in tag_latest:", [c[0] for c in cols])
    
    cur.execute("""
        SELECT tag_code, value_number, value_text, source_ts, updated_at 
        FROM tag_latest 
        WHERE asset_id = 'JF-LB-10' 
        ORDER BY updated_at DESC LIMIT 8;
    """)
    rows = cur.fetchall()
    print("Latest tags in tag_latest for JF-LB-10:")
    for r in rows:
        print(f"  {r[0]}: val_num={r[1]}, val_text={r[2]}, source_ts={r[3]}, updated_at={r[4]}")
    
    cur.execute("SELECT count(*) FROM tag_latest WHERE asset_id = 'JF-LB-10'")
    total_tags = cur.fetchone()[0]
    print(f"Total active tags registered in tag_latest: {total_tags}")

    cur.execute("""
        SELECT state, connected, active_batch_code, active_step_no, updated_at 
        FROM asset_snapshot 
        WHERE asset_id = 'JF-LB-10'
    """)
    snap = cur.fetchone()
    if snap:
        print(f"asset_snapshot: state={snap[0]}, connected={snap[1]}, batch={snap[2]}, step={snap[3]}, updated_at={snap[4]}")
    conn.close()
except Exception as e:
    print(f"[DB SCADA ERR] {e}")

print("\n=== 3. CHECK DATABASE pt_smm_jetflow (192.168.100.30:5433) ===")
try:
    conn = psycopg2.connect("postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow")
    cur = conn.cursor()
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'live_iw_telemetry';
    """)
    cols = cur.fetchall()
    print("Columns in live_iw_telemetry:", [c[0] for c in cols])

    cur.execute("SELECT * FROM live_iw_telemetry WHERE machine_id = '10B' ORDER BY 2 DESC LIMIT 1;")
    row = cur.fetchone()
    print("Latest live_iw_telemetry:", row[:10] if row else "None")

    cur.execute("SELECT count(*) FROM datalog_iw_records WHERE machine_id = '10B'")
    cnt = cur.fetchone()[0]
    print(f"Total datalog_iw_records for 10B: {cnt}")
    conn.close()
except Exception as e:
    print(f"[DB JETFLOW ERR] {e}")
