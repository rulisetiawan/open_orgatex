import os
import sys
import json
import psycopg2

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "temp_analysis"))
sys.path.insert(0, os.path.join(BASE_DIR, "open_orgatex", "backend"))

from download_and_parse_all_machines import decode_typeconf_cat10, machine_to_asset_id
from open_orgatex.backend.services.machine_config_service import sync_machine_ready_config
from open_orgatex.backend.sync_all_machines_iw_mapping import sync_machine

TARGETS = [
    ("2E", "172.16.120.102"),
    ("3E", "172.16.120.103"),
    ("5E", "172.16.120.105"),
    ("8E", "172.16.120.108"),
    ("9E", "172.16.120.109"),
    ("4F", "172.16.120.154"),
]

DB_URL = "postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow"
pg_conn = psycopg2.connect(DB_URL, connect_timeout=5)

for m_no, ip in TARGETS:
    folder = f"MESIN_{m_no}"
    raw_dir = os.path.join(BASE_DIR, "WORKSPACE_PROGRAM_MESIN", folder, "01_CONFIG_DARI_HMI")
    dec_dir = os.path.join(BASE_DIR, "WORKSPACE_PROGRAM_MESIN", folder, "02_CONFIG_SIAP_PAKAI")
    tc_path = os.path.join(raw_dir, "TYPECONF.CNF")
    asset_id = machine_to_asset_id(folder)

    # 1. Decode TYPECONF.CNF -> typeconf_functions.json + machine_profile.json
    sync_machine_ready_config(m_no, ip_address=ip)

    # 2. Decode TYPECONF.CNF Cat 10 -> typeconf_iw_map.json
    iw_map = decode_typeconf_cat10(tc_path, asset_id)
    out_map_path = os.path.join(dec_dir, "typeconf_iw_map.json")
    if iw_map:
        with open(out_map_path, "w", encoding="utf-8") as f:
            json.dump(iw_map, f, indent=2)

    # Ensure controller_type stays SETEX SECOM 797CE in machine_profile.json
    prof_path = os.path.join(dec_dir, "machine_profile.json")
    if os.path.isfile(prof_path):
        with open(prof_path, "r", encoding="utf-8") as f:
            pd = json.load(f)
        pd["controller_type"] = "SETEX SECOM 797CE"
        pd["asset_id"] = asset_id
        pd["registers_count"] = len(iw_map) if iw_map else 0
        with open(prof_path, "w", encoding="utf-8") as f:
            json.dump(pd, f, indent=2)

    # 3. Sync to PostgreSQL cfg_machine_iw_tag_mapping
    synced_cnt = sync_machine(m_no, out_map_path, conn=pg_conn, sqlite_conn=None)
    print(f"{m_no:<4} ({asset_id}) | IW decoded: {len(iw_map) if iw_map else 0:<4} | DB synced: {synced_cnt}")

pg_conn.close()
print("Done!")
