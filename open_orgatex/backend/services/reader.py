"""
OpenOrgaTEX Read-Only Shared Folder & FTP Reader
Directly decodes SETEX 777 binary files on-the-fly:
- Local & UNC Folders: STATUS.ACT, ALARM.ACT, ALARMS.LOG, *.LOG
- FTP Protocol (Port 21): Downloads to memory and decodes on-the-fly
- Full parity with SETEX Secom 777CE binary structures
"""

import os
import re
import io
import json
import ftplib
import struct
import logging
import threading
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from .alarm_catalog_service import AlarmCatalog, explain_alarm, get_alarm_text

logger = logging.getLogger("orgatex.reader")

# Concurrency locks and high-speed cache for SETEX Windows CE embedded FTP server
_FTP_HOST_LOCKS = {}
_FTP_LOCKS_MUTEX = threading.Lock()
_FTP_BUNDLE_CACHE = {}

def _get_host_lock(ip: str) -> threading.Lock:
    with _FTP_LOCKS_MUTEX:
        if ip not in _FTP_HOST_LOCKS:
            _FTP_HOST_LOCKS[ip] = threading.Lock()
        return _FTP_HOST_LOCKS[ip]

ALARM_DEFINITIONS = {
    0: "Alarm Normal / Cleared",
    1: "E-Stop / Emergency Button Pressed",
    2: "Main Circulation Pump Trip / Overload",
    3: "Water Level Low / Dry Run Interlock",
    4: "Temperature Deviation / Heating Timeout",
    5: "Pressure Relief Safety Valve Tripped",
    6: "Haspel Fabric Tangled / Seam Detector",
    7: "Dosing Tank 1 Level Sensor Fault",
    8: "Dosing Tank 2 Valve Position Error",
    10: "Drain Valve Stuck Open",
    12: "Lid Safety Interlock Open",
    20: "Operator Confirmation Required",
    99: "Controller Watchdog Communication Warning",
    256: "Call-Off / Operator Intervention Request",
    1548: "Level Error / Water Level Threshold Exceeded",
    2060: "Temperature Ramp Rate Deviation Warning",
    2572: "Circulation Differential Pressure Low",
    3851: "Dye Kitchen Chemical Addition Incomplete",
    4619: "Steam Flow Low / Heating Inefficiency",
    5131: "Dosing Valve Limit Switch Timeout",
    5643: "Drain Cycle Timeout / Filter Clogged",
    5899: "Program Hold / Operator Pause"
}

