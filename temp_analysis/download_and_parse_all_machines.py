#!/usr/bin/env python3
"""
Scan and Download CP14.AWL & TYPECONF.CNF from all online dyeing machines via FTP,
Decode TYPECONF.CNF Category 10 (Info Words / IW mapping),
Classify Setpoints (SV) vs Actual Data (PV) vs Status,
and update typeconf_iw_map.json for each machine.
"""

import os
import sys
import ftplib
import json
import struct
import hashlib
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WORKSPACE_DIR = os.path.join(BASE_DIR, "WORKSPACE_PROGRAM_MESIN")
ANALISIS_DIR = os.path.join(BASE_DIR, "program", "Analisis")

if ANALISIS_DIR not in sys.path:
    sys.path.append(ANALISIS_DIR)

from cnf_decode import CNFReader, txt

def machine_to_asset_id(folder_name: str) -> str:
    mach = folder_name.replace("MESIN_", "").upper().strip()
    import re
    match = re.match(r"^(\d+)([A-Z])$", mach)
    if match:
        num, lane = match.groups()
        return f"JF-L{lane}-{int(num):02d}"
    if mach == "DA01":
        return "JF-LB-01"
    return f"JF-LB-{mach}"

def classify_register(reg_num: int, name_en: str, asset_id: str):
    """
    Returns (tag_role, data_type, is_setpoint, category, field_name, tag_name)
    tag_role: 'SV' (Setpoint), 'PV' (Actual Data / Process Value), 'STATUS', 'ALARM'
    data_type: 'SETPOINT', 'ACTUAL', 'STATUS', 'ALARM'
    """
    n = name_en.lower()

    # Explicit Setpoints (SV)
    if reg_num == 10 or "set temperature" in n or "hedef" in n:
        return "SV", "SETPOINT", True, "MAIN_TANK", "temp_setpoint", f"SMM.{asset_id}.MAIN_TANK.TEMPERATURE_SV"
    if reg_num in (34, 36, 38) or "start dosing" in n:
        tank = "DOSING_TANK_02" if "at2" in n or reg_num == 34 else "DOSING_TANK_01"
        fn = f"start_dosing_amo_{'at2' if reg_num == 34 else 'at1'}"
        return "SV", "SETPOINT", True, tank, fn, f"SMM.{asset_id}.{tank}.{fn.upper()}_SV"

    # Alarms
    if reg_num == 70 or "alarm" in n:
        return "ALARM", "ALARM", False, "ALARM", "circ_control_alarm", f"SMM.{asset_id}.ALARM.CIRC_CONTROL_ALARM"

    # Status / Controls / Digital Flags
    if reg_num in (20, 24, 39, 61, 62, 63, 64, 65, 66, 67, 68, 69, 149, 150, 151, 152, 153, 154, 155, 161, 162, 163, 165, 166, 167, 168, 173, 179, 180, 181, 182, 183, 184, 185, 200) or n.startswith("man ") or "rc " in n or "stirrer" in n or n in ("main pump", "winch", "addition pump"):
        cat = "STATUS"
        if "at2" in n or reg_num in (65, 66, 69, 168, 179, 180, 181, 182, 183, 185):
            cat = "DOSING_TANK_02"
        elif "at1" in n or reg_num in (63, 64, 68, 167, 155):
            cat = "DOSING_TANK_01"
        elif "st" in n or reg_num in (61, 62, 67, 165):
            cat = "SERVICE_TANK"
        clean_fn = re_sub(n)
        return "STATUS", "STATUS", False, cat, clean_fn, f"SMM.{asset_id}.{cat}.{clean_fn.upper()}_STATUS"

    # Actual Data / Process Values (PV)
    if reg_num == 1 or "act.temp" in n:
        return "PV", "ACTUAL", False, "MAIN_TANK", "act_temp", f"SMM.{asset_id}.MAIN_TANK.TEMPERATURE_PV"
    if reg_num == 2 or n == "time":
        return "PV", "ACTUAL", False, "PROCESS", "time", f"SMM.{asset_id}.PROCESS.TIME_PV"
    if reg_num == 3 or n == "level at":
        return "PV", "ACTUAL", False, "ADDITION_TANK", "level_at_pct", f"SMM.{asset_id}.ADDITION_TANK.LEVEL_PV"
    if reg_num == 11 or "level machine dig" in n:
        return "PV", "ACTUAL", False, "MAIN_TANK", "level_machine_dig", f"SMM.{asset_id}.MAIN_TANK.LEVEL_DIG_PV"
    if reg_num == 12 or "level machine (%)" in n:
        return "PV", "ACTUAL", False, "MAIN_TANK", "level_machine_pct", f"SMM.{asset_id}.MAIN_TANK.LEVEL_PV"
    if reg_num in (13, 17) or "quantity machine" in n:
        return "PV", "ACTUAL", False, "MAIN_TANK", "quantity_machine_l", f"SMM.{asset_id}.MAIN_TANK.QUANTITY_L_PV"
    if reg_num == 14 or "flow" in n:
        return "PV", "ACTUAL", False, "WATER_INLET", "flow_rate", f"SMM.{asset_id}.WATER_INLET.FLOW_PV"
    if reg_num == 15 or "water counter" in n:
        return "PV", "ACTUAL", False, "WATER_INLET", "water_counter", f"SMM.{asset_id}.WATER_INLET.COUNTER_PV"
    if reg_num == 16 or "pressure machine" in n:
        return "PV", "ACTUAL", False, "VESSEL", "pressure_machine", f"SMM.{asset_id}.VESSEL.PRESSURE_PV"
    if reg_num == 19 or "quantity at2" in n:
        return "PV", "ACTUAL", False, "DOSING_TANK_02", "quantity_at2_l", f"SMM.{asset_id}.DOSING_TANK_02.QUANTITY_L_PV"
    if reg_num == 21 or "speed main pump" in n:
        return "PV", "ACTUAL", False, "MAIN_MOTOR", "speed_main_pump", f"SMM.{asset_id}.MAIN_MOTOR.SPEED_PV"
    if reg_num == 22 or "winch speed" in n:
        return "PV", "ACTUAL", False, "MAIN_MOTOR", "winch_speed", f"SMM.{asset_id}.MAIN_MOTOR.WINCH_SPEED_PV"
    if reg_num == 23 or "vario nozzle" in n:
        return "PV", "ACTUAL", False, "MAIN_TANK", "vario_nozzle", f"SMM.{asset_id}.MAIN_TANK.NOZZLE_PV"
    if reg_num == 25:
        return "PV", "ACTUAL", False, "SERVICE_TANK", "temperature_st", f"SMM.{asset_id}.SERVICE_TANK.TEMPERATURE_PV"
    if reg_num == 26:
        return "PV", "ACTUAL", False, "SERVICE_TANK", "time_st", f"SMM.{asset_id}.SERVICE_TANK.TIME_PV"
    if reg_num == 27:
        return "PV", "ACTUAL", False, "SERVICE_TANK", "level_st_l", f"SMM.{asset_id}.SERVICE_TANK.LEVEL_L_PV"
    if reg_num == 28:
        return "PV", "ACTUAL", False, "SERVICE_TANK", "level_st_pct", f"SMM.{asset_id}.SERVICE_TANK.LEVEL_PV"
    if reg_num == 30:
        return "PV", "ACTUAL", False, "ADDITION_TANK", "temperature_at", f"SMM.{asset_id}.ADDITION_TANK.TEMPERATURE_PV"
    if reg_num == 31:
        return "PV", "ACTUAL", False, "ADDITION_TANK", "time_at", f"SMM.{asset_id}.ADDITION_TANK.TIME_PV"
    if reg_num == 32:
        return "PV", "ACTUAL", False, "ADDITION_TANK", "level_at_l", f"SMM.{asset_id}.ADDITION_TANK.LEVEL_L_PV"
    if reg_num == 33:
        return "PV", "ACTUAL", False, "ADDITION_TANK", "level_at_pct", f"SMM.{asset_id}.ADDITION_TANK.LEVEL_PV"
    if reg_num == 40:
        return "PV", "ACTUAL", False, "DOSING_TANK_01", "temperature_at1", f"SMM.{asset_id}.DOSING_TANK_01.TEMPERATURE_PV"
    if reg_num == 41:
        return "PV", "ACTUAL", False, "DOSING_TANK_01", "time_at1", f"SMM.{asset_id}.DOSING_TANK_01.TIME_PV"
    if reg_num == 42:
        return "PV", "ACTUAL", False, "DOSING_TANK_01", "level_at1_l", f"SMM.{asset_id}.DOSING_TANK_01.LEVEL_L_PV"
    if reg_num == 43:
        return "PV", "ACTUAL", False, "DOSING_TANK_01", "level_at1_pct", f"SMM.{asset_id}.DOSING_TANK_01.LEVEL_PV"
    if reg_num == 45:
        return "PV", "ACTUAL", False, "DOSING_TANK_02", "temperature_at2", f"SMM.{asset_id}.DOSING_TANK_02.TEMPERATURE_PV"
    if reg_num == 46:
        return "PV", "ACTUAL", False, "DOSING_TANK_02", "time_at2", f"SMM.{asset_id}.DOSING_TANK_02.TIME_PV"
    if reg_num == 47:
        return "PV", "ACTUAL", False, "DOSING_TANK_02", "level_at2_l", f"SMM.{asset_id}.DOSING_TANK_02.LEVEL_L_PV"
    if reg_num == 48:
        return "PV", "ACTUAL", False, "DOSING_TANK_02", "level_at2_pct", f"SMM.{asset_id}.DOSING_TANK_02.LEVEL_PV"
    if 71 <= reg_num <= 76:
        hank_num = reg_num - 70
        return "PV", "ACTUAL", False, "FABRIC", f"hank_time_{hank_num}", f"SMM.{asset_id}.FABRIC.HANK_{hank_num}_TIME_PV"
    if reg_num == 84:
        return "PV", "ACTUAL", False, "MAIN_TANK", "nozzle_pressure", f"SMM.{asset_id}.MAIN_TANK.NOZZLE_PRESSURE_PV"
    if reg_num == 85:
        return "PV", "ACTUAL", False, "MAIN_TANK", "memory_level", f"SMM.{asset_id}.MAIN_TANK.MEMORY_LEVEL_PV"
    if reg_num == 86:
        return "PV", "ACTUAL", False, "MAIN_TANK", "ph_value", f"SMM.{asset_id}.MAIN_TANK.PH_PV"
    if 90 <= reg_num <= 95:
        cycle_num = reg_num - 89
        return "PV", "ACTUAL", False, "PROCESS", f"cycle_time_{cycle_num}", f"SMM.{asset_id}.PROCESS.CYCLE_{cycle_num}_TIME_PV"
    if reg_num == 100:
        return "PV", "ACTUAL", False, "MAIN_MOTOR", "cycle_control_speed", f"SMM.{asset_id}.MAIN_MOTOR.CYCLE_CONTROL_SPEED_PV"
    if reg_num == 160:
        return "PV", "ACTUAL", False, "MAIN_MOTOR", "main_pump_rpm", f"SMM.{asset_id}.MAIN_MOTOR.PUMP_RPM_PV"
    if reg_num == 190:
        return "PV", "ACTUAL", False, "MAIN_TANK", "temp_ctrl_output_pct", f"SMM.{asset_id}.MAIN_TANK.TEMP_CTRL_OUTPUT_PV"
    if reg_num == 199:
        return "PV", "ACTUAL", False, "MAIN_TANK", "act_conductivity", f"SMM.{asset_id}.MAIN_TANK.CONDUCTIVITY_PV"

    # Default fallback
    clean_fn = re_sub(n)
    is_sp = "set" in n or "sp" in n
    role = "SV" if is_sp else "PV"
    dt = "SETPOINT" if is_sp else "ACTUAL"
    return role, dt, is_sp, "PROCESS", clean_fn, f"SMM.{asset_id}.PROCESS.{clean_fn.upper()}_{role}"

