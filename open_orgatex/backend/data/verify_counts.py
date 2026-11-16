import psycopg2

conn = psycopg2.connect(
    host='192.168.100.30',
    port=5433,
    dbname='pt_smm_jetflow',
    user='postgres',
    password='sensorSMM!'
)
cur = conn.cursor()

tables = [
    'machines',
    'datalog_cyclic_records',
    'datalog_alarms',
    'batch_headers',
    'program_headers',
    'program_steps',
    'recipes',
    'categories',
    'items'
]

print("STATUS TABEL DI DATABASE pt_smm_jetflow (Schema: public):")
for t in tables:
    try:
        cur.execute(f"SELECT COUNT(*) FROM public.{t};")
        cnt = cur.fetchone()[0]
        print(f"  * public.{t:<25} : {cnt} baris data")
    except Exception as e:
        print(f"  * public.{t:<25} : ERROR ({e})")
        conn.rollback()

conn.close()
