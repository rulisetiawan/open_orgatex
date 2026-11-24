import psycopg2

conn = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow')
cur = conn.cursor()

cur.execute('SELECT count(DISTINCT machine_id), count(*) FROM cfg_machine_iw_tag_mapping;')
m_count, t_count = cur.fetchone()
print(f"Total distinct machines in cfg_machine_iw_tag_mapping: {m_count}")
print(f"Total mapped tag records in database: {t_count}")

cur.execute("""
    SELECT machine_id, count(*) 
    FROM cfg_machine_iw_tag_mapping 
    WHERE machine_id IN ('10E', '1E', '1F', '12C', '15D', '10B') 
    GROUP BY machine_id ORDER BY machine_id;
""")
for r in cur.fetchall():
    print(f"  Mesin {r[0]}: {r[1]} tags mapped")

conn.close()
