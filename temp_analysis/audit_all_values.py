import psycopg2, json

conn_j = psycopg2.connect("host=192.168.100.30 port=5433 dbname=pt_smm_jetflow user=postgres password=sensorSMM!")
cur_j = conn_j.cursor()

print("================ 1. LIVE IW TELEMETRY (NON-ZERO + KEY TAGS) ================")
cur_j.execute("""
    SELECT machine_id, asset_id, last_updated, connection_status, batch_no, program_no, step_no, telemetry_json
    FROM live_iw_telemetry
    WHERE machine_id IN ('10B', '1F')
    ORDER BY machine_id;
""")
for m_id, a_id, upd, st, bno, pno, sno, tjson in cur_j.fetchall():
    print(f"\n--- {m_id} ({a_id}) | status={st} | batch={bno!r} | prog={pno!r} | step={sno} | upd={str(upd)[:19]} ---")
    if isinstance(tjson, str):
        tjson = json.loads(tjson)
    print(f"Total tags in telemetry_json: {len(tjson)}")
    for k in sorted(tjson.keys()):
        v = tjson[k]
        val = v.get("value") if isinstance(v, dict) else v
        raw = v.get("raw") if isinstance(v, dict) else None
        unit = v.get("unit", "") if isinstance(v, dict) else ""
        # Print all non-zero OR main/key tags
        is_key = any(w in k for w in ("MAIN_TANK", "MAIN_PUMP", "MAIN_MOTOR", "PROCESS", "MACHINE.", "HMI.", "CONSUMPTION", "FABRIC"))
        if (val not in (0, 0.0, None, "")) or is_key:
            print(f"  {k:52s} | raw={str(raw):7s} | val={str(val):12s} {unit}")

conn_j.close()

print("\n================ 2. SCADA tag_latest (JF-LB-10 & JF-LF-01, NON-ZERO + KEY) ================")
conn_s = psycopg2.connect("host=192.168.100.30 port=5433 dbname=pt_smm_scada user=postgres password=sensorSMM!")
cur_s = conn_s.cursor()
cur_s.execute("""
    SELECT td.asset_id, tl.tag_code, td.signal_role, tl.value_number, tl.value_text, tl.quality, tl.source_ts
    FROM tag_latest tl
    JOIN tag_definition td ON td.tag_code = tl.tag_code
    WHERE td.asset_id IN ('JF-LB-10', 'JF-LF-01')
    ORDER BY td.asset_id, tl.tag_code;
""")
rows = cur_s.fetchall()
print(f"Total SCADA tag_latest rows for JF-LB-10 & JF-LF-01: {len(rows)}")
for a_id, tc, role, vnum, vtxt, q, ts in rows:
    is_key = any(w in tc for w in ("MAIN_TANK", "MAIN_PUMP", "MAIN_MOTOR", "PROCESS", "MACHINE.", "HMI.", "CONSUMPTION"))
    if (vnum not in (0, 0.0, None)) or (vtxt not in (None, "", "0")) or is_key:
        print(f"  [{a_id}] {tc:52s} | role={str(role):8s} | num={str(vnum):12s} | txt={str(vtxt):15s} | q={q} | ts={str(ts)[:19]}")

print("\n================ 3. SCADA asset_snapshot (JF-LB-10 & JF-LF-01) ================")
cur_s.execute("SELECT * FROM asset_snapshot WHERE asset_id IN ('JF-LB-10', 'JF-LF-01') ORDER BY asset_id;")
scols = [d[0] for d in cur_s.description]
for r in cur_s.fetchall():
    print(f"\n--- asset_snapshot: {r[0]} ---")
    for c, v in zip(scols, r):
        if v is not None:
            print(f"  {c:28s}: {v}")
conn_s.close()
