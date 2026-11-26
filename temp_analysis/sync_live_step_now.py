import psycopg2

c_jf = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow', connect_timeout=5)
cur_jf = c_jf.cursor()
cur_jf.execute("SELECT machine_no, current_batch, current_step FROM machines WHERE machine_no IN ('10B','1F')")
rows = cur_jf.fetchall()
c_jf.close()

asset_map = {"10B": "JF-LB-10", "1F": "JF-LF-01"}

c_sc = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_scada', connect_timeout=5)
cur_sc = c_sc.cursor()
for m_no, b_no, step_no in rows:
    aid = asset_map.get(m_no)
    if not aid or not step_no or step_no <= 0:
        continue
    cur_sc.execute("SELECT EXISTS(SELECT 1 FROM asset WHERE asset_id = %s)", (aid,))
    if not cur_sc.fetchone()[0]:
        continue
    for tc in (f"SMM.{aid}.MACHINE.PROCESS_STEP_CODE", f"SMM.{aid}.PROCESS.STEP_CODE"):
        cur_sc.execute("""
            INSERT INTO tag_definition (tag_code, asset_id, signal_role, engineering_unit, source_status, active, created_at, stale_after_seconds, freshness_mode, display_name)
            VALUES (%s, %s, 'PV', 'step', 'LIVE', TRUE, NOW(), 600, 'TAG_TIMESTAMP', %s)
            ON CONFLICT (tag_code) DO UPDATE SET asset_id = EXCLUDED.asset_id;
        """, (tc, aid, tc))
        cur_sc.execute("""
            INSERT INTO tag_latest (tag_code, asset_id, value_number, quality, source_ts, ingested_at, updated_at, message_id)
            VALUES (%s, %s, %s, 'GOOD', NOW(), NOW(), NOW(), gen_random_uuid())
            ON CONFLICT (tag_code) DO UPDATE SET
                value_number = EXCLUDED.value_number,
                quality = 'GOOD',
                source_ts = EXCLUDED.source_ts,
                ingested_at = NOW(),
                updated_at = NOW(),
                message_id = gen_random_uuid();
        """, (tc, aid, float(step_no)))
    cur_sc.execute("SELECT sync_jetflow_asset_snapshot(%s);", (aid,))
    print(f"Synced {m_no} ({aid}): batch={b_no}, step={step_no}")
c_sc.commit()
c_sc.close()
