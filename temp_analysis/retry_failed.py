import os
import sys
import json
import time

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from temp_analysis.download_and_parse_all_machines import process_machine

def main():
    summary_path = os.path.join(os.path.dirname(__file__), "sync_summary.json")
    with open(summary_path, "r", encoding="utf-8") as f:
        results = json.load(f)

    retry_items = [(r["folder"], r["ip"]) for r in results if not r["success"]]
    print(f"[*] Retrying {len(retry_items)} machines sequentially...")

    updated_results = {r["folder"]: r for r in results}

    for folder, ip in retry_items:
        time.sleep(0.5)
        res = process_machine((folder, ip))
        updated_results[folder] = res
        if res["success"]:
            print(f"  [+] {folder:<15} ({ip}): CP14={res.get('cp14_size')} B | Regs={res.get('registers_count')} (SV={res.get('setpoints_count')}, PV={res.get('actuals_count')})")
        else:
            print(f"  [-] {folder:<15} ({ip}): {res.get('error')}")

    all_res = list(updated_results.values())
    succ = [r for r in all_res if r["success"]]
    print(f"\nFinal Total Success: {len(succ)} / {len(all_res)}")

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(all_res, f, indent=2)

if __name__ == "__main__":
    main()
