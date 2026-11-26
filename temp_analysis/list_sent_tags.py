import psycopg2

conn = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow', connect_timeout=5)
cur = conn.cursor()
cur.execute("SELECT machine_id, asset_id, telemetry_json FROM live_iw_telemetry WHERE machine_id IN ('10B','1F') ORDER BY machine_id")
rows = cur.fetchall()
conn.close()

for m_id, a_id, tj in rows:
    print(f"================ {m_id} ({a_id}) - TOTAL {len(tj)} TAGS ================")
    for k in sorted(tj.keys()):
        v = tj[k]
        print(f"  {k:<55} | role={str(v.get('role','')):<9} | val={v.get('value')} {v.get('unit','')}")
