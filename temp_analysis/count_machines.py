import psycopg2

conn = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow')
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM machines;')
total = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*) FROM machines 
    WHERE ip_address IS NOT NULL AND ip_address != '' AND ip_address NOT IN ('127.0.0.1', '0.0.0.0', 'localhost');
""")
with_ip = cur.fetchone()[0]

cur.execute("""
    SELECT machine_no, ip_address, controller_type 
    FROM machines 
    WHERE ip_address IS NOT NULL AND ip_address != '' AND ip_address NOT IN ('127.0.0.1', '0.0.0.0', 'localhost') 
    ORDER BY machine_no;
""")
machines = cur.fetchall()
conn.close()

print(f"Total Mesin di Database: {total}")
print(f"Mesin dengan IP Controller Valid: {with_ip}")
print("Daftar Mesin (sample):", [m[0] for m in machines[:20]])
