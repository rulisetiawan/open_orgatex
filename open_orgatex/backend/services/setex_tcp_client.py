"""
OpenOrgaTEX - SETEX Controller TCP Protocol Client (SC737 over TCP Port 50000)
Ports and enhances the verified protocol implementation from SETEX-LAN 50000:
- Reads IW (Info Words / 1025)
- Reads SET (Setpoint SOLL / 1009)
- Reads ACT (Aktual IST / 1010)
- Reads active function parameters (Object 6, e.g. Func 141 Temp/Gradient/Time)
- Provides scaffolded safe write mechanism
"""

import os
import socket
import struct
import math
import logging
import threading
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger("orgatex.setex_tcp")

FRAME_SIZE = 516
ALLOWED_OBJECTS = {1001, 1002, 1009, 1010, 1025, 1026, 1035, 1057, 1058, 6}

OBJECT_NAMES = {
    1025: "IW (Info Words)",
    1009: "SET (Target/SOLL)",
    1010: "ACT (Actual/IST)",
    1001: "LW (Link Words)",
    1058: "MW (Memory Words)",
    1035: "BATCH_CONSUMPTION",
    6: "FUNCTION_PARAMETERS"
}

PROFILE_PARAMETERS = {
    141: {
        "name": "Temperature Control",
        "params": {
            0: ("Target Temperature", "°C", 0.0, 150.0),
            1: ("Temperature Gradient", "°C/min", 0.0, 9.9),
            2: ("Holding Time", "min", 0.0, 180.0)
        }
    },
    71: {
        "name": "Drain Percent",
        "params": {
            0: ("End Level", "%", 0.0, 100.0),
            2: ("Drain Time", "min", 0.0, 180.0)
        }
    },
    713: {
        "name": "Fill Level",
        "params": {
            1: ("Fill Volume", "L", 0.0, 50000.0)
        }
    }
}

