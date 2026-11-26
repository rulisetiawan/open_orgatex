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
DA_TEX_ROOT = "/app/sc777ce_root" if os.path.isdir("/app/sc777ce_root/WORKSPACE_PROGRAM_MESIN") else os.path.abspath(os.path.join(BACKEND_DIR, "..", ".."))

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
    "TYPECONT.CNF",
    "TYPEFORM.CNF",
    "USERCONF.CNF",
    "PASSCODE.CNF"
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

def _decode_cnf_records(cnf_path: str, expected_len: Optional[int] = None) -> Dict[tuple, bytes]:
    """
    Decodes Btrieve RLE-compressed records from a SETEX .CNF file using CNFReader.
    Returns dict mapping (cat, sub, idx) -> raw_bytes.
    """
    import struct
    analisis_dir = os.path.join(DA_TEX_ROOT, "program", "Analisis")
    if analisis_dir not in sys.path:
        sys.path.append(analisis_dir)

    from cnf_decode import CNFReader
    reader = CNFReader(cnf_path)
    incoming = {f['next'] for f in reader.fragments.values() if f.get('next') and f['next'][1] != 255}
    allrecords: Dict[tuple, bytes] = {}
    for address in reader.fragments:
        if address in incoming:
            continue
        try:
            packed, _ = reader.chain(*address)
            raw, _ = reader.decompress(packed)
            if expected_len is not None and len(raw) != expected_len:
                continue
            if len(raw) >= 6:
                key = struct.unpack_from('<3H', raw)
                allrecords[key] = raw
        except Exception:
            continue
    return allrecords


