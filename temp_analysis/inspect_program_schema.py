import psycopg2

conn = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow', connect_timeout=5)
cur = conn.cursor()

for tbl in ('program_components', 'steps', 'step_functions', 'step_function_parameters'):
    cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (tbl,))
    print(f"=== {tbl} ===")
    for r in cur.fetchall():
        print(" ", r)

# Sample 3 steps from program id=2 (10B, 342)
cur.execute("""
    SELECT s.id, s.position, s.label, s.summary_temp, s.summary_time_min, s.summary_water_l,
           sf.resource_number, sf.function_number, sf.function_name, sf.comment,
           ARRAY_AGG(sfp.value ORDER BY sfp.function_parameter_number) AS params
    FROM steps s
    LEFT JOIN step_functions sf ON sf.step_id = s.id
    LEFT JOIN step_function_parameters sfp ON sfp.step_function_id = sf.id
    WHERE s.parent_component_id = 2 AND s.position <= 5
    GROUP BY s.id, s.position, s.label, s.summary_temp, s.summary_time_min, s.summary_water_l,
             sf.resource_number, sf.function_number, sf.function_name, sf.comment
    ORDER BY s.position, sf.resource_number
""")
print("\n=== Sample steps for program_component id=2 ===")
for r in cur.fetchall():
    print(" ", r)

conn.close()
