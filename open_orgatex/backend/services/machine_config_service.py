"""
OpenOrgaTEX Machine Config Downloader & Decoder Service
Automatically retrieves controller configuration files (.CNF) from SETEX / SECOM 777 HMI
via FTP (Port 21) when a machine is added or manually synchronized.
"""

import os
import sys
import shutil
import json
import ftplib
import socket
import logging
import io
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from ..utils.secom_codec import parse_prg_binary

logger = logging.getLogger("orgatex.machine_config")

# Base paths
SERVICES_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(SERVICES_DIR, ".."))
BACKEND_DATA_DIR = os.path.join(BACKEND_DIR, "data")
DA_TEX_ROOT = os.path.abspath(os.path.join(BACKEND_DIR, "..", ".."))

WORKSPACE_BASE = os.path.join(DA_TEX_ROOT, "WORKSPACE_PROGRAM_MESIN")
TEMPLATE_DIR = os.path.join(WORKSPACE_BASE, "_TEMPLATE_MESIN_BARU")

BASELINE_FUNCTIONS = os.path.join(BACKEND_DATA_DIR, "typeconf_functions.json")
BASELINE_CONFTEXT = os.path.join(BACKEND_DATA_DIR, "conftext_aligned.json")

# Candidate remote directories on SETEX HMI
CANDIDATE_CONFIG_DIRS = [
    # SECOM 777
    "/Storage/sc777ce/Config",
    "/Storage/SC777CE/Config",
    "/storage/sc777ce/config",
    "\\Storage\\SC777CE\\Config",
    "\\storage\\sc777ce\\config",
    "/sc777ce/Config",
    "/Storage/sc777ce",
    "/Storage/SC777CE",
    # SECOM 797
    "/Flashdisk/SC797CE/Config",
    "/Flashdisk/sc797ce/Config",
    "/flashdisk/sc797ce/config",
    "/flashdisk/SC797CE/config",
    "\\Flashdisk\\SC797CE\\Config",
    "\\flashdisk\\sc797ce\\config",
    "/sc797ce/Config",
    "/Storage/SC797CE/Config",
    "/Flashdisk/SC797CE",
    "/flashdisk/sc797ce",
    # Generic
    "/Config",
    "/CONFIG",
    "."
]

TARGET_CONFIG_FILES = [
    "TYPECONF.CNF",
    "CONFTEXT.CNF",
    "MACHCONF.CNF",
    "FNLEGEND.CNF",
    "TYPECONT.CNF"
]

def normalize_folder_name(machine_no: str) -> str:
    """Ensures folder name follows MESIN_<ID> convention."""
    clean = machine_no.strip().upper().replace(" ", "_")
    if not clean.startswith("MESIN_"):
        return f"MESIN_{clean}"
    return clean

def ensure_machine_workspace(machine_no: str) -> str:
    """Creates machine workspace from template if not existing, returns path."""
    folder_name = normalize_folder_name(machine_no)
    m_dir = os.path.join(WORKSPACE_BASE, folder_name)

    if not os.path.exists(m_dir):
        if os.path.exists(TEMPLATE_DIR):
            try:
                shutil.copytree(TEMPLATE_DIR, m_dir)
                logger.info(f"Initialized workspace for {folder_name} from template.")
            except Exception as e:
                logger.warning(f"Failed to copy template: {e}, creating manually.")
                os.makedirs(m_dir, exist_ok=True)
        else:
            os.makedirs(m_dir, exist_ok=True)

    # Ensure all 4 standardized subfolders exist
    os.makedirs(os.path.join(m_dir, "01_CONFIG_DARI_HMI"), exist_ok=True)
    os.makedirs(os.path.join(m_dir, "02_CONFIG_SIAP_PAKAI"), exist_ok=True)
    os.makedirs(os.path.join(m_dir, "03_CONTOH_PRG_DARI_HMI"), exist_ok=True)
    os.makedirs(os.path.join(m_dir, "04_HASIL_PROGRAM_CELUP"), exist_ok=True)

    return m_dir

