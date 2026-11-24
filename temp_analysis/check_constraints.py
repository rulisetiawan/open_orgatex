import psycopg2

conn = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_scada')
cur = conn.cursor()
cur.execute("""
    SELECT conname, pg_get_constraintdef(oid) 
    FROM pg_constraint 
    WHERE conrelid = 'tag_definition'::regclass;
""")
for r in cur.fetchall():
    print(r)
conn.close()