def re_sub(text: str) -> str:
    import re
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", text.strip())
    return cleaned.strip("_").lower()

def decode_typeconf_cat10(typeconf_path: str, asset_id: str):
    """Decodes Category 10 from TYPECONF.CNF and returns rich dict mapping."""
    reader = CNFReader(typeconf_path)
    incoming = {f['next'] for f in reader.fragments.values() if f.get('next') and f['next'][1] != 255}
    cat10 = {}

    for address in reader.fragments:
        if address in incoming:
            continue
        try:
            packed, trace = reader.chain(*address)
            raw, runs = reader.decompress(packed)
            if len(raw) == 290:
                key = struct.unpack_from('<3H', raw)
                if key[:2] == (10, 0):
                    idx = key[2]
                    name_en = txt(raw[27:48])
                    name_local = txt(raw[6:27])
                    unit = raw[59:70].split(b'\0', 1)[0].decode('cp437', errors='replace').strip()
                    scale = struct.unpack_from('<BB6fB', raw, 70)

                    role, data_type, is_sp, category, field_name, tag_name = classify_register(idx, name_en, asset_id)

                    cat10[str(idx)] = {
                        "index": idx,
                        "iw_number": idx,
                        "name": name_en,
                        "name_local": name_local,
                        "unit": unit,
                        "tag_role": role,          # "SV" (Setpoint) vs "PV" (Actual Data) vs "STATUS"
                        "data_type": data_type,    # "SETPOINT" vs "ACTUAL" vs "STATUS" vs "ALARM"
                        "is_setpoint": is_sp,      # Boolean True if Setpoint, False if Actual / Status
                        "category": category,
                        "field_name": field_name,
                        "tag_name": tag_name,
                        "digits_before": scale[0],
                        "digits_after": scale[1],
                        "factor": round(scale[2], 4),
                        "offset": round(scale[3], 4),
                        "x1": round(scale[4], 2),
                        "x2": round(scale[5], 2),
                        "y1": round(scale[6], 2),
                        "y2": round(scale[7], 2)
                    }
        except Exception:
            continue

    return cat10

