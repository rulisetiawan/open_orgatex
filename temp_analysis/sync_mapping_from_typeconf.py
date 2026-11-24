import os
import json
import sqlite3
import psycopg2
from psycopg2.extras import execute_values

PG_URL = "postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow"
SQLITE_PATH = r"c:\Users\ruli_smm\DA-TEX\open_orgatex\backend\data\orgatex_local.db"
JSON_PATH = r"c:\Users\ruli_smm\DA-TEX\WORKSPACE_PROGRAM_MESIN\MESIN_10B\02_CONFIG_SIAP_PAKAI\typeconf_iw_map.json"

with open(JSON_PATH, "r", encoding="utf-8") as f:
    tc_data = json.load(f)

mach_id = "10B"
asset_id = "JF-LB-10"

records = []
for k_str, meta in tc_data.items():
    try:
        reg_num = int(k_str)
    except ValueError:
        continue

    # Skip dummy / invalid registers
    name = meta.get("name", "")
    if reg_num <= 0 or name == "---":
        continue

    tag_name = meta.get("tag_name", "")
    if not tag_name or tag_name.endswith("._PV"):
        continue

    # Fix IW 70 role if needed
    if reg_num == 70 and tag_name.endswith("_ALARM"):
        tag_name = tag_name.replace("_ALARM", "_ALM")

    field_name = meta.get("field_name", "")
    tag_role = meta.get("tag_role", "PV")
    if tag_role in ["ACTUAL", ""]:
        tag_role = "PV"
    elif tag_role == "SETPOINT":
        tag_role = "SV"
    elif tag_role == "ALARM":
        tag_role = "ALM"

    unit = meta.get("unit", "")
    data_type = meta.get("data_type", "ACTUAL")
    raw_min = float(meta.get("y1", 0.0))
    raw_max = float(meta.get("y2", 1000.0))
    eng_min = float(meta.get("x1", 0.0))
    eng_max = float(meta.get("x2", 100.0))
    factor = float(meta.get("factor", 1.0))
    is_active = True
    name_local = meta.get("name_local", "")
    notes = f"{name} ({name_local}) [IW {reg_num}]".strip() if name_local else f"{name} [IW {reg_num}]"

    records.append((
        mach_id,
        asset_id,
        reg_num,        # register_index
        reg_num,        # iw_number
        tag_name,
        tag_role,
        field_name,
        unit,
        data_type,
        raw_min,
        raw_max,
        eng_min,
        eng_max,
        factor,
        is_active,
        notes
    ))

print(f"Prepared {len(records)} valid records for machine {mach_id} ({asset_id}).")

# 1. Sync PostgreSQL
try:
    pg_conn = psycopg2.connect(PG_URL)
    pg_cur = pg_conn.cursor()

    # Clear existing 10B rows to avoid stale tags
    pg_cur.execute("DELETE FROM cfg_machine_iw_tag_mapping WHERE machine_id = %s;", (mach_id,))
    print(f"Cleared old mappings for {mach_id} in PostgreSQL.")

    insert_sql = """
        INSERT INTO cfg_machine_iw_tag_mapping (
            machine_id, asset_id, register_index, iw_number,
            tag_name, tag_role, field_name, unit, data_type,
            raw_min, raw_max, eng_min, eng_max, scale_factor,
            is_active, notes, updated_at
        ) VALUES %s;
    """
    values = [
        (
            r[0], r[1], r[2], r[3],
            r[4], r[5], r[6], r[7], r[8],
            r[9], r[10], r[11], r[12], r[13],
            r[14], r[15]
        )
        for r in records
    ]

    execute_values(
        pg_cur,
        """
        INSERT INTO cfg_machine_iw_tag_mapping (
            machine_id, asset_id, register_index, iw_number,
            tag_name, tag_role, field_name, unit, data_type,
            raw_min, raw_max, eng_min, eng_max, scale_factor,
            is_active, notes, updated_at
        ) VALUES %s
        """,
        values,
        template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())"
    )
    pg_conn.commit()
    print(f"Successfully inserted {len(records)} records into PostgreSQL cfg_machine_iw_tag_mapping!")
    pg_conn.close()
except Exception as e:
    print(f"PostgreSQL Sync Error: {e}")

# 2. Sync SQLite local cache if present
if os.path.exists(SQLITE_PATH):
    try:
        sq_conn = sqlite3.connect(SQLITE_PATH)
        sq_cur = sq_conn.cursor()
        # Check if table exists
        sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cfg_machine_iw_tag_mapping';")
        if sq_cur.fetchone():
            sq_cur.execute("DELETE FROM cfg_machine_iw_tag_mapping WHERE machine_id = ?;", (mach_id,))
            sq_cur.executemany("""
                INSERT INTO cfg_machine_iw_tag_mapping (
                    machine_id, asset_id, register_index, iw_number,
                    tag_name, tag_role, field_name, unit, data_type,
                    raw_min, raw_max, eng_min, eng_max, scale_factor,
                    is_active, notes, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'));
            """, records)
            sq_conn.commit()
            print(f"Successfully synced {len(records)} records into SQLite local db!")
        sq_conn.close()
    except Exception as e:
        print(f"SQLite Sync Error: {e}")

print("Sync completed!")
