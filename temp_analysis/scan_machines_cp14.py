import os
import sys
import ftplib
import json
from concurrent.futures import ThreadPoolExecutor

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WORKSPACE_DIR = os.path.join(BASE_DIR, "WORKSPACE_PROGRAM_MESIN")

def get_machines():
    machines = []
    for d in sorted(os.listdir(WORKSPACE_DIR)):
        if not d.startswith("MESIN_"):
            continue
        p = os.path.join(WORKSPACE_DIR, d, "02_CONFIG_SIAP_PAKAI", "machine_profile.json")
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    ip = data.get("ip_address")
                    if ip:
                        machines.append((d, ip))
            except Exception:
                pass
    return machines

def scan_machine(item):
    folder, ip = item
    res = {
        "folder": folder,
        "ip": ip,
        "status": "offline",
        "has_cp14": False,
        "has_typeconf": False,
        "has_conftext": False,
        "has_machconf": False,
        "path": None,
        "error": None
    }
    try:
        ftp = ftplib.FTP(timeout=3.0)
        ftp.connect(ip, 21)
        ftp.login()
        for cand in ["/Storage/SC777CE/Config", "/Storage/sc777ce/Config", "/SC777CE/Config"]:
            try:
                nlst = ftp.nlst(cand)
                upper = [os.path.basename(x.replace("\\", "/")).upper() for x in nlst]
                if "CP14.AWL" in upper or "TYPECONF.CNF" in upper:
                    res["status"] = "online"
                    res["path"] = cand
                    res["has_cp14"] = "CP14.AWL" in upper
                    res["has_typeconf"] = "TYPECONF.CNF" in upper
                    res["has_conftext"] = "CONFTEXT.CNF" in upper
                    res["has_machconf"] = "MACHCONF.CNF" in upper
                    break
            except Exception:
                pass
        ftp.quit()
    except Exception as e:
        res["error"] = str(e)
    return res

def main():
    machines = get_machines()
    print(f"[*] Scanning {len(machines)} machines for CP14.AWL and TYPECONF.CNF...")
    with ThreadPoolExecutor(max_workers=20) as ex:
        results = list(ex.map(scan_machine, machines))

    online_cp14 = [r for r in results if r["has_cp14"]]
    online_typeconf = [r for r in results if r["has_typeconf"]]
    offline = [r for r in results if r["status"] == "offline"]

    print("\n" + "=" * 70)
    print(f"Total Mesin Terdaftar       : {len(results)}")
    print(f"Online dengan CP14.AWL      : {len(online_cp14)}")
    print(f"Online dengan TYPECONF.CNF  : {len(online_typeconf)}")
    print(f"Offline / Timeout           : {len(offline)}")
    print("=" * 70)

    print("\nDaftar Mesin Online dengan CP14.AWL & TYPECONF.CNF:")
    for r in online_cp14:
        print(f"  + {r['folder']:<15} ({r['ip']:<15}) -> path: {r['path']}")

    if offline:
        print(f"\nMesin Offline ({len(offline)}):")
        for r in offline:
            print(f"  - {r['folder']:<15} ({r['ip']:<15}) -> {r['error']}")

    with open(os.path.join(os.path.dirname(__file__), "scan_results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    main()