def decode_typeconf_if_possible(typeconf_path: str, output_json_path: str) -> bool:
    """
    Attempts to decode raw TYPECONF.CNF to typeconf_functions.json using cnf_decode if available.
    Falls back to baseline if decoding cannot complete.
    """
    try:
        # Import CNFReader from program/Analisis
        analisis_dir = os.path.join(DA_TEX_ROOT, "program", "Analisis")
        if analisis_dir not in sys.path:
            sys.path.append(analisis_dir)

        from cnf_decode import CNFReader, function, parameter
        reader = CNFReader(typeconf_path)
        incoming = {f['next'] for f in reader.fragments.values() if f.get('next') and f['next'][1] != 255}
        allrecords = {}
        for address in reader.fragments:
            if address in incoming:
                continue
            packed, trace = reader.chain(*address)
            raw, runs = reader.decompress(packed)
            if len(raw) == 290:
                import struct
                key = struct.unpack_from('<3H', raw)
                allrecords[key] = raw

        funcs = {k[2]: function(v) for k, v in allrecords.items() if k[:2] == (3, 0)}
        params = {k[2]: parameter(v) for k, v in allrecords.items() if k[:2] == (2, 0)}

        if funcs and params:
            export_data = {
                "functions": {str(fid): fdata for fid, fdata in funcs.items()},
                "parameters": {str(pid): pdata for pid, pdata in params.items()},
                "source": os.path.basename(typeconf_path),
                "generated_at": datetime.now().isoformat()
            }
            with open(output_json_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2)
            logger.info(f"Successfully decoded {len(funcs)} functions and {len(params)} parameters.")
            return True
    except Exception as e:
        logger.warning(f"Direct CNF decoding encountered error: {e}. Using baseline fallback.")

    # Fallback to copying baseline
    if os.path.exists(BASELINE_FUNCTIONS):
        shutil.copy2(BASELINE_FUNCTIONS, output_json_path)
        return True
    return False

def sync_machine_ready_config(machine_no: str, ip_address: Optional[str] = None):
    """
    Synchronizes downloaded HMI config files to 02_CONFIG_SIAP_PAKAI/.
    """
    folder_name = normalize_folder_name(machine_no)
    m_dir = os.path.join(WORKSPACE_BASE, folder_name)
    raw_dir = os.path.join(m_dir, "01_CONFIG_DARI_HMI")
    dec_dir = os.path.join(m_dir, "02_CONFIG_SIAP_PAKAI")
    prof_file = os.path.join(dec_dir, "machine_profile.json")

    tc_file = os.path.join(raw_dir, "TYPECONF.CNF")
    ct_file = os.path.join(raw_dir, "CONFTEXT.CNF")
    has_tc = os.path.exists(tc_file)
    has_ct = os.path.exists(ct_file)

    target_func = os.path.join(dec_dir, "typeconf_functions.json")
    target_conf = os.path.join(dec_dir, "conftext_aligned.json")

    # Functions dictionary
    if has_tc:
        decode_typeconf_if_possible(tc_file, target_func)
    elif not os.path.exists(target_func) and os.path.exists(BASELINE_FUNCTIONS):
        shutil.copy2(BASELINE_FUNCTIONS, target_func)

    # Texts dictionary
    if not os.path.exists(target_conf) and os.path.exists(BASELINE_CONFTEXT):
        shutil.copy2(BASELINE_CONFTEXT, target_conf)

    # Machine profile JSON
    prof_data = {}
    if os.path.exists(prof_file):
        try:
            with open(prof_file, "r", encoding="utf-8") as f:
                prof_data = json.load(f)
        except Exception:
            pass

    prof_data.update({
        "machine_no": machine_no.upper(),
        "folder_name": folder_name,
        "ip_address": ip_address or prof_data.get("ip_address", ""),
        "has_custom_hmi_config": (has_tc and has_ct),
        "status": "ready" if (has_tc and has_ct) else "baseline_ready",
        "last_synced_at": datetime.now().isoformat(),
        "files_in_hmi_dir": os.listdir(raw_dir) if os.path.exists(raw_dir) else []
    })

    with open(prof_file, "w", encoding="utf-8") as f:
        json.dump(prof_data, f, indent=2)

