import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow')
cur = conn.cursor(cursor_factory=RealDictCursor)

key_registers = [1, 2, 10, 11, 12, 13, 15, 16, 17, 21, 22, 25, 27, 28, 30, 32, 33, 36, 39, 40, 42, 43, 45]
cur.execute('''
    SELECT register_index, iw_number, tag_name, tag_role, notes, scale_factor, eng_max, unit 
    FROM cfg_machine_iw_tag_mapping 
    WHERE machine_id = '10B' AND register_index = ANY(%s)
    ORDER BY register_index ASC;
''', (key_registers,))

rows = cur.fetchall()
print(f"Total key rows retrieved: {len(rows)} / {len(key_registers)}")
for r in rows:
    iw = r["iw_number"]
    idx = r["register_index"]
    notes = r["notes"]
    tag = r["tag_name"]
    unit = r["unit"]
    print(f"IW {iw:2d} (Idx {idx:2d}) | {notes:48s} | Unit: {unit:5s} | Tag: {tag}")

# Also check a different machine, e.g. 11B
cur.execute("SELECT COUNT(*) FROM cfg_machine_iw_tag_mapping WHERE machine_id = '11B';")
print("\nMachine 11B total mapped tags:", cur.fetchone()["count"])

# Check machine count in database
cur.execute("SELECT COUNT(DISTINCT machine_id) FROM cfg_machine_iw_tag_mapping;")
print("Total machines with standardized IW mapping in database:", cur.fetchone()["count"])

conn.close()
