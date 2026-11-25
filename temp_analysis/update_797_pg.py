import psycopg2

conn = psycopg2.connect("postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow", connect_timeout=5)
cur = conn.cursor()
cur.execute("""
    UPDATE machines
    SET controller_type = 'SETEX SECOM 797CE'
    WHERE machine_no IN ('2E', '3E', '5E', '8E', '9E', '4F')
    RETURNING machine_no, ip_address, controller_type
""")
print("PostgreSQL updated:", cur.fetchall())
conn.commit()
conn.close()
