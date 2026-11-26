"""
DA-Batch-Worker (24x7 Dedicated Background File Ingestion Daemon)
Continuously polls factory dyeing controllers (SECOM 777 / 797) via FTP port 21:
- Reads STATUS.ACT  -> Decodes live batch, step, program & publishes to EMQX
- Reads PR<batch>.LOG -> Decodes cyclic process curve points & publishes to EMQX
- Reads ALARM.ACT & ALARMS.LOG -> Decodes active/historical alarms & publishes to EMQX

All data is strictly published to EMQX Message Broker (QoS 1).
Database persistence is decoupled and handled by the da-db-writer service.
"""

import os
import re
import sys
import time
import json
import yaml
import socket
import signal
import struct
import logging
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional

import psycopg2
import paho.mqtt.client as mqtt

from reader import SetexFolderReader

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("da-batch-worker")

# Load Configuration
CONFIG_PATH = os.getenv("CONFIG_PATH", "config.yaml")
if not os.path.exists(CONFIG_PATH) and os.path.exists(os.path.join(os.path.dirname(__file__), "config.yaml")):
    CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")

try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        CFG = yaml.safe_load(f)
except Exception as e:
    logger.warning(f"Could not load {CONFIG_PATH}, using defaults: {e}")
    CFG = {
        "worker": {"poll_interval_sec": 60, "max_workers": 6, "socket_timeout_sec": 0.35},
        "emqx": {"host": "192.168.100.30", "port": 1883, "username": "admin", "password": "sensorSMM!"},
        "database": {"url": "postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow"}
    }

EMQX_HOST = os.getenv("EMQX_HOST", CFG["emqx"].get("host", "192.168.100.30"))
EMQX_PORT = int(os.getenv("EMQX_PORT", CFG["emqx"].get("port", 1883)))
EMQX_USER = os.getenv("EMQX_USER", CFG["emqx"].get("username", "admin"))
EMQX_PASS = os.getenv("EMQX_PASS", CFG["emqx"].get("password", "sensorSMM!"))
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SEC", CFG["worker"].get("poll_interval_sec", 60)))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", CFG["worker"].get("max_workers", 6)))
SOCKET_TIMEOUT = float(os.getenv("SOCKET_TIMEOUT_SEC", CFG["worker"].get("socket_timeout_sec", 0.35)))
DB_URL = os.getenv("DATABASE_URL", CFG["database"].get("url", ""))

# Global State
_running = True
_mqtt_client: Optional[mqtt.Client] = None
_mqtt_connected = False


def init_mqtt() -> Optional[mqtt.Client]:
    """Initializes persistent MQTT client connected to EMQX."""
    global _mqtt_client, _mqtt_connected
    client_id = f"da_batch_worker_{os.getpid()}"
    client = mqtt.Client(client_id=client_id, clean_session=True)
    if EMQX_USER:
        client.username_pw_set(EMQX_USER, EMQX_PASS)

    def on_connect(c, userdata, flags, rc):
        global _mqtt_connected
        if rc == 0:
            _mqtt_connected = True
            logger.info(f"Connected to EMQX broker at {EMQX_HOST}:{EMQX_PORT} (ClientID={client_id})")
        else:
            _mqtt_connected = False
            logger.warning(f"EMQX connect failed with rc={rc}")

    def on_disconnect(c, userdata, rc):
        global _mqtt_connected
        _mqtt_connected = False
        logger.debug(f"Disconnected from EMQX broker (rc={rc})")

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    try:
        client.connect_async(EMQX_HOST, EMQX_PORT, keepalive=30)
        client.loop_start()
        _mqtt_client = client
        return client
    except Exception as e:
        logger.error(f"Failed to connect to EMQX broker: {e}")
        return None


def resolve_asset_id(machine_no: str) -> str:
    """Standardizes asset code (e.g. 10B -> JF-LB-10, 10C -> JF-LC-10, 1A -> JF-LA-01)."""
    clean = (machine_no or '').strip().upper()
    digits = re.sub(r'[^0-9]', '', clean)
    letters = re.sub(r'[^A-Z]', '', clean)
    if digits:
        line = letters if len(letters) == 1 else 'B'
        return f"JF-L{line}-{int(digits):02d}"
    return f"JF-LB-{clean}"


