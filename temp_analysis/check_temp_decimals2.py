import psycopg2

conn = psycopg2.connect("host=192.168.100.30 port=5433 dbname=pt_smm_jetflow user=postgres password=sensorSMM!")
cur = conn.cursor()

print("--- 1. Summary of operator_interventions with fractional value_after ---")
cur.execute("""
    SELECT trigger_source, function_id, parameter_name,
           COUNT(*) AS total,
           COUNT(*) FILTER (WHERE value_after <> trunc(value_after)) AS fractional_count,
           COUNT(*) FILTER (WHERE value_after = trunc(value_after)) AS integer_count
    FROM operator_interventions
    GROUP BY trigger_source, function_id, parameter_name
    ORDER BY total DESC;
""")
for r in cur.fetchall():
    print(r)

print("\n--- 2. Sample fractional operator_interventions for 1E batch 072216 step 54 ---")
cur.execute("""
    SELECT id, machine_no, batch_no, step_no, timestamp, function_id, value_before, value_after, delta, notes
    FROM operator_interventions
    WHERE machine_no = '1E' AND batch_no = '072216' AND step_no = 54
    ORDER BY timestamp ASC;
""")
for r in cur.fetchall():
    print(r)

print("\n--- 3. Function names for those function_ids in cfg_functions ---")
cur.execute("""
    SELECT function_id, name_en, name_id, category
    FROM cfg_functions
    WHERE function_id IN (141, 939, 938, 716, 140, 142, 143, 144, 145)
    ORDER BY function_id;
""")
for r in cur.fetchall():
    print(r)

print("\n--- 4. Check step_function_parameters & steps for any fractional temperatures ---")
cur.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name = 'step_function_parameters' ORDER BY ordinal_position;
""")
print("sfp cols:", [r[0] for r in cur.fetchall()])

cur.execute("""
    SELECT COUNT(*) AS total,
           COUNT(*) FILTER (WHERE summary_temp <> trunc(summary_temp)) AS fractional_summary_temp
    FROM steps WHERE summary_temp IS NOT NULL;
""")
print("steps summary_temp:", cur.fetchone())

print("\n--- 5. Check datalog_cyclic_records temp_sp for 1E batch 072216 step 54 ---")
cur.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name = 'datalog_cyclic_records' ORDER BY ordinal_position;
""")
print("dcr cols:", [r[0] for r in cur.fetchall()])

cur.execute("""
    SELECT timestamp, step_no, temp_pv, temp_sp
    FROM datalog_cyclic_records
    WHERE machine_no = '1E' AND batch_no = '072216' AND step_no = 54
    ORDER BY timestamp ASC
    LIMIT 25;
""")
for r in cur.fetchall():
    print(r)

conn.close()
