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
                val_str = f"{p_val} {p_unit}".strip() if p_val is not None else ""
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
            timeout=3.5
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

    # 1b. Parse PRG Recipe Steps and publish for SCADA Tabel proses
    if bundle.get("prg_bytes") and batch_no:
        try:
            raw_steps = SetexFolderReader.parse_prg_steps(bundle["prg_bytes"])
            if raw_steps:
                scada_steps = build_scada_program_steps(raw_steps)
                prog_int = int(prog_no) if str(prog_no).isdigit() else 0
                topic_prog = f"smm/jetflow/{asset_id}/batch_program"
                payload_prog = {
                    "asset_id": asset_id,
                    "machine_no": m_no,
                    "batch_no": batch_no,
                    "program_no": str(prog_no),
                    "program_name": prog_name,
                    "program_file": f"M_{prog_int:04d}.PRG" if prog_int > 0 else "",
                    "program_source": "SETEX_FTP_PRG",
                    "current_step": int(step_no),
                    "total_steps": len(scada_steps),
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