class SetexTcpClient:
    """
    Client for direct TCP communication with SETEX SECOM 777/737 controllers on Port 50000.
    """

    @staticmethod
    def _exchange(host: str, port: int, request_frame: bytes, timeout: float = 3.0) -> bytes:
        """Sends a 516-byte frame and receives the 516-byte response."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.sendall(request_frame)

            response = bytearray()
            while len(response) < FRAME_SIZE:
                chunk = sock.recv(FRAME_SIZE - len(response))
                if not chunk:
                    break
                response.extend(chunk)

            if len(response) != FRAME_SIZE:
                raise ConnectionError(f"Received incomplete frame: {len(response)} bytes (expected {FRAME_SIZE})")

            return bytes(response)

    @classmethod
    def build_read_frame(cls, service: int, obj: int, address: int, count: int = 1) -> bytes:
        """Builds standard 516-byte SC737 read frame."""
        payload = struct.pack('<H', address) if service == 1 else struct.pack('<HH', address, count)
        frame = bytearray(FRAME_SIZE)
        struct.pack_into('<HH', frame, 0, 2, 16 + len(payload))
        frame[4:7] = bytes((10, 12, 0))
        struct.pack_into('<H', frame, 9, 1)
        frame[14] = 1        # Message Type
        frame[15] = service  # Service (1 = SV_READ, 11 = SV_READ_BLOCK)
        struct.pack_into('<HH', frame, 16, obj, len(payload))
        frame[20:20 + len(payload)] = payload
        return bytes(frame)

    @classmethod
    def read_word(cls, host: str, port: int, obj: int, address: int, timeout: float = 2.5) -> int:
        """Reads a single uint16 register from controller."""
        frame = cls.build_read_frame(1, obj, address, 1)
        resp = cls._exchange(host, port, frame, timeout)
        cls._validate_frame(resp, 1, obj)
        return struct.unpack_from('<H', resp, 20)[0]

    @classmethod
    def read_block(cls, host: str, port: int, obj: int, start_address: int, count: int, timeout: float = 3.0) -> List[int]:
        """Reads a continuous block of uint16 registers (up to 240 words)."""
        if count < 1 or count > 240:
            raise ValueError("Count must be between 1 and 240.")
        frame = cls.build_read_frame(11, obj, start_address, count)
        resp = cls._exchange(host, port, frame, timeout)
        size = cls._validate_frame(resp, 11, obj)
        width = 4 if obj == 1035 else 2
        code = 'I' if obj == 1035 else 'H'
        if size != count * width:
            raise ValueError(f"Payload size mismatch: expected {count*width}, got {size}")
        return list(struct.unpack_from('<' + code * count, resp, 20))

    @classmethod
    def read_batch_consumption(cls, host: str, port: int, start_index: int = 1, count: int = 10, timeout: float = 3.0) -> List[int]:
        """
        Reads batch consumption counters (Object 1035 - 32-bit DWORD Little-Endian).
        Counters include total water (L), steam, energy/power (kWh), and runtime.
        """
        if count < 1 or count > 80:
            raise ValueError("Consumption counter count must be between 1 and 80.")
        return cls.read_block(host, port, 1035, start_index, count, timeout=timeout)

    @classmethod
    def build_change_parameter_extended_frame(cls, entries: List[Tuple[int, float]], flag: int = 1, target_extra: int = 0) -> bytes:
        """
        Builds SV_CHANGE_EXTENDED (Service 137) on OBJID_PARAMETER (Object 41).
        Reconstructed from SETEX-LAN 50000 reverse engineering of SecomCE_D_BackGround_2d.dll.
        - flag = 1 triggers the internal PLC intervention bit (Object 1079 addr 12 / Object 1002 addr 3512)
        - target_extra = 0 updates both active running PLC step and logs to PRxxxxxx.LOG
        """
        if not entries or len(entries) > 20:
            raise ValueError("Entries count must be between 1 and 20.")

        frame = bytearray(FRAME_SIZE)
        struct.pack_into('<HH', frame, 0, 2, 16 + 124)
        frame[4:7] = bytes((10, 12, 0))
        struct.pack_into('<H', frame, 9, 1)
        frame[14] = 1        # Message Type (1 = Request)
        frame[15] = 137      # Service 137 (SV_CHANGE_EXTENDED)
        struct.pack_into('<HH', frame, 16, 41, 124)  # Object 41 (OBJID_PARAMETER), length 124
        frame[20] = flag     # Flag: 1 = trigger PLC intervention
        frame[21] = len(entries)  # Count of entries

        for i, (pid, val) in enumerate(entries):
            off = 22 + 6 * i
            struct.pack_into('<H', frame, off, int(pid))
            struct.pack_into('<f', frame, off + 2, float(val))

        # Target extra at frame offset 142 (payload offset 122)
        struct.pack_into('<H', frame, 142, int(target_extra))
        return bytes(frame)

    @classmethod
    def change_parameter_da01_only(cls, machine_no: str, host: str, port: int, param_id: int, value: float, parameter_name: str = "") -> Dict[str, Any]:
        """
        Executes parameter modification (Intervent) via Service 137 / Object 41.
        
        SAFETY INTERLOCK:
        Strictly restricted to pilot machine 'DA01' only. All other machines are locked
        in Read-Only mode to protect factory production lines.
        """
        clean_mach = str(machine_no or "").strip().upper()
        if clean_mach != "DA01":
            raise PermissionError(
                f"Akses Ditolak: Perubahan parameter jarak jauh via web HANYA diizinkan untuk mesin pilot 'DA01'. "
                f"Mesin '{clean_mach}' terkunci dalam mode Aman / Read-Only demi keselamatan operasional pabrik."
            )

        # Build and send frame
        req = cls.build_change_parameter_extended_frame([(param_id, value)], flag=1, target_extra=0)
        resp = cls._exchange(host, port, req, timeout=3.5)

        # Validate response
        cls._validate_frame(resp, 137, 41)

        return {
            "status": "success",
            "machine_no": "DA01",
            "param_id": param_id,
            "parameter_name": parameter_name or f"Param {param_id}",
            "value_applied": value,
            "message": f"Berhasil mengirim Intervent parameter {param_id} = {value} ke kontroler SETEX mesin DA01 via Port 50000 (Svc 137 / Obj 41)."
        }

    @classmethod
    def read_active_function(cls, host: str, port: int, function_id: int = 141, timeout: float = 3.0) -> Dict[str, Any]:
        """
        Reads active function parameters from controller (Service 1 on Object 6).
        Used for reading active Temperature, Gradient, and Time on the fly.
        """
        frame = bytearray(cls.build_read_frame(1, 1025, 1))
        frame[20:] = bytes(len(frame) - 20)
        frame[15] = 1  # SV_READ
        struct.pack_into('<HH', frame, 16, 6, 64)
        struct.pack_into('<H', frame, 2, 80)
        frame[20] = 0  # Active line (0 = current active)
        struct.pack_into('<H', frame, 21, function_id)
        req = bytes(frame)

        resp = cls._exchange(host, port, req, timeout)
        cls._validate_frame(resp, 1, 6)

        line = resp[20]
        fid = struct.unpack_from('<H', resp, 21)[0]
        values = tuple(struct.unpack_from('<f', resp, 25 + 8 * i)[0] for i in range(6))
        parameter_ids = tuple(struct.unpack_from('<H', resp, 29 + 8 * i)[0] for i in range(6))

        spec = PROFILE_PARAMETERS.get(fid, {"name": f"Function {fid}", "params": {}})
        parsed_params = []
        for i in range(6):
            val = values[i] if i < len(values) else 0.0
            pid = parameter_ids[i] if i < len(parameter_ids) else 0
            pinfo = spec["params"].get(i, (f"Param P{i+1}", "", 0.0, 9999.0))
            parsed_params.append({
                "param_no": i + 1,
                "name": pinfo[0],
                "unit": pinfo[1],
                "value": round(val, 2) if math.isfinite(val) else 0.0,
                "parameter_id": pid,
                "min": pinfo[2],
                "max": pinfo[3]
            })

        return {
            "function_id": fid,
            "function_name": spec["name"],
            "line": line,
            "parameters": parsed_params,
            "raw_values": list(values)
        }

    @classmethod
    def read_setpoints_snapshot(cls, host: str, port: int, machine_no: str = "") -> Dict[str, Any]:
        """
        Captures a comprehensive setpoint snapshot from the controller:
        - Primary Target Temperature (SET / Obj 1009)
        - Target Holding Time
        - Target Pump Speed
        - Active Function 141 Parameters (Temp, Gradient, Time)
        - Key Info Words (IW / Obj 1025)
        """
        snapshot = {
            "machine_no": machine_no,
            "host": host,
            "port": port,
            "online": False,
            "setpoints": {},
            "active_function": None,
            "info_words": {},
            "error": None
        }

        try:
            # 1. Read first 20 SET registers (Object 1009)
            set_words = cls.read_block(host, port, 1009, 1, 20, timeout=2.0)
            snapshot["setpoints"] = {
                "temp_sp": set_words[0] / 10.0 if len(set_words) > 0 and set_words[0] > 0 else 0.0,
                "holding_time_sp": set_words[1] if len(set_words) > 1 else 0.0,
                "gradient_sp": set_words[2] / 10.0 if len(set_words) > 2 else 0.0,
                "pump_sp": set_words[3] if len(set_words) > 3 else 0.0,
                "raw_set_words": set_words
            }
            snapshot["online"] = True
        except Exception as e:
            logger.debug(f"Could not read SET block from {host}:{port}: {e}")
            snapshot["error"] = str(e)

        try:
            # 2. Read Active Function 141 (Temperature Control)
            func_data = cls.read_active_function(host, port, 141, timeout=2.0)
            snapshot["active_function"] = func_data
            snapshot["online"] = True
            # If function 141 returned valid temperature, enrich temp_sp
            if func_data.get("parameters"):
                p1_val = func_data["parameters"][0]["value"]
                if p1_val > 0:
                    snapshot["setpoints"]["temp_sp"] = p1_val
                p2_val = func_data["parameters"][1]["value"]
                if p2_val > 0:
                    snapshot["setpoints"]["gradient_sp"] = p2_val
                p3_val = func_data["parameters"][2]["value"]
                if p3_val > 0:
                    snapshot["setpoints"]["holding_time_sp"] = p3_val
        except Exception as e:
            logger.debug(f"Could not read Function 141 from {host}:{port}: {e}")

        try:
            # 3. Read key IW words (Object 1025)
            iw_words = cls.read_block(host, port, 1025, 1, 10, timeout=2.0)
            snapshot["info_words"] = {
                "iw_raw": iw_words
            }
            snapshot["online"] = True
        except Exception as e:
            logger.debug(f"Could not read IW block from {host}:{port}: {e}")

        return snapshot

    @classmethod
    def read_iw_telemetry(cls, host: str, port: int = 50000, count: int = 80, machine_no: str = "", timeout: float = 1.5) -> Dict[str, Any]:
        """
        Reads live IW (Object 1025 / Info Words) directly from SETEX Controller TCP Port 50000.
        Decodes operational registers using each machine's specific TYPECONF.CNF configuration and linear calibration.
        """
        try:
            from .typeconf_iw_service import TypeconfIwService
            words = cls.read_block(host, port, 1025, 1, min(count, 240), timeout=timeout)

            # Convert every word using the machine's own TYPECONF formula
            decoded_registers = []
            non_zero = {}
            for idx, raw_val in enumerate(words):
                reg_num = idx + 1
                conv = TypeconfIwService.convert_register(machine_no, reg_num, raw_val)
                decoded_registers.append(conv)
                if raw_val != 0:
                    non_zero[f"IW_{reg_num}"] = raw_val

            # Key measurements decoded through machine TYPECONF
            # IW 1: act.Temp.
            t1 = decoded_registers[0]["conv_val"] if len(decoded_registers) > 0 and 0 <= decoded_registers[0]["conv_val"] <= 150 else None
            # IW 12: level machine (%) / pump act
            level_act = decoded_registers[11]["conv_val"] if len(decoded_registers) > 11 else None
            # IW 21: speed main pump (%)
            pump_sp = decoded_registers[20]["conv_val"] if len(decoded_registers) > 20 else None
            # IW 22: winch speed (m/dak)
            reel_act = decoded_registers[21]["conv_val"] if len(decoded_registers) > 21 else None

            return {
                "online": True,
                "machine_no": machine_no,
                "host": host,
                "port": port,
                "word_count": len(words),
                "iw_t1_pv": t1,
                "iw_level_act": level_act,
                "iw_pump_act": level_act,  # fallback parity
                "iw_pump_sp": pump_sp,
                "iw_reel_act": reel_act,
                "raw_words": words,
                "decoded_registers": decoded_registers,
                "non_zero": non_zero
            }
        except Exception as e:
            return {
                "online": False,
                "machine_no": machine_no,
                "host": host,
                "port": port,
                "error": str(e),
                "word_count": 0,
                "raw_words": [],
                "decoded_registers": [],
                "non_zero": {}
            }

    @classmethod
    def read_live_alarm_status(cls, host: str, port: int, timeout: float = 2.0) -> Dict[str, Any]:
        """
        Queries Controller Service 112 (Object 0) directly via TCP Port 50000.
        Returns authentic live alarm state directly from controller CPU without relying on stale files.
        """
        try:
            frame = bytearray(cls.build_read_frame(1, 1025, 1))
            frame[20:] = bytes(len(frame) - 20)
            frame[15] = 112  # Service 112
            struct.pack_into('<HHH', frame, 16, 0, 0, 0)
            struct.pack_into('<H', frame, 2, 16)

            resp = cls._exchange(host, port, bytes(frame), timeout=timeout)
            if len(resp) != FRAME_SIZE:
                return {"is_alarm_active": False, "alarm_count": 0, "priority": 0}

            priority, count = struct.unpack_from('<HH', resp, 399)
            if priority > 2000 or count > 2000:
                return {"is_alarm_active": False, "alarm_count": 0, "priority": 0}

            return {
                "is_alarm_active": count > 0,
                "alarm_count": count,
                "priority": priority,
                "stop": int(resp[404]),
                "halt": int(resp[405])
            }
        except Exception as e:
            return {"is_alarm_active": False, "alarm_count": 0, "priority": 0, "error": str(e)}

    @classmethod
    def write_setpoint(cls, host: str, port: int, obj: int, address: int, value: int) -> Dict[str, Any]:
        """
        Scaffolded Setpoint Write (Service 2 SV_WRITE).
        Protected by WRITE_MODE_ENABLED environment flag.
        """
        write_enabled = os.getenv("WRITE_MODE_ENABLED", "false").lower() in ("true", "1")
        if not write_enabled:
            return {
                "status": "blocked",
                "message": "Write mode is currently DISABLED in OpenOrgaTEX safety settings (Read-Only Mode Active).",
                "target": f"{host}:{port}",
                "obj": obj,
                "address": address,
                "value": value
            }

        # Build frame
        frame = bytearray(cls.build_read_frame(1, obj, address, 1))
        struct.pack_into('<H', frame, 2, 20)
        frame[15] = 2  # SV_WRITE
        struct.pack_into('<HHH', frame, 18, 4, address, value)
        req = bytes(frame)

        resp = cls._exchange(host, port, req, timeout=3.0)
        cls._validate_frame(resp, 2, obj)

        return {
            "status": "success",
            "message": f"Successfully wrote {value} to address {address} (Obj {obj})",
            "acknowledged": True
        }

    @staticmethod
    def _validate_frame(frame: bytes, service: int, obj: int) -> int:
        if len(frame) != FRAME_SIZE:
            raise ConnectionError(f"Frame size invalid: expected {FRAME_SIZE}, got {len(frame)}")
        magic, declared = struct.unpack_from('<HH', frame)
        reply_obj, size = struct.unpack_from('<HH', frame, 16)
        if magic != 2 or declared != size + 16:
            raise ConnectionError("Invalid protocol magic or declared size in header")
        if frame[15] != service or reply_obj != obj:
            raise ConnectionError(f"Response mismatch: requested service={service}, obj={obj}; got service={frame[15]}, obj={reply_obj}")
        if frame[14] != 2:
            raise ConnectionError(f"Controller rejected request (type={frame[14]}). Check controller status.")
        return size
