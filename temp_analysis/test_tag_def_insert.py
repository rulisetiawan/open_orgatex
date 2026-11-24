import psycopg2

conn = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_scada')
cur = conn.cursor()
try:
    sql = """
        INSERT INTO tag_definition (tag_code, asset_id, signal_role, engineering_unit, source_status, active, created_at, stale_after_seconds, freshness_mode, display_name)
        VALUES ('SMM.JF-LB-10.MAIN_TANK.TEMPERATURE_SV', 'JF-LB-10', 'SV', '°C', 'LIVE', TRUE, NOW(), 60, 'TAG_TIMESTAMP', 'Target Temp')
        ON CONFLICT (tag_code) DO NOTHING;
    """
    cur.execute(sql)
    conn.commit()
    print("Manual insert test SUCCESS!")
except Exception as e:
    print("Manual insert test ERROR:", e)
conn.close()
