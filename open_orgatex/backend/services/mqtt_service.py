"""
EMQX MQTT Telemetry & Batch Forwarder Service
Publishes decoded machine states, batch curves (PR<batch>.LOG), and alarms
to EMQX MQTT broker so dedicated consumer services (e.g. da-db-writer) can persist them asynchronously.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
import paho.mqtt.client as mqtt

logger = logging.getLogger("orgatex.mqtt_forwarder")

EMQX_HOST = os.getenv("EMQX_HOST", "192.168.100.30")
EMQX_PORT = int(os.getenv("EMQX_PORT", "1883"))
EMQX_USER = os.getenv("EMQX_USER", "admin")
EMQX_PASS = os.getenv("EMQX_PASS", "sensorSMM!")

_client: Optional[mqtt.Client] = None
_is_connected = False


def get_mqtt_client() -> Optional[mqtt.Client]:
    """Returns singleton active MQTT client connection to EMQX broker."""
    global _client, _is_connected
    if _client is not None and _is_connected:
        return _client

    try:
        client_id = f"open_orgatex_forwarder_{os.getpid()}"
        client = mqtt.Client(client_id=client_id, clean_session=True)
        if EMQX_USER:
            client.username_pw_set(EMQX_USER, EMQX_PASS)

        def on_connect(c, userdata, flags, rc):
            global _is_connected
            if rc == 0:
                _is_connected = True
                logger.info(f"Connected to EMQX broker at {EMQX_HOST}:{EMQX_PORT}")
            else:
                _is_connected = False
                logger.warning(f"Failed connecting to EMQX, return code {rc}")

        def on_disconnect(c, userdata, rc):
            global _is_connected
            _is_connected = False
            logger.debug(f"Disconnected from EMQX broker (rc={rc})")

        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        client.connect_async(EMQX_HOST, EMQX_PORT, keepalive=30)
        client.loop_start()

        _client = client
        return _client
    except Exception as e:
        logger.warning(f"Unable to initialize MQTT client to {EMQX_HOST}: {e}")
        return None


def forward_batch_curve(asset_id: str, machine_no: str, batch_no: str, points: List[Dict[str, Any]]):
    """Publishes parsed cyclic curve points to EMQX topic smm/jetflow/{asset_id}/batch_curve."""
    if not points:
        return
    client = get_mqtt_client()
    if not client:
        return

    topic = f"smm/jetflow/{asset_id}/batch_curve"
    payload = {
        "asset_id": asset_id,
        "machine_no": machine_no,
        "batch_no": batch_no,
        "points": [
            {
                "log_timestamp": pt["timestamp"].isoformat() if isinstance(pt["timestamp"], datetime) else str(pt["timestamp"]),
                "machine_no": machine_no,
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
            for pt in points
        ]
    }

    try:
        client.publish(topic, json.dumps(payload), qos=1)
    except Exception as e:
        logger.debug(f"Failed to publish batch curve to {topic}: {e}")


def forward_machine_status(asset_id: str, machine_no: str, status: str, batch_no: str, step_no: int, prog_no: str):
    """Publishes machine operational state to EMQX topic smm/jetflow/{asset_id}/status."""
    client = get_mqtt_client()
    if not client:
        return

    topic = f"smm/jetflow/{asset_id}/status"
    payload = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "asset_id": asset_id,
        "machine_id": machine_no,
        "connection_status": "ONLINE" if status in ("RUNNING", "ONLINE") else "OFFLINE",
        "batch_no": batch_no,
        "step_no": step_no,
        "program_no": str(prog_no)
    }

    try:
        client.publish(topic, json.dumps(payload), qos=1, retain=True)
    except Exception as e:
        logger.debug(f"Failed to publish machine status to {topic}: {e}")


def forward_alarms(asset_id: str, machine_no: str, alarms: List[Dict[str, Any]]):
    """Publishes alarm events to EMQX topic smm/jetflow/{asset_id}/alarms."""
    if not alarms:
        return
    client = get_mqtt_client()
    if not client:
        return

    topic = f"smm/jetflow/{asset_id}/alarms"
    payload = {
        "asset_id": asset_id,
        "machine_id": machine_no,
        "alarms": alarms
    }

    try:
        client.publish(topic, json.dumps(payload), qos=1)
    except Exception as e:
        logger.debug(f"Failed to publish alarms to {topic}: {e}")
