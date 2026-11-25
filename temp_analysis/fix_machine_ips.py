import os
import json
import sqlite3
import psycopg2

OFFICIAL_IPS = {
    # Prod 1 Area A & B
    "1A": "172.16.110.101", "2A": "172.16.110.102", "3A": "172.16.110.103",
    "4A": "172.16.110.104", "5A": "172.16.110.105", "6A": "172.16.110.106",
    "1B": "172.16.110.151", "2B": "172.16.110.152", "3B": "172.16.110.153",
    "4B": "172.16.110.154", "5B": "172.16.110.155", "6B": "172.16.110.156",
    "7B": "172.16.110.157", "8B": "172.16.110.158", "9B": "172.16.110.159",
    "10B": "172.16.110.160", "11B": "172.16.110.161", "12B": "172.16.110.162",
    "13B": "172.16.110.163", "14B": "172.16.110.164", "15B": "172.16.110.165",
    "16B": "172.16.110.166", "17B": "172.16.110.167", "18B": "172.16.110.168",
    # Prod 2 Area E & F
    "1E": "172.16.120.101", "2E": "172.16.120.102", "3E": "172.16.120.103",
    "4E": "172.16.120.104", "5E": "172.16.120.105", "6E": "172.16.120.106",
    "7E": "172.16.120.107", "8E": "172.16.120.108", "9E": "172.16.120.109",
    "10E": "172.16.120.110", "11E": "172.16.120.111", "12E": "172.16.120.112",
    "13E": "172.16.120.113",
    "1F": "172.16.120.151", "2F": "172.16.120.152", "3F": "172.16.120.153",
    "4F": "172.16.120.154", "5F": "172.16.120.155", "6F": "172.16.120.156",
    # Prod 3 Area C & D
    "1C": "172.16.130.101", "2C": "172.16.130.102", "3C": "172.16.130.103",
    "4C": "172.16.130.104", "5C": "172.16.130.105", "6C": "172.16.130.106",
    "7C": "172.16.130.107", "8C": "172.16.130.108", "9C": "172.16.130.109",
    "10C": "172.16.130.110", "11C": "172.16.130.111", "12C": "172.16.130.112",
    "13C": "172.16.130.113", "14C": "172.16.130.114", "15C": "172.16.130.115",
    "16C": "172.16.130.116", "17C": "172.16.130.117",
    "11D": "172.16.130.161", "12D": "172.16.130.162", "13D": "172.16.130.163",
    "14D": "172.16.130.164", "15D": "172.16.130.165", "16D": "172.16.130.166",
    "18D": "172.16.130.168", "19D": "172.16.130.169",
}

# 1. Update PostgreSQL pt_smm_jetflow.machines
DB_URL = "postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow"
conn = psycopg2.connect(DB_URL, connect_timeout=5)
cur = conn.cursor()

cur.execute("SELECT machine_no, ip_address FROM machines")
existing = {r[0]: r[1] for r in cur.fetchall()}

updated_pg = []
missing_pg = []
for m_no, new_ip in sorted(OFFICIAL_IPS.items()):
    if m_no not in existing:
        missing_pg.append((m_no, new_ip))
        continue
    old_ip = (existing[m_no] or "").strip()
    if old_ip != new_ip:
        cur.execute("UPDATE machines SET ip_address = %s WHERE machine_no = %s", (new_ip, m_no))
        updated_pg.append((m_no, old_ip, new_ip))

conn.commit()
conn.close()

print(f"=== PostgreSQL pt_smm_jetflow.machines ===")
print(f"Updated: {len(updated_pg)} rows")
for m_no, old_ip, new_ip in updated_pg:
    print(f"  {m_no:<5}: {old_ip:<15} -> {new_ip}")
if missing_pg:
    print(f"Not in machines table ({len(missing_pg)}): {missing_pg}")

# 2. Update WORKSPACE_PROGRAM_MESIN/*/02_CONFIG_SIAP_PAKAI/machine_profile.json
ws_root = "WORKSPACE_PROGRAM_MESIN"
updated_ws = []
if os.path.isdir(ws_root):
    for m_no, new_ip in sorted(OFFICIAL_IPS.items()):
        for cand in (f"MESIN_{m_no}", m_no):
            prof = os.path.join(ws_root, cand, "02_CONFIG_SIAP_PAKAI", "machine_profile.json")
            if os.path.isfile(prof):
                try:
                    with open(prof, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    old_ip = str(data.get("ip_address") or "").strip()
                    if old_ip != new_ip:
                        data["ip_address"] = new_ip
                        with open(prof, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2)
                        updated_ws.append((m_no, old_ip, new_ip))
                except Exception as e:
                    print(f"  Warn {prof}: {e}")

print(f"\n=== WORKSPACE_PROGRAM_MESIN machine_profile.json ===")
print(f"Updated: {len(updated_ws)} files")
for m_no, old_ip, new_ip in updated_ws:
    print(f"  {m_no:<5}: {old_ip:<15} -> {new_ip}")

# 3. Update local SQLite if present
for sq_path in ("open_orgatex/backend/data/orgatex.db", "open_orgatex/backend/orgatex.db"):
    if os.path.isfile(sq_path):
        sconn = sqlite3.connect(sq_path)
        scur = sconn.cursor()
        try:
            scur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='machines'")
            if scur.fetchone():
                cnt = 0
                for m_no, new_ip in OFFICIAL_IPS.items():
                    scur.execute("UPDATE machines SET ip_address = ? WHERE machine_no = ? AND COALESCE(ip_address,'') != ?", (new_ip, m_no, new_ip))
                    cnt += scur.rowcount
                sconn.commit()
                print(f"\n=== SQLite {sq_path} === Updated: {cnt} rows")
        finally:
            sconn.close()