def fetch_machine_config_from_hmi(
    ip: str,
    machine_no: str,
    ftp_port: int = 21,
    timeout: float = 4.0
) -> Dict[str, Any]:
    """
    Connects to SETEX HMI via FTP and downloads TYPECONF.CNF, CONFTEXT.CNF, MACHCONF.CNF, etc.
    Saves them to WORKSPACE_PROGRAM_MESIN/<NAMA_MESIN>/01_CONFIG_DARI_HMI/
    and runs synchronization to 02_CONFIG_SIAP_PAKAI/.
    """
    folder_name = normalize_folder_name(machine_no)
    m_dir = ensure_machine_workspace(machine_no)
    raw_dir = os.path.join(m_dir, "01_CONFIG_DARI_HMI")

    logger.info(f"Starting auto-fetch config for {machine_no} ({folder_name}) at {ip}:{ftp_port}")

    downloaded = []
    failed = []
    resolved_remote_dir = None

    # Step 1: Probe and Connect FTP
    ftp = None
    try:
        ftp = ftplib.FTP(timeout=timeout)
        ftp.connect(ip, ftp_port)

        # Try anonymous first, then standard SETEX factory credentials
        logged_in = False
        login_attempts = [
            ("", ""),
            ("anonymous", ""),
            ("setex", "setex"),
            ("SETEX", "SETEX"),
            ("admin", "admin")
        ]
        last_auth_err = None
        for u, p in login_attempts:
            try:
                if u:
                    ftp.login(u, p)
                else:
                    ftp.login()
                logged_in = True
                break
            except Exception as auth_err:
                last_auth_err = auth_err
                continue

        if not logged_in:
            raise PermissionError(f"Login FTP gagal di {ip}: {last_auth_err}")

        ftp.voidcmd("TYPE I")  # Binary mode

        # Step 2: Auto-detect remote directory where .CNF files reside
        remote_files_map = {}
        for cand_dir in CANDIDATE_CONFIG_DIRS:
            try:
                nlst = ftp.nlst(cand_dir)
                cand_map = {}
                for item in nlst:
                    base_name = os.path.basename(item.replace("\\", "/"))
                    cand_map[base_name.upper()] = base_name
                
                # Check if TYPECONF.CNF or CONFTEXT.CNF is in this candidate folder
                if any(target in cand_map for target in TARGET_CONFIG_FILES):
                    resolved_remote_dir = cand_dir
                    remote_files_map = cand_map
                    break
            except Exception:
                continue

        if not resolved_remote_dir:
            try:
                cur_nlst = ftp.nlst()
                cand_map = {os.path.basename(i.replace("\\", "/")).upper(): os.path.basename(i.replace("\\", "/")) for i in cur_nlst}
                if any(target in cand_map for target in TARGET_CONFIG_FILES):
                    resolved_remote_dir = "/"
                    remote_files_map = cand_map
            except Exception:
                pass

        if not resolved_remote_dir or not remote_files_map:
            raise FileNotFoundError(
                f"Tidak ditemukan folder konfigurasi HMI yang berisi file .CNF pada kontroler {ip}. "
                f"Direktori yang dicek: {', '.join(CANDIDATE_CONFIG_DIRS)}"
            )

        # Step 3: Change directory to resolved_remote_dir and download
        try:
            ftp.cwd(resolved_remote_dir)
        except Exception:
            pass

        for target in TARGET_CONFIG_FILES:
            if target in remote_files_map:
                filename = remote_files_map[target]
                local_file = os.path.join(raw_dir, target)
                try:
                    with open(local_file, "wb") as f_out:
                        ftp.retrbinary(f"RETR {filename}", f_out.write)
                    size = os.path.getsize(local_file)
                    downloaded.append({
                        "filename": target,
                        "size_bytes": size,
                        "remote_path": f"{resolved_remote_dir}/{filename}"
                    })
                    logger.info(f"Downloaded {target} ({size} bytes) from {resolved_remote_dir}/{filename}")
                except Exception as dl_err:
                    failed.append({"filename": target, "error": str(dl_err)})
                    logger.warning(f"Failed to download {target}: {dl_err}")

    except (socket.timeout, TimeoutError):
        msg = f"Koneksi timeout ke HMI di {ip}:{ftp_port}. Kontroler offline atau tidak merespon dalam {timeout}s."
        logger.warning(msg)
        sync_machine_ready_config(machine_no, ip)
        return {
            "success": False,
            "machine_no": machine_no,
            "folder_name": folder_name,
            "ip_address": ip,
            "error_type": "TIMEOUT",
            "message": msg,
            "downloaded": [],
            "status": "baseline_active"
        }
    except Exception as e:
        msg = f"Gagal mengambil file config via FTP dari {ip}: {str(e)}"
        logger.warning(msg)
        sync_machine_ready_config(machine_no, ip)
        return {
            "success": False,
            "machine_no": machine_no,
            "folder_name": folder_name,
            "ip_address": ip,
            "error_type": "FTP_ERROR",
            "message": msg,
            "downloaded": [],
            "status": "baseline_active"
        }
    finally:
        if ftp:
            try:
                ftp.quit()
            except Exception:
                pass

    # Step 4: Run auto-sync and decoding
    sync_machine_ready_config(machine_no, ip)

    success = len(downloaded) > 0
    return {
        "success": success,
        "machine_no": machine_no,
        "folder_name": folder_name,
        "ip_address": ip,
        "remote_dir": resolved_remote_dir,
        "downloaded": downloaded,
        "downloaded_count": len(downloaded),
        "failed": failed,
        "local_raw_path": raw_dir,
        "status": "ready" if success else "baseline_active",
        "message": (
            f"Berhasil mengunduh {len(downloaded)} file konfigurasi HMI dari {ip}." 
            if success else 
            f"Koneksi berhasil tetapi file .CNF tidak ditemukan di {ip}."
        )
    }

