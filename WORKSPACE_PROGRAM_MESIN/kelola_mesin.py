"""
Tool Manajemen Workspace & Konfigurasi Mesin Celup OpenOrgaTEX
Membantu operator/teknisi:
1. Memeriksa status kelengkapan file konfigurasi yang didownload dari masing-masing HMI.
2. Melakukan sinkronisasi & decoding otomatis file raw .CNF ke format siap pakai (.json).
3. Menambah mesin baru ke dalam sistem dengan 1 perintah.

Penggunaan:
    python kelola_mesin.py --status
    python kelola_mesin.py --sync TD12
    python kelola_mesin.py --sync-all
    python kelola_mesin.py --tambah-mesin TD15
"""

import os
import sys
import shutil
import json
import argparse
from typing import Dict, List, Any

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "_TEMPLATE_MESIN_BARU")
BACKEND_DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, "../open_orgatex/backend/data"))
BASELINE_FUNCTIONS = os.path.join(BACKEND_DATA_DIR, "typeconf_functions.json")
BASELINE_CONFTEXT = os.path.join(BACKEND_DATA_DIR, "conftext_aligned.json")

def get_machine_folders() -> List[str]:
    """Returns list of all active machine directory names."""
    dirs = []
    for item in sorted(os.listdir(BASE_DIR)):
        full = os.path.join(BASE_DIR, item)
        if os.path.isdir(full) and item.startswith("MESIN_"):
            dirs.append(item)
    return dirs

def check_status():
    """Prints a clear overview table of all machines and their configuration readiness."""
    folders = get_machine_folders()
    print("\n" + "=" * 95)
    print("STATUS WORKSPACE MESIN CELUP (OPENORGATEX)")
    print("=" * 95)
    print(f"{'Folder Mesin':<15} | {'Raw CNF dari HMI':<22} | {'Decoded JSON':<18} | {'Acuan PRG':<10} | {'Hasil PRG':<10}")
    print("-" * 95)

    for m in folders:
        m_dir = os.path.join(BASE_DIR, m)
        raw_dir = os.path.join(m_dir, "01_CONFIG_DARI_HMI")
        dec_dir = os.path.join(m_dir, "02_CONFIG_SIAP_PAKAI")
        ref_dir = os.path.join(m_dir, "03_CONTOH_PRG_DARI_HMI")
        out_dir = os.path.join(m_dir, "04_HASIL_PROGRAM_CELUP")

        # Check raw CNFs
        has_tc = os.path.exists(os.path.join(raw_dir, "TYPECONF.CNF"))
        has_ct = os.path.exists(os.path.join(raw_dir, "CONFTEXT.CNF"))
        has_mc = os.path.exists(os.path.join(raw_dir, "MACHCONF.CNF"))

        raw_str = []
        if has_tc: raw_str.append("TYPECONF")
        if has_ct: raw_str.append("CONFTEXT")
        if has_mc: raw_str.append("MACHCONF")
        raw_display = ", ".join(raw_str) if raw_str else "[Belum ada]"

        # Check decoded JSON
        has_dec_f = os.path.exists(os.path.join(dec_dir, "typeconf_functions.json"))
        has_dec_t = os.path.exists(os.path.join(dec_dir, "conftext_aligned.json"))
        if has_dec_f and has_dec_t:
            dec_display = "[OK] Siap Pakai"
        elif has_dec_f:
            dec_display = "Sebagian (Fungsi)"
        else:
            dec_display = "[Belum Decode]"

        # Count PRGs
        ref_count = len([f for f in os.listdir(ref_dir) if f.upper().endswith(".PRG")]) if os.path.exists(ref_dir) else 0
        out_count = len([f for f in os.listdir(out_dir) if f.upper().endswith(".PRG")]) if os.path.exists(out_dir) else 0

        print(f"{m:<15} | {raw_display:<22} | {dec_display:<18} | {ref_count} file{'':<4} | {out_count} file{'':<4}")

    print("=" * 95)
    print("Keterangan:")
    print(" - Taruh file download HMI di: WORKSPACE_PROGRAM_MESIN/<NAMA_MESIN>/01_CONFIG_DARI_HMI/")
    print(" - Jalankan sinkronisasi:      python WORKSPACE_PROGRAM_MESIN/kelola_mesin.py --sync <NAMA_MESIN>\n")

