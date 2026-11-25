import psycopg2

conn = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow', connect_timeout=5)
cur = conn.cursor()

cur.execute("""
    SELECT pc.id, pc.machine_code, pc.number, pc.name,
           (SELECT COUNT(*) FROM steps s WHERE s.parent_component_id = pc.id) AS step_cnt
    FROM program_components pc
    WHERE pc.level = 1
    ORDER BY step_cnt DESC, pc.machine_code, pc.number
    LIMIT 25
""")
print("=== Top 25 ProgramComponent (Level 1) ===")
for r in cur.fetchall():
    print(r)

cur.execute("""
    SELECT pc.machine_code,
           COUNT(*) AS total_progs,
           COUNT(*) FILTER (WHERE EXISTS (SELECT 1 FROM steps s WHERE s.parent_component_id = pc.id)) AS with_steps
    FROM program_components pc
    WHERE pc.level = 1
    GROUP BY pc.machine_code
    ORDER BY total_progs DESC
""")
print("\n=== Summary per machine_code ===")
for r in cur.fetchall():
    print(r)

conn.close()
