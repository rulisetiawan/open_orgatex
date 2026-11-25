import psycopg2

conn = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow', connect_timeout=5)
cur = conn.cursor()

q = {
    "program_components L1 per machine": "SELECT machine_code, COUNT(*) FROM program_components WHERE level=1 GROUP BY machine_code ORDER BY 2 DESC LIMIT 20",
    "program_components L2": "SELECT COUNT(*) FROM program_components WHERE level=2",
    "steps": "SELECT COUNT(*) FROM steps",
    "step_functions": "SELECT COUNT(*) FROM step_functions",
    "step_function_parameters": "SELECT COUNT(*) FROM step_function_parameters",
    "program_headers": "SELECT COUNT(*) FROM program_headers",
    "program_steps": "SELECT COUNT(*) FROM program_steps",
}
for k, sql in q.items():
    try:
        cur.execute(sql)
        print(k, "=>", cur.fetchall())
    except Exception as e:
        conn.rollback()
        print(k, "ERROR", e)

# Sample: programs whose number matches 10B active (4 / 0004) and 1A sample
for num in ("4", "0004", "66", "0066", "553", "0553"):
    try:
        cur.execute("""
            SELECT pc.id, pc.machine_code, pc.number, pc.name,
                   (SELECT COUNT(*) FROM steps s WHERE s.parent_component_id = pc.id) AS direct_steps,
                   (SELECT COUNT(*) FROM program_component_items i WHERE i.parent_component_id = pc.id) AS treatments
            FROM program_components pc WHERE pc.level=1 AND pc.number = %s LIMIT 10
        """, (num,))
        rows = cur.fetchall()
        if rows:
            print(f"number={num}:", rows)
    except Exception as e:
        conn.rollback()
        print("sample ERROR", e)
conn.close()
