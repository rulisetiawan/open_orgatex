import psycopg2

c1 = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_scada', connect_timeout=5)
cur1 = c1.cursor()
for tbl in ('production_batch', 'batch_process_run'):
    cur1.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name=%s ORDER BY ordinal_position", (tbl,))
    print(f"=== pt_smm_scada.{tbl} ===")
    for r in cur1.fetchall(): print(" ", r)
cur1.execute("SELECT batch_no, customer_name, fabric_type, batch_status FROM production_batch ORDER BY created_at DESC LIMIT 5")
print("=== sample production_batch ===")
for r in cur1.fetchall(): print(" ", r)
c1.close()

c2 = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow', connect_timeout=5)
cur2 = c2.cursor()
cur2.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='batch_headers' ORDER BY ordinal_position")
print("=== pt_smm_jetflow.batch_headers ===")
for r in cur2.fetchall(): print(" ", r)
c2.close()
