"""
Import and Decode HMI Configuration Files for OpenOrgaTEX.
Usage:
    python import_hmi_config.py --group GROUP_001_HIGH_TEMP_JET
    python import_hmi_config.py --all
"""

import os
import sys
import argparse
import shutil
import json

BASE_CONFIGS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GROUPS_DIR = os.path.join(BASE_CONFIGS_DIR, "groups")
BASELINE_FUNCTIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/typeconf_functions.json"))
BASELINE_CONFTEXT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/conftext_aligned.json"))

def process_group(group_name: str):
    group_path = os.path.join(GROUPS_DIR, group_name)
    if not os.path.isdir(group_path):
        print(f"[ERROR] Group directory not found: {group_path}")
        return

    raw_dir = os.path.join(group_path, "raw")
    decoded_dir = os.path.join(group_path, "decoded")
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(decoded_dir, exist_ok=True)

    typeconf_raw = os.path.join(raw_dir, "TYPECONF.CNF")
    conftext_raw = os.path.join(raw_dir, "CONFTEXT.CNF")

    print(f"\n[*] Processing group: {group_name}")
    print(f"    Raw directory: {raw_dir}")
    print(f"    Decoded directory: {decoded_dir}")

    # Check raw TYPECONF.CNF
    if os.path.exists(typeconf_raw):
        print(f"    [+] Found raw TYPECONF.CNF ({os.path.getsize(typeconf_raw)} bytes)")
        # In full production, hook cnf_decode parser here to extract records
    else:
        print(f"    [-] No raw TYPECONF.CNF found in raw/. Checking baseline...")
        target_tf = os.path.join(decoded_dir, "typeconf_functions.json")
        if not os.path.exists(target_tf) and os.path.exists(BASELINE_FUNCTIONS):
            shutil.copy2(BASELINE_FUNCTIONS, target_tf)
            print(f"    [+] Initialized decoded/typeconf_functions.json with baseline dictionary.")

    # Check raw CONFTEXT.CNF
    if os.path.exists(conftext_raw):
        print(f"    [+] Found raw CONFTEXT.CNF ({os.path.getsize(conftext_raw)} bytes)")
    else:
        print(f"    [-] No raw CONFTEXT.CNF found in raw/. Checking baseline...")
        target_cf = os.path.join(decoded_dir, "conftext_aligned.json")
        if not os.path.exists(target_cf) and os.path.exists(BASELINE_CONFTEXT):
            shutil.copy2(BASELINE_CONFTEXT, target_cf)
            print(f"    [+] Initialized decoded/conftext_aligned.json with baseline labels.")

    # Update group_info.json
    info_path = os.path.join(group_path, "group_info.json")
    if os.path.exists(info_path):
        try:
            with open(info_path, "r", encoding="utf-8") as f:
                info = json.load(f)
            has_tf = os.path.exists(os.path.join(decoded_dir, "typeconf_functions.json"))
            has_cf = os.path.exists(os.path.join(decoded_dir, "conftext_aligned.json"))
            info["status"] = "ready" if (has_tf and has_cf) else "incomplete"
            with open(info_path, "w", encoding="utf-8") as f:
                json.dump(info, f, indent=2)
            print(f"    [+] Updated group_info.json status: {info['status']}")
        except Exception as e:
            print(f"    [!] Failed to update group_info.json: {e}")

def main():
    parser = argparse.ArgumentParser(description="HMI Config Import Tool")
    parser.add_argument("--group", type=str, help="Specific group folder name")
    parser.add_argument("--all", action="store_true", help="Process all group folders")
    args = parser.parse_args()

    if args.group:
        process_group(args.group)
    elif args.all:
        for item in sorted(os.listdir(GROUPS_DIR)):
            if os.path.isdir(os.path.join(GROUPS_DIR, item)):
                process_group(item)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
