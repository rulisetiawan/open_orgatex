import psycopg2

conn = psycopg2.connect(
    host='192.168.100.30',
    port=5433,
    dbname='pt_smm_jetflow',
    user='postgres',
    password='sensorSMM!'
)
cur = conn.cursor()

cur.execute("""
SELECT table_schema, table_name, table_type 
FROM information_schema.tables 
WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
ORDER BY table_schema, table_name;
""")
rows = cur.fetchall()
print("FOUND TABLES IN pt_smm_jetflow:")
for r in rows:
    print(f"  Schema: {r[0]:<15} | Table: {r[1]:<30} | Type: {r[2]}")

cur.execute("SELECT datname FROM pg_database WHERE datistemplate = false;")
dbs = cur.fetchall()
print("\nDATABASES ON THIS SERVER:")
for d in dbs:
    print(f"  - {d[0]}")

cur.execute("SHOW search_path;")
print("\nCURRENT SEARCH_PATH:", cur.fetchone()[0])

conn.close()
