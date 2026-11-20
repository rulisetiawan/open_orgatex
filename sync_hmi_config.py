"""
Script Sinkronisasi Otomatis File Konfigurasi (.CNF) dan Program PLC (.AWL)
dari Kontroler HMI SETEX / SECOM ke Workspace Mesin OpenOrgaTEX.

Penggunaan:
    # 1. Download langsung dari URL FTP ke folder mesin (cth: MESIN_16C):
    python sync_hmi_config.py --ftp ftp://172.16.110.106/Storage/SC777CE/Config/ --mesin 16C

    # 2. Download via IP tertentu ke mesin tertentu:
    python sync_hmi_config.py --ip 172.16.110.106 --mesin 16C

    # 3. Download otomatis menggunakan IP resmi mesin di profile/database:
    python sync_hmi_config.py --mesin 16C

    # 4. Sinkronisasi massal seluruh mesin yang online:
    python sync_hmi_config.py --all
"""

import os
import sys
import json
import ftplib
import socket
import argparse
from urllib.parse import urlparse
from typing import Dict, List, Optional, Any

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from open_orgatex.backend.services.machine_config_service import (
    fetch_machine_config_from_hmi,
    ensure_machine_workspace,
    sync_machine_ready_config,
    normalize_folder_name
)

WORKSPACE_DIR = os.path.join(BASE_DIR, "WORKSPACE_PROGRAM_MESIN")

def parse_ftp_url(ftp_url: str):
    """Parses ftp://<host>[:port]/<path> into host, port, remote_dir."""
    if not ftp_url.startswith("ftp://"):
        ftp_url = "ftp://" + ftp_url
    parsed = urlparse(ftp_url)
    host = parsed.hostname
    port = parsed.port or 21
    path = parsed.path
    if path.endswith("/"):
        path = path.rstrip("/")
    return host, port, path