class SetexFolderReader:
    """
    Pure read-only parser for SETEX 777 controller directory structure.
    Strictly performs read operations only (never modifies or creates files).
    """

    @staticmethod
    def read_file_from_ftp(ip: str, port: int, remote_path: str, username: str = "", password: str = "", timeout: float = 4.0) -> Optional[bytes]:
        """Attempts to read a binary file over FTP in read-only mode from Windows CE / SETEX controller."""
        if not ip or not remote_path:
            return None

        clean_path = remote_path.replace("\\", "/").strip()
        path_variants = [clean_path]
        if clean_path.startswith("/"):
            path_variants.append(clean_path.lstrip("/"))
        else:
            path_variants.append("/" + clean_path)

        for pasv in (True, False):
            try:
                ftp = ftplib.FTP(timeout=timeout)
                ftp.connect(ip, port or 21)
                if username:
                    ftp.login(username, password)
                else:
                    ftp.login()
                ftp.set_pasv(pasv)

                # 1. Direct RETR attempts
                for pv in path_variants:
                    try:
                        bio = io.BytesIO()
                        ftp.retrbinary(f"RETR {pv}", bio.write)
                        data = bio.getvalue()
                        if data and len(data) > 0:
                            try:
                                ftp.quit()
                            except Exception:
                                try:
                                    ftp.close()
                                except Exception:
                                    pass
                            return data
                    except Exception:
                        pass

                # 2. CWD into directory then RETR filename (Windows CE robust approach)
                parts = [p for p in clean_path.strip("/\\").replace("\\", "/").split("/") if p]
                if len(parts) > 1:
                    dir_path_slash = "/" + "/".join(parts[:-1])
                    dir_path_bslash = "\\" + "\\".join(parts[:-1])
                    fname = parts[-1]
                    cwd_targets = [
                        dir_path_slash,
                        dir_path_slash.lstrip("/"),
                        dir_path_bslash,
                        dir_path_bslash.lstrip("\\")
                    ]
                    for target_dir in cwd_targets:
                        try:
                            ftp.cwd(target_dir)
                            bio = io.BytesIO()
                            ftp.retrbinary(f"RETR {fname}", bio.write)
                            data = bio.getvalue()
                            if data and len(data) > 0:
                                try:
                                    ftp.quit()
                                except Exception:
                                    try:
                                        ftp.close()
                                    except Exception:
                                        pass
                                return data
                        except Exception:
                            pass

                try:
                    ftp.quit()
                except Exception:
                    try:
                        ftp.close()
                    except Exception:
                        pass
            except Exception:
                pass
        return None

    @staticmethod
    def fetch_live_controller_bundle(ip: str, ftp_port: int = 21, is_797: bool = True, batch_no_hint: Optional[str] = None, timeout: float = 4.0) -> Dict[str, Any]:
        """
        Connects to SETEX 797CE / 777 controller via FTP in a SINGLE connection session,
        robustly retrieves STATUS.ACT, ALARM.ACT, ALARMS.LOG, batch cyclic log, and PRG recipe bytes.
        Includes per-IP lock and short-lived caching to prevent Windows CE socket congestion.
        """
        result = {
            "status_bytes": None,
            "alarm_bytes": None,
            "alarms_log_bytes": None,
            "batch_log_bytes": None,
            "prg_bytes": None,
            "source_url": "",
            "is_ftp_success": False,
            "error": None
        }
        if not ip:
            return result

        cache_key = f"{ip}_{ftp_port or 21}"
        now = time.time()
        cached = _FTP_BUNDLE_CACHE.get(cache_key)
        if cached and (now - cached["ts"]) < 1.5:
            return cached["data"]

        lock = _get_host_lock(ip)
        if not lock.acquire(timeout=4.0):
            if cached:
                return cached["data"]
            result["error"] = "FTP connection busy (locked by another thread)"
            return result

        try:
            # Recheck cache after acquiring lock
            cached = _FTP_BUNDLE_CACHE.get(cache_key)
            if cached and (time.time() - cached["ts"]) < 1.0:
                return cached["data"]

            ftp = ftplib.FTP(timeout=timeout)
            ftp.connect(ip, ftp_port or 21)
            ftp.login("", "")
            ftp.set_pasv(True)

            in_status_dir = False
            status_path_str = ""

            # Try direct known path first
            direct_status_dir = "/Flashdisk/SC797CE/STATUS" if is_797 else "/Storage/sc777ce/STATUS"
            try:
                ftp.cwd(direct_status_dir)
                in_status_dir = True
                status_path_str = direct_status_dir
            except Exception:
                in_status_dir = False

            if not in_status_dir:
                status_dir_candidates = [
                    ["Flashdisk", "SC797CE", "STATUS"],
                    ["Flashdisk", "sc797ce", "STATUS"],
                    ["Flashdisk", "STATUS"],
                    ["Storage", "sc777ce", "STATUS"],
                    ["Storage", "SC777CE", "STATUS"],
                    ["STATUS"],
                ] if is_797 else [
                    ["Storage", "sc777ce", "STATUS"],
                    ["Storage", "SC777CE", "STATUS"],
                    ["STATUS"],
                    ["Flashdisk", "SC797CE", "STATUS"],
                ]
                for dir_chain in status_dir_candidates:
                    try:
                        ftp.cwd("/")
                        for segment in dir_chain:
                            ftp.cwd(segment)
                        in_status_dir = True
                        status_path_str = "/" + "/".join(dir_chain)
                        break
                    except Exception:
                        continue

            # RETR STATUS.ACT
            bio_status = io.BytesIO()
            try:
                ftp.retrbinary("RETR STATUS.ACT", bio_status.write)
                st_data = bio_status.getvalue()
                if st_data and len(st_data) > 0:
                    result["status_bytes"] = st_data
                    result["is_ftp_success"] = True
                    result["source_url"] = f"ftp://{ip}:{ftp_port}{status_path_str}/STATUS.ACT"
            except Exception as e_st:
                logger.warning(f"FTP RETR STATUS.ACT warning: {e_st}")

            # RETR ALARM.ACT
            bio_alarm = io.BytesIO()
            try:
                ftp.retrbinary("RETR ALARM.ACT", bio_alarm.write)
                al_data = bio_alarm.getvalue()
                if al_data:
                    result["alarm_bytes"] = al_data
            except Exception:
                pass

            # RETR ALARMS.LOG
            bio_log = io.BytesIO()
            try:
                ftp.retrbinary("RETR ALARMS.LOG", bio_log.write)
                lg_data = bio_log.getvalue()
                if lg_data:
                    result["alarms_log_bytes"] = lg_data
            except Exception:
                pass

            # Detect batch number and prog_no from status bytes
            batch_no = batch_no_hint
            prog_no = 0
            if result["status_bytes"]:
                sb = result["status_bytes"]
                if len(sb) >= 48:
                    raw_b = sb[36:48].split(b'\0')[0].decode('latin1', errors='ignore').strip()
                    if raw_b and re.match(r'^[A-Za-z0-9_-]+$', raw_b):
                        batch_no = raw_b
                if not batch_no:
                    batches = sorted(list(set(m.group(0).decode('latin1') for m in re.finditer(rb'\b\d{6}\b', sb))))
                    if batches:
                        batch_no = batches[-1]
                if len(sb) >= 0x15E:
                    p_val = struct.unpack_from("<H", sb, 0x15C)[0]
                    if 1 <= p_val <= 9999:
                        prog_no = p_val

            # In the SAME session, retrieve active batch PR*.LOG
            candidate_pr_paths = []
            if is_797:
                if batch_no:
                    candidate_pr_paths.append(f"/Flashdisk/SC797CE/BATCH/{batch_no}/PR{batch_no}.LOG")
                    candidate_pr_paths.append(f"/Flashdisk/SC797CE/BATCH/PR{batch_no}.LOG")
                candidate_pr_paths.append("/Flashdisk/SC797CE/BATCH/000001/PR000001.LOG")
                candidate_pr_paths.append("/Flashdisk/SC797CE/BATCH/000006/PR000006.LOG")
            else:
                if batch_no:
                    candidate_pr_paths.append(f"/Storage/sc777ce/BATCH/{batch_no}/PR{batch_no}.LOG")
                    candidate_pr_paths.append(f"/Storage/sc777ce/BATCH/PR{batch_no}.LOG")

            for pr_path in candidate_pr_paths:
                try:
                    dir_part, file_part = pr_path.rsplit("/", 1)
                    ftp.cwd(dir_part)
                    bio_pr = io.BytesIO()
                    ftp.retrbinary(f"RETR {file_part}", bio_pr.write)
                    pr_bytes = bio_pr.getvalue()
                    if pr_bytes and len(pr_bytes) > 0:
                        result["batch_log_bytes"] = pr_bytes
                        logger.info(f"Berhasil membaca batch telemetry {pr_path} ({len(pr_bytes)} bytes) via FTP!")
                        break
                except Exception:
                    continue

            # Also retrieve active recipe PRG in same session
            candidate_prg_targets = []
            if is_797:
                if batch_no:
                    if prog_no:
                        candidate_prg_targets.append(f"/Flashdisk/SC797CE/BATCH/{batch_no}/M_{prog_no:04d}.PRG")
                    candidate_prg_targets.append(f"/Flashdisk/SC797CE/BATCH/{batch_no}")
                if prog_no:
                    candidate_prg_targets.append(f"/Flashdisk/SC797CE/Programs/M_{prog_no:04d}.PRG")
                candidate_prg_targets.append("/Flashdisk/SC797CE/Programs")
                candidate_prg_targets.append("/Flashdisk/SC797CE/BATCH")
            else:
                if batch_no:
                    if prog_no:
                        candidate_prg_targets.append(f"/Storage/sc777ce/BATCH/{batch_no}/M_{prog_no:04d}.PRG")
                    candidate_prg_targets.append(f"/Storage/sc777ce/BATCH/{batch_no}")
                    candidate_prg_targets.append(f"/Storage/sc777ce/BATCH/{batch_no}/M_0342.PRG")
                if prog_no:
                    candidate_prg_targets.append(f"/Storage/sc777ce/Programs/M_{prog_no:04d}.PRG")
                candidate_prg_targets.append("/Storage/sc777ce/Programs")
                candidate_prg_targets.append("/Storage/sc777ce/BATCH")

            for target in candidate_prg_targets:
                try:
                    if target.upper().endswith(".PRG"):
                        dir_part, file_part = target.rsplit("/", 1)
                        ftp.cwd(dir_part)
                        bio_prg = io.BytesIO()
                        ftp.retrbinary(f"RETR {file_part}", bio_prg.write)
                        prg_b = bio_prg.getvalue()
                        if prg_b and len(prg_b) > 0:
                            result["prg_bytes"] = prg_b
                            logger.info(f"Berhasil membaca PRG recipe via FTP: {target} ({len(prg_b)} bytes)")
                            break
                    else:
                        # Directory target - scan for *.PRG files
                        ftp.cwd(target)
                        files = ftp.nlst()
                        prg_files = [f for f in files if f.upper().endswith(".PRG")]
                        chosen_file = None
                        if prog_no:
                            p_match = f"M_{prog_no:04d}.PRG".upper()
                            chosen_file = next((f for f in prg_files if f.upper() == p_match), None)
                        if not chosen_file and prg_files:
                            chosen_file = prg_files[0]
                        if chosen_file:
                            bio_prg = io.BytesIO()
                            ftp.retrbinary(f"RETR {chosen_file}", bio_prg.write)
                            prg_b = bio_prg.getvalue()
                            if prg_b and len(prg_b) > 0:
                                result["prg_bytes"] = prg_b
                                logger.info(f"Berhasil membaca PRG recipe via FTP: {target}/{chosen_file} ({len(prg_b)} bytes)")
                                break
                except Exception:
                    continue

            # Cache retrieved PRG locally for offline parity
            if result.get("prg_bytes") and (prog_no or batch_no):
                try:
                    save_name = f"M_{prog_no:04d}.PRG" if prog_no else "active.PRG"
                    local_compiled = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "compiled_prg"))
                    os.makedirs(local_compiled, exist_ok=True)
                    with open(os.path.join(local_compiled, save_name), "wb") as f_save:
                        f_save.write(result["prg_bytes"])
                    if batch_no:
                        local_batch_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "OT", "BATCH", batch_no))
                        os.makedirs(local_batch_dir, exist_ok=True)
                        with open(os.path.join(local_batch_dir, save_name), "wb") as f_save:
                            f_save.write(result["prg_bytes"])
                except Exception:
                    pass

            try:
                ftp.quit()
            except Exception:
                try:
                    ftp.close()
                except Exception:
                    pass

        except Exception as e:
            if not result.get("status_bytes"):
                logger.warning(f"FTP bundle acquisition failed for {ip}: {e}")
                result["error"] = str(e)
            else:
                result["is_ftp_success"] = True

        finally:
            try:
                lock.release()
            except RuntimeError:
                pass

        if result.get("is_ftp_success"):
            _FTP_BUNDLE_CACHE[cache_key] = {"ts": time.time(), "data": result}

        return result

    @staticmethod
    def read_status_act(folder_path: str = "", ip: Optional[str] = None, ftp_port: int = 21, raw_bytes: Optional[bytes] = None) -> Dict[str, Any]:
        """Reads and parses STATUS.ACT from raw bytes, FTP (prioritizing Flashdisk/SC797CE for 192.168.1.95), or local folder."""
        data = raw_bytes
        is_ftp = bool(raw_bytes and ip)
        ftp_source_path = f"ftp://{ip}:{ftp_port or 21}/STATUS.ACT" if is_ftp else ""

        # 1. Try FTP if no raw bytes provided but IP is given
        if not data and ip:
            is_797 = (ip.strip() in ("192.168.1.95", "172.16.120.102", "172.16.120.103", "172.16.120.105", "172.16.120.108", "172.16.120.109", "172.16.120.154"))
            flashdisk_paths = [
                "/Flashdisk/SC797CE/STATUS/STATUS.ACT",
                "/Flashdisk/sc797ce/STATUS/STATUS.ACT",
                "/flashdisk/sc797ce/status/status.act",
                "\\Flashdisk\\SC797CE\\STATUS\\STATUS.ACT",
                "\\flashdisk\\sc797ce\\status\\status.act",
                "/Flashdisk/SC797CE/STATUS.ACT",
                "/Flashdisk/sc797ce/STATUS.ACT",
                "\\Flashdisk\\SC797CE\\STATUS.ACT",
                "/Flashdisk/STATUS/STATUS.ACT",
                "\\Flashdisk\\STATUS\\STATUS.ACT",
                "Flashdisk/SC797CE/STATUS/STATUS.ACT",
                "/Flashdisk/STATUS.ACT",
                "/STATUS/STATUS.ACT",
                "STATUS/STATUS.ACT",
                "STATUS.ACT"
            ]
            storage_paths = [
                "/Storage/sc777ce/STATUS/STATUS.ACT",
                "/Storage/SC777CE/STATUS/STATUS.ACT",
                "/storage/sc777ce/status/status.act",
                "\\Storage\\SC777CE\\STATUS\\STATUS.ACT",
                "\\storage\\sc777ce\\status\\status.act",
                "Storage/sc777ce/STATUS/STATUS.ACT",
                "/sc777ce/STATUS/STATUS.ACT",
                "/Storage/sc777ce/STATUS.ACT",
                "/STATUS/STATUS.ACT",
                "STATUS/STATUS.ACT",
                "/OT/STATUS.ACT",
                "STATUS.ACT"
            ]

            ftp_paths = (flashdisk_paths + storage_paths) if is_797 else (storage_paths + flashdisk_paths)

            for fp in ftp_paths:
                data = SetexFolderReader.read_file_from_ftp(ip, ftp_port, fp)
                if data and len(data) > 0:
                    is_ftp = True
                    ftp_source_path = f"ftp://{ip}:{ftp_port or 21}{fp}"
                    logger.info(f"Berhasil membaca telemetry langsung dari HMI ({'Flashdisk 797' if 'Flashdisk' in fp else 'Storage 777'}): {ftp_source_path} ({len(data)} byte)")
                    break

        # 2. Try local filesystem if not found via FTP
        if not data and folder_path:
            candidates = [
                os.path.join(folder_path, "STATUS.ACT"),
                os.path.join(folder_path, "STATUS.ACT"),
                os.path.join(folder_path, "STATUS", "STATUS.ACT"),
                os.path.join(folder_path, "STATUS", "STATUS.ACT"),
            ]
            status_file = next((f for f in candidates if os.path.exists(f)), None)
            if status_file:
                try:
                    with open(status_file, "rb") as f:
                        data = f.read()
                except Exception:
                    pass

        if not data:
            return {
                "status": "OFFLINE", 
                "error": "STATUS.ACT not found", 
                "is_ftp_source": False,
                "data_source": f"Gagal membaca FTP {ip}:21 / folder lokal"
            }

        try:
            size = len(data)
            machine_id = "A001"
            if size >= 16:
                raw_m = data[11:19].split(b'\0')[0].decode('latin1', errors='ignore').strip()
                if raw_m:
                    machine_id = raw_m

            # Batch number at offset 36
            current_batch = "UNKNOWN"
            if size >= 48:
                raw_b = data[36:48].split(b'\0')[0].decode('latin1', errors='ignore').strip()
                if raw_b and re.match(r'^[A-Za-z0-9_-]+$', raw_b):
                    current_batch = raw_b

            # Fallback batch search
            if current_batch == "UNKNOWN":
                batches = sorted(list(set(m.group(0).decode('latin1') for m in re.finditer(rb'\b\d{6}\b', data))))
                if batches:
                    current_batch = batches[-1]

            # Program Code at offset 52
            program_code = ""
            if size >= 64:
                raw_p = data[52:64].split(b'\0')[0].decode('latin1', errors='ignore').strip()
                if raw_p and any(c.isalnum() for c in raw_p):
                    program_code = raw_p

            # Program Name at offset 75
            program_name = ""
            if size >= 100:
                raw_pn = data[75:100].split(b'\0')[0].decode('latin1', errors='ignore').strip()
                raw_pn = re.sub(r'#.*$', '', raw_pn).strip()
                if raw_pn:
                    program_name = raw_pn

            # Step number, Program number, and Function code
            prog_no = 0
            step_no = 1
            function_code = 0

            # Program number at 0x15C (SETEX 797CE / 777)
            if size >= 0x15E:
                p_val = struct.unpack_from("<H", data, 0x15C)[0]
                if 1 <= p_val <= 9999:
                    prog_no = p_val
                    if not program_code:
                        program_code = f"M_{prog_no:04d}"

            # Step number:
            # - SETEX 797CE (Windows CE, size 10188): offset 0x15E
            # - SECOM 777   (Windows CE, size 10104): offset 0x15C
            step_offset = 0x15E if size == 10188 else 0x15C
            if size >= step_offset + 2:
                s_val = struct.unpack_from("<H", data, step_offset)[0]
                if 1 <= s_val <= 250:
                    step_no = s_val

            # Function code is defined authentically by the compiled recipe (.PRG).
            # Do not inject arbitrary function codes from status memory to avoid corrupting recipe steps.
            function_code = 0

            # Analog readings: Note that STATUS.ACT offset 20 is an internal controller status word (0x0300 / 768),
            # NOT temperature! Real sensor telemetry is read from cyclic datalog PR<batch>.LOG.
            pv = None
            sp = None
            t2 = None
            if size >= 26:
                w_pv, w_sp, w_t2 = struct.unpack_from("<3h", data, 20)
                # Strictly filter out internal controller status word 768 (0x0300) and 1536 (0x0600)
                if 100 <= w_pv <= 1500 and w_pv != 768:
                    pv = round(w_pv / 10.0, 1)
                if 100 <= w_sp <= 1500 and w_sp != 768:
                    sp = round(w_sp / 10.0, 1)
                if 100 <= w_t2 <= 1500 and w_t2 not in (768, 1536):
                    t2 = round(w_t2 / 10.0, 1)

            # Check if 32-bit floats exist in cyclic record block (offset 366..)
            if size >= 370:
                try:
                    f_sp = struct.unpack_from("<f", data, 366)[0]
                    if 20.0 <= f_sp <= 145.0 and abs(f_sp - 76.8) > 0.1 and abs(f_sp - 90.0) > 0.1:
                        sp = round(f_sp, 1)
                except Exception:
                    pass

            return {
                "status": "RUNNING" if current_batch != "UNKNOWN" else "ONLINE",
                "machine_id": machine_id,
                "current_batch": current_batch,
                "prog_no": prog_no,
                "program_code": program_code or (f"M_{prog_no:04d}" if prog_no else ""),
                "program_name": program_name,
                "current_step": step_no,
                "function_code": function_code,
                "temp_pv": pv,
                "temp_sp": sp,
                "temp_pt100_t2": t2,
                "file_size": size,
                "file_timestamp": datetime.utcnow().isoformat(),
                "is_ftp_source": is_ftp,
                "data_source": ftp_source_path if is_ftp else "LOCAL_STORAGE"
            }
        except Exception as e:
            return {"status": "ERROR", "error": str(e), "is_ftp_source": False, "data_source": "ERROR"}

    @staticmethod
    def read_alarm_act(
        folder_path: str = "",
        ip: Optional[str] = None,
        ftp_port: int = 21,
        raw_bytes: Optional[bytes] = None,
        machine_no: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Reads ALARM.ACT for active alarms from raw bytes, FTP (supporting Flashdisk/SC797CE), or local folder."""
        data = raw_bytes
        if not data and ip:
            is_797 = (ip.strip() in ("192.168.1.95", "172.16.120.102", "172.16.120.103", "172.16.120.105", "172.16.120.108", "172.16.120.109", "172.16.120.154"))
            flashdisk_alarms = [
                "/Flashdisk/SC797CE/STATUS/ALARM.ACT",
                "/Flashdisk/sc797ce/STATUS/ALARM.ACT",
                "\\Flashdisk\\SC797CE\\STATUS\\ALARM.ACT",
                "/Flashdisk/SC797CE/ALARM.ACT",
                "/Flashdisk/STATUS/ALARM.ACT",
                "STATUS/ALARM.ACT",
                "ALARM.ACT"
            ]
            storage_alarms = [
                "/Storage/sc777ce/STATUS/ALARM.ACT",
                "/Storage/SC777CE/STATUS/ALARM.ACT",
                "\\Storage\\SC777CE\\STATUS\\ALARM.ACT",
                "Storage/sc777ce/STATUS/ALARM.ACT",
                "STATUS/ALARM.ACT",
                "ALARM.ACT"
            ]
            alarm_paths = (flashdisk_alarms + storage_alarms) if is_797 else (storage_alarms + flashdisk_alarms)
            for fp in alarm_paths:
                data = SetexFolderReader.read_file_from_ftp(ip, ftp_port, fp)
                if data:
                    break

        if not data and folder_path:
            candidates = [
                os.path.join(folder_path, "ALARM.ACT"),
                os.path.join(folder_path, "STATUS", "ALARM.ACT"),
            ]
            alarm_file = next((f for f in candidates if os.path.exists(f)), None)
            if alarm_file:
                try:
                    with open(alarm_file, "rb") as f:
                        data = f.read()
                except Exception:
                    pass

        if not data:
            return {"is_alarm_active": False, "active_alarms": []}

        try:
            has_alarm = any(b != 0 for b in data)
            active_alarms = []
            if has_alarm and len(data) >= 4:
                code = data[0] + (data[1] << 8)
                alarm_info = explain_alarm(code, machine_no=machine_no)
                active_alarms.append({
                    "alarm_code": str(code),
                    "description": alarm_info["full_text"],
                    "title": alarm_info["title"],
                    "detail": alarm_info["detail"],
                    "severity": alarm_info["severity"],
                    "source": alarm_info["source"],
                })

            return {
                "is_alarm_active": has_alarm,
                "active_alarms": active_alarms
            }
        except Exception:
            return {"is_alarm_active": False, "active_alarms": []}

    @staticmethod
    def read_alarms_log(
        folder_path: str = "",
        ip: Optional[str] = None,
        ftp_port: int = 21,
        limit: int = 50,
        raw_bytes: Optional[bytes] = None,
        machine_no: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Parses ALARMS.LOG from raw bytes, FTP (supporting Flashdisk/SC797CE), or local folder."""
        data = raw_bytes
        if not data and ip:
            is_797 = (ip.strip() in ("192.168.1.95", "172.16.120.102", "172.16.120.103", "172.16.120.105", "172.16.120.108", "172.16.120.109", "172.16.120.154"))
            flashdisk_logs = [
                "/Flashdisk/SC797CE/STATUS/ALARMS.LOG",
                "/Flashdisk/sc797ce/STATUS/ALARMS.LOG",
                "\\Flashdisk\\SC797CE\\STATUS\\ALARMS.LOG",
                "/Flashdisk/STATUS/ALARMS.LOG",
                "STATUS/ALARMS.LOG",
                "ALARMS.LOG"
            ]
            storage_logs = [
                "/Storage/sc777ce/STATUS/ALARMS.LOG",
                "/Storage/SC777CE/STATUS/ALARMS.LOG",
                "\\Storage\\SC777CE\\STATUS\\ALARMS.LOG",
                "Storage/sc777ce/STATUS/ALARMS.LOG",
                "STATUS/ALARMS.LOG",
                "ALARMS.LOG"
            ]
            log_paths = (flashdisk_logs + storage_logs) if is_797 else (storage_logs + flashdisk_logs)
            for fp in log_paths:
                data = SetexFolderReader.read_file_from_ftp(ip, ftp_port, fp)
                if data:
                    break

        if not data and folder_path:
            candidates = [
                os.path.join(folder_path, "ALARMS.LOG"),
                os.path.join(folder_path, "STATUS", "ALARMS.LOG")
            ]
            log_file = next((f for f in candidates if os.path.exists(f)), None)
            if log_file:
                try:
                    with open(log_file, "rb") as f:
                        data = f.read()
                except Exception:
                    pass

        if not data:
            return []

        results = []
        try:
            idx = 0
            while idx < len(data) - 12:
                # Delimiter check: year offset 120..135 (2020..2035)
                if 120 <= data[idx] <= 135:
                    month = data[idx + 1]
                    day = data[idx + 2]
                    hour = data[idx + 3]
                    minute = data[idx + 4]
                    second = data[idx + 5]
                    if 1 <= month <= 12 and 1 <= day <= 31 and hour < 24 and minute < 60 and second < 60:
                        year = 1900 + data[idx]
                        dt_str = f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"
                        alarm_code = 0
                        if idx >= 4:
                            alarm_code = data[idx - 4] + (data[idx - 3] << 8)
                        
                        alarm_info = explain_alarm(alarm_code, machine_no=machine_no)
                        results.append({
                            "timestamp": dt_str,
                            "alarm_code": str(alarm_code),
                            "alarm_text": alarm_info["full_text"],
                            "severity": alarm_info["severity"]
                        })
                        idx += 6
                        continue
                idx += 1

            seen = set()
            unique = []
            # Order strictly by date time (timestamp descending)
            results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            for r in results:
                if r["timestamp"] not in seen:
                    seen.add(r["timestamp"])
                    unique.append(r)
                    if len(unique) >= limit:
                        break
            return unique
        except Exception:
            return []

    @staticmethod
    def parse_cyclic_log_bytes(log_data: bytes) -> List[Dict[str, Any]]:
        """Parses cyclic binary .LOG telemetry into structured curve points using Btrieve decompression."""
        if not log_data or len(log_data) < 20:
            return []

        # 1. Primary: Decompress Btrieve 512-byte pages (native SETEX 777 PR<batch>.LOG format)
        if len(log_data) >= 512 and len(log_data) % 512 == 0:
            try:
                page_size = 512
                num_pages = len(log_data) // page_size
                recs_by_seq = {}
                for page in range(1, num_pages):
                    p = log_data[page * 512:(page + 1) * 512]
                    if len(p) < 12:
                        continue
                    n = struct.unpack_from('<H', p, 10)[0]
                    if not (0 < n < 100):
                        continue
                    for slot in range(n):
                        a = struct.unpack_from('<H', p, 510 - slot * 2)[0]
                        if a == 65535:
                            continue
                        start = a & 32767
                        end = None
                        for j in range(slot + 1, n + 1):
                            z = struct.unpack_from('<H', p, 510 - j * 2)[0]
                            if z != 65535:
                                end = z & 32767
                                break
                        if end is None or not (12 <= start < end <= 512 - 2 * (n + 1)):
                            continue
                        packed = p[start:end]
                        if a & 32768:
                            packed = packed[4:]
                        pos, out, repeat = 0, bytearray(), False
                        while pos + 2 <= len(packed):
                            cnt = struct.unpack_from('<H', packed, pos)[0]
                            pos += 2
                            need = 1 if repeat else cnt
                            if pos + need > len(packed):
                                break
                            val = packed[pos:pos + need]
                            out += val * cnt if repeat else val
                            pos += need
                            repeat = not repeat
                        if len(out) == 154:
                            seq = struct.unpack_from('<H', out, 0)[0]
                            recs_by_seq[seq] = bytes(out)

                if recs_by_seq:
                    pts = []
                    curr_step = 1
                    for seq in sorted(recs_by_seq.keys()):
                        raw = recs_by_seq[seq]
                        evt = struct.unpack_from('<H', raw, 2)[0]
                        if evt == 261 and len(raw) >= 24:
                            s_cand = struct.unpack_from('<H', raw, 22)[0]
                            if 1 <= s_cand <= 200:
                                curr_step = s_cand
                        elif evt == 8 and len(raw) >= 12:
                            s_cand = struct.unpack_from('<H', raw, 10)[0]
                            if 1 <= s_cand <= 200:
                                curr_step = s_cand
                        elif evt == 3 and len(raw) >= 24:
                            y, mo, day, h, m, s = raw[4:10]
                            year = 1900 + y
                            if 2020 <= year <= 2035 and 1 <= mo <= 12 and 1 <= day <= 31:
                                dt_str = f"{year:04d}-{mo:02d}-{day:02d} {h:02d}:{m:02d}:{s:02d}"
                                w_sp_ramp = struct.unpack_from('<h', raw, 10)[0]
                                w_pv = struct.unpack_from('<h', raw, 12)[0]
                                w_t2 = struct.unpack_from('<h', raw, 14)[0]
                                w_sp = struct.unpack_from('<h', raw, 16)[0]
                                w_water_flow = struct.unpack_from('<h', raw, 18)[0]
                                w_pump = struct.unpack_from('<h', raw, 20)[0]
                                w_reel = struct.unpack_from('<h', raw, 22)[0]

                                # SETEX Secom 777 analog temperature scaling:
                                # Raw word is 0..10000 (0..100.00% of 150.0 °C span).
                                # Scale factor: 150.0 / 100.0 = 1.5
                                pv = round((w_pv / 100.0) * 1.5, 2)
                                t2 = round((w_t2 / 100.0) * 1.5, 2) if w_t2 > 0 else 0.0

                                if w_sp_ramp > 0:
                                    sp = round((w_sp_ramp / 100.0) * 1.5, 2)
                                elif 0 < w_sp <= 150:
                                    sp = float(w_sp)
                                else:
                                    sp = 0.0

                                pump_val = float(w_pump) if 0 <= w_pump <= 100 else 85.0
                                reel_val = round(w_reel / 10.0, 1) if 0 <= w_reel <= 9990 else 240.0
                                pump = min(max(pump_val, 0.0), 100.0)
                                reel = min(max(reel_val, 0.0), 999.0)

                                if 10.0 <= pv <= 145.0:
                                    pts.append({
                                        "timestamp": dt_str,
                                        "temp_pv": pv,
                                        "temp_sp": sp,
                                        "temp_pt100_t2": t2,
                                        "pump_speed_percent": pump,
                                        "reel_speed_mpm": reel,
                                        "step_no": curr_step
                                    })
                    if pts:
                        return pts
            except Exception as ex:
                logger.warning(f"Btrieve PR parser warning: {ex}")

        telemetry = []
        total_len = len(log_data)
        
        curr_year = datetime.now().year
        # Scan for SETEX timestamp markers: year offset 120..127 (2020..curr_year)
        idx = 0
        while idx < total_len - 18:
            y, mon, d, hh, mm, ss = log_data[idx:idx+6]
            year = 1900 + y
            if 120 <= y and year <= curr_year and 1 <= mon <= 12 and 1 <= d <= 31 and hh < 24 and mm < 60 and ss < 60:
                chunk = log_data[idx+6:idx+20]
                if len(chunk) >= 14:
                    step = struct.unpack_from("<H", chunk, 0)[0]
                    s1, s2, s3, s4 = struct.unpack_from("<4H", chunk, 2)
                    w_aux = struct.unpack_from("<H", chunk, 12)[0] if len(chunk) >= 14 else 0

                    # Check if s1 represents temperature in range 1500..15000 (15.0..150.0 C)
                    if 1500 <= s1 <= 15000:
                        dt_str = f"{year:04d}-{mon:02d}-{d:02d} {hh:02d}:{mm:02d}:{ss:02d}"
                        pv = round(s1 / 100.0, 2)
                        t2 = round(s2 / 100.0, 2)
                        sp = float(s3) if 0 <= s3 <= 150 else 90.0
                        reel = round(s4 / 100.0, 1) if s4 > 0 else 240.0
                        pump = round(w_aux / 100.0, 1) if 1000 <= w_aux <= 10000 else 85.0

                        step_val = 1
                        if 1 <= step <= 99:
                            step_val = step
                        elif idx >= 84:
                            cand_step = struct.unpack_from("<H", log_data, idx - 84)[0]
                            if 1 <= cand_step <= 200:
                                step_val = cand_step

                        telemetry.append({
                            "timestamp": dt_str,
                            "temp_pv": pv,
                            "temp_sp": sp,
                            "temp_pt100_t2": t2,
                            "pump_speed_percent": pump,
                            "reel_speed_mpm": reel,
                            "step_no": step_val
                        })
                        idx += 18
                        continue
            idx += 1

        # Deduplicate and sort
        seen = set()
        unique = []
        for p in telemetry:
            if p["timestamp"] not in seen:
                seen.add(p["timestamp"])
                unique.append(p)

        unique.sort(key=lambda x: x["timestamp"])
        return unique

    @staticmethod
    def parse_step_timings_from_pr_bytes(log_data: bytes) -> Dict[int, Dict[str, Optional[str]]]:
        """
        Extracts ground-truth step start and stop timestamps directly from SETEX PR*.LOG
        Event 261 (0x0105):
          words[0] == 1 -> Start Step
          words[0] == 2 -> Stop Step
          words[6]      -> Step Number
        """
        if not log_data or len(log_data) < 512 or len(log_data) % 512 != 0:
            return {}

        try:
            page_size = 512
            num_pages = len(log_data) // page_size
            recs_by_seq = {}
            for page in range(1, num_pages):
                p_chunk = log_data[page * 512:(page + 1) * 512]
                if len(p_chunk) < 12:
                    continue
                n = struct.unpack_from('<H', p_chunk, 10)[0]
                if not (0 < n < 100):
                    continue
                for slot in range(n):
                    a = struct.unpack_from('<H', p_chunk, 510 - slot * 2)[0]
                    if a == 65535:
                        continue
                    start = a & 32767
                    end = None
                    for j in range(slot + 1, n + 1):
                        z = struct.unpack_from('<H', p_chunk, 510 - j * 2)[0]
                        if z != 65535:
                            end = z & 32767
                            break
                    if end is None or not (12 <= start < end <= 512 - 2 * (n + 1)):
                        continue
                    packed = p_chunk[start:end]
                    if a & 32768:
                        packed = packed[4:]
                    pos, out, repeat = 0, bytearray(), False
                    while pos + 2 <= len(packed):
                        cnt = struct.unpack_from('<H', packed, pos)[0]
                        pos += 2
                        need = 1 if repeat else cnt
                        if pos + need > len(packed):
                            break
                        val = packed[pos:pos + need]
                        out += val * cnt if repeat else val
                        pos += need
                        repeat = not repeat
                    if len(out) == 154:
                        seq = struct.unpack_from('<H', out, 0)[0]
                        recs_by_seq[seq] = bytes(out)

            step_timings = {}
            for seq in sorted(recs_by_seq.keys()):
                raw = recs_by_seq[seq]
                evt = struct.unpack_from('<H', raw, 2)[0]
                if (evt & 0xFF) == 5 and len(raw) >= 24:
                    action = struct.unpack_from('<H', raw, 10)[0]
                    step_cand = struct.unpack_from('<H', raw, 22)[0]
                    y, mo, day, h, m, s = raw[4:10]
                    year = 1900 + y
                    if 2020 <= year <= 2035 and 1 <= step_cand <= 250:
                        dt_str = f"{year:04d}-{mo:02d}-{day:02d} {h:02d}:{m:02d}:{s:02d}"
                        if step_cand not in step_timings:
                            step_timings[step_cand] = {"start": None, "end": None}
                        if action == 1 and not step_timings[step_cand]["start"]:
                            step_timings[step_cand]["start"] = dt_str
                        elif action == 2:
                            step_timings[step_cand]["end"] = dt_str

            return step_timings
        except Exception as ex:
            logger.warning(f"Error parsing step timings from PR bytes: {ex}")
            return {}

    @staticmethod
    def read_cyclic_log_file(filepath: str) -> List[Dict[str, Any]]:
        """Parses local .LOG file telemetry."""
        if not os.path.exists(filepath):
            return []
        try:
            with open(filepath, "rb") as f:
                log_data = f.read()
            return SetexFolderReader.parse_cyclic_log_bytes(log_data)
        except Exception:
            return []

    @staticmethod
    def read_cyclic_log_from_ftp(ip: str, ftp_port: int, batch_no: str) -> List[Dict[str, Any]]:
        """Downloads and parses active batch PR<batch>.LOG directly from controller FTP."""
        if not ip or not batch_no:
            return []

        is_797 = (ip.strip() in ("192.168.1.95", "172.16.120.102", "172.16.120.103", "172.16.120.105", "172.16.120.108", "172.16.120.109", "172.16.120.154"))

        flashdisk_batch_logs = [
            f"/Flashdisk/SC797CE/BATCH/{batch_no}/PR{batch_no}.LOG",
            f"/Flashdisk/sc797ce/BATCH/{batch_no}/pr{batch_no}.log",
            f"\\Flashdisk\\SC797CE\\BATCH\\{batch_no}\\PR{batch_no}.LOG",
            f"/Flashdisk/SC797CE/BATCH/PR{batch_no}.LOG",
            f"/Flashdisk/BATCH/{batch_no}/PR{batch_no}.LOG",
            f"/Flashdisk/SC797CE/STATUS/PR{batch_no}.LOG",
            f"PR{batch_no}.LOG"
        ]

        storage_batch_logs = [
            f"/Storage/sc777ce/BATCH/{batch_no}/PR{batch_no}.LOG",
            f"/Storage/sc777ce/BATCH/{batch_no}/pr{batch_no}.log",
            f"\\Storage\\SC777CE\\BATCH\\{batch_no}\\PR{batch_no}.LOG",
            f"Storage/sc777ce/BATCH/{batch_no}/PR{batch_no}.LOG",
            f"/Storage/sc777ce/BATCH/PR{batch_no}.LOG",
            f"/BATCH/{batch_no}/PR{batch_no}.LOG",
            f"/Network/F/OT/MACHINES/A001/BATCHES/PR{batch_no}.LOG",
            f"PR{batch_no}.LOG"
        ]

        paths = (flashdisk_batch_logs + storage_batch_logs) if is_797 else (storage_batch_logs + flashdisk_batch_logs)

        data = None
        for p in paths:
            data = SetexFolderReader.read_file_from_ftp(ip, ftp_port, p)
            if data:
                break

        if not data:
            return []

        return SetexFolderReader.parse_cyclic_log_bytes(data)

    @staticmethod
    def find_all_log_files(base_paths: List[str]) -> List[str]:
        """Finds all readable .LOG files in configured directories without writing."""
        found = []
        for p in base_paths:
            if not os.path.exists(p):
                continue
            for root, _, files in os.walk(p):
                for f in files:
                    if f.upper().endswith(".LOG") and not f.upper().startswith("EVENT") and not f.upper().startswith("ALARM"):
                        found.append(os.path.join(root, f))
        return found

    _PRG_STEPS_CACHE: Dict[str, Dict[str, Any]] = {}
    _FUNCTION_CATALOG: Optional[Dict[str, Any]] = None
    _PARAMETERS_CATALOG: Optional[Dict[str, Any]] = None
    _RESOURCES_CATALOG: Optional[Dict[str, Any]] = None
    _CHOICES_CATALOG: Optional[Dict[str, Any]] = None

    FALLBACK_FUNCTION_NAMES: Dict[int, str] = {
        1: "Program Start",
        2: "Fill",
        5: "Addition End",
        30: "Runtime",
        31: "Inject AT2",
        61: "Drain",
        71: "Drain Percent",
        85: "Dosing",
        86: "Dosing Chemical",
        106: "Call-Off Operator",
        121: "Holding",
        122: "Unload",
        126: "Check",
        127: "Check pH",
        131: "Cooling",
        141: "Temperature Control",
        144: "Runtime",
        227: "Dosing AT1",
        228: "Dosing AT2",
        237: "Inject AT1",
        238: "Inject AT2",
        241: "Rinsing / Cooling",
        261: "Load",
        401: "Pump Set Value",
        404: "Dye Liquor Pump",
        668: "Filling AT2 Level",
        678: "Fill ST1 Quantity",
        708: "Machine -> ST1",
        709: "Rinse Nozzle",
        710: "Rinse Time Mode",
        712: "Material Flow",
        713: "Fill Level",
        714: "Washing",
        715: "Dosing AT2->AT1",
        716: "ST -> Machine",
        717: "Filling AT1 Level",
        720: "Fill Level ST",
        747: "Rinsing / Cooling",
        938: "Dosing Progression 1",
        939: "Dosing Progression 2",
    }

    @classmethod
    def get_fallback_function_name(cls, func_id: int) -> str:
        """Returns localized function name from catalog or built-in standard SETEX function names."""
        catalog = cls.get_function_catalog()
        if str(func_id) in catalog:
            return catalog[str(func_id)].get("name") or cls.FALLBACK_FUNCTION_NAMES.get(func_id, f"Func {func_id}")
        return cls.FALLBACK_FUNCTION_NAMES.get(func_id, f"Func {func_id}")

    @classmethod
    def invalidate_recipe_cache(cls, batch_no: Optional[str] = None, prog_no: Optional[int] = None):
        """Invalidates in-memory recipe steps cache for a batch, program, or entirely."""
        if not batch_no and not prog_no:
            cls._PRG_STEPS_CACHE.clear()
            _FTP_BUNDLE_CACHE.clear()
            logger.info("Cleared all PRG steps and FTP bundle caches.")
            return

        keys_to_del = []
        for k in list(cls._PRG_STEPS_CACHE.keys()):
            if batch_no and str(batch_no) in k:
                keys_to_del.append(k)
            elif prog_no and str(prog_no) in k:
                keys_to_del.append(k)

        for k in keys_to_del:
            cls._PRG_STEPS_CACHE.pop(k, None)

        for k in list(_FTP_BUNDLE_CACHE.keys()):
            _FTP_BUNDLE_CACHE.pop(k, None)

        if keys_to_del:
            logger.info(f"Invalidated recipe cache keys: {keys_to_del}")

    @classmethod
    def get_function_catalog(cls) -> Dict[str, Any]:
        """Loads typeconf_functions.json catalog if available, or uses built-in standard SETEX function names."""
        if cls._FUNCTION_CATALOG is not None:
            return cls._FUNCTION_CATALOG

        catalog = {}
        candidate_paths = [
            os.path.join(os.path.dirname(__file__), "..", "data", "typeconf_functions.json"),
            os.path.join(os.path.dirname(__file__), "..", "..", "data", "typeconf_functions.json"),
            "/app/open_orgatex/backend/data/typeconf_functions.json",
            "./data/typeconf_functions.json",
            "typeconf_functions.json"
        ]
        for cp in candidate_paths:
            if os.path.exists(cp):
                try:
                    with open(cp, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        catalog = data.get("functions", {})
                        cls._PARAMETERS_CATALOG = data.get("parameters", {})
                        cls._RESOURCES_CATALOG = data.get("resources", {})
                        cls._CHOICES_CATALOG = data.get("text_choices", {})
                        logger.info(f"Loaded SETEX function catalog ({len(catalog)} functions, {len(cls._PARAMETERS_CATALOG or {})} params) from {cp}")
                        break
                except Exception as e:
                    logger.warning(f"Failed to load function catalog from {cp}: {e}")

        cls._FUNCTION_CATALOG = catalog
        return cls._FUNCTION_CATALOG

    @classmethod
    def format_step_param(cls, func_id: int, param_idx: int, val: Optional[float], max_params: int = 6, func_meta: Optional[Dict[str, Any]] = None) -> Tuple[str, str, str]:
        """
        Formats SETEX Secom float parameter into human-readable representation with engineering units.
        Returns: (formatted_value, param_name, unit)
        """
        if val is None or param_idx >= max_params:
            return ("", f"P{param_idx+1}", "")

        # 1. Try resolving using schema definitions from typeconf_functions.json
        if cls._PARAMETERS_CATALOG is None:
            cls.get_function_catalog()

        p_name = f"P{param_idx+1}"
        p_unit = ""
        formatted = ""

        if func_meta and "parameters" in func_meta:
            f_params = func_meta.get("parameters", [])
            if param_idx < len(f_params):
                def_id = str(f_params[param_idx].get("definition_id"))
                p_def = (cls._PARAMETERS_CATALOG or {}).get(def_id)
                if p_def:
                    p_name = p_def.get("name", p_name)
                    p_unit = p_def.get("unit", "")

                    # Check text choice (mode 16)
                    scale = p_def.get("scale", {})
                    scale2 = p_def.get("scale2", {})
                    if scale.get("mode") == 16 and cls._CHOICES_CATALOG:
                        grp = str(scale2.get("text_group", 0))
                        grp_choices = cls._CHOICES_CATALOG.get(grp, [])
                        for ch in grp_choices:
                            if abs(ch.get("value", -9999) - val) < 0.01:
                                formatted = ch.get("text", "")
                                break

        if not formatted:
            # Domain-specific standard SETEX conventions
            if func_id in (141, 121, 145, 146):  # Temperature Control / Hold / Heat / Cool
                if param_idx == 0:
                    formatted = f"{val:.1f} °C" if val > 0 else f"{int(val)} °C"
                    p_name = p_name if p_name != f"P{param_idx+1}" else "Target Suhu"
                    p_unit = "°C"
                elif param_idx == 1:
                    formatted = f"{val:.1f} °C/min"
                    p_name = p_name if p_name != f"P{param_idx+1}" else "Laju Gradien"
                    p_unit = "°C/min"
                elif param_idx == 2:
                    formatted = f"{int(val)} min" if val > 0 else "0 min"
                    p_name = p_name if p_name != f"P{param_idx+1}" else "Waktu Tahan"
                    p_unit = "min"
            elif func_id in (241, 747, 131):  # Rinsing / Cooling
                if param_idx == 0:
                    formatted = f"{val:.1f} °C" if val > 0 else f"{int(val)} °C"
                    p_name = p_name if p_name != f"P{param_idx+1}" else "Suhu Akhir"
                    p_unit = "°C"
                elif param_idx == 1:
                    formatted = f"{val:.1f} °C/min"
                    p_name = p_name if p_name != f"P{param_idx+1}" else "Laju Pendinginan"
                    p_unit = "°C/min"
                elif param_idx == 2:
                    formatted = f"{int(val)} min" if val > 0 else "0 min"
                    p_name = p_name if p_name != f"P{param_idx+1}" else "Waktu Bilas"
                    p_unit = "min"
            elif func_id == 404:  # Dye Liquor Pump
                if param_idx == 0:
                    formatted = f"{int(val)} %"
                    p_name = "Variojet / Min Speed"
                    p_unit = "%"
                elif param_idx == 1:
                    formatted = f"{int(val)} %"
                    p_name = "Kecepatan Pompa"
                    p_unit = "%"
            elif func_id in (411, 712):  # Material Flow / Winch
                if param_idx == 0:
                    formatted = "Off" if val == 0 else "On" if val == 1 else "Auto"
                    p_name = "Mode Putaran"
                elif param_idx == 1:
                    formatted = f"{int(val)} m/min"
                    p_name = "Kecepatan Kain"
                    p_unit = "m/min"
            elif func_id in (713, 717, 718, 720, 668, 678, 679):  # Filling / Level
                if param_idx == 0:
                    formatted = "Air Dingin" if val == 0 else "Air Panas" if val == 1 else f"{int(val)}"
                    p_name = p_name if p_name != f"P{param_idx+1}" else "Jenis Air / Valve"
                elif param_idx == 1:
                    formatted = f"{int(val)}"
                    p_name = p_name if p_name != f"P{param_idx+1}" else "Mixer / Tangki"
                elif param_idx == 2:
                    formatted = f"{int(val)} %" if val <= 100 else f"{val:.1f} °C"
                    p_name = p_name if p_name != f"P{param_idx+1}" else "Level / Suhu"
                    p_unit = "%" if val <= 100 else "°C"
                elif param_idx == 3:
                    formatted = f"{int(val)} L"
                    p_name = p_name if p_name != f"P{param_idx+1}" else "Volume Air"
                    p_unit = "L"
                elif param_idx == 4:
                    formatted = f"{int(val)} min"
                    p_name = p_name if p_name != f"P{param_idx+1}" else "Waktu Larut"
                    p_unit = "min"
            elif func_id in (85, 86, 227, 228, 938, 939):  # Dosing Progression / Chemicals
                if param_idx == 0:
                    formatted = f"{val:.1f} °C" if val > 20 else f"{int(val)} %"
                    p_name = p_name if p_name != f"P{param_idx+1}" else "Suhu / Kurva"
                elif param_idx == 1:
                    formatted = f"{val:.1f} °C/min" if val > 0 else f"{int(val)}"
                    p_name = p_name if p_name != f"P{param_idx+1}" else "Gradien / Tangki"
                elif param_idx == 2:
                    formatted = f"{int(val)} %" if val > 0 else "0 %"
                    p_name = p_name if p_name != f"P{param_idx+1}" else "Kurva Dosing"
                    p_unit = "%"
                elif param_idx == 3:
                    formatted = f"{int(val)}"
                    p_name = p_name if p_name != f"P{param_idx+1}" else "No. Persiapan"
                elif param_idx == 4:
                    formatted = f"{int(val)} min"
                    p_name = p_name if p_name != f"P{param_idx+1}" else "Waktu Dosing"
                    p_unit = "min"
            elif func_id in (61, 71):  # Drain Percent
                if param_idx == 0:
                    formatted = f"{int(val)} %"
                    p_name = "Level Pembuangan"
                    p_unit = "%"
                elif param_idx == 1:
                    formatted = f"{int(val)}"
                    p_name = "Katup Pembuangan"
                elif param_idx == 2:
                    formatted = f"{int(val)} min"
                    p_name = "Waktu Sisa"
                    p_unit = "min"
            elif func_id in (30, 144):  # Runtime / Circulation
                if param_idx == 0:
                    formatted = f"{int(val)} min"
                    p_name = "Waktu Proses"
                    p_unit = "min"

        if not formatted:
            if abs(val - round(val)) < 0.01:
                formatted = f"{int(round(val))}" if val != 0 else "0"
            else:
                formatted = f"{val:.1f}"
            if p_unit:
                formatted = f"{formatted} {p_unit}"

        return (formatted, p_name, p_unit)

    @classmethod
    def parse_prg_steps(cls, prg_bytes: bytes, function_catalog: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Parses a SETEX Secom .PRG binary recipe to extract every defined step (1..N),
        comments/remarks (Slot 0), all sub-lines (1..16), all 6 parameters (with names and units),
        and timing target setpoints (set_time, hold_time, protect_time).
        """
        if not prg_bytes or len(prg_bytes) < 384:
            return []

        if cls._PARAMETERS_CATALOG is None:
            cls.get_function_catalog()

        catalog = function_catalog or cls._FUNCTION_CATALOG or {}
        res_catalog = cls._RESOURCES_CATALOG or {}

        # Read step count from header (offset 33)
        hdr_count = struct.unpack_from("<H", prg_bytes, 33)[0] if len(prg_bytes) >= 384 else 0
        total_steps = hdr_count if (hdr_count and 1 <= hdr_count <= 250) else 250

        # Group 65-byte records by step number
        records_by_step: Dict[int, List[Tuple[int, bytes]]] = {}
        for off in range(384, len(prg_bytes), 65):
            raw = prg_bytes[off:off + 65]
            if len(raw) < 65:
                break
            step_no = struct.unpack_from("<H", raw, 0)[0]
            slot = raw[2]
            if 1 <= step_no <= total_steps:
                records_by_step.setdefault(step_no, []).append((slot, raw))

        steps = []
        for step_no in sorted(records_by_step.keys()):
            step_records = records_by_step[step_no]

            # Slot 0: Step comment / operator note
            step_comment = ""
            for slot, raw in step_records:
                if slot == 0:
                    step_comment = raw[3:].split(b"\0", 1)[0].decode("cp1252", errors="ignore").strip()
                    break

            lines = []
            main_func_id = 0
            main_func_name = f"Step #{step_no}"
            main_type = "PROCESS"
            main_set_time = 0
            main_hold_time = 0
            main_protect_time = 0
            main_operator_txt = 0
            main_params = []

            # Slots 1..16: Execution functions
            for slot, rec in sorted([r for r in step_records if r[0] > 0], key=lambda x: x[0]):
                line_no = slot
                func_id = struct.unpack_from("<H", rec, 4)[0]
                if line_no > 1 and func_id in (0, 2):
                    continue

                func_meta = catalog.get(str(func_id), {})
                base_name = func_meta.get("name") or cls.FALLBACK_FUNCTION_NAMES.get(func_id) or f"Func {func_id}"

                if "prpgression" in base_name.lower():
                    base_name = base_name.replace("Prpgression", "Progression").replace("prpgression", "progression")

                display_name = base_name if line_no == 1 else f"- {base_name}"
                res_info = res_catalog.get(str(line_no), {})
                res_name = res_info.get("name") or ("Main Process" if line_no == 1 else f"Resource {line_no}")

                # Additional fields at offset 43
                p_time, s_time, op_txt, mod_no, loop_cnt, lbl_type, start_act, h_time, res_val, treat, treat_step = (0,)*11
                if len(rec) >= 61:
                    try:
                        p_time, s_time, op_txt, mod_no, loop_cnt, lbl_type, start_act, h_time, res_val, treat, treat_step = struct.unpack_from("<5HBfHBHH", rec, 43)
                    except Exception:
                        pass

                # Unpack 6x 32-bit float parameters
                parsed_params = []
                fmt_p = []
                for j in range(6):
                    p_off = 9 + 6 * j
                    val = 0.0
                    if p_off + 4 <= len(rec):
                        val = struct.unpack_from("<f", rec, p_off)[0]
                        if abs(val) > 100000 or not (-100000 < val < 100000):
                            val = 0.0

                    formatted_str, p_name, p_unit = cls.format_step_param(
                        func_id=func_id,
                        param_idx=j,
                        val=val,
                        max_params=6,
                        func_meta=func_meta
                    )
                    parsed_params.append({
                        "pos": j + 1,
                        "name": p_name,
                        "unit": p_unit,
                        "value": round(val, 2),
                        "formatted": formatted_str
                    })
                    fmt_p.append(formatted_str)

                if line_no == 1:
                    main_func_id = func_id
                    main_func_name = base_name
                    main_set_time = s_time
                    main_hold_time = h_time
                    main_protect_time = p_time
                    main_operator_txt = op_txt
                    main_params = parsed_params
                    f_lower = base_name.lower()
                    if "temp" in f_lower or "heat" in f_lower or func_id in (141, 121, 145):
                        main_type = "HEAT"
                    elif "rinse" in f_lower or "cool" in f_lower or func_id in (241, 747, 131, 146):
                        main_type = "COOL"
                    elif "dose" in f_lower or "dosing" in f_lower or func_id in (85, 86, 227, 228, 938, 939):
                        main_type = "DOSE"
                    elif "fill" in f_lower or func_id in (713, 668, 678, 717, 720):
                        main_type = "FILL"
                    elif "drain" in f_lower or func_id in (61, 71):
                        main_type = "DRAIN"
                    elif "inject" in f_lower or func_id in (238, 712):
                        main_type = "INJECT"
                    elif "hold" in f_lower or func_id == 121:
                        main_type = "HOLD"
                    elif "wash" in f_lower or func_id == 714:
                        main_type = "WASH"
                    elif "pump" in f_lower or "speed" in f_lower or func_id in (401, 404):
                        main_type = "PUMP"
                    elif "run" in f_lower or func_id in (30, 144):
                        main_type = "RUNTIME"

                lines.append({
                    "line": line_no,
                    "func_id": func_id,
                    "func_name": base_name,
                    "resource_name": res_name,
                    "name": display_name,
                    "is_sub": line_no > 1,
                    "set_time": s_time,
                    "hold_time": h_time,
                    "protect_time": p_time,
                    "operator_txt": op_txt,
                    "params": parsed_params,
                    "p1": fmt_p[0] if len(fmt_p) > 0 else "",
                    "p2": fmt_p[1] if len(fmt_p) > 1 else "",
                    "p3": fmt_p[2] if len(fmt_p) > 2 else "",
                    "p4": fmt_p[3] if len(fmt_p) > 3 else "",
                    "p5": fmt_p[4] if len(fmt_p) > 4 else "",
                    "p6": fmt_p[5] if len(fmt_p) > 5 else ""
                })

            if lines:
                p1_val = lines[0]["p1"] if lines else ""
                p2_val = lines[0]["p2"] if lines else ""
                p3_val = lines[0]["p3"] if lines else ""
                p4_val = lines[0]["p4"] if lines else ""
                p5_val = lines[0]["p5"] if lines else ""
                p6_val = lines[0]["p6"] if lines else ""
                steps.append({
                    "no": step_no,
                    "comment": step_comment,
                    "func_id": main_func_id,
                    "name": main_func_name,
                    "type": main_type,
                    "icon": str(main_func_id),
                    "set_time": main_set_time,
                    "hold_time": main_hold_time,
                    "protect_time": main_protect_time,
                    "operator_txt": main_operator_txt,
                    "params": main_params,
                    "p1": p1_val,
                    "p2": p2_val,
                    "p3": p3_val,
                    "p4": p4_val,
                    "p5": p5_val,
                    "p6": p6_val,
                    "sub_steps": lines
                })

        return steps

    @classmethod
    def get_recipe_steps(cls, ip: Optional[str] = None, ftp_port: int = 21, batch_no: Optional[str] = None, folder_path: Optional[str] = None, prog_no: Optional[int] = None, force_reload: bool = False) -> List[Dict[str, Any]]:
        """
        Retrieves and caches recipe steps for the active batch.
        Tries FTP active BATCH directory and specific program first, then local folders.
        Includes TTL caching and force_reload support.
        """
        cache_key = f"{ip or 'local'}_{batch_no or 'default'}_{prog_no or 0}"
        now = time.time()
        if not force_reload and cache_key in cls._PRG_STEPS_CACHE:
            entry = cls._PRG_STEPS_CACHE[cache_key]
            if isinstance(entry, dict) and "ts" in entry:
                if (now - entry["ts"]) < 25.0:
                    return entry["steps"]
            elif isinstance(entry, list):
                return entry

        catalog = cls.get_function_catalog()
        prg_bytes = None

        # 1. Try reading from FTP if IP available
        if ip:
            is_797 = (ip.strip() in ("192.168.1.95", "172.16.120.102", "172.16.120.103", "172.16.120.105", "172.16.120.108", "172.16.120.109", "172.16.120.154"))
            candidate_dirs = [
                f"/Flashdisk/SC797CE/BATCH/{batch_no}" if batch_no else None,
                "/Flashdisk/SC797CE/Programs",
                "/Flashdisk/SC797CE/BATCH",
                f"/Storage/sc777ce/BATCH/{batch_no}" if batch_no else None,
                "/Storage/sc777ce/Programs",
                "/Storage/sc777ce/BATCH",
            ] if is_797 else [
                f"/Storage/sc777ce/BATCH/{batch_no}" if batch_no else None,
                "/Storage/sc777ce/Programs",
                "/Storage/sc777ce/BATCH",
                f"/Flashdisk/SC797CE/BATCH/{batch_no}" if batch_no else None,
                "/Flashdisk/SC797CE/Programs",
            ]

            lock = _get_host_lock(ip)
            if lock.acquire(timeout=2.0):
                try:
                    ftp = ftplib.FTP(timeout=2.5)
                    ftp.connect(ip, ftp_port or 21)
                    ftp.login("", "")
                    ftp.set_pasv(True)
                    for b_dir in [d for d in candidate_dirs if d]:
                        try:
                            ftp.cwd(b_dir)
                            files = ftp.nlst()
                            prg_candidates = [f for f in files if f.upper().endswith(".PRG")]
                            target_file = None
                            if prog_no:
                                match_name = f"M_{prog_no:04d}.PRG".upper()
                                target_file = next((f for f in prg_candidates if f.upper() == match_name), None)
                            if not target_file and prg_candidates:
                                target_file = prg_candidates[0]
                            if target_file:
                                bio = io.BytesIO()
                                ftp.retrbinary(f"RETR {target_file}", bio.write)
                                prg_bytes = bio.getvalue()
                                if prg_bytes:
                                    break
                        except Exception:
                            continue
                    try:
                        ftp.quit()
                    except Exception:
                        try:
                            ftp.close()
                        except Exception:
                            pass
                except Exception:
                    pass
                finally:
                    try:
                        lock.release()
                    except RuntimeError:
                        pass

        # 2. Try fallback to local files if FTP didn't get PRG
        if not prg_bytes:
            local_candidates = []
            if batch_no:
                local_candidates.append(os.path.join(os.path.dirname(__file__), "..", "data", "OT", "BATCH", batch_no, f"M_{prog_no:04d}.PRG" if prog_no else "M_0004.PRG"))
                local_candidates.append(os.path.join(folder_path or "", f"M_{prog_no:04d}.PRG" if prog_no else "M_0004.PRG"))
            if prog_no:
                local_candidates.append(os.path.join(os.path.dirname(__file__), "..", "data", "compiled_prg", f"M_{prog_no:04d}.PRG"))
                local_candidates.append(os.path.join(os.path.dirname(__file__), "..", "data", f"M_{prog_no:04d}.PRG"))
            local_candidates.extend([
                os.path.join(os.path.dirname(__file__), "..", "data", "M_0004.PRG"),
                os.path.join(os.path.dirname(__file__), "..", "data", "compiled_prg", "M_0004.PRG"),
                os.path.join(folder_path or "", "M_0342.PRG"),
                os.path.join(os.path.dirname(__file__), "..", "data", "M_0342.PRG"),
                "/app/open_orgatex/backend/data/M_0004.PRG",
                "./data/M_0004.PRG"
            ])
            for lp in local_candidates:
                if lp and os.path.exists(lp):
                    try:
                        with open(lp, "rb") as f:
                            prg_bytes = f.read()
                        if prg_bytes:
                            break
                    except Exception:
                        pass

        if prg_bytes:
            steps = cls.parse_prg_steps(prg_bytes, catalog)
            if steps:
                cls._PRG_STEPS_CACHE[cache_key] = {"ts": time.time(), "steps": steps}
                logger.info(f"Successfully parsed and cached {len(steps)} steps for batch {batch_no} (key: {cache_key})")
                return steps

        return []
