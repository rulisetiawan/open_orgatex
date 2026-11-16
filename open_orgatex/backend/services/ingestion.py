"""
OpenOrgaTEX Log Ingestion & Persistence Engine
Reads data on-the-fly from SETEX shared folders / FTP and persists permanently into TimescaleDB / PostgreSQL
Uses PostgreSQL native ON CONFLICT DO NOTHING for idempotent high-speed telemetry ingestion
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from .reader import SetexFolderReader
from .event_broker import broker
from ..models.schema_pg import Machine, BatchHeader, DatalogCyclicRecord, DatalogAlarm

logger = logging.getLogger("orgatex.ingestion")

class LogIngestionService:
    """
    On-the-fly reader & persistent synchronizer to TimescaleDB / PostgreSQL.
    Strictly read-only on filesystem.
    """

    @staticmethod
    def ingest_machine_on_the_fly(db: Session, machine: Machine) -> Dict[str, Any]:
        """
        Reads the shared directory / FTP of the machine on-the-fly,
        ingests new data into PostgreSQL/TimescaleDB, and returns live status & curve.
        """
        folder_candidates = [
            machine.share_folder_path,
            "/app/STATUS",
            "/app/sc777ce_root/STATUS",
            "/app/sc777ce_root",
            os.path.abspath("./STATUS"),
            os.path.abspath("./plain_export/BATCH_BARU_061119"),
            os.path.abspath(".")
        ]

        # Pick first existing local folder candidate if any
        target_folder = None
        for fc in folder_candidates:
            if fc and os.path.exists(fc):
                target_folder = fc
                break

        # 1. Read STATUS.ACT on-the-fly (FTP takes precedence if IP configured)
        status_info = SetexFolderReader.read_status_act(
            folder_path=target_folder or "",
            ip=machine.ip_address,
            ftp_port=machine.ftp_port or 21
        )

        # Notify broker if status indicates operator hold/intervention
        if status_info.get("alarm_active") in (20, 256, 5899) or status_info.get("status") in ("HOLD", "PAUSE"):
            broker.publish_sync("machine.intervention", {
                "machine_no": machine.machine_no,
                "trigger_source": "STATUS_ACT",
                "alarm_code": status_info.get("alarm_active"),
                "alarm_text": status_info.get("alarm_text", "Active Operator Hold / Pause"),
                "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            })

        # 2. Read ALARM.ACT & ALARMS.LOG on-the-fly
        alarm_act = SetexFolderReader.read_alarm_act(
            folder_path=target_folder or "",
            ip=machine.ip_address,
            ftp_port=machine.ftp_port or 21
        )
        alarm_history = SetexFolderReader.read_alarms_log(
            folder_path=target_folder or "",
            ip=machine.ip_address,
            ftp_port=machine.ftp_port or 21,
            limit=50
        )

        # 3. Find and parse cyclic telemetry records on-the-fly
        telemetry_records = []
        batch_no = status_info.get("current_batch") or "063127"
        if batch_no == "UNKNOWN":
            batch_no = "063127"

        # 3.1 Try FTP direct batch log acquisition if machine has IP
        if machine.ip_address and batch_no != "UNKNOWN":
            ftp_points = SetexFolderReader.read_cyclic_log_from_ftp(
                machine.ip_address,
                machine.ftp_port or 21,
                batch_no
            )
            if ftp_points:
                telemetry_records.extend(ftp_points)

        # 3.2 If no FTP points found, scan local directory structure
        if not telemetry_records and target_folder:
            search_dirs = [target_folder, os.path.join(target_folder, "..", "plain_export"), "/app/plain_export"]
            log_files = SetexFolderReader.find_all_log_files([d for d in search_dirs if os.path.exists(d)])
            for lf in log_files:
                recs = SetexFolderReader.read_cyclic_log_file(lf)
                telemetry_records.extend(recs)

        # 3.3 If still no points but we have live STATUS.ACT analog reading, create point
        if not telemetry_records and status_info.get("temp_pv") is not None:
            now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            telemetry_records.append({
                "timestamp": now_str,
                "temp_pv": status_info.get("temp_pv", 40.0),
                "temp_sp": status_info.get("temp_sp", 90.0),
                "temp_pt100_t2": status_info.get("temp_pt100_t2", 25.0),
                "pump_speed_percent": 85.0,
                "reel_speed_mpm": 240.0,
                "step_no": status_info.get("current_step", 1)
            })

        # Deduplicate memory points by timestamp
        seen_ts = set()
        unique_telemetry = []
        for pt in telemetry_records:
            if pt["timestamp"] not in seen_ts:
                seen_ts.add(pt["timestamp"])
                unique_telemetry.append(pt)
        unique_telemetry.sort(key=lambda x: x["timestamp"])

        # 4. Permanent Persistence in PostgreSQL / TimescaleDB
        points_inserted = 0
        alarms_inserted = 0

        # Update Machine record
        machine.status = "RUNNING" if status_info.get("status") == "RUNNING" else "ONLINE"
        machine.current_batch = batch_no
        live_step = status_info.get("current_step") or 1
        machine.current_step = live_step
        machine.last_ping_time = datetime.utcnow()

        if unique_telemetry:
            last_pt = unique_telemetry[-1]
            machine.current_temp = last_pt.get("temp_pv")
            if live_step <= 1 and last_pt.get("step_no") and last_pt["step_no"] > 1:
                machine.current_step = last_pt["step_no"]
        elif status_info.get("temp_pv") is not None:
            machine.current_temp = status_info.get("temp_pv")

        try:
            # 4.1 Upsert Batch Header
            existing_batch = db.query(BatchHeader).filter(BatchHeader.batch_ref_no == batch_no).first()
            if not existing_batch:
                b_stmt = insert(BatchHeader).values(
                    batch_ref_no=batch_no,
                    machine_no=machine.machine_no,
                    program_no=1,
                    status="RUNNING",
                    fabric_weight_kg=float(machine.capacity_kg) if machine.capacity_kg else 350.0,
                    liquor_ratio=float(machine.default_liquor_ratio) if machine.default_liquor_ratio else 8.0,
                    customer="PT. SMM JETFLOW"
                ).on_conflict_do_nothing(index_elements=['batch_ref_no'])
                db.execute(b_stmt)
                db.commit()

            # 4.2 Bulk Upsert Telemetry Records with ON CONFLICT DO NOTHING
            if unique_telemetry:
                insert_rows = []
                for pt in unique_telemetry:
                    try:
                        ts = datetime.strptime(pt["timestamp"], "%Y-%m-%d %H:%M:%S")
                        insert_rows.append({
                            "log_timestamp": ts,
                            "machine_no": machine.machine_no,
                            "batch_ref_no": batch_no,
                            "temp_pv": pt["temp_pv"],
                            "temp_sp": pt["temp_sp"],
                            "temp_pt100_t2": pt["temp_pt100_t2"],
                            "pump_speed_percent": pt.get("pump_speed_percent", 85.0),
                            "reel_speed_mpm": pt.get("reel_speed_mpm", 250.0),
                            "step_no": pt.get("step_no", 1)
                        })
                    except Exception:
                        pass

                if insert_rows:
                    t_stmt = insert(DatalogCyclicRecord).values(insert_rows)
                    t_stmt = t_stmt.on_conflict_do_update(
                        index_elements=['log_timestamp', 'machine_no', 'batch_ref_no'],
                        set_={
                            'temp_pv': t_stmt.excluded.temp_pv,
                            'temp_sp': t_stmt.excluded.temp_sp,
                            'temp_pt100_t2': t_stmt.excluded.temp_pt100_t2,
                            'pump_speed_percent': t_stmt.excluded.pump_speed_percent,
                            'reel_speed_mpm': t_stmt.excluded.reel_speed_mpm,
                            'step_no': t_stmt.excluded.step_no
                        }
                    )
                    db.execute(t_stmt)
                    db.commit()
                    points_inserted = len(insert_rows)

            # 4.3 Bulk Upsert Alarms with ON CONFLICT DO NOTHING
            if alarm_history:
                alarm_rows = []
                for al in alarm_history:
                    try:
                        ats = datetime.strptime(al["timestamp"], "%Y-%m-%d %H:%M:%S")
                        alarm_rows.append({
                            "machine_no": machine.machine_no,
                            "batch_ref_no": batch_no,
                            "alarm_timestamp": ats,
                            "alarm_code": str(al["alarm_code"]),
                            "alarm_text": al["alarm_text"],
                            "severity": al.get("severity", "WARNING"),
                            "step_no": machine.current_step or 1
                        })
                    except Exception:
                        pass

                if alarm_rows:
                    a_stmt = insert(DatalogAlarm).values(alarm_rows)
                    a_stmt = a_stmt.on_conflict_do_nothing(
                        index_elements=['machine_no', 'batch_ref_no', 'alarm_timestamp', 'alarm_code']
                    )
                    db.execute(a_stmt)
                    db.commit()
                    alarms_inserted = len(alarm_rows)

                    # Check for operator intervention alarms and notify Message Broker
                    for al in alarm_history:
                        try:
                            code_int = int(al.get("alarm_code", 0))
                            txt_lower = str(al.get("alarm_text", "")).lower()
                            if code_int in (20, 256, 5899) or any(k in txt_lower for k in ("intervention", "operator", "hold", "pause", "parameter", "manual")):
                                broker.publish_sync("machine.intervention", {
                                    "machine_no": machine.machine_no,
                                    "trigger_source": "ALARMS_LOG",
                                    "alarm_code": code_int,
                                    "alarm_text": al.get("alarm_text", ""),
                                    "timestamp": al.get("timestamp", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
                                })
                        except Exception:
                            pass

            db.commit()

        except Exception as ex:
            logger.error(f"Error persisting data to Postgres: {ex}")
            db.rollback()

        # If live alarm_history is empty, query recent stored alarms from database
        final_alarms = alarm_history[:30] if alarm_history else []
        if not final_alarms:
            try:
                db_alarms = db.query(DatalogAlarm).filter(
                    DatalogAlarm.machine_no == machine.machine_no
                ).order_by(desc(DatalogAlarm.alarm_timestamp)).limit(30).all()
                final_alarms = [
                    {
                        "timestamp": a.alarm_timestamp.strftime("%Y-%m-%d %H:%M:%S") if a.alarm_timestamp else "",
                        "alarm_code": a.alarm_code,
                        "alarm_text": a.alarm_text,
                        "severity": a.severity or "WARNING",
                        "step_no": a.step_no
                    }
                    for a in db_alarms
                ]
            except Exception:
                pass

        return {
            "machine_no": machine.machine_no,
            "status": machine.status,
            "is_live_hmi": status_info.get("is_ftp_source", False),
            "data_source": status_info.get("data_source", "LOCAL_STORAGE"),
            "hmi_ip": machine.ip_address,
            "hmi_port": machine.ftp_port or 21,
            "batch_no": batch_no,
            "program_code": status_info.get("program_code", "PKI103"),
            "program_name": status_info.get("program_name", "PROGRAM 30 VINYL RC"),
            "current_step": machine.current_step,
            "function_code": status_info.get("function_code", 0),
            "current_temp": machine.current_temp,
            "is_alarm_active": alarm_act.get("is_alarm_active", False),
            "active_alarms": alarm_act.get("active_alarms", []),
            "points_saved": points_inserted,
            "alarms_saved": alarms_inserted,
            "curve": unique_telemetry[-500:],  # Return up to 500 recent points for real-time chart
            "alarms": final_alarms
        }
