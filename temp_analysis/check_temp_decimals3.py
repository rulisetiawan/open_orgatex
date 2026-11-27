import psycopg2

conn = psycopg2.connect("host=192.168.100.30 port=5433 dbname=pt_smm_jetflow user=postgres password=sensorSMM!")
cur = conn.cursor()

print("--- 1. ALARMS_LOG Target Temperature with fractional values ---")
cur.execute("""
    SELECT id, machine_no, batch_no, step_no, timestamp, alarm_code, function_id, parameter_name, value_before, value_after, delta, notes, raw_details
    FROM operator_interventions
    WHERE trigger_source = 'ALARMS_LOG' AND parameter_name = 'Target Temperature'
    ORDER BY id DESC;
""")
for r in cur.fetchall():
    print(r)

print("\n--- 2. cfg_functions for function_no 141, 71, 938, 939, 716, 261, 238, 2, 144 ---")
cur.execute("""
    SELECT function_no, name
    FROM cfg_functions
    WHERE function_no IN (141, 71, 938, 939, 716, 261, 238, 2, 144, 536)
    ORDER BY function_no;
""")
for r in cur.fetchall():
    print(r)

print("\n--- 3. Check steps.summary_temp & step_function_parameters for fractional values ---")
cur.execute("""
    SELECT COUNT(*) AS total,
           COUNT(*) FILTER (WHERE summary_temp <> trunc(summary_temp)) AS fractional_summary_temp
    FROM steps WHERE summary_temp IS NOT NULL;
""")
print("steps summary_temp:", cur.fetchone())

cur.execute("""
    SELECT sfp.id, sfp.param_name, sfp.value, sfp.unit
    FROM step_function_parameters sfp
    WHERE sfp.value IS NOT NULL
      AND sfp.value <> trunc(sfp.value)
      AND (sfp.param_name ILIKE '%temp%' OR sfp.unit ILIKE '%C%')
    LIMIT 20;
""")
rows = cur.fetchall()
print("step_function_parameters fractional temp:", len(rows))
for r in rows:
    print(r)

print("\n--- 4. Sample SETPOINT_OVERRIDE fractional rows (non-141 too) ---")
cur.execute("""
    SELECT id, machine_no, batch_no, step_no, timestamp, function_id, value_before, value_after, notes
    FROM operator_interventions
    WHERE trigger_source = 'SETPOINT_OVERRIDE'
      AND value_after <> trunc(value_after)
      AND function_id <> 141
    ORDER BY id DESC LIMIT 15;
""")
for r in cur.fetchall():
    print(r)

conn.close()