def decode_typeconf_if_possible(
    typeconf_path: str,
    output_json_path: str,
    sample_prg_dir: Optional[str] = None
) -> bool:
    """
    Decodes raw TYPECONF.CNF to typeconf_functions.json strictly from TYPECONF.CNF
    (never from .AWL PLC logic files).
    Extracts:
      - functions (cat 3, sub 0): Function ID, name, parameter_count, parameter limits
      - parameters (cat 2, sub 0): Parameter definition ID, name, unit, scale
      - resources (cat 78): Column/Slot 1..8 definitions
      - groups (cat 1): Function groups & allowed lines/columns per Function ID
      - text_choices (cat 51): Discrete choices for mode-16 parameters
    Optionally enriches allowed `lines` from sample .PRG files in sample_prg_dir ONLY for
    Function IDs already defined in TYPECONF.CNF.
    """
    try:
        import struct
        import hashlib
        analisis_dir = os.path.join(DA_TEX_ROOT, "program", "Analisis")
        if analisis_dir not in sys.path:
            sys.path.append(analisis_dir)

        from cnf_decode import function as decode_fn, parameter as decode_param, txt as decode_txt

        allrecords = _decode_cnf_records(typeconf_path, expected_len=290)
        if not allrecords:
            raise ValueError("Tidak ada record 290-byte yang dapat didekode dari TYPECONF.CNF")

        funcs: Dict[str, Dict[str, Any]] = {}
        params: Dict[str, Dict[str, Any]] = {}
        resources: Dict[str, Dict[str, Any]] = {}
        groups: List[Dict[str, Any]] = []
        text_choices: Dict[str, List[Dict[str, Any]]] = {}

        for key, raw in allrecords.items():
            cat, sub, idx = key
            if cat == 3 and sub == 0:
                try:
                    fdata = decode_fn(raw)
                    fdata["lines"] = []
                    fdata["groups"] = []
                    funcs[str(idx)] = fdata
                except Exception:
                    continue
            elif cat == 2 and sub == 0:
                try:
                    params[str(idx)] = decode_param(raw)
                except Exception:
                    continue
            elif cat == 78:
                res_name = raw[27:48].split(b'\0', 1)[0].decode('cp437', errors='replace').strip()
                resources[str(idx)] = {
                    "id": idx,
                    "name": res_name or f"Slot {idx}",
                    "type": struct.unpack_from('<H', raw, 71)[0],
                    "disabled": bool(raw[76])
                }
            elif cat == 1:
                g_name = raw[27:48].split(b'\0', 1)[0].decode('cp437', errors='replace').strip()
                count = min(raw[76], 8)
                ids = list(struct.unpack_from('<8H', raw, 77))[:count]
                groups.append({
                    "name": g_name,
                    "line": raw[75],
                    "disabled": bool(raw[98]),
                    "ids": ids
                })
            elif cat == 51:
                group_id, val = struct.unpack_from('<Hf', raw, 48)
                t_str = decode_txt(raw[27:48])
                text_choices.setdefault(str(group_id), []).append({
                    "text": t_str,
                    "value": val,
                    "key": list(key)
                })

        # Map groups -> function lines & group names
        for fid_str, fdata in funcs.items():
            fid_int = int(fid_str)
            lines_set = {g["line"] for g in groups if not g["disabled"] and fid_int in g["ids"]}
            grp_names = [g["name"] for g in groups if not g["disabled"] and fid_int in g["ids"]]
            fdata["lines"] = sorted(lines_set)
            fdata["groups"] = grp_names

        # Enrich observed lines from machine's own .PRG files ONLY for functions defined in TYPECONF.CNF
        if sample_prg_dir and os.path.isdir(sample_prg_dir):
            for fname in sorted(os.listdir(sample_prg_dir)):
                if not fname.upper().endswith(".PRG"):
                    continue
                try:
                    with open(os.path.join(sample_prg_dir, fname), "rb") as pf:
                        b = pf.read()
                    if len(b) < 384 or b[:4] != bytes.fromhex("508fc2f5"):
                        continue
                    for off in range(384, len(b) - 64, 65):
                        line = b[off + 2]
                        if line:
                            fid_str = str(struct.unpack_from('<H', b, off + 4)[0])
                            if fid_str in funcs and line not in funcs[fid_str]["lines"]:
                                funcs[fid_str]["lines"] = sorted(set(funcs[fid_str]["lines"]) | {line})
                except Exception:
                    continue

        if funcs and params:
            with open(typeconf_path, "rb") as f_raw:
                cnf_sha = hashlib.sha256(f_raw.read()).hexdigest()

            export_data = {
                "functions": funcs,
                "parameters": params,
                "resources": resources,
                "groups": groups,
                "text_choices": text_choices,
                "cnf_sha256": cnf_sha,
                "source": os.path.basename(typeconf_path),
                "source_policy": "Function ID & parameters strictly decoded from Config/TYPECONF.CNF (never from .AWL PLC logic).",
                "generated_at": datetime.now().isoformat()
            }
            with open(output_json_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            logger.info(
                f"Decoded TYPECONF.CNF: {len(funcs)} functions, {len(params)} parameters, "
                f"{len(resources)} resources, {len(groups)} groups, {len(text_choices)} text_choices."
            )
            return True
    except Exception as e:
        logger.warning(f"Direct CNF decoding encountered error: {e}. Using baseline fallback.")

    # Fallback to copying baseline only when TYPECONF.CNF cannot be decoded
    if not os.path.exists(output_json_path) and os.path.exists(BASELINE_FUNCTIONS):
        shutil.copy2(BASELINE_FUNCTIONS, output_json_path)
        return True
    return False


def decode_userconf_if_possible(userconf_path: str, output_json_path: str) -> bool:
    """
    Decodes Config/USERCONF.CNF to extract custom main process labels (Label 1..20)
    and additional/Nachsatz process labels (NETRAL ULANG, SOAPING, FIXING, etc.).
    """
    try:
        import hashlib
        analisis_dir = os.path.join(DA_TEX_ROOT, "program", "Analisis")
        if analisis_dir not in sys.path:
            sys.path.append(analisis_dir)
        from cnf_decode import txt as decode_txt

        allrecords = _decode_cnf_records(userconf_path, expected_len=290)
        if not allrecords:
            return False

        main_labels: Dict[str, Dict[str, Any]] = {}
        nachsatz_labels: Dict[str, Dict[str, Any]] = {}

        for (cat, sub, idx), raw in sorted(allrecords.items()):
            if cat != 4:
                continue
            name_local = decode_txt(raw[6:27])
            name_en = decode_txt(raw[27:48]) or name_local
            entry = {
                "id": idx,
                "name_local": name_local,
                "name": name_en
            }
            if sub == 0:
                main_labels[str(idx)] = entry
            elif sub == 1:
                nachsatz_labels[str(idx)] = entry

        with open(userconf_path, "rb") as f_raw:
            sha = hashlib.sha256(f_raw.read()).hexdigest()

        export_data = {
            "source": os.path.basename(userconf_path),
            "sha256": sha,
            "main_labels": main_labels,
            "nachsatz_labels": nachsatz_labels,
            "generated_at": datetime.now().isoformat()
        }
        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Decoded USERCONF.CNF: {len(main_labels)} main labels, {len(nachsatz_labels)} nachsatz labels.")
        return True
    except Exception as e:
        logger.warning(f"USERCONF.CNF decoding failed: {e}")
        return False


def decode_machconf_if_possible(machconf_path: str, output_json_path: str) -> bool:
    """
    Decodes Config/MACHCONF.CNF metadata (machine-specific calibration/options summary).
    """
    try:
        import re
        import hashlib
        allrecords = _decode_cnf_records(machconf_path, expected_len=None)
        with open(machconf_path, "rb") as f_raw:
            raw_bytes = f_raw.read()
        sha = hashlib.sha256(raw_bytes).hexdigest()

        info_strings: List[str] = []
        for (_, _, _), rec in sorted(allrecords.items()):
            for m in re.findall(rb"[\x20-\x7e]{4,40}", rec):
                s = m.decode("cp1252", errors="ignore").strip()
                if s and s not in info_strings and any(c.isalpha() for c in s):
                    info_strings.append(s)
                    if len(info_strings) >= 25:
                        break
            if len(info_strings) >= 25:
                break

        export_data = {
            "source": os.path.basename(machconf_path),
            "sha256": sha,
            "size_bytes": len(raw_bytes),
            "record_count": len(allrecords),
            "metadata_strings": info_strings,
            "generated_at": datetime.now().isoformat()
        }
        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.warning(f"MACHCONF.CNF decoding failed: {e}")
        return False


def sync_machine_ready_config(machine_no: str, ip_address: Optional[str] = None):
    """
    Synchronizes downloaded HMI config files (.CNF) to 02_CONFIG_SIAP_PAKAI/.
    Strictly separates SECOM configuration files from .AWL PLC execution binaries:
      - Config/TYPECONF.CNF -> typeconf_functions.json (Function IDs, parameters, limits, slots, choices)
      - Config/CONFTEXT.CNF & FNLEGEND.CNF -> text & alarm metadata
      - Config/USERCONF.CNF -> userconf_labels.json (Label 1-20 & Nachsatz process labels)
      - Config/MACHCONF.CNF -> machconf_info.json (machine-specific settings)
      - Config/*.AWL -> PLC execution logic metadata only (NEVER used as Function ID source)
    """
    folder_name = normalize_folder_name(machine_no)
    m_dir = os.path.join(WORKSPACE_BASE, folder_name)
    raw_dir = os.path.join(m_dir, "01_CONFIG_DARI_HMI")
    dec_dir = os.path.join(m_dir, "02_CONFIG_SIAP_PAKAI")
    ref_prg_dir = os.path.join(m_dir, "03_CONTOH_PRG_DARI_HMI")
    os.makedirs(dec_dir, exist_ok=True)
    prof_file = os.path.join(dec_dir, "machine_profile.json")

    tc_file = os.path.join(raw_dir, "TYPECONF.CNF")
    ct_file = os.path.join(raw_dir, "CONFTEXT.CNF")
    fn_file = os.path.join(raw_dir, "FNLEGEND.CNF")
    uc_file = os.path.join(raw_dir, "USERCONF.CNF")
    mc_file = os.path.join(raw_dir, "MACHCONF.CNF")

    has_tc = os.path.exists(tc_file)
    has_ct = os.path.exists(ct_file)
    has_fn = os.path.exists(fn_file)
    has_uc = os.path.exists(uc_file)
    has_mc = os.path.exists(mc_file)

    target_func = os.path.join(dec_dir, "typeconf_functions.json")
    target_conf = os.path.join(dec_dir, "conftext_aligned.json")
    target_userconf = os.path.join(dec_dir, "userconf_labels.json")
    target_machconf = os.path.join(dec_dir, "machconf_info.json")

    # 1. Functions & Parameters strictly from TYPECONF.CNF
    if has_tc:
        decode_typeconf_if_possible(tc_file, target_func, sample_prg_dir=ref_prg_dir)
    elif not os.path.exists(target_func) and os.path.exists(BASELINE_FUNCTIONS):
        shutil.copy2(BASELINE_FUNCTIONS, target_func)

    # 2. Texts & Alarms dictionary (CONFTEXT.CNF / FNLEGEND.CNF)
    if not os.path.exists(target_conf) and os.path.exists(BASELINE_CONFTEXT):
        shutil.copy2(BASELINE_CONFTEXT, target_conf)

    # 3. Custom Program / Process Labels from USERCONF.CNF
    if has_uc:
        decode_userconf_if_possible(uc_file, target_userconf)

    # 4. Machine Parameters from MACHCONF.CNF
    if has_mc:
        decode_machconf_if_possible(mc_file, target_machconf)

    # Machine profile JSON
    prof_data = {}
    if os.path.exists(prof_file):
        try:
            with open(prof_file, "r", encoding="utf-8") as f:
                prof_data = json.load(f)
        except Exception:
            pass

    raw_files = os.listdir(raw_dir) if os.path.exists(raw_dir) else []
    awl_files = [f for f in raw_files if f.upper().endswith(".AWL")]

    prof_data.update({
        "machine_no": machine_no.upper(),
        "folder_name": folder_name,
        "ip_address": ip_address or prof_data.get("ip_address", ""),
        "has_custom_hmi_config": (has_tc and has_ct),
        "has_typeconf": has_tc,
        "has_conftext": has_ct,
        "has_fnlegend": has_fn,
        "has_userconf": has_uc,
        "has_machconf": has_mc,
        "has_awl_plc_program": len(awl_files) > 0,
        "awl_files": awl_files,
        "config_sources": {
            "program_recipes": "PROGRAMS/*.PRG",
            "function_definitions": "Config/TYPECONF.CNF" if has_tc else "baseline_typeconf",
            "function_texts_alarms": [f for f, ok in [("Config/CONFTEXT.CNF", has_ct), ("Config/FNLEGEND.CNF", has_fn)] if ok],
            "custom_process_labels": "Config/USERCONF.CNF" if has_uc else None,
            "machine_parameters": "Config/MACHCONF.CNF" if has_mc else None,
            "plc_execution_logic_only": [f"Config/{f}" for f in awl_files]
        },
        "status": "ready" if (has_tc and has_ct) else "baseline_ready",
        "last_synced_at": datetime.now().isoformat(),
        "files_in_hmi_dir": raw_files
    })

    with open(prof_file, "w", encoding="utf-8") as f:
        json.dump(prof_data, f, indent=2)

def fetch_machine_config_from_hmi(
    ip: str,
    machine_no: str,
    ftp_port: int = 21,
    remote_dir: Optional[str] = None,
    timeout: float = 4.0
) -> Dict[str, Any]:
    """
    Connects to SETEX HMI via FTP and downloads TYPECONF.CNF, CONFTEXT.CNF, MACHCONF.CNF,
    as well as all PLC program statement list files (.AWL).
    Saves them to WORKSPACE_PROGRAM_MESIN/<NAMA_MESIN>/01_CONFIG_DARI_HMI/
    and runs synchronization to 02_CONFIG_SIAP_PAKAI/.
    """
    folder_name = normalize_folder_name(machine_no)
    m_dir = ensure_machine_workspace(machine_no)
    raw_dir = os.path.join(m_dir, "01_CONFIG_DARI_HMI")

    logger.info(f"Starting auto-fetch config & AWL for {machine_no} ({folder_name}) at {ip}:{ftp_port}")

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

        # Step 2: Auto-detect remote directory where .CNF & .AWL files reside
        check_dirs = list(CANDIDATE_CONFIG_DIRS)
        if remote_dir:
            normalized_remote = remote_dir.rstrip("/")
            if normalized_remote and normalized_remote not in check_dirs:
                check_dirs.insert(0, normalized_remote)

        remote_files_map = {}
        for cand_dir in check_dirs:
            try:
                nlst = ftp.nlst(cand_dir)
                cand_map = {}
                for item in nlst:
                    base_name = os.path.basename(item.replace("\\", "/"))
                    cand_map[base_name.upper()] = base_name
                
                # Check if TYPECONF.CNF, CONFTEXT.CNF, or any .CNF/.AWL is in this candidate folder
                has_target = any(target in cand_map for target in TARGET_CONFIG_FILES)
                has_awl_or_cnf = any(f.endswith(".AWL") or f.endswith(".CNF") for f in cand_map)
                if has_target or has_awl_or_cnf:
                    resolved_remote_dir = cand_dir
                    remote_files_map = cand_map
                    break
            except Exception:
                continue

        if not resolved_remote_dir:
            try:
                cur_nlst = ftp.nlst()
                cand_map = {os.path.basename(i.replace("\\", "/")).upper(): os.path.basename(i.replace("\\", "/")) for i in cur_nlst}
                if any(target in cand_map for target in TARGET_CONFIG_FILES) or any(f.endswith(".AWL") or f.endswith(".CNF") for f in cand_map):
                    resolved_remote_dir = "/"
                    remote_files_map = cand_map
            except Exception:
                pass

        if not resolved_remote_dir or not remote_files_map:
            raise FileNotFoundError(
                f"Tidak ditemukan folder konfigurasi HMI yang berisi file .CNF / .AWL pada kontroler {ip}. "
                f"Direktori yang dicek: {', '.join(check_dirs)}"
            )

        # Step 3: Change directory to resolved_remote_dir and download .CNF and .AWL files
        try:
            ftp.cwd(resolved_remote_dir)
        except Exception:
            pass

        # Identify all files to download: Standard TARGET_CONFIG_FILES + all *.CNF + all *.AWL
        download_targets = set(TARGET_CONFIG_FILES)
        for fname_upper in remote_files_map:
            if fname_upper.endswith(".CNF") or fname_upper.endswith(".AWL"):
                download_targets.add(fname_upper)

        # Sort so primary CNFs come first, then AWLs
        sorted_targets = sorted(
            download_targets,
            key=lambda x: (0 if x in TARGET_CONFIG_FILES else (1 if x.endswith(".AWL") else 2), x)
        )

        for target in sorted_targets:
            if target in remote_files_map:
                filename = remote_files_map[target]
                local_file = os.path.join(raw_dir, filename)
                try:
                    with open(local_file, "wb") as f_out:
                        ftp.retrbinary(f"RETR {filename}", f_out.write)
                    size = os.path.getsize(local_file)
                    file_category = "AWL" if target.endswith(".AWL") else "CNF"
                    downloaded.append({
                        "filename": filename,
                        "type": file_category,
                        "size_bytes": size,
                        "remote_path": f"{resolved_remote_dir}/{filename}"
                    })
                    logger.info(f"Downloaded {file_category} {filename} ({size} bytes) from {resolved_remote_dir}/{filename}")
                except Exception as dl_err:
                    failed.append({"filename": filename, "error": str(dl_err)})
                    logger.warning(f"Failed to download {filename}: {dl_err}")

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
                try:
                    ftp.quit()
                except Exception:
                    try:
                        ftp.close()
                    except Exception:
                        pass
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
                try:
                    ftp.set_pasv(True)
                except Exception:
                    pass
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

                # Support OrgaTEX Central Network Share
                if ip == "192.168.1.95" or "DA01" in clean_no or "NETWORK" in str(remote_dir).upper():
                    dirs_to_try.extend([
                        "/Network/F/OT/PROGRAMS",
                        "/Network/F/OT/PROGRAM",
                        "/Network/F/OT/PROGS",
                        "/Network/F/OT/BATCH",
                        "\\Network\\F\\OT\\PROGRAMS"
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

                            # Mirror to fallback or host if running in Docker
                            alt_dir = "/app/WORKSPACE_PROGRAM_MESIN" if "/sc777ce_root" in ref_dir else "/app/sc777ce_root/WORKSPACE_PROGRAM_MESIN"
                            alt_ref = os.path.join(alt_dir, folder_name, "03_CONTOH_PRG_DARI_HMI")
                            if os.path.isdir(alt_dir):
                                os.makedirs(alt_ref, exist_ok=True)
                                try:
                                    with open(os.path.join(alt_ref, pf), "wb") as f_alt:
                                        f_alt.write(raw_bytes)
                                except Exception:
                                    pass

                            downloaded.append({
                                "filename": pf,
                                "size_bytes": len(raw_bytes),
                                "remote_path": f"{resolved_remote_dir}/{pf}"
                            })
                        except Exception as dl_err:
                            logger.warning(f"Failed to download {pf}: {dl_err}")
                            failed.append({"filename": pf, "error": str(dl_err)})

                try:
                    ftp.quit()
                except Exception:
                    try:
                        ftp.close()
                    except Exception:
                        pass
            else:
                ftp_error_msg = "Login FTP ditolak oleh kontroler."
        except Exception as e:
            ftp_error_msg = str(e)
            logger.warning(f"FTP download error for {machine_no} ({ip}): {e}")

    # Step 2: Parse and register all .PRG files found locally in ref_dir and out_dir
    raw_store = {}
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                raw_store = json.load(f)
        except Exception:
            raw_store = {}

    # Migrate any legacy flat keys ("141") into machine-scoped keys ("5A:141") so machines never collide
    custom_store: Dict[str, Any] = {}
    for k, v in raw_store.items():
        if not isinstance(v, dict):
            continue
        v_mc = str(v.get("machine_code") or (k.split(":", 1)[0] if ":" in str(k) else "TD12")).strip().upper().replace("MESIN_", "") or "TD12"
        v_pno = v.get("program_no") or (k.split(":", 1)[1] if ":" in str(k) else k)
        try:
            v_pno_norm = str(int(str(v_pno).strip()))
        except Exception:
            v_pno_norm = str(v_pno).strip()
        v["machine_code"] = v_mc
        custom_store[f"{v_mc}:{v_pno_norm}"] = v

    machine_compiled_dir = os.path.join(compiled_dir, clean_no)
    os.makedirs(machine_compiled_dir, exist_ok=True)

    seen_program_nos = set()
    machine_parsed_entries: List[Dict[str, Any]] = []
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
                    p_no = int(parsed["program_no"])
                    if p_no in seen_program_nos:
                        continue
                    seen_program_nos.add(p_no)

                    parsed["machine_code"] = clean_no
                    parsed["filename"] = fname
                    parsed["source"] = "FTP_HMI" if any(d["filename"] == fname for d in downloaded) else "LOCAL_WORKSPACE"

                    # Store in programs_custom.json keyed by MACHINE:PROGRAM_NO
                    custom_store[f"{clean_no}:{p_no}"] = parsed

                    # Store in machine-scoped compiled cache
                    c_path = os.path.join(machine_compiled_dir, f"M_{str(p_no).zfill(4)}.PRG")
                    with open(c_path, "wb") as cf:
                        cf.write(prg_data)

                    machine_parsed_entries.append(parsed)
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

    # Synchronize updated programs AND their steps/functions/parameters to DB (UPDATE existing, NEVER create duplicate on same machine)
    try:
        from ..database import get_db
        from ..models.schema_pg import ProgramComponent, ProgramComponentItem, ProgramComponent2Group, Step, StepFunction, StepFunctionParameter
        from ..services.db_sync_service import DBSyncService

        for db in get_db():
            # Load all existing Level 1 programs for this machine and deduplicate if any exist
            existing_rows = [
                r for r in db.query(ProgramComponent).filter(ProgramComponent.level == 1).order_by(ProgramComponent.id.asc()).all()
                if DBSyncService._norm_machine(r.machine_code) == clean_no
            ]
            by_pno: Dict[str, ProgramComponent] = {}
            for r in existing_rows:
                n_norm = DBSyncService._norm_prog_no(r.number)
                if n_norm in by_pno:
                    keeper = by_pno[n_norm]
                    db.query(ProgramComponentItem).filter(
                        ProgramComponentItem.parent_component_id == r.id
                    ).update({"parent_component_id": keeper.id}, synchronize_session=False)
                    db.query(ProgramComponentItem).filter(
                        ProgramComponentItem.program_component_id == r.id
                    ).update({"program_component_id": keeper.id}, synchronize_session=False)
                    db.query(ProgramComponent2Group).filter(
                        ProgramComponent2Group.program_component_id == r.id
                    ).update({"program_component_id": keeper.id}, synchronize_session=False)
                    db.delete(r)
                else:
                    r.machine_code = clean_no
                    r.number = n_norm
                    by_pno[n_norm] = r
            db.flush()

            for parsed in machine_parsed_entries:
                p_no_str = str(int(parsed["program_no"]))
                p_row = by_pno.get(p_no_str)
                if p_row:
                    # UPDATE existing record in place — never insert a duplicate
                    if parsed.get("program_name"):
                        p_row.name = parsed["program_name"]
                    p_row.machine_code = clean_no
                    p_row.number = p_no_str
                    p_row.modification_time = datetime.utcnow()
                else:
                    p_row = ProgramComponent(
                        number=p_no_str,
                        name=parsed.get("program_name") or f"PROGRAM #{p_no_str}",
                        level=1,
                        type=1,
                        machine_code=clean_no
                    )
                    db.add(p_row)
                    db.flush()
                    by_pno[p_no_str] = p_row

                steps_data = parsed.get("steps") or []
                if steps_data:
                    # Replace existing steps cleanly (ORM cascade removes step_functions & parameters)
                    for old_s in list(p_row.steps):
                        db.delete(old_s)
                    db.flush()

                    for st in steps_data:
                        new_s = Step(
                            position=int(st.get("step_no") or 1),
                            parent_component_id=p_row.id,
                            label=str(st.get("label") or f"Langkah {st.get('step_no', 1)}")[:100],
                            summary_temp=st.get("summary_temp"),
                            summary_time_min=st.get("summary_time_min") or 0.0,
                            summary_water_l=st.get("summary_water_l") or 0.0,
                        )
                        db.add(new_s)
                        db.flush()

                        for fn in st.get("functions") or []:
                            new_fn = StepFunction(
                                step_id=new_s.id,
                                resource_number=int(fn.get("column") or 1),
                                function_number=int(fn.get("function_id") or 0),
                                function_name=str(fn.get("name") or "")[:100],
                                acknowledge=int(fn.get("flags") or 0),
                            )
                            db.add(new_fn)
                            db.flush()

                            for p_idx, p_val in enumerate(fn.get("params") or []):
                                try:
                                    f_val = float(p_val)
                                except Exception:
                                    f_val = 0.0
                                db.add(StepFunctionParameter(
                                    step_function_id=new_fn.id,
                                    function_parameter_number=p_idx + 1,
                                    value=f_val,
                                ))
            db.commit()
            break

        # Also mirror updated entries into local SQLite so offline DB stays consistent
        for parsed in machine_parsed_entries:
            DBSyncService.mirror_program_to_sqlite(parsed)
    except Exception as e_db:
        logger.warning(f"Failed to sync ProgramComponent & steps to PostgreSQL: {e_db}")

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
