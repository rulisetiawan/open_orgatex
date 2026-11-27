import psycopg2

conn = psycopg2.connect("host=192.168.100.30 port=5433 dbname=pt_smm_jetflow user=postgres password=sensorSMM!")
cur = conn.cursor()

print("--- 1. steps.summary_temp fractional check ---")
cur.execute("""
    SELECT COUNT(*) AS total,
           COUNT(*) FILTER (WHERE summary_temp <> trunc(summary_temp)) AS fractional_summary_temp
    FROM steps WHERE summary_temp IS NOT NULL;
""")
print("steps summary_temp:", cur.fetchone())

print("\n--- 2. step_function_parameters fractional check ---")
cur.execute("""
    SELECT COUNT(*) AS total,
           COUNT(*) FILTER (WHERE value <> trunc(value)) AS fractional_vals
    FROM step_function_parameters WHERE value IS NOT NULL;
""")
print("step_function_parameters:", cur.fetchone())

cur.execute("""
    SELECT sfp.id, sfp.param_no, sfp.param_name, sfp.value, sfp.unit
    FROM step_function_parameters sfp
    WHERE sfp.value IS NOT NULL AND sfp.value <> trunc(sfp.value)
      AND (sfp.param_name ILIKE '%temp%' OR sfp.unit ILIKE '%C%')
    LIMIT 15;
""")
for r in cur.fetchall():
    print("  sfp frac:", r)

print("\n--- 3. Sample SETPOINT_OVERRIDE fractional rows (both 141 and non-141) ---")
cur.execute("""
    SELECT id, machine_no, batch_no, step_no, timestamp, function_id, value_before, value_after, delta, notes
    FROM operator_interventions
    WHERE trigger_source = 'SETPOINT_OVERRIDE'
      AND value_after <> trunc(value_after)
    ORDER BY id DESC LIMIT 15;
""")
for r in cur.fetchall():
    print(" ", r)

conn.close()
