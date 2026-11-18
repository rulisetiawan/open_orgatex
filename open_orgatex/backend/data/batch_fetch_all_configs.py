"""
Batch Config Fetcher for all 68 factory machines via FTP (Port 21).
Uses concurrent threads to rapidly probe and download HMI configuration files.
"""

import os
import sys
import socket
import ftplib
import concurrent.futures
from datetime import datetime
from typing import Dict, List, Any

# Ensure project root in sys.path
BASE_DIR = r"c:\Users\ruli_smm\DA-TEX"
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from open_orgatex.backend import database
from open_orgatex.backend.models.schema_pg import Machine
from open_orgatex.backend.services.machine_config_service import (
    fetch_machine_config_from_hmi,
    get_machine_config_summary,
    ensure_machine_workspace,
    sync_machine_ready_config
)

def fetch_single(machine_item: Dict[str, Any], timeout: float = 2.0) -> Dict[str, Any]:
    m_no = machine_item["no"]
    ip = machine_item["ip"]
    ftp_port = machine_item.get("ftp_port", 21)

    # 1. Quick socket check on port 21
    is_open = False
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((ip, ftp_port))
            is_open = True
    except Exception:
        pass

    if not is_open:
        # Initialize baseline in workspace so it's ready
        ensure_machine_workspace(m_no)
        sync_machine_ready_config(m_no, ip)
        return {
            "no": m_no,
            "ip": ip,
            "online": False,
            "success": False,
            "message": "Offline / Port 21 tidak merespon",
            "downloaded": []
        }

    # 2. Port is open -> run FTP fetch
    try:
        res = fetch_machine_config_from_hmi(ip=ip, machine_no=m_no, ftp_port=ftp_port, timeout=4.0)
        return {
            "no": m_no,
            "ip": ip,
            "online": True,
            "success": res.get("success", False),
            "message": res.get("message", ""),
            "downloaded": res.get("downloaded", []),
            "downloaded_count": res.get("downloaded_count", 0)
        }
    except Exception as e:
        return {
            "no": m_no,
            "ip": ip,
            "online": True,
            "success": False,
            "message": f"Error: {e}",
            "downloaded": []
        }

def main():
    database.init_db()
    db = database.SessionLocal()
    machines = db.query(Machine).order_by(Machine.group_name, Machine.machine_no).all()
    machine_list = [
        {"no": m.machine_no, "ip": m.ip_address, "ftp_port": m.ftp_port or 21, "group": m.group_name}
        for m in machines
    ]
    db.close()

    total = len(machine_list)
    print("=" * 85)
    print(f"MEMULAI PENARIKAN MASSAL CONFIG HMI VIA FTP UNTUK {total} MESIN")
    print("=" * 85)

    results = []
    # Concurrently probe 15 machines at a time
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        future_map = {executor.submit(fetch_single, m): m for m in machine_list}
        for future in concurrent.futures.as_completed(future_map):
            res = future.result()
            results.append(res)
            status_tag = "[ONLINE & DOWNLOADED]" if res["success"] else ("[ONLINE (No CNF)]" if res["online"] else "[OFFLINE]")
            print(f" -> Mesin {res['no']:<4} ({res['ip']:<15}): {status_tag} {res['message']}")

    # Sort results
    results.sort(key=lambda x: x["no"])

    success_list = [r for r in results if r["success"]]
    online_no_cnf = [r for r in results if r["online"] and not r["success"]]
    offline_list = [r for r in results if not r["online"]]

    print("\n" + "=" * 85)
    print("RINGKASAN HASIL PENARIKAN CONFIG HMI")
    print("=" * 85)
    print(f"Total Mesin Dipindai : {total}")
    print(f"Berhasil Diunduh     : {len(success_list)} mesin")
    print(f"Online (Tanpa CNF)   : {len(online_no_cnf)} mesin")
    print(f"Offline / Belum Konek: {len(offline_list)} mesin")
    print("=" * 85)

    if success_list:
        print("\nMesin yang Berhasil Diunduh File Konfigurasinya:")
        for r in success_list:
            files_str = ", ".join([f"{d['filename']} ({d['size_bytes']//1024}KB)" for d in r['downloaded']])
            print(f"  + Mesin {r['no']:<4} ({r['ip']}): {files_str}")

if __name__ == "__main__":
    main()