def get_machine_config_summary(machine_no: str) -> Dict[str, Any]:
    """Returns local configuration status for a given machine."""
    folder_name = normalize_folder_name(machine_no)
    m_dir = os.path.join(WORKSPACE_BASE, folder_name)
    raw_dir = os.path.join(m_dir, "01_CONFIG_DARI_HMI")
    dec_dir = os.path.join(m_dir, "02_CONFIG_SIAP_PAKAI")

    exists = os.path.isdir(m_dir)
    has_tc = os.path.exists(os.path.join(raw_dir, "TYPECONF.CNF")) if exists else False
    has_ct = os.path.exists(os.path.join(raw_dir, "CONFTEXT.CNF")) if exists else False
    has_mc = os.path.exists(os.path.join(raw_dir, "MACHCONF.CNF")) if exists else False

    has_dec_f = os.path.exists(os.path.join(dec_dir, "typeconf_functions.json")) if exists else False
    has_dec_t = os.path.exists(os.path.join(dec_dir, "conftext_aligned.json")) if exists else False

    status = "READY" if (has_tc and has_ct and has_dec_f) else ("BASELINE" if has_dec_f else "NOT_CONFIGURED")

    return {
        "machine_no": machine_no.upper(),
        "folder_name": folder_name,
        "workspace_exists": exists,
        "has_typeconf": has_tc,
        "has_conftext": has_ct,
        "has_machconf": has_mc,
        "has_decoded_functions": has_dec_f,
        "has_decoded_texts": has_dec_t,
        "config_status": status,
        "has_custom_hmi_config": (has_tc and has_ct)
    }

CANDIDATE_PROGRAM_DIRS = [
    # SECOM 777 default storage paths
    "/Storage/sc777ce/Programs",
    "/Storage/SC777CE/Programs",
    "/storage/sc777ce/programs",
    "\\Storage\\SC777CE\\Programs",
    "\\storage\\sc777ce\\Programs",
    "/Storage/SC777CE/PROGRAMS",
    "/storage/SC777CF/Programs",
    "/Storage/SC777CF/Programs",
    "/sc777ce/Programs",
    "/SC777CF/Programs",
    # SECOM 797 default flashdisk paths
    "/Flashdisk/SC797CE/Programs",
    "/Flashdisk/sc797ce/Programs",
    "/flashdisk/sc797ce/programs",
    "/flashdisk/SC797CE/programs",
    "\\Flashdisk\\SC797CE\\Programs",
    "\\flashdisk\\sc797ce\\programs",
    "/Flashdisk/SC797CE/PROGRAMS",
    "/Flashdisk/sc797ce/PROGRAMS",
    "/sc797ce/Programs",
    "/Storage/SC797CE/Programs",
    "\\Storage\\SC797CE\\Programs",
    # Generic root programs
    "/Programs",
    "/PROGRAMS",
    "."
]

