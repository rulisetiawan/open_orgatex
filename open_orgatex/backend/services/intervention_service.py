"""
OpenOrgaTEX - Operator Intervention & Setpoint Tracking Service
Listens to Message Broker ('machine.intervention') and performs:
1. Instant Setpoint Acquisition via TCP Port 50000 (and STATUS.ACT fallback)
2. Differential Comparison (Before vs After)
3. Permanent Audit Logging to PostgreSQL (operator_interventions table)
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from .event_broker import broker, EventMessage
from .setex_tcp_client import SetexTcpClient
from .reader import SetexFolderReader
from .. import database
from ..models.schema_pg import Machine, OperatorIntervention

logger = logging.getLogger("orgatex.intervention")

class InterventionService:
    """
    Subscribes to intervention events, fetches fresh setpoints,
    and detects parameter modifications.
    """
    _baseline_cache: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def register_listener(cls):
        """Registers listener on Message Broker topic."""
        broker.subscribe("machine.intervention", cls.handle_intervention_event)
        logger.info("Registered InterventionService listener on topic: machine.intervention")

    @classmethod
    def set_baseline(cls, machine_no: str, snapshot: Dict[str, Any]):
        """Sets or initializes baseline setpoints for a machine."""
        cls._baseline_cache[machine_no.upper()] = snapshot

    @classmethod
    def get_baseline(cls, machine_no: str) -> Optional[Dict[str, Any]]:
        return cls._baseline_cache.get(machine_no.upper())

    @classmethod
    def handle_intervention_event(cls, msg: EventMessage):
        """
        Handler triggered whenever a message arrives on 'machine.intervention'.
        """
        data = msg.data
        machine_no = data.get("machine_no", "").upper()
        trigger_source = data.get("trigger_source", "ALARMS_LOG")
        alarm_code = data.get("alarm_code")
        notes = data.get("notes") or data.get("alarm_text", "Operator intervention detected")

        if not machine_no:
            logger.warning("Intervention message missing machine_no; ignoring.")
            return

        logger.info(f"[*] Processing intervention event for Machine {machine_no} (Trigger: {trigger_source}, Code: {alarm_code})")

        # Run detection and persistence
        cls.evaluate_and_record(
            machine_no=machine_no,
            trigger_source=trigger_source,
            alarm_code=alarm_code,
            notes=notes
        )

    @classmethod
    def evaluate_and_record(
        cls,
        machine_no: str,
        trigger_source: str = "MANUAL",
        alarm_code: Optional[int] = None,
        notes: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Fetches latest setpoints, compares against baseline, and saves intervention records.
        """
        m_no = machine_no.upper()
        db: Optional[Session] = None
        detected_changes = []

        try:
            if database.SessionLocal is not None:
                db = database.SessionLocal()

            machine = None
            if db:
                machine = db.query(Machine).filter(Machine.machine_no == m_no).first()

            ip = machine.ip_address if machine else "172.16.110.101"
            tcp_port = machine.tcp_port if (machine and machine.tcp_port) else 50000
            current_batch = machine.current_batch if machine else "UNKNOWN"
            current_step = machine.current_step if machine else 1

            # 1. Fetch latest setpoint snapshot from TCP Controller Port 50000
            current_snapshot = {}
            try:
                current_snapshot = SetexTcpClient.read_setpoints_snapshot(ip, tcp_port, m_no)
            except Exception as e:
                logger.debug(f"TCP read from {ip}:{tcp_port} failed: {e}")

            # 2. Fallback to STATUS.ACT on-the-fly only if TCP offline or incomplete
            status_act = None
            if not current_snapshot.get("online"):
                share_path = machine.share_folder_path if machine else ""
                try:
                    status_act = SetexFolderReader.read_status_act(
                        folder_path=share_path or os.path.abspath("./STATUS"),
                        ip="",  # Fast local read without FTP blocking
                        ftp_port=machine.ftp_port if machine else 21
                    )
                except Exception as e:
                    logger.debug(f"Status.act fallback read failed: {e}")

            # Merge / synthesize current live setpoints
            setpoints = current_snapshot.get("setpoints", {})
            temp_sp = setpoints.get("temp_sp")
            time_sp = setpoints.get("holding_time_sp")
            pump_sp = setpoints.get("pump_sp")
            gradient_sp = setpoints.get("gradient_sp")

            if (temp_sp is None or temp_sp == 0.0) and status_act and status_act.get("temp_sp") is not None:
                temp_sp = status_act.get("temp_sp")

            if current_step is None and status_act:
                current_step = status_act.get("step_no")
            if (current_batch == "UNKNOWN" or not current_batch) and status_act:
                current_batch = status_act.get("current_batch")

            live_params = {
                "Target Temperature": {"val": temp_sp, "unit": "°C", "func_id": 141, "reg": 1009},
                "Holding Time": {"val": time_sp, "unit": "min", "func_id": 141, "reg": 1009},
                "Temperature Gradient": {"val": gradient_sp, "unit": "°C/min", "func_id": 141, "reg": 1009},
                "Pump Speed": {"val": pump_sp, "unit": "%", "func_id": 404, "reg": 1009}
            }

            # 3. Retrieve or establish baseline
            baseline = cls.get_baseline(m_no)
            if not baseline:
                # First observation: establish initial baseline
                cls.set_baseline(m_no, {k: v["val"] for k, v in live_params.items() if v["val"] is not None})
                logger.info(f"Initialized baseline setpoints for Machine {m_no}: {cls.get_baseline(m_no)}")
                return []

            # 4. Compare each parameter
            for param_name, meta in live_params.items():
                cur_val = meta["val"]
                if cur_val is None:
                    continue

                prev_val = baseline.get(param_name)
                if param_name == "Target Temperature":
                    cur_val = float(round(cur_val))
                    prev_val = float(round(prev_val)) if prev_val is not None else None
                    min_diff = 1.0
                else:
                    min_diff = 0.01

                # If value is different from baseline, record intervention!
                if prev_val is not None and abs(cur_val - prev_val) >= min_diff:
                    delta = round(cur_val - prev_val, 2)
                    change_item = {
                        "machine_no": m_no,
                        "batch_no": current_batch,
                        "step_no": current_step,
                        "trigger_source": trigger_source,
                        "alarm_code": alarm_code,
                        "function_id": meta["func_id"],
                        "parameter_name": param_name,
                        "unit": meta["unit"],
                        "value_before": prev_val,
                        "value_after": cur_val,
                        "delta": delta,
                        "notes": f"Intervention: {param_name} changed from {prev_val} to {cur_val} {meta['unit']} (Delta {delta:+})"
                    }
                    detected_changes.append(change_item)

                    logger.warning(
                        f"[INTERVENTION RECORDED] Machine {m_no} Step {current_step}: "
                        f"{param_name} changed from {prev_val} to {cur_val} {meta['unit']} ({delta:+})"
                    )

                    # Persist to database
                    if db:
                        try:
                            record = OperatorIntervention(
                                machine_no=m_no,
                                batch_no=current_batch,
                                step_no=current_step,
                                trigger_source=trigger_source,
                                alarm_code=alarm_code,
                                function_id=meta["func_id"],
                                parameter_name=param_name,
                                register_address=meta["reg"],
                                unit=meta["unit"],
                                value_before=prev_val,
                                value_after=cur_val,
                                delta=delta,
                                notes=notes or change_item["notes"],
                                raw_details=json.dumps(current_snapshot)
                            )
                            db.add(record)
                            db.commit()
                        except Exception as dbe:
                            logger.error(f"Failed to save OperatorIntervention to DB: {dbe}")
                            db.rollback()

                    # Update baseline to the new value
                    baseline[param_name] = cur_val

            # Publish setpoints updated event
            if detected_changes:
                broker.publish_sync("machine.setpoints_updated", {
                    "machine_no": m_no,
                    "changes": detected_changes,
                    "timestamp": datetime.utcnow().isoformat()
                })

        except Exception as e:
            logger.error(f"Error evaluating setpoint intervention for {machine_no}: {e}")
        finally:
            if db:
                db.close()

        return detected_changes
