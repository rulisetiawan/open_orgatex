import psycopg2

conn = psycopg2.connect("host=192.168.100.30 port=5433 dbname=pt_smm_jetflow user=postgres password=sensorSMM!")
cur = conn.cursor()

def run_q(title, sql):
    print(f"\n--- {title} ---")
    try:
        cur.execute(sql)
        for r in cur.fetchall():
            print(" ", r)
    except Exception as e:
        print("  ERROR:", e)
        conn.rollback()

run_q("1. step_function_parameters fractional breakdown", """
    SELECT sf.function_name, p.function_parameter_number, COUNT(*) AS frac_cnt, MIN(p.value), MAX(p.value)
    FROM step_function_parameters p
    JOIN step_functions sf ON sf.id = p.step_function_id
    WHERE p.value IS NOT NULL AND p.value <> trunc(p.value)
    GROUP BY sf.function_name, p.function_parameter_number
    ORDER BY frac_cnt DESC
    LIMIT 15;
""")

run_q("2. datalog_cyclic_records for batch 072216 step 54", """
    SELECT timestamp, step_no, temp_pv, temp_sp
    FROM datalog_cyclic_records
    WHERE batch_no = '072216' AND step_no = 54
    ORDER BY timestamp ASC LIMIT 12;
""")

run_q("3. cfg_function_parameters for function_no 141", """
    SELECT * FROM cfg_function_parameters
    WHERE function_no = 141
    ORDER BY param_no;
""")

run_q("4. Sample SETPOINT_OVERRIDE fractional rows (non-141)", """
    SELECT id, machine_no, batch_no, step_no, timestamp, function_id, value_before, value_after, delta, notes
    FROM operator_interventions
    WHERE trigger_source = 'SETPOINT_OVERRIDE'
      AND value_after <> trunc(value_after)
      AND function_id <> 141
    ORDER BY id DESC LIMIT 10;
""")

conn.close()
