import os, json, psycopg2

DB_URL = "postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow"
conn = psycopg2.connect(DB_URL, connect_timeout=5)
cur = conn.cursor()
cur.execute("""
    UPDATE machines
    SET controller_type = 'SETEX SECOM 797CE'
    WHERE machine_no IN ('2E', '4F', '9E')
       OR ip_address IN ('172.16.120.102', '172.16.120.154', '172.16.120.109')
    RETURNING machine_no, ip_address, controller_type
""")
print("PostgreSQL updated:", cur.fetchall())
conn.commit()
conn.close()

for m_no in ("2E", "4F", "9E"):
    p = f"WORKSPACE_PROGRAM_MESIN/MESIN_{m_no}/02_CONFIG_SIAP_PAKAI/machine_profile.json"
    if os.path.isfile(p):
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        d["controller_type"] = "SETEX SECOM 797CE"
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2)
        print("Workspace profile updated:", p)
