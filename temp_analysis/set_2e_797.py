import os, json, sqlite3, psycopg2

DB_URL = "postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow"
conn = psycopg2.connect(DB_URL, connect_timeout=5)
cur = conn.cursor()
cur.execute("""
    UPDATE machines
    SET controller_type = 'SETEX SECOM 797CE'
    WHERE machine_no = '2E' OR ip_address = '172.16.120.102'
    RETURNING machine_no, ip_address, controller_type
""")
print("PostgreSQL updated:", cur.fetchall())
conn.commit()
conn.close()

for sq_path in ("open_orgatex/backend/data/orgatex.db", "open_orgatex/backend/orgatex.db"):
    if os.path.isfile(sq_path):
        sc = sqlite3.connect(sq_path)
        sc.execute("UPDATE machines SET controller_type = 'SETEX SECOM 797CE' WHERE machine_no = '2E' OR ip_address = '172.16.120.102'")
        sc.commit()
        print("SQLite updated:", sq_path)
        sc.close()

for cand in ("WORKSPACE_PROGRAM_MESIN/MESIN_2E/02_CONFIG_SIAP_PAKAI/machine_profile.json",
             "WORKSPACE_PROGRAM_MESIN/2E/02_CONFIG_SIAP_PAKAI/machine_profile.json"):
    if os.path.isfile(cand):
        with open(cand, "r", encoding="utf-8") as f:
            d = json.load(f)
        d["controller_type"] = "SETEX SECOM 797CE"
        with open(cand, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2)
        print("Workspace profile updated:", cand)
