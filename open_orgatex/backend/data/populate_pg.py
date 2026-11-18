"""
Reset and populate 68 factory machines into PostgreSQL inside Docker container,
handling foreign key constraints gracefully.
"""

import os
import sys
from sqlalchemy import text

from open_orgatex.backend import database
from open_orgatex.backend.models.schema_pg import Machine

MACHINES_DATA = [
    # ==========================================
    # Prod 1 Area A & B (Subnet: 172.16.110.0/24, Gateway: 172.16.110.1)
    # ==========================================
    {"no": "1A", "ip": "172.16.110.101", "name": "Novatech", "type": "Novatech Digital", "group": "Prod 1 Area A"},
    {"no": "2A", "ip": "172.16.110.102", "name": "Novatech", "type": "Novatech Digital", "group": "Prod 1 Area A"},
    {"no": "3A", "ip": "172.16.110.103", "name": "Novatech", "type": "Novatech Digital", "group": "Prod 1 Area A"},
    {"no": "4A", "ip": "172.16.110.104", "name": "Novatech", "type": "Novatech Digital", "group": "Prod 1 Area A"},
    {"no": "5A", "ip": "172.16.110.105", "name": "Novatech", "type": "Novatech Digital", "group": "Prod 1 Area A"},
    {"no": "6A", "ip": "172.16.110.106", "name": "Novatech", "type": "Novatech Digital", "group": "Prod 1 Area A"},

    {"no": "1B", "ip": "172.16.110.151", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 1 Area B"},
    {"no": "2B", "ip": "172.16.110.152", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 1 Area B"},
    {"no": "3B", "ip": "172.16.110.153", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 1 Area B"},
    {"no": "4B", "ip": "172.16.110.154", "name": "Novatech", "type": "Novatech Digital", "group": "Prod 1 Area B"},
    {"no": "5B", "ip": "172.16.110.155", "name": "Novatech", "type": "Novatech Digital", "group": "Prod 1 Area B"},
    {"no": "6B", "ip": "172.16.110.156", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 1 Area B"},
    {"no": "7B", "ip": "172.16.110.157", "name": "Novatech", "type": "Novatech Digital", "group": "Prod 1 Area B"},
    {"no": "8B", "ip": "172.16.110.158", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 1 Area B"},
    {"no": "9B", "ip": "172.16.110.159", "name": "Novatech", "type": "Novatech Digital", "group": "Prod 1 Area B"},
    {"no": "10B", "ip": "172.16.110.160", "name": "Novatech", "type": "Novatech Digital", "group": "Prod 1 Area B"},
    {"no": "11B", "ip": "172.16.110.161", "name": "Novatech", "type": "Novatech Digital", "group": "Prod 1 Area B"},
    {"no": "12B", "ip": "172.16.110.162", "name": "Novatech", "type": "Novatech Digital", "group": "Prod 1 Area B"},
    {"no": "13B", "ip": "172.16.110.163", "name": "Novatech", "type": "Novatech Digital", "group": "Prod 1 Area B"},
    {"no": "14B", "ip": "172.16.110.164", "name": "Novatech", "type": "Novatech Digital", "group": "Prod 1 Area B"},
    {"no": "15B", "ip": "172.16.110.165", "name": "Novatech", "type": "Novatech Digital", "group": "Prod 1 Area B"},
    {"no": "16B", "ip": "172.16.110.166", "name": "Novatech", "type": "Novatech Digital", "group": "Prod 1 Area B"},
    {"no": "17B", "ip": "172.16.110.167", "name": "Novatech", "type": "Novatech Digital", "group": "Prod 1 Area B"},
    {"no": "18B", "ip": "172.16.110.168", "name": "Novatech", "type": "Novatech Digital", "group": "Prod 1 Area B"},

    # ==========================================
    # Prod 2 Area E & F (Subnet: 172.16.120.0/24, Gateway: 172.16.120.1)
    # ==========================================
    {"no": "1E", "ip": "172.16.120.101", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 2 Area E"},
    {"no": "2E", "ip": "172.16.120.102", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 2 Area E"},
    {"no": "3E", "ip": "172.16.120.103", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 2 Area E"},
    {"no": "4E", "ip": "172.16.120.104", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 2 Area E"},
    {"no": "5E", "ip": "172.16.120.105", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 2 Area E"},
    {"no": "6E", "ip": "172.16.120.106", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 2 Area E"},
    {"no": "7E", "ip": "172.16.120.107", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 2 Area E"},
    {"no": "8E", "ip": "172.16.120.108", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 2 Area E"},
    {"no": "9E", "ip": "172.16.120.109", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 2 Area E"},
    {"no": "10E", "ip": "172.16.120.110", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 2 Area E"},
    {"no": "11E", "ip": "172.16.120.111", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 2 Area E"},
    {"no": "12E", "ip": "172.16.120.112", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 2 Area E"},
    {"no": "13E", "ip": "172.16.120.113", "name": "Setex", "type": "SECOM 777 (Versi Lama)", "group": "Prod 2 Area E"},

    {"no": "1F", "ip": "172.16.120.151", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 2 Area F"},
    {"no": "2F", "ip": "172.16.120.152", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 2 Area F"},
    {"no": "3F", "ip": "172.16.120.153", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 2 Area F"},
    {"no": "4F", "ip": "172.16.120.154", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 2 Area F"},
    {"no": "5F", "ip": "172.16.120.155", "name": "Setex", "type": "SECOM 777 (Versi Lama)", "group": "Prod 2 Area F"},
    {"no": "6F", "ip": "172.16.120.156", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 2 Area F"},

    # ==========================================
    # Prod 3 Area C & D (Subnet: 172.16.130.0/24, Gateway: 172.16.130.1)
    # ==========================================
    {"no": "1C", "ip": "172.16.130.101", "name": "Novatech", "type": "Novatech Digital", "group": "Prod 3 Area C"},
    {"no": "2C", "ip": "172.16.130.102", "name": "Novatech", "type": "Novatech Digital", "group": "Prod 3 Area C"},
    {"no": "3C", "ip": "172.16.130.103", "name": "Novatech", "type": "Novatech Digital", "group": "Prod 3 Area C"},
    {"no": "4C", "ip": "172.16.130.104", "name": "Novatech", "type": "Novatech Digital", "group": "Prod 3 Area C"},
    {"no": "5C", "ip": "172.16.130.105", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 3 Area C"},
    {"no": "6C", "ip": "172.16.130.106", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 3 Area C"},
    {"no": "7C", "ip": "172.16.130.107", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 3 Area C"},
    {"no": "8C", "ip": "172.16.130.108", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 3 Area C"},
    {"no": "9C", "ip": "172.16.130.109", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 3 Area C"},
    {"no": "10C", "ip": "172.16.130.110", "name": "Novatech", "type": "Novatech Digital", "group": "Prod 3 Area C"},
    {"no": "11C", "ip": "172.16.130.111", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 3 Area C"},
    {"no": "12C", "ip": "172.16.130.112", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 3 Area C"},
    {"no": "13C", "ip": "172.16.130.113", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 3 Area C"},
    {"no": "14C", "ip": "172.16.130.114", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 3 Area C"},
    {"no": "15C", "ip": "172.16.130.115", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 3 Area C"},
    {"no": "16C", "ip": "172.16.130.116", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 3 Area C"},
    {"no": "17C", "ip": "172.16.130.117", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 3 Area C"},

    {"no": "11D", "ip": "172.16.130.161", "name": "Novatech", "type": "Novatech Digital", "group": "Prod 3 Area D"},
    {"no": "12D", "ip": "172.16.130.162", "name": "Novatech", "type": "Novatech Digital", "group": "Prod 3 Area D"},
    {"no": "13D", "ip": "172.16.130.163", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 3 Area D"},
    {"no": "14D", "ip": "172.16.130.164", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 3 Area D"},
    {"no": "15D", "ip": "172.16.130.165", "name": "Novatech", "type": "Novatech Digital", "group": "Prod 3 Area D"},
    {"no": "16D", "ip": "172.16.130.166", "name": "Novatech", "type": "Novatech Digital", "group": "Prod 3 Area D"},
    {"no": "18D", "ip": "172.16.130.168", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 3 Area D"},
    {"no": "19D", "ip": "172.16.130.169", "name": "Setex", "type": "SECOM 777 (Windows CE)", "group": "Prod 3 Area D"},

    # ==========================================
    # Dyeing Sample / DA Area (Controller SETEX 797CE)
    # ==========================================
    {"no": "DA01", "ip": "192.168.1.95", "name": "SETEX 797CE", "type": "SETEX 797CE (Windows CE)", "group": "Dyeing Sample / DA", "share_folder_path": "/Flashdisk/SC797CE"},
]

def run(db=None):
    should_close = False
    if db is None:
        database.init_db()
        db = database.SessionLocal()
        should_close = True
    print("Database connection:", getattr(database, "DATABASE_URL", "unknown"))
    print("IS_POSTGRES:", getattr(database, "IS_POSTGRES", False))

    # 1. Insert or update the machines first
    for m in MACHINES_DATA:
        no = m["no"]
        is_setex = "setex" in m["name"].lower() or "797" in m.get("type", "").lower() or "777" in m.get("type", "").lower()
        disp_name = f"Mesin {no} ({m['name']})" if not m["name"].startswith("SETEX") else f"{m['name']} Mesin {no}"
        share_path = m.get("share_folder_path", f"/Network/F/OT/{no}/")

        existing = db.query(Machine).filter(Machine.machine_no == no).first()
        if existing:
            existing.display_name = disp_name
            existing.ip_address = m["ip"]
            existing.tcp_port = 50100 if is_setex else 50000
            existing.ftp_port = 21
            existing.controller_type = m["type"]
            existing.os_family = "WindowsCE" if is_setex else "EmbeddedLinux"
            existing.group_name = m["group"]
            existing.capacity_kg = 350.0
            existing.default_liquor_ratio = 8.0
            existing.tanks_count = 2
            existing.share_folder_path = share_path
            existing.status = "ONLINE"
        else:
            new_m = Machine(
                machine_no=no,
                display_name=disp_name,
                ip_address=m["ip"],
                tcp_port=50100 if is_setex else 50000,
                ftp_port=21,
                controller_type=m["type"],
                os_family="WindowsCE" if is_setex else "EmbeddedLinux",
                group_name=m["group"],
                capacity_kg=350.0,
                default_liquor_ratio=8.0,
                tanks_count=2,
                share_folder_path=share_path,
                polling_interval_sec=5,
                is_active=True,
                status="ONLINE"
            )
            db.add(new_m)

    db.commit()
    print(f"Upserted all {len(MACHINES_DATA)} machines into database.")

    # 1.1 Ensure any 192.168.1.95 or M_95 record is strictly SETEX 797CE
    try:
        for m95 in db.query(Machine).filter((Machine.machine_no == 'M_95') | (Machine.ip_address == '192.168.1.95')):
            m95.controller_type = "SETEX 797CE (Windows CE)"
            m95.share_folder_path = "/Flashdisk/SC797CE"
            if m95.machine_no == 'M_95':
                m95.display_name = "SETEX 797CE Mesin DA01 (M_95)"
        db.commit()
    except Exception as e:
        db.rollback()
        print("Note updating M_95/192.168.1.95:", e)

    # 2. Re-point any batches or foreign keys away from deprecated machines
    deprecated_codes = ['TD12', 'TD13', 'TD14', 'A002', 'A003', 'M01', 'TEST_M1', 'TEST_AUTO']
    try:
        # Check if batch_headers table exists
        db.execute(text("UPDATE batch_headers SET machine_no = '1A' WHERE machine_no IN ('TD12', 'TD13', 'TD14', 'A002', 'A003', 'M01');"))
        db.commit()
        print("Updated batch_headers to point to '1A'.")
    except Exception as e:
        db.rollback()
        print("batch_headers update note:", e)

    try:
        db.execute(text("UPDATE dyelots SET machine_no = '1A' WHERE machine_no IN ('TD12', 'TD13', 'TD14', 'A002', 'A003', 'M01');"))
        db.commit()
        print("Updated dyelots to point to '1A'.")
    except Exception as e:
        db.rollback()
        print("dyelots update note:", e)

    # 3. Now safely delete deprecated machines
    for code in deprecated_codes:
        dep = db.query(Machine).filter(Machine.machine_no == code).first()
        if dep:
            try:
                db.delete(dep)
                db.commit()
                print(f"Deleted deprecated machine {code}.")
            except Exception as e:
                db.rollback()
                print(f"Could not delete {code}: {e}")

    # Verify total
    total = db.query(Machine).count()
    print(f"==================================================")
    print(f"Total machines currently in PostgreSQL: {total}")
    print(f"==================================================")
    if should_close:
        db.close()

if __name__ == "__main__":
    run()
