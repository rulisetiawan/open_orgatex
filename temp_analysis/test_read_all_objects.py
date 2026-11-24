import socket
import struct
import sys
import json
import os
import threading

sys.path.append(os.path.abspath("SETEX-LAN 50000/SETEX-LAN 50000"))
from setex_controller import build_read, parse_response
from setex_intervent import decode_function, function_frame, _exchange

def read_all_objects(host="172.16.110.101", port=50000, machine_no="1A"):
    # Load parameters metadata from typeconf_functions.json
    tf_path = f"WORKSPACE_PROGRAM_MESIN/MESIN_{machine_no}/02_CONFIG_SIAP_PAKAI/typeconf_functions.json"
    params_meta = {}
    if os.path.exists(tf_path):
        with open(tf_path, "r", encoding="utf-8") as f:
            params_meta = json.load(f).get("parameters", {})

    # Load IW metadata from typeconf_iw_map.json
    iw_path = f"WORKSPACE_PROGRAM_MESIN/MESIN_{machine_no}/02_CONFIG_SIAP_PAKAI/typeconf_iw_map.json"
    iw_meta = {}
    if os.path.exists(iw_path):
        with open(iw_path, "r", encoding="utf-8") as f:
            iw_meta = json.load(f)

    result = {
        "host": host,
        "port": port,
        "machine_no": machine_no,
        "objects": {}
    }

    # 1. Object 1009 (SET - Setpoints / SOLL)
    try:
        s = socket.socket()
        s.settimeout(2.5)
        s.connect((host, port))
        s.sendall(build_read(11, 1009, 1, 40))
        set_words = parse_response(s.recv(516), 11, 1009, 40)
        s.close()

        decoded_set = []
        for i, raw in enumerate(set_words, 1):
            meta = params_meta.get(str(i), {})
            factor = meta.get("scale", {}).get("factor", 1.0) or 1.0
            val = round(raw / factor, 2) if factor > 0 else raw
            if raw != 0 or i in [1, 2, 3, 4, 5, 9, 73, 83]:
                decoded_set.append({
                    "address": i,
                    "name": meta.get("name", f"Parameter {i}"),
                    "name_local": meta.get("name_local", ""),
                    "unit": meta.get("unit", ""),
                    "raw": raw,
                    "calibrated_value": val,
                    "role": "SV",
                    "data_type": "SETPOINT"
                })
        result["objects"]["SET_1009"] = {
            "name": "SET (SOLL - Setpoint Target)",
            "role": "SV",
            "total_read": len(set_words),
            "registers": decoded_set
        }
    except Exception as e:
        result["objects"]["SET_1009"] = {"error": str(e)}

    # 2. Object 1010 (ACT - Actuals / IST)
    try:
        s = socket.socket()
        s.settimeout(2.5)
        s.connect((host, port))
        s.sendall(build_read(11, 1010, 1, 20))
        act_words = parse_response(s.recv(516), 11, 1010, 20)
        s.close()

        decoded_act = []
        for i, raw in enumerate(act_words, 1):
            if raw != 0:
                decoded_act.append({
                    "address": i,
                    "raw": raw,
                    "role": "PV",
                    "data_type": "ACTUAL"
                })
        result["objects"]["ACT_1010"] = {
            "name": "ACT (IST - Loop Actuals)",
            "role": "PV",
            "total_read": len(act_words),
            "registers": decoded_act
        }
    except Exception as e:
        result["objects"]["ACT_1010"] = {"error": str(e)}

    # 3. Object 1025 (IW - Info Words)
    try:
        s = socket.socket()
        s.settimeout(2.5)
        s.connect((host, port))
        s.sendall(build_read(11, 1025, 1, 40))
        iw_words = parse_response(s.recv(516), 11, 1025, 40)
        s.close()

        decoded_iw = []
        for i, raw in enumerate(iw_words, 1):
            meta = iw_meta.get(str(i), {})
            factor = meta.get("factor", 1.0) or 1.0
            val = round(raw / factor, 2) if factor > 0 else raw
            if raw != 0 or i in [1, 2, 10, 12, 13, 16, 21, 22]:
                decoded_iw.append({
                    "address": i,
                    "name": meta.get("name", f"IW {i}"),
                    "name_local": meta.get("name_local", ""),
                    "unit": meta.get("unit", ""),
                    "raw": raw,
                    "calibrated_value": val,
                    "role": meta.get("tag_role", "PV"),
                    "data_type": meta.get("data_type", "ACTUAL")
                })
        result["objects"]["IW_1025"] = {
            "name": "IW (Info Words Telemetry)",
            "role": "PV / Telemetry",
            "total_read": len(iw_words),
            "registers": decoded_iw
        }
    except Exception as e:
        result["objects"]["IW_1025"] = {"error": str(e)}

    # 4. Object 1035 (Batch Consumption DWORD)
    try:
        s = socket.socket()
        s.settimeout(2.5)
        s.connect((host, port))
        s.sendall(build_read(11, 1035, 1, 10))
        batch_words = parse_response(s.recv(516), 11, 1035, 10)
        s.close()
        result["objects"]["BATCH_1035"] = {
            "name": "BATCH_CONSUMPTION (DWORD 32-bit)",
            "role": "COUNTER",
            "counters": {f"Counter_{i}": v for i, v in enumerate(batch_words, 1) if v != 0}
        }
    except Exception as e:
        result["objects"]["BATCH_1035"] = {"error": str(e)}

    # 5. Object 6 (Active Step Functions: 141, 713, 71)
    active_funcs = {}
    for fid in [141, 713, 71]:
        try:
            f_resp = _exchange(host, port, function_frame(1, function_id=fid), threading.Event())
            snap = decode_function(f_resp, fid)
            active_funcs[f"Function_{fid}"] = {
                "line": snap.line,
                "values": list(snap.values),
                "parameter_ids": list(snap.parameter_ids)
            }
        except Exception as e:
            active_funcs[f"Function_{fid}"] = {"error": str(e)}

    result["objects"]["FUNCTION_6"] = {
        "name": "ACTIVE_FUNCTIONS (Step Recipe Parameters)",
        "role": "RECIPE_SV",
        "functions": active_funcs
    }

    return result

if __name__ == "__main__":
    res = read_all_objects()
    print(json.dumps(res, indent=2))