def get_machine_ip(machine_no: str) -> Optional[str]:
    """Retrieves machine IP from machine_profile.json or database."""
    folder_name = normalize_folder_name(machine_no)
    prof_file = os.path.join(WORKSPACE_DIR, folder_name, "02_CONFIG_SIAP_PAKAI", "machine_profile.json")
    if os.path.exists(prof_file):
        try:
            with open(prof_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("ip_address"):
                    return data["ip_address"]
        except Exception:
            pass

    # Try database
    try:
        from open_orgatex.backend import database
        from open_orgatex.backend.models.schema_pg import Machine
        db = database.SessionLocal()
        m = db.query(Machine).filter(Machine.machine_no == machine_no.upper()).first()
        db.close()
        if m and m.ip_address:
            return m.ip_address
    except Exception:
        pass

    return None

def sync_single_machine(
    machine_no: str,
    ip: Optional[str] = None,
    remote_path: Optional[str] = None,
    port: int = 21,
    timeout: float = 6.0
) -> bool:
    """Performs FTP download of .CNF and .AWL files and decodes for a single machine."""
    folder_name = normalize_folder_name(machine_no)
    m_code = folder_name.replace("MESIN_", "")
    target_ip = ip or get_machine_ip(m_code)

    if not target_ip:
        print(f"[ERROR] IP untuk {folder_name} tidak ditemukan! Gunakan opsi --ip <IP> atau --ftp <FTP_URL>")
        return False

    print("\n" + "=" * 80)
    print(f"SINKRONISASI HMI -> {folder_name}")
    print("=" * 80)
    print(f"Target Controller IP : {target_ip}:{port}")
    if remote_path:
        print(f"Target Remote Path   : {remote_path}")
    print(f"Workspace Lokal      : WORKSPACE_PROGRAM_MESIN/{folder_name}/01_CONFIG_DARI_HMI/")
    print("-" * 80)
    print(f"[*] Menghubungi kontroler via FTP dan mencari file .CNF serta .AWL...")

    res = fetch_machine_config_from_hmi(
        ip=target_ip,
        machine_no=m_code,
        ftp_port=port,
        remote_dir=remote_path,
        timeout=timeout
    )

    if res.get("success"):
        downloaded = res.get("downloaded", [])
        print(f"\n[SUKSES] Berhasil mengunduh {len(downloaded)} file dari HMI:")
        awl_count = 0
        cnf_count = 0
        for item in downloaded:
            ftype = item.get("type", "FILE")
            if ftype == "AWL":
                awl_count += 1
                tag = "[AWL PLC]"
            else:
                cnf_count += 1
                tag = "[CONFIG ]"
            size_kb = item["size_bytes"] / 1024.0
            print(f"  + {tag} {item['filename']:<16} ({size_kb:>7.1f} KB) <- {item.get('remote_path', '')}")

        print("\n[INFO] Rangkuman:")
        print(f"  - File PLC AWL  : {awl_count} file")
        print(f"  - File CNF HMI  : {cnf_count} file")
        print(f"  - Lokasi Simpan : {res.get('local_raw_path')}")
        print("  - Status Decode : 02_CONFIG_SIAP_PAKAI berhasil diperbarui!")
        return True
    else:
        print(f"\n[GAGAL] {res.get('message')}")
        if res.get("error_type") == "TIMEOUT":
            print("  -> Pastikan controller HMI menyala dan terhubung ke jaringan LAN yang sama.")
        return False

def sync_all_machines():
    """Syncs all machine workspaces that have configured IP addresses."""
    folders = [d for d in sorted(os.listdir(WORKSPACE_DIR)) if d.startswith("MESIN_")]
    print("\n" + "=" * 80)
    print(f"MEMULAI SINKRONISASI MASSAL HMI UNTUK {len(folders)} MESIN")
    print("=" * 80)

    success_count = 0
    fail_count = 0
    skip_count = 0

    for folder in folders:
        m_code = folder.replace("MESIN_", "")
        ip = get_machine_ip(m_code)
        if not ip:
            print(f"[-] Lewati {folder}: Tidak ada IP address.")
            skip_count += 1
            continue

        ok = sync_single_machine(machine_no=m_code, ip=ip, timeout=3.0)
        if ok:
            success_count += 1
        else:
            fail_count += 1

    print("\n" + "=" * 80)
    print("HASIL AKHIR SINKRONISASI MASSAL")
    print("=" * 80)
    print(f"Total Mesin        : {len(folders)}")
    print(f"Berhasil Sinkron   : {success_count} mesin")
    print(f"Gagal / Offline    : {fail_count} mesin")
    print(f"Dilewati (Tanpa IP): {skip_count} mesin")
    print("=" * 80 + "\n")

def main():
    parser = argparse.ArgumentParser(
        description="Sinkronisasi Otomatis File Config (.CNF) dan Program PLC (.AWL) dari HMI SETEX"
    )
    parser.add_argument("--mesin", type=str, help="Kode mesin target (cth: 16C, MESIN_16C, 6A, TD12)")
    parser.add_argument("--ftp", type=str, help="URL FTP kontroler (cth: ftp://172.16.110.106/Storage/SC777CE/Config/)")
    parser.add_argument("--ip", type=str, help="Alamat IP kontroler (cth: 172.16.110.106)")
    parser.add_argument("--port", type=int, default=21, help="Port FTP kontroler (default: 21)")
    parser.add_argument("--remote-path", type=str, help="Path remote folder pada kontroler (cth: /Storage/SC777CE/Config)")
    parser.add_argument("--all", action="store_true", help="Sinkronkan seluruh mesin yang memiliki IP")

    args = parser.parse_args()

    if args.all:
        sync_all_machines()
        return

    target_machine = args.mesin or "16C"
    target_ip = args.ip
    target_port = args.port
    target_path = args.remote_path

    if args.ftp:
        f_host, f_port, f_path = parse_ftp_url(args.ftp)
        target_ip = target_ip or f_host
        target_port = f_port
        target_path = target_path or f_path

    sync_single_machine(
        machine_no=target_machine,
        ip=target_ip,
        remote_path=target_path,
        port=target_port
    )

if __name__ == "__main__":
    main()
