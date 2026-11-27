import psycopg2

conn = psycopg2.connect("host=192.168.100.30 port=5433 dbname=pt_smm_jetflow user=postgres password=sensorSMM!")
cur = conn.cursor()

print("--- 1. MAIN_MOTOR.SPEED_SV & HOLDING_TIME_SV in cfg_machine_iw_tag_mapping (10B, 1F) ---")
cur.execute("""
    SELECT id, machine_id, iw_number, source_register, scada_tag_code, unit, x1, x2, y1, y2, scale_factor, description
    FROM cfg_machine_iw_tag_mapping
    WHERE machine_id IN ('10B', '1F')
      AND (scada_tag_code ILIKE '%SPEED_SV%' OR scada_tag_code ILIKE '%HOLDING_TIME%' OR scada_tag_code ILIKE '%NOZZLE_PRESSURE%')
    ORDER BY machine_id, iw_number;
""")
for r in cur.fetchall():
    print(" ", r)

print("\n--- 2. How many machines have MAIN_MOTOR.SPEED_SV mapped to SET 5 (iw_number=10005)? ---")
cur.execute("""
    SELECT iw_number, source_register, scada_tag_code, unit, scale_factor, description, COUNT(*)
    FROM cfg_machine_iw_tag_mapping
    WHERE scada_tag_code ILIKE '%MAIN_MOTOR.SPEED_SV%'
    GROUP BY iw_number, source_register, scada_tag_code, unit, scale_factor, description
    ORDER BY COUNT(*) DESC;
""")
for r in cur.fetchall():
    print(" ", r)

conn.close()
