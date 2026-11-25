import psycopg2

conn = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_scada')
cur = conn.cursor()
cur.execute("SELECT pg_get_functiondef('sync_jetflow_asset_snapshot(text)'::regprocedure);")
sql = cur.fetchone()[0]
with open('temp_analysis/sync_jetflow_func.sql', 'w', encoding='utf-8') as f:
    f.write(sql)
print("Function definition saved to temp_analysis/sync_jetflow_func.sql")
conn.close()
