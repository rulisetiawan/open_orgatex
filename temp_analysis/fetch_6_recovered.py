import os
import sys
import json
import time
import psycopg2

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "temp_analysis"))
sys.path.insert(0, os.path.join(BASE_DIR, "open_orgatex", "backend"))

from fetch_and_parse_all_awl import fetch_missing_for_machine, parse_awl_file, DB_URL, WORKSPACE_DIR
from download_and_parse_all_machines import decode_typeconf_cat10, machine_to_asset_id
from open_orgatex.backend.services.machine_config_service import sync_machine_ready_config
from open_orgatex.backend.sync_all_machines_iw_mapping import sync_machine

TARGETS = [
    ("1E", "172.16.120.101", True),
    ("2E", "172.16.120.102", True),
    ("9E", "172.16.120.109", True),
    ("1F", "172.16.120.151", True),
    ("2F", "172.16.120.152", True),
    ("3C", "172.16.130.103", False),
]

conn = psycopg2.connect(DB_URL, connect_timeout=5)
cur = conn.cursor()

print("=== Fetching 6 recovered machines (1 clean session each) ===")
for m_no, ip, is_797_hint in TARGETS:
    m, ip_s, st, info, dls, is_797_act = fetch_missing_for_machine(m_no, ip, is_797_hint)
    print(f"  {m:<4} | {ip_s:<15} | {st:<10} | {info:<26} | dl({len(dls)}): {', '.join(dls)}")
    if st == "OK":
        if is_797_act:
            cur.execute("UPDATE machines SET controller_type = 'SETEX SECOM 797CE' WHERE machine_no = %s", (m,))
            conn.commit()

        folder = f"MESIN_{m}"
        raw_dir = os.path.join(WORKSPACE_DIR, folder, "01_CONFIG_DARI_HMI")
        dec_dir = os.path.join(WORKSPACE_DIR, folder, "02_CONFIG_SIAP_PAKAI")
        os.makedirs(dec_dir, exist_ok=True)
        asset_id = machine_to_asset_id(folder)

        # Compile TYPECONF.CNF if downloaded or missing map
        tc_path = os.path.join(raw_dir, "TYPECONF.CNF")
        if any(x.startswith("TYPECONF.CNF") for x in dls) and os.path.isfile(tc_path):
            sync_machine_ready_config(m, ip_address=ip_s)
            iw_map = decode_typeconf_cat10(tc_path, asset_id)
            out_map_path = os.path.join(dec_dir, "typeconf_iw_map.json")
            if iw_map:
                with open(out_map_path, "w", encoding="utf-8") as f:
                    json.dump(iw_map, f, indent=2)
                sync_machine(m, out_map_path, conn=conn, sqlite_conn=None)
            print(f"       -> Compiled TYPECONF & synced DB ({len(iw_map) if iw_map else 0} IW)")

        # Parse all .AWL files
        awl_files = sorted([f for f in os.listdir(raw_dir) if f.upper().endswith(".AWL")])
        if awl_files:
            parsed_list = [parse_awl_file(os.path.join(raw_dir, af)) for af in awl_files]
            with open(os.path.join(dec_dir, "awl_metadata.json"), "w", encoding="utf-8") as f:
                json.dump({"machine": m, "awl_count": len(parsed_list), "files": parsed_list}, f, indent=2)

            prof_path = os.path.join(dec_dir, "machine_profile.json")
            prof = {}
            if os.path.isfile(prof_path):
                try:
                    with open(prof_path, "r", encoding="utf-8") as f:
                        prof = json.load(f)
                except Exception:
                    pass
            if is_797_act:
                prof["controller_type"] = "SETEX SECOM 797CE"
            prof["has_awl_plc_program"] = True
            prof["awl_files"] = awl_files
            prof["awl_cpu_types"] = sorted(set(p["cpu_type"] for p in parsed_list))
            prof["awl_project_names"] = sorted(set(p["primary_project"] for p in parsed_list if p["primary_project"]))
            prof["awl_sha256"] = parsed_list[0]["sha256"]
            with open(prof_path, "w", encoding="utf-8") as f:
                json.dump(prof, f, indent=2)
            print(f"       -> Parsed AWL: {awl_files} | Project: {prof['awl_project_names']}")
    time.sleep(0.4)

conn.close()
print("Done!")