def fetch_machine_programs_from_hmi(
    machine_no: str,
    ip: str,
    ftp_port: int = 21,
    timeout: float = 10.0,
    remote_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Connects to SETEX HMI controller via FTP (Port 21), locates the remote Programs folder,
    downloads all .PRG binary files into WORKSPACE_PROGRAM_MESIN/<NAMA_MESIN>/03_CONTOH_PRG_DARI_HMI/,
    parses each program, and registers it into OpenOrgaTEX programs database.
    Optimized for Windows CE (SETEX SECOM 777/737).
    """
    folder_name = normalize_folder_name(machine_no)
    clean_no = machine_no.strip().upper().replace("MESIN_", "")
    m_dir = ensure_machine_workspace(machine_no)
    ref_dir = os.path.join(m_dir, "03_CONTOH_PRG_DARI_HMI")
    out_dir = os.path.join(m_dir, "04_HASIL_PROGRAM_CELUP")
    os.makedirs(ref_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)

    meta_path = os.path.join(BACKEND_DATA_DIR, "programs_custom.json")
    compiled_dir = os.path.join(BACKEND_DATA_DIR, "compiled_prg")
    os.makedirs(compiled_dir, exist_ok=True)

    downloaded = []
    failed = []
    parsed_programs = []
    resolved_remote_dir = None
    ftp_connected = False
    ftp_error_msg = None

    # Step 1: Attempt FTP download from HMI controller
    if ip:
        ftp = None
        try:
            ftp = ftplib.FTP(timeout=timeout)
            ftp.connect(ip, ftp_port)
            login_attempts = [
                ("", ""),
                ("anonymous", ""),
                ("setex", "setex"),
                ("SETEX", "SETEX"),
                ("admin", "admin")
            ]
            logged_in = False
            for u, p in login_attempts:
                try:
                    if u:
                        ftp.login(u, p)
                    else:
                        ftp.login()
                    logged_in = True
                    break
                except Exception:
                    continue

            if logged_in:
                ftp_connected = True
                ftp.voidcmd("TYPE I")  # Binary mode

                # Target dirs to try: prioritize requested remote_dir, then smart fallback
                dirs_to_try = []
                if remote_dir:
                    clean_r = remote_dir.strip().rstrip("/\\")
                    dirs_to_try.append(clean_r)
                    dirs_to_try.append(clean_r.replace("/", "\\"))
                    dirs_to_try.append(clean_r.replace("\\", "/"))
                    if "SC777" in clean_r.upper():
                        # Automatic fallback to SECOM 797 Flashdisk
                        dirs_to_try.extend([
                            "/Flashdisk/SC797CE/Programs",
                            "/flashdisk/sc797ce/programs",
                            "\\Flashdisk\\SC797CE\\Programs",
                            "/Flashdisk/SC797CE/PROGRAMS"
                        ])
                    elif "SC797" in clean_r.upper():
                        # Automatic fallback to SECOM 777 Storage
                        dirs_to_try.extend([
                            "/Storage/SC777CE/Programs",
                            "/Storage/sc777ce/Programs",
                            "/storage/sc777ce/programs",
                            "\\Storage\\SC777CE\\Programs"
                        ])

                for c in CANDIDATE_PROGRAM_DIRS:
                    if c not in dirs_to_try:
                        dirs_to_try.append(c)

                cwd_success_dir = None
                found_prg_files = []

                for target_d in dirs_to_try:
                    try:
                        ftp.cwd(target_d)
                        cwd_success_dir = target_d
                    except Exception:
                        try:
                            ftp.cwd(target_d.replace("/", "\\"))
                            cwd_success_dir = target_d.replace("/", "\\")
                        except Exception:
                            continue

                    # Once cwd succeeds, list files in this folder
                    current_prgs = []

                    # Method 1: Windows CE LIST parsing
                    try:
                        raw_lines = []
                        ftp.retrlines("LIST", raw_lines.append)
                        for line in raw_lines:
                            line_str = line.strip()
                            if not line_str or "<DIR>" in line_str.upper():
                                continue
                            parts = line_str.split()
                            if len(parts) >= 4:
                                fname = " ".join(parts[3:])
                            elif parts:
                                fname = parts[-1]
                            else:
                                continue
                            if fname.upper().endswith(".PRG"):
                                current_prgs.append(fname)
                    except Exception as e_list:
                        logger.warning(f"LIST failed in {target_d}: {e_list}")

                    # Method 2: NLST fallback
                    if not current_prgs:
                        try:
                            items = ftp.nlst()
                            for item in items:
                                base = os.path.basename(item.replace("\\", "/"))
                                if base.upper().endswith(".PRG"):
                                    current_prgs.append(base)
                        except Exception as e_nlst:
                            logger.warning(f"NLST failed in {target_d}: {e_nlst}")

                    if current_prgs:
                        resolved_remote_dir = cwd_success_dir
                        found_prg_files = list(dict.fromkeys(current_prgs))
                        break

                # Download all found PRG files directly using relative filename
                if found_prg_files:
                    logger.info(f"Found {len(found_prg_files)} PRG files in {resolved_remote_dir}: {found_prg_files}")
                    for pf in found_prg_files:
                        local_path = os.path.join(ref_dir, pf)
                        try:
                            bio = io.BytesIO()
                            ftp.retrbinary(f"RETR {pf}", bio.write)
                            raw_bytes = bio.getvalue()
                            with open(local_path, "wb") as f_out:
                                f_out.write(raw_bytes)
                            downloaded.append({
                                "filename": pf,
                                "size_bytes": len(raw_bytes),
                                "remote_path": f"{resolved_remote_dir}/{pf}"
                            })
                        except Exception as dl_err:
                            logger.warning(f"Failed to download {pf}: {dl_err}")
                            failed.append({"filename": pf, "error": str(dl_err)})

                ftp.quit()
            else:
                ftp_error_msg = "Login FTP ditolak oleh kontroler."
        except Exception as e:
            ftp_error_msg = str(e)
            logger.warning(f"FTP download error for {machine_no} ({ip}): {e}")

    # Step 2: Parse and register all .PRG files found locally in ref_dir and out_dir
    custom_store = {}
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                custom_store = json.load(f)
        except Exception:
            custom_store = {}

    seen_program_nos = set()
    for scan_dir in [ref_dir, out_dir]:
        if not os.path.exists(scan_dir):
            continue
        for fname in sorted(os.listdir(scan_dir)):
            if fname.upper().endswith(".PRG"):
                f_path = os.path.join(scan_dir, fname)
                try:
                    with open(f_path, "rb") as pf:
                        prg_data = pf.read()
                    parsed = parse_prg_binary(prg_data)
                    p_no = parsed["program_no"]
                    if p_no in seen_program_nos:
                        continue
                    seen_program_nos.add(p_no)

                    parsed["machine_code"] = clean_no
                    parsed["filename"] = fname
                    parsed["source"] = "FTP_HMI" if any(d["filename"] == fname for d in downloaded) else "LOCAL_WORKSPACE"

                    # Store in programs_custom.json
                    custom_store[str(p_no)] = parsed

                    # Store in compiled cache
                    c_path = os.path.join(compiled_dir, f"M_{str(p_no).zfill(4)}.PRG")
                    with open(c_path, "wb") as cf:
                        cf.write(prg_data)

                    parsed_programs.append({
                        "program_number": p_no,
                        "program_name": parsed.get("program_name"),
                        "filename": fname,
                        "machine_code": clean_no,
                        "total_steps": len(parsed.get("steps", [])),
                        "file_size": len(prg_data)
                    })
                except Exception as parse_err:
                    logger.warning(f"Failed to parse {fname}: {parse_err}")

    # Save updated custom store
    try:
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(custom_store, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to write custom store: {e}")

    total_programs = len(parsed_programs)
    success = total_programs > 0 or len(downloaded) > 0

    if len(downloaded) > 0:
        msg = f"Berhasil mengunduh {len(downloaded)} berkas .PRG dari kontroler Mesin {clean_no} ({ip}) dan dimuat ke sistem!"
    elif total_programs > 0:
        msg = f"Ditemukan {total_programs} berkas .PRG di folder workspace Mesin {clean_no} dan berhasil dimuat ke sistem."
        if ftp_error_msg:
            msg += f" (Koneksi FTP langsung ke {ip} gagal/offline: {ftp_error_msg})"
    else:
        msg = f"Gagal mengunduh program: Kontroler Mesin {clean_no} di {ip}:{ftp_port} tidak merespon/offline ({ftp_error_msg or 'File .PRG tidak ditemukan di folder remote'})."

    return {
        "success": success,
        "machine_no": clean_no,
        "folder_name": folder_name,
        "ip_address": ip,
        "remote_dir": resolved_remote_dir,
        "downloaded_count": len(downloaded),
        "downloaded": downloaded,
        "failed": failed,
        "programs_loaded_count": total_programs,
        "programs": parsed_programs,
        "message": msg
    }