def process_machine(item):
    folder, ip = item
    asset_id = machine_to_asset_id(folder)
    raw_dir = os.path.join(WORKSPACE_DIR, folder, "01_CONFIG_DARI_HMI")
    dec_dir = os.path.join(WORKSPACE_DIR, folder, "02_CONFIG_SIAP_PAKAI")
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(dec_dir, exist_ok=True)

    result = {
        "folder": folder,
        "asset_id": asset_id,
        "ip": ip,
        "success": False,
        "downloaded": [],
        "cp14_sha256": None,
        "cp14_size": None,
        "typeconf_sha256": None,
        "registers_count": 0,
        "setpoints_count": 0,
        "actuals_count": 0,
        "error": None
    }

    try:
        ftp = ftplib.FTP(timeout=4.0)
        ftp.connect(ip, 21)
        ftp.login()
        ftp.voidcmd("TYPE I")

        remote_config_dir = None
        for cand in ["/Storage/SC777CE/Config", "/Storage/sc777ce/Config", "/SC777CE/Config"]:
            try:
                nlst = ftp.nlst(cand)
                upper = [os.path.basename(x.replace("\\", "/")).upper() for x in nlst]
                if "CP14.AWL" in upper or "TYPECONF.CNF" in upper:
                    remote_config_dir = cand
                    break
            except Exception:
                continue

        if not remote_config_dir:
            result["error"] = "Remote config directory not found"
            ftp.quit()
            return result

        # Download targets: CP14.AWL, TYPECONF.CNF, CONFTEXT.CNF, MACHCONF.CNF
        targets = ["CP14.AWL", "TYPECONF.CNF", "CONFTEXT.CNF", "MACHCONF.CNF"]
        remote_files = ftp.nlst(remote_config_dir)
        rf_map = {os.path.basename(x.replace("\\", "/")).upper(): os.path.basename(x.replace("\\", "/")) for x in remote_files}

        for t in targets:
            if t in rf_map:
                actual_name = rf_map[t]
                local_file = os.path.join(raw_dir, t)
                with open(local_file, "wb") as f:
                    ftp.retrbinary(f"RETR {remote_config_dir}/{actual_name}", f.write)
                size = os.path.getsize(local_file)
                result["downloaded"].append(t)
                if t == "CP14.AWL":
                    result["cp14_size"] = size
                    with open(local_file, "rb") as cf:
                        result["cp14_sha256"] = hashlib.sha256(cf.read()).hexdigest()
                elif t == "TYPECONF.CNF":
                    with open(local_file, "rb") as cf:
                        result["typeconf_sha256"] = hashlib.sha256(cf.read()).hexdigest()

        ftp.quit()

        # Parse TYPECONF.CNF if downloaded
        tc_path = os.path.join(raw_dir, "TYPECONF.CNF")
        if os.path.exists(tc_path) and os.path.getsize(tc_path) > 1000:
            iw_map = decode_typeconf_cat10(tc_path, asset_id)
            if iw_map:
                out_map_path = os.path.join(dec_dir, "typeconf_iw_map.json")
                with open(out_map_path, "w", encoding="utf-8") as f:
                    json.dump(iw_map, f, indent=2)

                sp_cnt = sum(1 for v in iw_map.values() if v.get("tag_role") == "SV")
                pv_cnt = sum(1 for v in iw_map.values() if v.get("tag_role") == "PV")
                result["registers_count"] = len(iw_map)
                result["setpoints_count"] = sp_cnt
                result["actuals_count"] = pv_cnt
                result["success"] = True

        # Update machine_profile.json
        prof_file = os.path.join(dec_dir, "machine_profile.json")
        prof_data = {}
        if os.path.exists(prof_file):
            try:
                with open(prof_file, "r", encoding="utf-8") as f:
                    prof_data = json.load(f)
            except Exception:
                pass

        prof_data.update({
            "machine_no": folder.replace("MESIN_", "").upper(),
            "asset_id": asset_id,
            "ip_address": ip,
            "has_cp14_awl": "CP14.AWL" in result["downloaded"],
            "cp14_sha256": result["cp14_sha256"],
            "cp14_size_bytes": result["cp14_size"],
            "has_typeconf": "TYPECONF.CNF" in result["downloaded"],
            "typeconf_sha256": result["typeconf_sha256"],
            "registers_count": result["registers_count"],
            "setpoints_count": result["setpoints_count"],
            "actuals_count": result["actuals_count"],
            "last_synced_at": datetime.now().isoformat(),
            "status": "ready" if result["success"] else prof_data.get("status", "unknown")
        })
        with open(prof_file, "w", encoding="utf-8") as f:
            json.dump(prof_data, f, indent=2)

    except Exception as e:
        result["error"] = str(e)

    return result