def build_scada_program_steps(raw_steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Converts parsed PRG steps into the exact JSON format expected by pt_smm_scada Tabel proses."""
    out = []
    for st in raw_steps:
        slots = []
        temp_sv = None
        for sub in st.get("sub_steps") or []:
            params_out = []
            for p in sub.get("params") or []:
                p_name = str(p.get("name") or "")
                p_val = p.get("value")
                p_unit = str(p.get("unit") or "").strip()
                p_fmt = str(p.get("formatted") or "").strip()
                val_str = p_fmt if p_fmt else (f"{p_val} {p_unit}".strip() if p_val is not None else "")
                params_out.append({"name": p_name, "value": val_str})
                if temp_sv is None and not bool(sub.get("is_sub")) and ("temperature ma" in p_name.lower() or "suhu" in p_name.lower() or "°c" in p_unit.lower()):
                    try:
                        fv = float(p_val)
                        if fv > 0:
                            temp_sv = int(fv) if fv.is_integer() else fv
                    except Exception:
                        pass
            slots.append({
                "func": sub.get("func_name") or sub.get("name") or "",
                "main": not bool(sub.get("is_sub")),
                "slot": int(sub.get("line") or 1),
                "params": params_out,
                "func_id": int(sub.get("func_id") or 0),
                "resource": sub.get("resource_name") or "main tank",
            })
        out.append({
            "no": int(st.get("no") or 0),
            "sv": temp_sv,
            "min": int(st.get("set_time") or 0),
            "step": st.get("name") or "",
            "slots": slots,
            "comment": st.get("comment") or None,
            "func_id": int(st.get("func_id") or 0),
            "hold_min": int(st.get("hold_time") or 0),
            "protect_min": int(st.get("protect_time") or 0),
        })
    return out


def load_program_from_db(
    machine_no: str,
    prog_no: int = 0,
    program_name: str = "",
    program_code: str = "",
) -> Optional[Dict[str, Any]]:
    """
    Looks up program & all its steps from PostgreSQL (program_components + steps +
    step_functions + step_function_parameters). Returns None if not found or has 0 steps,
    so the caller knows to fall back to downloading .PRG via FTP and inserting it into DB.
    """
    if not DB_URL:
        return None
    clean_m = (machine_no or "").strip().upper()
    clean_name = re.sub(r"\s+", " ", (program_name or "").strip()).upper()
    clean_code = (program_code or "").strip().upper()
    p_no_str = str(int(prog_no)) if prog_no and int(prog_no) > 0 else ""

    conn = None
    try:
        conn = psycopg2.connect(DB_URL, connect_timeout=3)
        cur = conn.cursor()

        row = None
        # 1. Exact match on same machine by number or normalized name
        if p_no_str:
            cur.execute("""
                SELECT pc.id, pc.number, pc.name
                FROM program_components pc
                WHERE pc.level = 1
                  AND UPPER(pc.machine_code) = %s
                  AND pc.number = %s
                  AND EXISTS (SELECT 1 FROM steps s WHERE s.parent_component_id = pc.id)
                LIMIT 1
            """, (clean_m, p_no_str))
            row = cur.fetchone()

        if not row and clean_name:
            cur.execute("""
                SELECT pc.id, pc.number, pc.name
                FROM program_components pc
                WHERE pc.level = 1
                  AND UPPER(pc.machine_code) = %s
                  AND UPPER(REGEXP_REPLACE(TRIM(pc.name), '\\s+', ' ', 'g')) = %s
                  AND EXISTS (SELECT 1 FROM steps s WHERE s.parent_component_id = pc.id)
                LIMIT 1
            """, (clean_m, clean_name))
            row = cur.fetchone()

        if not row and clean_code:
            cur.execute("""
                SELECT pc.id, pc.number, pc.name
                FROM program_components pc
                WHERE pc.level = 1
                  AND UPPER(pc.machine_code) = %s
                  AND (UPPER(TRIM(pc.number)) = %s OR UPPER(TRIM(pc.name)) = %s)
                  AND EXISTS (SELECT 1 FROM steps s WHERE s.parent_component_id = pc.id)
                LIMIT 1
            """, (clean_m, clean_code, clean_code))
            row = cur.fetchone()

        if not row:
            return None

        comp_id, db_prog_no, db_prog_name = row

        cur.execute("""
            SELECT s.id, s.position, s.label, s.summary_temp, s.summary_time_min,
                   sf.id, sf.resource_number, sf.function_number, sf.function_name, sf.comment,
                   sfp.function_parameter_number, sfp.value
            FROM steps s
            LEFT JOIN step_functions sf ON sf.step_id = s.id
            LEFT JOIN step_function_parameters sfp ON sfp.step_function_id = sf.id
            WHERE s.parent_component_id = %s
            ORDER BY s.position, sf.resource_number, sf.id, sfp.function_parameter_number
        """, (comp_id,))

        m_data = SetexFolderReader.load_machine_catalog(clean_m)
        func_cat = (m_data.get("functions") if m_data else None) or SetexFolderReader.get_function_catalog() or {}
        res_cat = (m_data.get("resources") if m_data else None) or SetexFolderReader._RESOURCES_CATALOG or {}

        steps_map: Dict[int, Dict[str, Any]] = {}
        funcs_map: Dict[int, Dict[str, Any]] = {}

        for (s_id, pos, lbl, s_temp, s_min, sf_id, res_no, func_no, func_name, sf_comment, p_num, p_val) in cur.fetchall():
            if s_id not in steps_map:
                steps_map[s_id] = {
                    "no": int(pos),
                    "label": lbl or "",
                    "summary_temp": float(s_temp) if s_temp is not None else None,
                    "summary_time_min": float(s_min) if s_min is not None else 0.0,
                    "func_ids": [],
                }
            if sf_id is not None:
                if sf_id not in funcs_map:
                    steps_map[s_id]["func_ids"].append(sf_id)
                    funcs_map[sf_id] = {
                        "slot": int(res_no or 1),
                        "func_id": int(func_no or 0),
                        "func_name": func_name or "",
                        "comment": sf_comment or "",
                        "params": [],
                    }
                if p_num is not None:
                    funcs_map[sf_id]["params"].append((int(p_num), float(p_val) if p_val is not None else 0.0))

        scada_steps = []
        for s_id in sorted(steps_map.keys(), key=lambda k: steps_map[k]["no"]):
            s_info = steps_map[s_id]
            slots = []
            main_func_id = 0
            main_step_name = ""
            temp_sv = s_info["summary_temp"]
            min_val = int(round(s_info["summary_time_min"] or 0))

            for sf_id in s_info["func_ids"]:
                fn = funcs_map[sf_id]
                fid = fn["func_id"]
                slot_no = fn["slot"]
                f_meta = func_cat.get(str(fid), {})
                fname = fn["func_name"] or f_meta.get("name") or SetexFolderReader.FALLBACK_FUNCTION_NAMES.get(fid) or f"Func {fid}"
                res_name = (res_cat.get(str(slot_no), {}) or {}).get("name") or ("main tank" if slot_no == 1 else f"Resource {slot_no}")

                if slot_no == 1:
                    main_func_id = fid
                    main_step_name = fname

                # Format parameters
                p_list = sorted(fn["params"], key=lambda x: x[0])
                p_specs = f_meta.get("params") or []
                params_out = []
                for p_idx, (_, pv) in enumerate(p_list):
                    if p_idx < len(p_specs):
                        ps = p_specs[p_idx]
                        p_name = ps.get("name") or f"P{p_idx + 1}"
                        p_unit = ps.get("unit") or ""
                    else:
                        if pv == 0.0:
                            continue
                        p_name = f"P{p_idx + 1}"
                        p_unit = ""
                    val_fmt = f"{int(pv)}" if float(pv).is_integer() else f"{pv:.1f}"
                    params_out.append({"name": p_name, "value": f"{val_fmt} {p_unit}".strip()})

                    if slot_no == 1 and temp_sv is None and ("temperature ma" in p_name.lower() or "suhu" in p_name.lower() or "°c" in p_unit.lower()):
                        if pv > 0:
                            temp_sv = int(pv) if float(pv).is_integer() else pv
                    if slot_no == 1 and min_val == 0 and ("time" in p_name.lower() or "waktu" in p_name.lower() or p_unit.lower() == "min"):
                        if pv > 0:
                            min_val = int(round(pv))

                slots.append({
                    "func": fname,
                    "main": slot_no == 1,
                    "slot": slot_no,
                    "params": params_out,
                    "func_id": fid,
                    "resource": res_name,
                })

            lbl = s_info["label"]
            comment = lbl if (lbl and not lbl.lower().startswith("langkah ")) else None
            scada_steps.append({
                "no": s_info["no"],
                "sv": int(temp_sv) if (temp_sv is not None and float(temp_sv).is_integer()) else temp_sv,
                "min": min_val,
                "step": main_step_name or lbl or f"Step #{s_info['no']}",
                "slots": slots,
                "comment": comment,
                "func_id": main_func_id,
                "hold_min": 0,
                "protect_min": 0,
            })

        if not scada_steps:
            return None

        return {
            "program_no": str(db_prog_no),
            "program_name": db_prog_name or program_name,
            "scada_steps": scada_steps,
        }
    except Exception as e:
        logger.debug(f"load_program_from_db error for {clean_m}: {e}")
        return None
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def save_prg_steps_to_db(
    machine_no: str,
    prog_no: int,
    program_name: str,
    raw_steps: List[Dict[str, Any]],
) -> bool:
    """
    Persists a newly downloaded .PRG program and all its steps/functions/parameters into
    PostgreSQL (program_components + steps + step_functions + step_function_parameters)
    so future cycles read directly from DB without downloading .PRG over FTP again.
    """
    if not DB_URL or not raw_steps:
        return False
    clean_m = (machine_no or "").strip().upper()
    p_no_str = str(int(prog_no)) if prog_no and int(prog_no) > 0 else "0"
    p_name = (program_name or f"M_{int(prog_no or 0):04d}").strip()[:255]

    conn = None
    try:
        conn = psycopg2.connect(DB_URL, connect_timeout=4)
        cur = conn.cursor()

        # Upsert ProgramComponent (Level 1) per machine_code + number
        cur.execute("""
            SELECT id FROM program_components
            WHERE level = 1 AND UPPER(machine_code) = %s AND number = %s
            LIMIT 1
        """, (clean_m, p_no_str))
        existing = cur.fetchone()
        if existing:
            comp_id = existing[0]
            cur.execute("""
                UPDATE program_components
                SET name = %s, modification_time = NOW()
                WHERE id = %s
            """, (p_name, comp_id))
            # Clear old steps before re-inserting
            cur.execute("""
                DELETE FROM step_function_parameters
                WHERE step_function_id IN (
                    SELECT sf.id FROM step_functions sf
                    JOIN steps s ON s.id = sf.step_id
                    WHERE s.parent_component_id = %s
                )
            """, (comp_id,))
            cur.execute("""
                DELETE FROM step_functions
                WHERE step_id IN (SELECT id FROM steps WHERE parent_component_id = %s)
            """, (comp_id,))
            cur.execute("DELETE FROM steps WHERE parent_component_id = %s", (comp_id,))
        else:
            cur.execute("""
                INSERT INTO program_components (level, type, number, name, hidden, machine_code, content_type, creation_time, modification_time)
                VALUES (1, 1, %s, %s, FALSE, %s, 0, NOW(), NOW())
                RETURNING id
            """, (p_no_str, p_name, clean_m))
            comp_id = cur.fetchone()[0]

        for st in raw_steps:
            step_no = int(st.get("no") or 1)
            label = str(st.get("comment") or st.get("name") or f"Langkah {step_no}")[:100]
            set_time = float(st.get("set_time") or 0.0)
            temp_sv = None
            water_l = 0.0

            sub_steps = st.get("sub_steps") or []
            for sub in sub_steps:
                if not sub.get("is_sub"):
                    for p in sub.get("params") or []:
                        pn = str(p.get("name") or "").lower()
                        pu = str(p.get("unit") or "").lower()
                        pv = p.get("value")
                        try:
                            fv = float(pv)
                        except Exception:
                            continue
                        if temp_sv is None and ("temperature ma" in pn or "suhu" in pn or "°c" in pu) and fv > 0:
                            temp_sv = fv
                        if water_l == 0.0 and ("fill quantity" in pn or "volume" in pn or pu == "l") and fv > 0:
                            water_l = fv

            cur.execute("""
                INSERT INTO steps (position, parent_component_id, label, summary_temp, summary_time_min, summary_water_l)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (step_no, comp_id, label, temp_sv, set_time, water_l))
            step_id = cur.fetchone()[0]

            for sub in sub_steps:
                res_no = int(sub.get("line") or 1)
                fid = int(sub.get("func_id") or 0)
                fname = str(sub.get("func_name") or sub.get("name") or "")[:100]
                cur.execute("""
                    INSERT INTO step_functions (step_id, resource_number, function_number, function_name, label, label_type, acknowledge)
                    VALUES (%s, %s, %s, %s, 0, 0, 0)
                    RETURNING id
                """, (step_id, res_no, fid, fname))
                sf_id = cur.fetchone()[0]

                for p_idx, p in enumerate(sub.get("params") or []):
                    try:
                        fv = float(p.get("value") or 0.0)
                    except Exception:
                        fv = 0.0
                    cur.execute("""
                        INSERT INTO step_function_parameters (step_function_id, function_parameter_number, attribute, value)
                        VALUES (%s, %s, 0, %s)
                    """, (sf_id, p_idx + 1, fv))

        conn.commit()
        logger.info(
            f"Auto-synced program #{p_no_str} ({p_name}, {len(raw_steps)} steps) for {clean_m} into PostgreSQL "
            f"— future cycles will read from DB without downloading .PRG."
        )
        return True
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.warning(f"Failed to auto-save PRG program #{p_no_str} for {clean_m} to PostgreSQL: {e}")
        return False
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def load_program_from_db(
    machine_no: str,
    prog_no: int = 0,
    program_name: str = "",
    program_code: str = "",
) -> Optional[Dict[str, Any]]:
    """
    Looks up program & steps in PostgreSQL (program_components + steps + step_functions + step_function_parameters).
    Returns SCADA-ready program dict if found with steps, else None (triggering one-time FTP .PRG download & DB insert).
    """
    if not DB_URL:
        return None
    clean_m = (machine_no or "").strip().upper().replace("MESIN_", "")
    clean_name = (program_name or "").strip().upper()
    clean_code = (program_code or "").strip().upper()
    if not prog_no and not clean_name and not clean_code:
        return None

    conn = None
    try:
        conn = psycopg2.connect(DB_URL, connect_timeout=3)
        cur = conn.cursor()

        row = None
        # 1. Exact match on same machine_code (by number or name)
        if prog_no and prog_no > 0:
            cur.execute("""
                SELECT pc.id, pc.number, pc.name
                FROM program_components pc
                WHERE pc.level = 1
                  AND UPPER(COALESCE(pc.machine_code, '')) = %s
                  AND pc.number = %s
                  AND EXISTS (SELECT 1 FROM steps s WHERE s.parent_component_id = pc.id)
                ORDER BY pc.modification_time DESC NULLS LAST, pc.id DESC
                LIMIT 1
            """, (clean_m, str(prog_no)))
            row = cur.fetchone()

        if not row and clean_name:
            cur.execute("""
                SELECT pc.id, pc.number, pc.name
                FROM program_components pc
                WHERE pc.level = 1
                  AND UPPER(COALESCE(pc.machine_code, '')) = %s
                  AND UPPER(TRIM(pc.name)) = %s
                  AND EXISTS (SELECT 1 FROM steps s WHERE s.parent_component_id = pc.id)
                ORDER BY pc.modification_time DESC NULLS LAST, pc.id DESC
                LIMIT 1
            """, (clean_m, clean_name))
            row = cur.fetchone()

        # 2. Fallback: exact program name match across machines (same factory recipe library)
        if not row and clean_name and len(clean_name) >= 4:
            cur.execute("""
                SELECT pc.id, pc.number, pc.name
                FROM program_components pc
                WHERE pc.level = 1
                  AND UPPER(TRIM(pc.name)) = %s
                  AND EXISTS (SELECT 1 FROM steps s WHERE s.parent_component_id = pc.id)
                ORDER BY pc.modification_time DESC NULLS LAST, pc.id DESC
                LIMIT 1
            """, (clean_name,))
            row = cur.fetchone()

        if not row:
            return None

        pc_id, db_prog_no, db_prog_name = row[0], str(row[1] or ""), str(row[2] or "")

        cur.execute("""
            SELECT s.id, s.position, s.label, s.summary_temp, s.summary_time_min,
                   sf.id, sf.resource_number, sf.function_number, sf.function_name, sf.comment,
                   sfp.function_parameter_number, sfp.value
            FROM steps s
            LEFT JOIN step_functions sf ON sf.step_id = s.id
            LEFT JOIN step_function_parameters sfp ON sfp.step_function_id = sf.id
            WHERE s.parent_component_id = %s
            ORDER BY s.position ASC, sf.resource_number ASC, sf.id ASC, sfp.function_parameter_number ASC
        """, (pc_id,))
        rows = cur.fetchall()
        if not rows:
            return None

        # Load function/resource catalog for human-readable names & units
        if SetexFolderReader._PARAMETERS_CATALOG is None:
            SetexFolderReader.get_function_catalog()
        m_cat = SetexFolderReader.load_machine_catalog(clean_m) or {}
        func_cat = m_cat.get("functions") or SetexFolderReader._FUNCTION_CATALOG or {}
        res_cat = m_cat.get("resources") or SetexFolderReader._RESOURCES_CATALOG or {}
        param_cat = SetexFolderReader._PARAMETERS_CATALOG or {}

        steps_by_pos: Dict[int, Dict[str, Any]] = {}
        for r in rows:
            s_id, pos, s_label, s_temp, s_time, sf_id, res_no, fn_no, fn_name, fn_comment, p_num, p_val = r
            pos_int = int(pos or 0)
            st = steps_by_pos.setdefault(pos_int, {
                "no": pos_int,
                "label": (s_label or "").strip(),
                "summary_temp": float(s_temp) if s_temp is not None else None,
                "summary_time_min": float(s_time) if s_time is not None else 0.0,
                "funcs": {},
            })
            if sf_id is not None:
                f_obj = st["funcs"].setdefault(sf_id, {
                    "slot": int(res_no or 1),
                    "func_id": int(fn_no or 0),
                    "func_name": (fn_name or "").strip(),
                    "comment": (fn_comment or "").strip(),
                    "params": [],
                })
                if p_num is not None:
                    f_obj["params"].append((int(p_num), float(p_val) if p_val is not None else 0.0))

        scada_steps = []
        for pos_int in sorted(steps_by_pos.keys()):
            st = steps_by_pos[pos_int]
            slots = []
            main_step_name = f"Step #{pos_int}"
            main_func_id = 0
            temp_sv = st["summary_temp"]
            step_min = int(round(st["summary_time_min"])) if st["summary_time_min"] else 0

            ordered_funcs = sorted(st["funcs"].values(), key=lambda x: x["slot"])
            for f_obj in ordered_funcs:
                fid = f_obj["func_id"]
                slot_no = f_obj["slot"]
                f_meta = func_cat.get(str(fid), {})
                f_display = f_obj["func_name"] or f_meta.get("name") or SetexFolderReader.FALLBACK_FUNCTION_NAMES.get(fid) or f"Func {fid}"
                res_info = res_cat.get(str(slot_no), {})
                res_name = res_info.get("name") or ("main tank" if slot_no == 1 else f"Resource {slot_no}")

                param_defs = f_meta.get("parameters") or []
                params_out = []
                for idx_p, (p_num, p_val) in enumerate(sorted(f_obj["params"], key=lambda x: x[0])):
                    p_def = param_defs[idx_p] if idx_p < len(param_defs) else {}
                    p_id_meta = p_def.get("definition_id") if p_def.get("definition_id") is not None else p_def.get("id")
                    p_cat_info = param_cat.get(str(p_id_meta), {}) if p_id_meta is not None else {}
                    p_name = p_def.get("name") or p_cat_info.get("name") or f"P{p_num}"
                    p_unit = (p_def.get("unit") or p_cat_info.get("unit") or "").strip()
                    if p_val == 0 and not p_def:
                        continue
                    v_clean = int(p_val) if float(p_val).is_integer() else round(p_val, 2)
                    val_str = f"{v_clean} {p_unit}".strip() if p_unit else str(v_clean)
                    params_out.append({"name": p_name, "value": val_str})
                    if slot_no == 1 and temp_sv is None and ("temperature ma" in p_name.lower() or "suhu" in p_name.lower() or "°c" in p_unit.lower()):
                        if p_val > 0:
                            temp_sv = int(p_val) if float(p_val).is_integer() else round(p_val, 1)
                    if slot_no == 1 and step_min == 0 and fid in (141, 121, 144) and ("time" in p_name.lower() or "waktu" in p_name.lower() or p_unit.lower() == "min"):
                        if p_val > 0:
                            step_min = int(round(p_val))

                if slot_no == 1:
                    main_step_name = f_display
                    main_func_id = fid

                slots.append({
                    "func": f_display,
                    "main": slot_no == 1,
                    "slot": slot_no,
                    "params": params_out,
                    "func_id": fid,
                    "resource": res_name,
                })

            comment_txt = st["label"]
            if comment_txt.lower().startswith("langkah "):
                comment_txt = None

            scada_steps.append({
                "no": pos_int,
                "sv": int(temp_sv) if (temp_sv is not None and float(temp_sv).is_integer()) else temp_sv,
                "min": step_min,
                "step": main_step_name,
                "slots": slots,
                "comment": comment_txt or None,
                "func_id": main_func_id,
                "hold_min": 0,
                "protect_min": 0,
            })

        return {
            "program_no": db_prog_no,
            "program_name": db_prog_name,
            "scada_steps": scada_steps,
        }
    except Exception as e:
        logger.debug(f"DB program lookup error for {machine_no}: {e}")
        return None
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def save_prg_steps_to_db(
    machine_no: str,
    prog_no: int,
    program_name: str,
    raw_steps: List[Dict[str, Any]],
) -> bool:
    """
    Inserts a newly downloaded .PRG program and all its steps/functions/parameters into PostgreSQL
    (program_components, steps, step_functions, step_function_parameters) so future cycles read from DB.
    """
    if not DB_URL or not raw_steps:
        return False
    clean_m = (machine_no or "").strip().upper().replace("MESIN_", "")
    p_no_str = str(prog_no) if prog_no and prog_no > 0 else "0"
    p_name = (program_name or f"PROGRAM #{p_no_str}").strip()[:255]

    conn = None
    try:
        conn = psycopg2.connect(DB_URL, connect_timeout=4)
        cur = conn.cursor()

        # Check existing ProgramComponent on this machine
        cur.execute("""
            SELECT id FROM program_components
            WHERE level = 1 AND UPPER(COALESCE(machine_code, '')) = %s AND number = %s
            LIMIT 1
        """, (clean_m, p_no_str))
        existing = cur.fetchone()
        if existing:
            pc_id = existing[0]
            cur.execute("""
                UPDATE program_components
                SET name = %s, modification_time = NOW()
                WHERE id = %s
            """, (p_name, pc_id))
            # Delete old child rows cleanly
            cur.execute("""
                DELETE FROM step_function_parameters
                WHERE step_function_id IN (
                    SELECT sf.id FROM step_functions sf
                    JOIN steps s ON s.id = sf.step_id
                    WHERE s.parent_component_id = %s
                )
            """, (pc_id,))
            cur.execute("""
                DELETE FROM step_functions
                WHERE step_id IN (SELECT id FROM steps WHERE parent_component_id = %s)
            """, (pc_id,))
            cur.execute("DELETE FROM steps WHERE parent_component_id = %s", (pc_id,))
        else:
            cur.execute("""
                INSERT INTO program_components (level, type, number, name, hidden, machine_code, content_type, creation_time, modification_time)
                VALUES (1, 1, %s, %s, FALSE, %s, 0, NOW(), NOW())
                RETURNING id
            """, (p_no_str, p_name, clean_m))
            pc_id = cur.fetchone()[0]

        for st in raw_steps:
            step_no = int(st.get("no") or 0)
            if step_no <= 0:
                continue
            label = (st.get("comment") or f"Langkah {step_no}")[:100]
            summary_temp = None
            summary_time = float(st.get("set_time") or 0.0)
            summary_water = 0.0

            sub_steps = st.get("sub_steps") or []
            for sub in sub_steps:
                fid = int(sub.get("func_id") or 0)
                p_list = sub.get("params") or []
                if fid == 141 and len(p_list) >= 1 and p_list[0].get("value") is not None:
                    try:
                        summary_temp = float(p_list[0]["value"])
                    except Exception:
                        pass
                if fid == 713 and len(p_list) >= 2 and p_list[1].get("value") is not None:
                    try:
                        summary_water = float(p_list[1]["value"])
                    except Exception:
                        pass

            cur.execute("""
                INSERT INTO steps (position, parent_component_id, label, summary_temp, summary_time_min, summary_water_l)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (step_no, pc_id, label, summary_temp, summary_time, summary_water))
            step_id = cur.fetchone()[0]

            for sub in sub_steps:
                res_no = int(sub.get("line") or 1)
                fid = int(sub.get("func_id") or 0)
                fname = str(sub.get("func_name") or sub.get("name") or "")[:100]
                cur.execute("""
                    INSERT INTO step_functions (step_id, resource_number, function_number, function_name, label, label_type, acknowledge)
                    VALUES (%s, %s, %s, %s, 0, 0, 0)
                    RETURNING id
                """, (step_id, res_no, fid, fname))
                sf_id = cur.fetchone()[0]

                for p_idx, p_obj in enumerate(sub.get("params") or []):
                    try:
                        pv = float(p_obj.get("value") or 0.0)
                    except Exception:
                        pv = 0.0
                    cur.execute("""
                        INSERT INTO step_function_parameters (step_function_id, function_parameter_number, attribute, value)
                        VALUES (%s, %s, 0, %s)
                    """, (sf_id, p_idx + 1, pv))

        conn.commit()
        logger.info(
            f"Auto-synced program #{p_no_str} ('{p_name}', {len(raw_steps)} steps) for machine {clean_m} into PostgreSQL."
        )
        return True
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.warning(f"Failed to auto-save PRG steps to PostgreSQL for {clean_m}: {e}")
        return False
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def is_controller_online(ip: str, port: int = 21, timeout: float = SOCKET_TIMEOUT) -> bool:
    """Rapid non-blocking socket check to prevent waiting on offline machines."""
    if not ip or ip in ("127.0.0.1", "0.0.0.0", "localhost"):
        return False
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False


def get_active_machines() -> List[Dict[str, Any]]:
    """Retrieves list of factory machines from DB, with fallback to local config workspace."""
    machines = []
    # 1. Try PostgreSQL machines table
    if DB_URL:
        try:
            conn = psycopg2.connect(DB_URL, connect_timeout=3)
            cur = conn.cursor()
            cur.execute("""
                SELECT machine_no, ip_address, ftp_port, controller_type, current_batch 
                FROM machines 
                WHERE ip_address IS NOT NULL AND ip_address != '' 
                  AND ip_address NOT IN ('127.0.0.1', 'localhost', '0.0.0.0')
                ORDER BY machine_no;
            """)
            for row in cur.fetchall():
                machines.append({
                    "machine_no": str(row[0]),
                    "ip_address": str(row[1]),
                    "ftp_port": int(row[2]) if row[2] else 21,
                    "controller_type": str(row[3]) if row[3] else "SETEX SECOM 777",
                    "current_batch": str(row[4]) if row[4] else ""
                })
            conn.close()
        except Exception as e:
            logger.debug(f"DB query notice (using fallback if any): {e}")

    # 2. Fallback to scanning WORKSPACE_PROGRAM_MESIN
    if not machines:
        workspace_dirs = [
            "WORKSPACE_PROGRAM_MESIN",
            "../../WORKSPACE_PROGRAM_MESIN",
            os.path.join(os.path.dirname(__file__), "..", "..", "WORKSPACE_PROGRAM_MESIN")
        ]
        for ws in workspace_dirs:
            if os.path.exists(ws) and os.path.isdir(ws):
                for m_dir in os.listdir(ws):
                    prof_file = os.path.join(ws, m_dir, "02_CONFIG_SIAP_PAKAI", "machine_profile.json")
                    if os.path.exists(prof_file):
                        try:
                            with open(prof_file, "r", encoding="utf-8") as pf:
                                data = json.load(pf)
                                ip = data.get("ip_address")
                                m_no = data.get("machine_no")
                                if ip and m_no and ip not in ("127.0.0.1", "localhost", "0.0.0.0"):
                                    machines.append({
                                        "machine_no": m_no,
                                        "ip_address": ip,
                                        "ftp_port": 21,
                                        "controller_type": data.get("controller_type", "SETEX SECOM 777"),
                                        "current_batch": ""
                                    })
                        except Exception:
                            pass
                if machines:
                    break

    # Default fallback
    if not machines:
        machines = [{"machine_no": "10B", "ip_address": "172.16.110.160", "ftp_port": 21, "controller_type": "SETEX SECOM 777", "current_batch": "072162"}]

    # Filter target machines jika ditentukan di config (misal: hanya 10B)
    target_env = os.getenv("TARGET_MACHINES", "")
    target_list = [x.strip() for x in target_env.split(",") if x.strip()] if target_env else CFG.get("worker", {}).get("target_machines", [])
    if target_list:
        machines = [m for m in machines if m["machine_no"] in target_list]

    return machines


def process_single_machine(m: Dict[str, Any]) -> Dict[str, Any]:
    """Worker task: connects to machine FTP, parses binary structures, publishes to EMQX."""
    m_no = m["machine_no"]
    ip = m["ip_address"]
    ftp_port = m.get("ftp_port", 21)
    asset_id = resolve_asset_id(m_no)
    is_797 = "797" in str(m.get("controller_type", "")).upper() or m_no.upper().startswith("DA")

    if not is_controller_online(ip, ftp_port):
        return {"machine_no": m_no, "status": "offline", "points": 0}

    t0 = time.time()
    bundle = None
    try:
        bundle = SetexFolderReader.fetch_live_controller_bundle(
            ip=ip,
            ftp_port=ftp_port,
            is_797=is_797,
            batch_no_hint=m.get("current_batch") or "",
            timeout=3.5,
            db_program_loader=lambda p_no, p_name, p_code: load_program_from_db(m_no, p_no, p_name, p_code),
        )
    except Exception as e:
        return {"machine_no": m_no, "status": "error", "error": str(e)}

    if not bundle:
        return {"machine_no": m_no, "status": "no_data", "points": 0}

    global _mqtt_client
    if not _mqtt_client:
        _mqtt_client = init_mqtt()
    if not _mqtt_client:
        return {"machine_no": m_no, "status": "mqtt_unavailable"}

    # 1. Parse STATUS.ACT
    batch_no = ""
    step_no = 1
    prog_no = "1"
    prog_name = ""
    m_state = "ONLINE"
    if bundle.get("status_bytes"):
        st = SetexFolderReader.read_status_act(folder_path="", ip=ip, ftp_port=ftp_port, raw_bytes=bundle["status_bytes"])
        batch_no = st.get("current_batch") or ""
        step_no = st.get("current_step") or 1
        prog_no = st.get("prog_no") or "1"
        prog_name = st.get("program_name") or st.get("program_code") or ""
        m_state = st.get("status") or "RUNNING"

        # Publish Status to EMQX
        topic_status = f"smm/jetflow/{asset_id}/status"
        payload_status = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "asset_id": asset_id,
            "machine_id": m_no,
            "connection_status": "ONLINE" if m_state in ("RUNNING", "ONLINE") else "OFFLINE",
            "batch_no": batch_no,
            "step_no": step_no,
            "program_no": str(prog_no)
        }
        _mqtt_client.publish(topic_status, json.dumps(payload_status), qos=1, retain=True)

    # 1a. Extract Batch Production Metadata (evt 257/513/1025) & Per-Step Actual Minutes (evt 261) from PR<batch>.LOG
    pr_meta = {"batch_info": {}, "step_actuals": {}}
    if bundle.get("batch_log_bytes"):
        try:
            pr_meta = SetexFolderReader.parse_pr_log_metadata_and_steps(bundle["batch_log_bytes"])
        except Exception as me:
            logger.debug(f"PR metadata parse notice for {m_no}: {me}")

    def _enrich_steps_with_actuals(steps_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        step_actuals = pr_meta.get("step_actuals") or {}
        if not step_actuals:
            return steps_list
        for st_item in steps_list:
            s_no = int(st_item.get("no") or 0)
            act = step_actuals.get(s_no)
            if act and act.get("ended_at") is not None:
                act_min = act.get("actual_min", 0.0)
                st_item["actual_min"] = int(round(act_min)) if act_min >= 1.0 else round(act_min, 1)
                st_item["started_at"] = act.get("started_at")
                st_item["ended_at"] = act.get("ended_at")
            elif act:
                st_item["started_at"] = act.get("started_at")
        return steps_list

    # 1b. Publish Recipe Steps for SCADA Tabel proses (prioritaskan DB; jika belum ada baru parse PRG & auto-insert ke DB)
    if batch_no and bundle.get("db_program"):
        db_p = bundle["db_program"]
        scada_steps = _enrich_steps_with_actuals(list(db_p.get("scada_steps") or []))
        if scada_steps:
            db_pno_str = str(db_p.get("program_no") or prog_no)
            prog_int = int(db_pno_str) if db_pno_str.isdigit() else 0
            topic_prog = f"smm/jetflow/{asset_id}/batch_program"
            payload_prog = {
                "asset_id": asset_id,
                "machine_no": m_no,
                "batch_no": batch_no,
                "program_no": db_pno_str,
                "program_name": db_p.get("program_name") or prog_name,
                "program_file": f"M_{prog_int:04d}.PRG" if prog_int > 0 else "",
                "program_source": "DATABASE_PROGRAM_STUDIO",
                "current_step": int(step_no),
                "total_steps": len(scada_steps),
                "batch_info": pr_meta.get("batch_info") or {},
                "program": scada_steps,
            }
            _mqtt_client.publish(topic_prog, json.dumps(payload_prog), qos=1)
    elif bundle.get("prg_bytes") and batch_no:
        try:
            pb = bundle["prg_bytes"]
            real_prog_no = struct.unpack_from("<H", pb, 8)[0] if len(pb) >= 10 else 0
            real_prog_name = pb[10:31].split(b"\0")[0].decode("cp1252", errors="ignore").strip() if len(pb) >= 31 else ""
            effective_prog_no = real_prog_no if 1 <= real_prog_no <= 9999 else (int(prog_no) if str(prog_no).isdigit() else 0)
            effective_prog_name = real_prog_name or prog_name

            raw_steps = SetexFolderReader.parse_prg_steps(pb, machine_no=m_no)
            if raw_steps:
                # Auto-insert ke PostgreSQL (program_components + steps + step_functions + step_function_parameters)
                # supaya siklus & batch berikutnya tidak perlu download .PRG lagi via FTP
                if not bundle.get("prg_from_cache"):
                    save_prg_steps_to_db(m_no, effective_prog_no, effective_prog_name, raw_steps)

                scada_steps = _enrich_steps_with_actuals(build_scada_program_steps(raw_steps))
                topic_prog = f"smm/jetflow/{asset_id}/batch_program"
                payload_prog = {
                    "asset_id": asset_id,
                    "machine_no": m_no,
                    "batch_no": batch_no,
                    "program_no": str(effective_prog_no),
                    "program_name": effective_prog_name,
                    "program_file": f"M_{effective_prog_no:04d}.PRG" if effective_prog_no > 0 else "",
                    "program_source": "SETEX_FTP_PRG",
                    "current_step": int(step_no),
                    "total_steps": len(scada_steps),
                    "batch_info": pr_meta.get("batch_info") or {},
                    "program": scada_steps,
                }
                _mqtt_client.publish(topic_prog, json.dumps(payload_prog), qos=1)
        except Exception as pe:
            logger.debug(f"PRG parse notice for {m_no}: {pe}")

    # 2. Parse PR<batch>.LOG
    points_count = 0
    if bundle.get("batch_log_bytes"):
        pts = SetexFolderReader.parse_cyclic_log_bytes(bundle["batch_log_bytes"])
        if pts:
            points_count = len(pts)
            topic_curve = f"smm/jetflow/{asset_id}/batch_curve"
            payload_curve = {
                "asset_id": asset_id,
                "machine_no": m_no,
                "batch_no": batch_no,
                "points": [
                    {
                        "log_timestamp": pt["timestamp"].isoformat() if isinstance(pt["timestamp"], datetime) else str(pt["timestamp"]),
                        "machine_no": m_no,
                        "batch_ref_no": batch_no,
                        "temp_pv": float(pt.get("temp_pv", 0.0) or 0.0),
                        "temp_sp": float(pt.get("temp_sp", 0.0) or 0.0),
                        "temp_pt100_t2": float(pt.get("temp_pt100_t2", 0.0) or 0.0),
                        "pump_speed_percent": float(pt.get("pump_speed_percent", 85.0) or 85.0),
                        "reel_speed_mpm": float(pt.get("reel_speed_mpm", 240.0) or 240.0),
                        "vessel_pressure_bar": float(pt.get("vessel_pressure_bar", 0.0) or 0.0),
                        "step_no": int(pt.get("step_no", 1) or 1),
                        "raw_digital_bits": int(pt.get("raw_digital_bits", 0) or 0)
                    }
                    for pt in pts
                ]
            }
            _mqtt_client.publish(topic_curve, json.dumps(payload_curve), qos=1)

    # 3. Parse ALARM.ACT & ALARMS.LOG
    alarms_list = []
    if bundle.get("alarms_log_bytes"):
        alarms_list = SetexFolderReader.read_alarms_log(raw_bytes=bundle["alarms_log_bytes"], limit=30)
    elif bundle.get("alarm_bytes"):
        act_alarm = SetexFolderReader.read_alarm_act(raw_bytes=bundle["alarm_bytes"])
        if act_alarm.get("is_alarm_active") and act_alarm.get("active_alarms"):
            alarms_list = act_alarm["active_alarms"]

    if alarms_list:
        topic_alarm = f"smm/jetflow/{asset_id}/alarms"
        payload_alarms = {
            "asset_id": asset_id,
            "machine_id": m_no,
            "alarms": alarms_list
        }
        _mqtt_client.publish(topic_alarm, json.dumps(payload_alarms), qos=1)

    dur = time.time() - t0
    return {
        "machine_no": m_no,
        "status": "success",
        "batch": batch_no,
        "step": step_no,
        "points": points_count,
        "alarms": len(alarms_list),
        "duration_sec": round(dur, 2)
    }


def run_cycle():
    """Executes single full parallel sweep across all factory machines."""
    t_start = time.time()
    machines = get_active_machines()
    if not machines:
        logger.warning("No machines found to poll")
        return

    online_count = 0
    total_points = 0
    success_machines = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_single_machine, m): m for m in machines}
        for fut in as_completed(futures):
            res = fut.result()
            if res.get("status") == "success":
                online_count += 1
                total_points += res.get("points", 0)
                success_machines.append(res["machine_no"])

    total_dur = time.time() - t_start
    logger.info(
        f"Cycle completed in {total_dur:.2f}s | "
        f"Total: {len(machines)}, Online: {online_count}, Curve Points: {total_points} | "
        f"Active: {', '.join(success_machines[:8])}{'...' if len(success_machines) > 8 else ''}"
    )


def handle_shutdown(signum, frame):
    """Graceful shutdown handler for 24x7 service."""
    global _running, _mqtt_client
    logger.info(f"Signal {signum} received. Stopping DA-Batch-Worker gracefully...")
    _running = False
    if _mqtt_client:
        _mqtt_client.loop_stop()
        _mqtt_client.disconnect()
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    logger.info("=" * 60)
    logger.info("DA-Batch-Worker 24x7 Dedicated Background Ingestion Service")
    logger.info(f"EMQX Broker: {EMQX_HOST}:{EMQX_PORT}")
    logger.info(f"Poll Interval: {POLL_INTERVAL} seconds | Max Workers: {MAX_WORKERS}")
    logger.info("=" * 60)

    init_mqtt()

    while _running:
        t_cycle_start = time.time()
        try:
            run_cycle()
        except Exception as e:
            logger.error(f"Error during ingestion cycle: {e}", exc_info=True)

        # Hitung waktu istirahat agar interval antar siklus tepat 60 detik (1 menit)
        elapsed = time.time() - t_cycle_start
        sleep_needed = max(1.0, float(POLL_INTERVAL) - elapsed)
        logger.info(f"Istirahat {sleep_needed:.1f}s sebelum siklus 1 menit berikutnya...")

        sleep_end = time.time() + sleep_needed
        while _running and time.time() < sleep_end:
            time.sleep(min(1.0, max(0.1, sleep_end - time.time())))


if __name__ == "__main__":
    main()
