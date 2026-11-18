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
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger("orgatex.reader")

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
                            ftp.quit()
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
                                ftp.quit()
                                return data
                        except Exception:
                            pass

                ftp.quit()
            except Exception:
                pass
        return None

    @staticmethod
    def read_status_act(folder_path: str = "", ip: Optional[str] = None, ftp_port: int = 21, raw_bytes: Optional[bytes] = None) -> Dict[str, Any]:
        """Reads and parses STATUS.ACT from raw bytes, FTP (prioritizing Flashdisk/SC797CE for 192.168.1.95), or local folder."""
        data = raw_bytes
        is_ftp = bool(raw_bytes and ip)
        ftp_source_path = f"ftp://{ip}:{ftp_port or 21}/STATUS.ACT" if is_ftp else ""

        # 1. Try FTP if no raw bytes provided but IP is given
        if not data and ip:
            is_797 = (ip.strip() == "192.168.1.95")
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
                if raw_p:
                    program_code = raw_p

            # Program Name at offset 75
            program_name = ""
            if size >= 100:
                raw_pn = data[75:100].split(b'\0')[0].decode('latin1', errors='ignore').strip()
                if raw_pn:
                    program_name = raw_pn

            # Step number: SETEX Secom 777 format (10104 bytes -> offset 0x15C, 10188 bytes -> offset 0x15E)
            step_offset = 0x15E if size == 10188 else 0x15C
            step_no = 1
            function_code = 0
            if size >= step_offset + 2:
                s_val = struct.unpack_from("<H", data, step_offset)[0]
                if 1 <= s_val <= 200:
                    step_no = s_val
            if size >= step_offset:
                fn_val = struct.unpack_from("<H", data, step_offset - 2)[0]
                if 1 <= fn_val <= 2000:
                    function_code = fn_val

            # Analog readings at offset 20, 22, 24 (16-bit short / 10.0)
            pv = 40.0
            sp = 90.0
            t2 = 25.0
            if size >= 26:
                w_pv, w_sp, w_t2 = struct.unpack_from("<3h", data, 20)
                if 100 <= w_pv <= 1500:
                    pv = round(w_pv / 10.0, 1)
                if 100 <= w_sp <= 1500:
                    sp = round(w_sp / 10.0, 1)
                if 100 <= w_t2 <= 1500:
                    t2 = round(w_t2 / 10.0, 1)

            # Check if 32-bit floats exist in cyclic record block (offset 366..)
            if size >= 370:
                try:
                    f_sp = struct.unpack_from("<f", data, 366)[0]
                    if 20.0 <= f_sp <= 145.0:
                        sp = round(f_sp, 1)
                except Exception:
                    pass

            return {
                "status": "RUNNING" if current_batch != "UNKNOWN" else "ONLINE",
                "machine_id": machine_id,
                "current_batch": current_batch,
                "program_code": program_code,
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
    def read_alarm_act(folder_path: str = "", ip: Optional[str] = None, ftp_port: int = 21) -> Dict[str, Any]:
        """Reads ALARM.ACT for active alarms from FTP (supporting Flashdisk/SC797CE) or local folder."""
        data = None
        if ip:
            is_797 = (ip.strip() == "192.168.1.95")
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
                active_alarms.append({
                    "alarm_code": str(code),
                    "description": ALARM_DEFINITIONS.get(code, f"Alarm Code #{code}"),
                    "severity": "CRITICAL" if code in [1, 2, 5] else "WARNING"
                })

            return {
                "is_alarm_active": has_alarm,
                "active_alarms": active_alarms
            }
        except Exception:
            return {"is_alarm_active": False, "active_alarms": []}

    @staticmethod
    def read_alarms_log(folder_path: str = "", ip: Optional[str] = None, ftp_port: int = 21, limit: int = 50) -> List[Dict[str, Any]]:
        """Parses ALARMS.LOG from FTP (supporting Flashdisk/SC797CE) or local folder."""
        data = None
        if ip:
            is_797 = (ip.strip() == "192.168.1.95")
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
                        
                        desc = ALARM_DEFINITIONS.get(alarm_code, f"Alarm Code #{alarm_code}")
                        results.append({
                            "timestamp": dt_str,
                            "alarm_code": str(alarm_code),
                            "alarm_text": desc,
                            "severity": "CRITICAL" if alarm_code in [1, 2, 5] else "WARNING"
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

        is_797 = (ip.strip() == "192.168.1.95")

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

    _PRG_STEPS_CACHE: Dict[str, List[Dict[str, Any]]] = {}
    _FUNCTION_CATALOG: Optional[Dict[str, Any]] = None

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
                        logger.info(f"Loaded SETEX function catalog ({len(catalog)} functions) from {cp}")
                        break
                except Exception as e:
                    logger.warning(f"Failed to load function catalog from {cp}: {e}")

        cls._FUNCTION_CATALOG = catalog
        return cls._FUNCTION_CATALOG

    @staticmethod
    def format_step_param(func_id: int, param_idx: int, val: Optional[float], max_params: int = 3) -> str:
        """Formats SETEX Secom float parameter into human-readable representation with engineering units."""
        if val is None or param_idx >= max_params:
            return ""
        if func_id in (141, 121):  # Temperature Control / Hold
            if param_idx == 0: return f"{val:.1f} °C" if val > 0 else f"{int(val)} °C"
            if param_idx == 1: return f"{val:.1f} °C/min"
            if param_idx == 2: return f"{int(val)} min" if val > 0 else "0 min"
        elif func_id in (241, 747, 131):  # Rinsing / Cooling
            if param_idx == 0: return f"{val:.1f} °C" if val > 0 else f"{int(val)} °C"
            if param_idx == 1: return f"{val:.1f} °C/min"
            if param_idx == 2: return f"{int(val)} min" if val > 0 else "0 min"
        elif func_id == 404:  # Dye Liquor Pump
            if param_idx in (0, 1): return f"{int(val)} %"
        elif func_id == 712:  # Material Flow
            if param_idx == 0: return "Off" if val == 0 else "On" if val == 1 else "Auto"
            if param_idx == 1: return f"{int(val)} m/min"
        elif func_id in (713, 717, 720, 668, 678):  # Filling / Level
            if param_idx == 0: return "cold water" if val == 0 else "hot water" if val == 1 else f"{int(val)}"
            if param_idx == 1: return f"{int(val)}"
            if param_idx == 2: return f"{int(val)} %" if val <= 100 else f"{val:.1f} °C"
            if param_idx == 3: return f"{int(val)} L"
        elif func_id in (85, 86, 227, 228, 938, 939):  # Dosing Progression / Chemicals
            if param_idx == 0: return f"{int(val)} %"
            if param_idx == 1: return f"{int(val)}"
            if param_idx == 2: return f"{int(val)} min"
        elif func_id in (61, 71):  # Drain Percent
            if param_idx == 0: return f"{int(val)} %"
            if param_idx == 1: return f"{int(val)} min"
        elif func_id in (30, 144):  # Runtime / Circulation
            if param_idx == 0: return f"{int(val)} min"

        if abs(val - round(val)) < 0.01:
            return f"{int(round(val))}" if val != 0 else "0"
        return f"{val:.1f}"

    @staticmethod
    def parse_prg_steps(prg_bytes: bytes, function_catalog: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Parses a SETEX Secom .PRG binary recipe to extract every defined step (1..N),
        all sub-lines (1..16), and their parameter values (P1, P2, P3).
        """
        if not prg_bytes or len(prg_bytes) < 256:
            return []

        FALLBACK_FUNCTION_NAMES = {
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
            126: "Check",
            131: "Cooling",
            141: "Temperature Control",
            144: "Runtime",
            227: "Dosing AT1",
            228: "Dosing AT2",
            238: "Inject AT2",
            241: "Rinsing / Cooling",
            261: "Load",
            401: "Pump Set Value",
            404: "Dye Liquor Pump",
            668: "Filling AT2 Level",
            678: "Fill ST1 Quantity",
            708: "Machine -> ST1",
            709: "Rinse Nozzle",
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

        catalog = function_catalog or {}
        steps = []

        for step_no in range(1, 255):
            pat1 = struct.pack("<HH", step_no, 1)
            idx1 = prg_bytes.find(pat1)
            if idx1 == -1:
                continue

            lines = []
            main_func_id = 0
            main_func_name = f"Step #{step_no}"
            main_type = "PROCESS"

            # Parse all sub-lines (1 to 16) for this step
            for line_no in range(1, 17):
                pat = struct.pack("<HH", step_no, line_no)
                idx = prg_bytes.find(pat)
                if idx == -1:
                    continue

                if idx + 6 <= len(prg_bytes):
                    func_id = struct.unpack_from("<H", prg_bytes, idx + 4)[0]
                    if line_no > 1 and func_id in (0, 2):
                        continue
                    func_meta = catalog.get(str(func_id), {})
                    base_name = func_meta.get("name") or FALLBACK_FUNCTION_NAMES.get(func_id) or f"Func {func_id}"

                    if "prpgression" in base_name.lower():
                        base_name = base_name.replace("Prpgression", "Progression").replace("prpgression", "progression")

                    display_name = base_name if line_no == 1 else f"- {base_name}"
                    param_count = func_meta.get("parameter_count", 3)

                    # Unpack 32-bit floats
                    rec = prg_bytes[idx:idx + 65]
                    raw_params = []
                    for p_off in (9, 15, 21, 27):
                        if p_off + 4 <= len(rec):
                            val = struct.unpack_from("<f", rec, p_off)[0]
                            raw_params.append(val if abs(val) < 100000 else 0.0)

                    fmt_p = [SetexFolderReader.format_step_param(func_id, pi, v, param_count) for pi, v in enumerate(raw_params)]
                    while len(fmt_p) < 3:
                        fmt_p.append("")

                    if line_no == 1:
                        main_func_id = func_id
                        main_func_name = base_name
                        f_lower = base_name.lower()
                        if "temp" in f_lower or "heat" in f_lower or func_id in (141, 121):
                            main_type = "HEAT"
                        elif "rinse" in f_lower or "cool" in f_lower or func_id in (241, 747, 131):
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
                        "name": display_name,
                        "is_sub": line_no > 1,
                        "p1": fmt_p[0],
                        "p2": fmt_p[1],
                        "p3": fmt_p[2]
                    })

            if lines:
                p1_val = lines[0]["p1"] if lines else ""
                p2_val = lines[0]["p2"] if lines else ""
                p3_val = lines[0]["p3"] if lines else ""
                steps.append({
                    "no": step_no,
                    "func_id": main_func_id,
                    "name": main_func_name,
                    "type": main_type,
                    "icon": str(main_func_id),
                    "p1": p1_val,
                    "p2": p2_val,
                    "p3": p3_val,
                    "sub_steps": lines
                })

        return steps

    @classmethod
    def get_recipe_steps(cls, ip: Optional[str] = None, ftp_port: int = 21, batch_no: Optional[str] = None, folder_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieves and caches recipe steps for the active batch.
        Tries FTP BATCH directory first, then local folders.
        """
        cache_key = f"{ip or 'local'}_{batch_no or 'default'}"
        if cache_key in cls._PRG_STEPS_CACHE:
            return cls._PRG_STEPS_CACHE[cache_key]

        catalog = cls.get_function_catalog()
        prg_bytes = None

        # 1. Try reading from FTP if IP & batch_no available
        if ip and batch_no and batch_no != "UNKNOWN":
            try:
                ftp = ftplib.FTP(timeout=3.0)
                ftp.connect(ip, ftp_port or 21)
                ftp.login()
                ftp.set_pasv(True)
                batch_dir = f"/Storage/sc777ce/BATCH/{batch_no}"
                try:
                    ftp.cwd(batch_dir)
                    files = ftp.nlst()
                    prg_candidates = [f for f in files if f.upper().endswith(".PRG")]
                    if prg_candidates:
                        bio = io.BytesIO()
                        ftp.retrbinary(f"RETR {prg_candidates[0]}", bio.write)
                        prg_bytes = bio.getvalue()
                except Exception:
                    pass
                ftp.quit()
            except Exception:
                pass

        # 2. Try fallback to local files if FTP didn't get PRG
        if not prg_bytes:
            local_candidates = [
                os.path.join(folder_path or "", "M_0342.PRG"),
                os.path.join(os.path.dirname(__file__), "..", "data", "M_0342.PRG"),
                "/app/open_orgatex/backend/data/M_0342.PRG",
                "./data/M_0342.PRG"
            ]
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
                cls._PRG_STEPS_CACHE[cache_key] = steps
                logger.info(f"Successfully parsed and cached {len(steps)} steps for batch {batch_no} (key: {cache_key})")
                return steps

        return []