def main():
    # Load scan results
    scan_file = os.path.join(os.path.dirname(__file__), "scan_results.json")
    if not os.path.exists(scan_file):
        print("[ERROR] scan_results.json not found! Run scan first.")
        return

    with open(scan_file, "r", encoding="utf-8") as f:
        scan_data = json.load(f)

    online_items = [(r["folder"], r["ip"]) for r in scan_data if r["status"] == "online"]
    print(f"[*] Starting download & parsing for {len(online_items)} online machines...")

    with ThreadPoolExecutor(max_workers=16) as ex:
        results = list(ex.map(process_machine, online_items))

    success = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]

    print("\n" + "=" * 80)
    print("HASIL SINKRONISASI & PARSING CP14.AWL + TYPECONF.CNF")
    print("=" * 80)
    print(f"Total Mesin Diproses : {len(results)}")
    print(f"Berhasil             : {len(success)}")
    print(f"Gagal / Parsial      : {len(failed)}")
    print("=" * 80)

    for r in success:
        print(f"  + {r['folder']:<15} ({r['ip']:<15}): CP14={r['cp14_size']} B | Registers={r['registers_count']} (SV={r['setpoints_count']}, PV={r['actuals_count']})")

    if failed:
        print("\nMesin Bermasalah:")
        for r in failed:
            print(f"  - {r['folder']:<15} ({r['ip']:<15}): {r['error']}")

    # Save summary
    with open(os.path.join(os.path.dirname(__file__), "sync_summary.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    main()