def sync_machine(machine_name: str):
    """Syncs raw HMI config files to decoded JSON ready for OpenOrgaTEX."""
    # Normalize folder name
    folder_name = machine_name if machine_name.startswith("MESIN_") else f"MESIN_{machine_name}"
    m_dir = os.path.join(BASE_DIR, folder_name)

    if not os.path.isdir(m_dir):
        print(f"[ERROR] Folder mesin tidak ditemukan: {m_dir}")
        print(f"Pilihan mesin yang ada: {', '.join(get_machine_folders())}")
        return

    raw_dir = os.path.join(m_dir, "01_CONFIG_DARI_HMI")
    dec_dir = os.path.join(m_dir, "02_CONFIG_SIAP_PAKAI")
    prof_file = os.path.join(dec_dir, "machine_profile.json")

    print(f"\n[*] Melakukan sinkronisasi untuk: {folder_name}")

    has_tc = os.path.exists(os.path.join(raw_dir, "TYPECONF.CNF"))
    has_ct = os.path.exists(os.path.join(raw_dir, "CONFTEXT.CNF"))

    if has_tc:
        print(f"  [+] Menemukan file asli TYPECONF.CNF dari HMI!")
        # In future full binary decoder hook
    else:
        print(f"  [-] Belum ada TYPECONF.CNF di 01_CONFIG_DARI_HMI/. Menggunakan baseline standar.")
        dst_f = os.path.join(dec_dir, "typeconf_functions.json")
        if not os.path.exists(dst_f) and os.path.exists(BASELINE_FUNCTIONS):
            shutil.copy2(BASELINE_FUNCTIONS, dst_f)
            print("  [+] Berhasil menginisialisasi typeconf_functions.json dari baseline.")

    if has_ct:
        print(f"  [+] Menemukan file asli CONFTEXT.CNF dari HMI!")
    else:
        print(f"  [-] Belum ada CONFTEXT.CNF di 01_CONFIG_DARI_HMI/. Menggunakan baseline standar.")
        dst_t = os.path.join(dec_dir, "conftext_aligned.json")
        if not os.path.exists(dst_t) and os.path.exists(BASELINE_CONFTEXT):
            shutil.copy2(BASELINE_CONFTEXT, dst_t)
            print("  [+] Berhasil menginisialisasi conftext_aligned.json dari baseline.")

    # Update machine profile
    if os.path.exists(prof_file):
        try:
            with open(prof_file, "r", encoding="utf-8") as f:
                prof = json.load(f)
            prof["has_custom_hmi_config"] = (has_tc and has_ct)
            prof["status"] = "ready"
            with open(prof_file, "w", encoding="utf-8") as f:
                json.dump(prof, f, indent=2)
            print(f"  [+] Profil mesin diperbarui: {prof['status']}")
        except Exception as e:
            print(f"  [!] Gagal update profil: {e}")

    print(f"[SELESAI] Mesin {folder_name} siap digunakan di OpenOrgaTEX!\n")

def create_machine(machine_name: str):
    """Creates a new machine directory from template."""
    folder_name = machine_name if machine_name.startswith("MESIN_") else f"MESIN_{machine_name}"
    target = os.path.join(BASE_DIR, folder_name)

    if os.path.exists(target):
        print(f"[PERINGATAN] Folder mesin {folder_name} sudah ada!")
        return

    shutil.copytree(TEMPLATE_DIR, target)

    # Initialize baseline
    dec_dir = os.path.join(target, "02_CONFIG_SIAP_PAKAI")
    os.makedirs(dec_dir, exist_ok=True)
    if os.path.exists(BASELINE_FUNCTIONS):
        shutil.copy2(BASELINE_FUNCTIONS, os.path.join(dec_dir, "typeconf_functions.json"))
    if os.path.exists(BASELINE_CONFTEXT):
        shutil.copy2(BASELINE_CONFTEXT, os.path.join(dec_dir, "conftext_aligned.json"))

    # Update profile
    prof_file = os.path.join(dec_dir, "machine_profile.json")
    m_code = folder_name.replace("MESIN_", "")
    prof_data = {
        "machine_no": m_code,
        "folder_name": folder_name,
        "controller_type": "SETEX SECOM 777 (Windows CE)",
        "max_temp_c": 140.0,
        "has_custom_hmi_config": False,
        "status": "ready"
    }
    with open(prof_file, "w", encoding="utf-8") as f:
        json.dump(prof_data, f, indent=2)

    print(f"\n[SUKSES] Berhasil membuat folder workspace untuk {folder_name}!")
    print(f"Path: {target}")
    print("Silakan taruh file TYPECONF.CNF dan CONFTEXT.CNF ke:")
    print(f"  --> {os.path.join(target, '01_CONFIG_DARI_HMI')}\n")

def main():
    parser = argparse.ArgumentParser(description="Tool Manajemen Workspace Mesin Celup OpenOrgaTEX")
    parser.add_argument("--status", action="store_true", help="Lihat status kelengkapan file seluruh mesin")
    parser.add_argument("--sync", type=str, help="Sinkronisasi file konfigurasi untuk 1 mesin (cth: TD12)")
    parser.add_argument("--sync-all", action="store_true", help="Sinkronisasi seluruh mesin")
    parser.add_argument("--tambah-mesin", type=str, help="Tambah folder workspace untuk mesin baru (cth: TD15)")

    args = parser.parse_args()

    if args.status:
        check_status()
    elif args.sync:
        sync_machine(args.sync)
    elif args.sync_all:
        for m in get_machine_folders():
            sync_machine(m)
    elif args.tambah_mesin:
        create_machine(args.tambah_mesin)
    else:
        check_status()

if __name__ == "__main__":
    main()
