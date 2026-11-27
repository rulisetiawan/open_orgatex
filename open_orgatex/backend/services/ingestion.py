"""
OpenOrgaTEX Log Ingestion & Persistence Engine
Reads data on-the-fly from SETEX shared folders / FTP and persists permanently into TimescaleDB / PostgreSQL
Uses PostgreSQL native ON CONFLICT DO NOTHING for idempotent high-speed telemetry ingestion
"""

import os
import re
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy import desc
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from .reader import SetexFolderReader
from .event_broker import broker
from .setex_tcp_client import SetexTcpClient
from .mqtt_service import forward_batch_curve, forward_machine_status, forward_alarms
from .. import database
from ..models.schema_pg import Machine, BatchHeader, DatalogCyclicRecord, DatalogAlarm, OperatorIntervention

logger = logging.getLogger("orgatex.ingestion")

# In-memory tracking of real-time step transitions during active polling
_LIVE_STEP_TRANSITIONS: Dict[str, Dict[str, Any]] = {}

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
        is_797 = (
            (machine.ip_address and machine.ip_address.strip() in ("192.168.1.95", "172.16.120.102", "172.16.120.103", "172.16.120.105", "172.16.120.108", "172.16.120.109", "172.16.120.154")) or
            (machine.controller_type and "797" in machine.controller_type.upper()) or
            "797" in (machine.machine_no or "").upper() or
            (machine.machine_no or "").upper().startswith("DA")
        )

        folder_candidates = [
            machine.share_folder_path,
            "/app/sc797ce_root/STATUS" if is_797 else None,
            "/app/sc797ce_root" if is_797 else None,
            "/app/STATUS",
            "/app/sc777ce_root/STATUS",
            "/app/sc777ce_root",
            os.path.abspath("./sc797ce_root/STATUS") if is_797 else None,
            os.path.abspath("./sc797ce_root") if is_797 else None,
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

        # 1. High-speed unified FTP acquisition if machine has IP
        ftp_bundle = None
        if machine.ip_address:
            try:
                ftp_bundle = SetexFolderReader.fetch_live_controller_bundle(
                    ip=machine.ip_address,
                    ftp_port=machine.ftp_port or 21,
                    is_797=is_797,
                    batch_no_hint=machine.current_batch,
                    timeout=3.0
                )
            except Exception as e_b:
                logger.warning(f"Error executing FTP bundle fetch: {e_b}")

        # 2. Decode STATUS.ACT (FTP bundle takes precedence)
        if ftp_bundle and ftp_bundle.get("status_bytes"):
            status_info = SetexFolderReader.read_status_act(
                folder_path=target_folder or "",
                ip=machine.ip_address,
                ftp_port=machine.ftp_port or 21,
                raw_bytes=ftp_bundle["status_bytes"]
            )
            status_info["is_ftp_source"] = True
            status_info["data_source"] = ftp_bundle.get("source_url") or f"ftp://{machine.ip_address}:21"
        else:
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

        # 3. Decode ALARM.ACT & ALARMS.LOG on-the-fly
        if ftp_bundle and ftp_bundle.get("alarm_bytes"):
            alarm_act = SetexFolderReader.read_alarm_act(
                raw_bytes=ftp_bundle["alarm_bytes"],
                machine_no=machine.machine_no
            )
        else:
            alarm_act = SetexFolderReader.read_alarm_act(
                folder_path=target_folder or "",
                ip=machine.ip_address,
                ftp_port=machine.ftp_port or 21,
                machine_no=machine.machine_no
            )

        # Real-time Controller CPU Alarm & IW Telemetry Check via Port 50000
        iw_data = None
        iw_t1 = None
        iw_pump = None
        iw_reel = None
        iw_level = None
        if machine.ip_address:
            tcp_p = getattr(machine, "tcp_port", 0) or 50000
            try:
                tcp_alarm = SetexTcpClient.read_live_alarm_status(machine.ip_address, tcp_p, timeout=1.5)
                if not tcp_alarm.get("error"):
                    alarm_act["is_alarm_active"] = tcp_alarm.get("is_alarm_active", False)
                    if not alarm_act["is_alarm_active"]:
                        alarm_act["active_alarms"] = []
            except Exception as e_tcp_al:
                logger.debug(f"TCP alarm check notice: {e_tcp_al}")

            try:
                iw_data = SetexTcpClient.read_iw_telemetry(
                    machine.ip_address,
                    tcp_p,
                    count=80,
                    machine_no=machine.machine_no,
                    timeout=1.5
                )
                if iw_data and iw_data.get("online"):
                    iw_t1 = iw_data.get("iw_t1_pv")
                    iw_pump = iw_data.get("iw_pump_sp") or iw_data.get("iw_pump_act")
                    iw_reel = iw_data.get("iw_reel_act")
                    iw_level = iw_data.get("iw_level_act")
                    if iw_t1 is not None and 10.0 <= float(iw_t1) <= 150.0:
                        status_info["temp_pv"] = float(iw_t1)
                        status_info["data_source"] = f"tcp://{machine.ip_address}:{tcp_p} (IW Realtime)"
                        status_info["is_iw_live"] = True
                        logger.info(
                            f"[IW REALTIME] Mesin {machine.machine_no} ({machine.ip_address}): "
                            f"T1={iw_t1}°C, Pump={iw_pump}%, Reel={iw_reel} m/min, Level={iw_level}%"
                        )
            except Exception as e_iw:
                logger.debug(f"Direct IW read from {machine.ip_address} notice: {e_iw}")

        if ftp_bundle and ftp_bundle.get("alarms_log_bytes"):
            alarm_history = SetexFolderReader.read_alarms_log(
                raw_bytes=ftp_bundle["alarms_log_bytes"],
                limit=50,
                machine_no=machine.machine_no
            )
        else:
            alarm_history = SetexFolderReader.read_alarms_log(
                folder_path=target_folder or "",
                ip=machine.ip_address,
                ftp_port=machine.ftp_port or 21,
                limit=50,
                machine_no=machine.machine_no
            )

        # 4. Find and parse cyclic telemetry records on-the-fly
        telemetry_records = []
        batch_no = status_info.get("current_batch") or machine.current_batch or "063127"
        if batch_no == "UNKNOWN":
            batch_no = machine.current_batch or "063127"

        # 4.1 First check batch log from unified FTP bundle
        if ftp_bundle and ftp_bundle.get("batch_log_bytes"):
            pts = SetexFolderReader.parse_cyclic_log_bytes(ftp_bundle["batch_log_bytes"])
            if pts:
                telemetry_records.extend(pts)

        # 4.2 If no points yet and machine has IP, try legacy fallback
        if not telemetry_records and machine.ip_address and batch_no != "UNKNOWN":
            ftp_points = SetexFolderReader.read_cyclic_log_from_ftp(
                machine.ip_address,
                machine.ftp_port or 21,
                batch_no
            )
            if ftp_points:
                telemetry_records.extend(ftp_points)

        # 4.3 If no FTP points found, scan local directory structure
        if not telemetry_records and target_folder:
            search_dirs = [target_folder, os.path.join(target_folder, "..", "plain_export"), "/app/plain_export"]
            log_files = SetexFolderReader.find_all_log_files([d for d in search_dirs if os.path.exists(d)])
            for lf in log_files:
                recs = SetexFolderReader.read_cyclic_log_file(lf)
                telemetry_records.extend(recs)

        # 3.3 Synthesize live point from IW (Priority) or verified live STATUS.ACT reading
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        live_step = status_info.get("current_step") or machine.current_step or 1

        if iw_data and iw_data.get("online") and iw_t1 is not None and 10.0 <= float(iw_t1) <= 150.0:
            live_iw_pt = {
                "timestamp": now_str,
                "temp_pv": float(iw_t1),
                "temp_sp": status_info.get("temp_sp"),
                "temp_pt100_t2": status_info.get("temp_pt100_t2") or 0.0,
                "pump_speed_percent": float(iw_pump) if iw_pump is not None else 85.0,
                "reel_speed_mpm": float(iw_reel) if iw_reel is not None else 240.0,
                "step_no": live_step,
                "source": "IW_REALTIME"
            }
            telemetry_records.append(live_iw_pt)
        elif not telemetry_records and status_info.get("temp_pv") is not None and abs(float(status_info["temp_pv"]) - 76.8) > 0.1:
            telemetry_records.append({
                "timestamp": now_str,
                "temp_pv": status_info.get("temp_pv", 40.0),
                "temp_sp": status_info.get("temp_sp"),
                "temp_pt100_t2": status_info.get("temp_pt100_t2"),
                "pump_speed_percent": 85.0,
                "reel_speed_mpm": 240.0,
                "step_no": live_step
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
        machine.current_step = live_step
        machine.last_ping_time = datetime.utcnow()

        if iw_t1 is not None and 10.0 <= float(iw_t1) <= 150.0:
            machine.current_temp = float(iw_t1)
        elif unique_telemetry:
            last_pt = unique_telemetry[-1]
            machine.current_temp = last_pt.get("temp_pv")
            if live_step <= 1 and last_pt.get("step_no") and last_pt["step_no"] > 1:
                machine.current_step = last_pt["step_no"]
        elif status_info.get("temp_pv") is not None:
            machine.current_temp = status_info.get("temp_pv")

        try:
            # 4.1 Upsert Batch Header with live program information
            real_prog_no = status_info.get("prog_no") or 1
            real_recipe_name = status_info.get("program_name") or f"Program {real_prog_no}"
            existing_batch = db.query(BatchHeader).filter(BatchHeader.batch_ref_no == batch_no).first()
            if not existing_batch:
                b_stmt = insert(BatchHeader).values(
                    batch_ref_no=batch_no,
                    batch_no=batch_no if batch_no.startswith("LOT-") else f"LOT-{batch_no}",
                    machine_no=machine.machine_no,
                    program_no=real_prog_no,
                    recipe_name=real_recipe_name,
                    status="RUNNING",
                    fabric_weight_kg=float(machine.capacity_kg) if machine.capacity_kg else 350.0,
                    liquor_ratio=float(machine.default_liquor_ratio) if machine.default_liquor_ratio else 8.0,
                    customer="PT. SMM JETFLOW"
                ).on_conflict_do_nothing(index_elements=['batch_ref_no'])
                db.execute(b_stmt)
                db.commit()
            else:
                needs_update = False
                if real_prog_no and existing_batch.program_no != real_prog_no:
                    existing_batch.program_no = real_prog_no
                    needs_update = True
                if real_recipe_name and existing_batch.recipe_name != real_recipe_name:
                    existing_batch.recipe_name = real_recipe_name
                    needs_update = True
                if needs_update:
                    db.commit()

            # 4.1 Forward Decoded State & Curve to EMQX MQTT Broker
            asset_code = getattr(machine, "asset_id", None)
            if not asset_code:
                m_digits = re.sub(r'[^0-9]', '', machine.machine_no or '')
                if m_digits:
                    asset_code = f"JF-LB-{int(m_digits):02d}" if int(m_digits) < 10 else f"JF-LB-{m_digits}"
                else:
                    asset_code = f"JF-LB-{machine.machine_no}"

            # Publish Status, Curve, and Alarms to EMQX Message Broker
            forward_machine_status(asset_code, machine.machine_no, machine.status, batch_no, live_step, real_prog_no)
            if unique_telemetry:
                forward_batch_curve(asset_code, machine.machine_no, batch_no, unique_telemetry)
            if alarm_history:
                forward_alarms(asset_code, machine.machine_no, alarm_history)

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
                    # Deduplicate rows by unique constraint to avoid PostgreSQL ON CONFLICT error
                    dedup_records = {}
                    for row in insert_rows:
                        key = (row["log_timestamp"], row["machine_no"], row["batch_ref_no"])
                        dedup_records[key] = row
                    clean_rows = list(dedup_records.values())

                    # Chunk in batches of 200 to prevent query parameter limits
                    chunk_size = 200
                    for c_idx in range(0, len(clean_rows), chunk_size):
                        chunk = clean_rows[c_idx:c_idx + chunk_size]
                        t_stmt = insert(DatalogCyclicRecord).values(chunk)
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
                    points_inserted = len(clean_rows)

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
                    # Deduplicate alarm rows by constraint
                    dedup_alarms = {}
                    for a_row in alarm_rows:
                        a_key = (a_row["machine_no"], a_row["batch_ref_no"], a_row["alarm_timestamp"], a_row["alarm_code"])
                        dedup_alarms[a_key] = a_row
                    clean_alarms = list(dedup_alarms.values())

                    chunk_size = 200
                    for c_idx in range(0, len(clean_alarms), chunk_size):
                        a_chunk = clean_alarms[c_idx:c_idx + chunk_size]
                        a_stmt = insert(DatalogAlarm).values(a_chunk)
                        a_stmt = a_stmt.on_conflict_do_nothing(
                            index_elements=['machine_no', 'batch_ref_no', 'alarm_timestamp', 'alarm_code']
                        )
                        db.execute(a_stmt)
                    db.commit()
                    alarms_inserted = len(clean_alarms)

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

        # 5. Extract program recipe step names (parity with SETEX Secom 777 HMI step list)
        recipe_steps = []
        try:
            catalog = SetexFolderReader.get_function_catalog()
            if ftp_bundle and ftp_bundle.get("prg_bytes"):
                recipe_steps = SetexFolderReader.parse_prg_steps(ftp_bundle["prg_bytes"], catalog)
            if not recipe_steps:
                recipe_steps = SetexFolderReader.get_recipe_steps(
                    ip=machine.ip_address,
                    ftp_port=machine.ftp_port or 21,
                    batch_no=batch_no,
                    folder_path=target_folder,
                    prog_no=status_info.get("prog_no")
                )

            # AUTOMATIC PARITY VERIFICATION:
            # Verify recipe's active step with the ground-truth function_code from HMI STATUS.ACT.
            curr_step_no = machine.current_step or status_info.get("current_step") or 1
            live_func_code = status_info.get("function_code") or 0

            if recipe_steps and live_func_code > 0:
                active_st = next((s for s in recipe_steps if s.get("no") == curr_step_no or s.get("step_no") == curr_step_no), None)
                if active_st:
                    is_generic = not active_st.get("func_id") or str(active_st.get("name", "")).startswith("Step #")
                    if is_generic:
                        catalog = SetexFolderReader.get_function_catalog()
                        if str(live_func_code) in catalog or live_func_code in SetexFolderReader.FALLBACK_FUNCTION_NAMES:
                            correct_name = SetexFolderReader.get_fallback_function_name(live_func_code)
                            logger.info(
                                f"[AUTO-ALIGN] Setting generic active step #{curr_step_no} to controller function: {correct_name} [F{live_func_code}]"
                            )
                            active_st["func_id"] = live_func_code
                            active_st["icon"] = str(live_func_code)
                            active_st["name"] = correct_name
                            if active_st.get("sub_steps") and len(active_st["sub_steps"]) > 0:
                                active_st["sub_steps"][0]["name"] = correct_name
                                active_st["sub_steps"][0]["func_id"] = live_func_code
                    elif active_st.get("func_id") != live_func_code:
                        logger.info(
                            f"[PARITY NOTE] Machine {machine.machine_no} active step #{curr_step_no}: "
                            f"Recipe PRG specifies {active_st.get('name')} [F{active_st['func_id']}], controller status reports F{live_func_code}."
                        )
        except Exception as e:
            logger.warning(f"Gagal mengekstrak langkah resep batch {batch_no}: {e}")

        # 6. Evaluate baseline vs active operator setpoint deviation (Intervention Tracking)
        active_interventions = []
        try:
            curr_step_no = machine.current_step or status_info.get("current_step") or 1
            live_sp = None
            # Only use authentic live SP from cyclic datalog curve or verified controller register
            if unique_telemetry:
                step_pts_curr = [p for p in unique_telemetry if p.get("step_no") == curr_step_no]
                if step_pts_curr and step_pts_curr[-1].get("temp_sp") is not None:
                    c_sp = float(step_pts_curr[-1]["temp_sp"])
                    # Filter out bogus 76.8 (status word 0x0300) and default 90.0
                    if c_sp > 0 and abs(c_sp - 76.8) > 0.1 and abs(c_sp - 90.0) > 0.1:
                        live_sp = c_sp
            elif status_info.get("temp_sp") is not None:
                c_sp = float(status_info["temp_sp"])
                if c_sp > 0 and abs(c_sp - 76.8) > 0.1 and abs(c_sp - 90.0) > 0.1:
                    live_sp = c_sp

            # Interventions are tracked authentically via InterventionService & Controller TCP Object 1030/1009
            # Cyclic datalog telemetry does not fabricate operator interventions to avoid false alarms (e.g. pump speed 95% or ramp phase)

            # Query all interventions for current batch (excluding bogus 76.8 entries)
            if db:
                db_invs = db.query(OperatorIntervention).filter(
                    OperatorIntervention.machine_no == machine.machine_no,
                    OperatorIntervention.batch_no == batch_no
                ).order_by(desc(OperatorIntervention.timestamp)).all()

                step_inv_map = {}
                for inv in db_invs:
                    if abs(float(inv.value_after or 0) - 76.8) < 0.05:
                        continue
                    if inv.step_no not in step_inv_map:
                        step_inv_map[inv.step_no] = inv
                    active_interventions.append({
                        "id": inv.id,
                        "timestamp": inv.timestamp.strftime("%Y-%m-%d %H:%M:%S") if inv.timestamp else "",
                        "step_no": inv.step_no,
                        "parameter_name": inv.parameter_name,
                        "unit": inv.unit,
                        "value_before": float(inv.value_before) if inv.value_before else 0.0,
                        "value_after": float(inv.value_after) if inv.value_after else 0.0,
                        "delta": float(inv.delta) if inv.delta else 0.0,
                        "notes": inv.notes
                    })

                # Attach intervention markers to steps
                for st in recipe_steps:
                    s_no = st.get("no")
                    if s_no in step_inv_map:
                        inv = step_inv_map[s_no]
                        st["has_intervention"] = True
                        st["actual_p1"] = f"{float(inv.value_after):.1f} {inv.unit}"
                        st["delta_p1"] = f"{float(inv.delta):+} {inv.unit}"
                        st["intervention_notes"] = inv.notes

                        for line in st.get("sub_steps", []):
                            if not line.get("is_sub"):
                                line["actual_p1"] = f"{float(inv.value_after):.1f} {inv.unit}"
                                line["delta_p1"] = f"{float(inv.delta):+} {inv.unit}"
                                line["has_delta"] = True
        except Exception as e:
            logger.warning(f"Gagal memproses evaluasi intervensi: {e}")

        # 7. Evaluate Execution Timings per Step & Target vs Actual Deviation
        try:
            curr_step_no = machine.current_step or status_info.get("current_step") or 1
            key = f"{machine.machine_no}_{batch_no}"
            now_dt = datetime.now()
            now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

            # 7.1 Primary: Ground-truth events from PR*.LOG if available
            step_timings = {}
            if ftp_bundle and ftp_bundle.get("batch_log_bytes"):
                pr_timings = SetexFolderReader.parse_step_timings_from_pr_bytes(ftp_bundle["batch_log_bytes"])
                if pr_timings:
                    step_timings.update(pr_timings)

            # 7.2 Secondary: Real-time Live Transition Tracker
            if key not in _LIVE_STEP_TRANSITIONS:
                _LIVE_STEP_TRANSITIONS[key] = {}
            live_map = _LIVE_STEP_TRANSITIONS[key]

            # Track transitions between steps in active session
            if curr_step_no not in live_map:
                # Mark previous active step as completed at current second
                for prev_s in list(live_map.keys()):
                    if prev_s < curr_step_no and not live_map[prev_s].get("end"):
                        live_map[prev_s]["end"] = now_str
                live_map[curr_step_no] = {"start": now_str, "end": None}

            # Merge live tracked steps into step_timings if not already in PR log
            for s_k, t_val in live_map.items():
                if s_k not in step_timings:
                    step_timings[s_k] = dict(t_val)
                else:
                    if not step_timings[s_k].get("start") and t_val.get("start"):
                        step_timings[s_k]["start"] = t_val["start"]
                    if not step_timings[s_k].get("end") and t_val.get("end"):
                        step_timings[s_k]["end"] = t_val["end"]

            # 7.3 Tertiary: Strict same-session database query (preventing cross-day 48-hour contamination)
            if db and batch_no and (not step_timings or len(step_timings) < 2):
                try:
                    from sqlalchemy import func
                    # Query only records for this machine and batch
                    db_step_rows = db.query(
                        DatalogCyclicRecord.step_no,
                        func.min(DatalogCyclicRecord.log_timestamp),
                        func.max(DatalogCyclicRecord.log_timestamp)
                    ).filter(
                        DatalogCyclicRecord.machine_no == machine.machine_no,
                        DatalogCyclicRecord.batch_ref_no == batch_no
                    ).group_by(DatalogCyclicRecord.step_no).all()

                    for s_val, min_ts, max_ts in db_step_rows:
                        if s_val is not None:
                            s_int = int(s_val)
                            # Never assign timestamps to future steps
                            if s_int > curr_step_no:
                                continue
                            # Sanity check: span between min and max should not exceed 24 hours
                            if min_ts and max_ts and (max_ts - min_ts).total_seconds() > 86400:
                                min_ts = max_ts  # Discard old cross-day date

                            min_s = min_ts.strftime("%Y-%m-%d %H:%M:%S") if min_ts else None
                            max_s = max_ts.strftime("%Y-%m-%d %H:%M:%S") if max_ts else None

                            if s_int not in step_timings:
                                step_timings[s_int] = {"start": min_s, "end": max_s if s_int < curr_step_no else None}
                            else:
                                if not step_timings[s_int].get("start"):
                                    step_timings[s_int]["start"] = min_s
                                if s_int < curr_step_no and not step_timings[s_int].get("end"):
                                    step_timings[s_int]["end"] = max_s
                except Exception as e_db_t:
                    logger.warning(f"Error querying step timings from DB: {e_db_t}")

            sorted_step_nums = sorted([k for k in step_timings.keys()])

            # 7.4 Evaluate Each Recipe Step: Timings, Target Setpoints, and Faster/Slower Deviations
            for st in recipe_steps:
                s_no = st.get("no")
                timing = step_timings.get(s_no)

                # Extract planned target duration in minutes from SETEX set_time or parameters
                target_min = None
                if st.get("set_time") and int(st["set_time"]) > 0:
                    target_min = int(st["set_time"])
                elif st.get("hold_time") and int(st["hold_time"]) > 0:
                    target_min = int(st["hold_time"])
                else:
                    for p_val in (st.get("p3"), st.get("p1"), st.get("p2"), st.get("p4"), st.get("p5")):
                        if p_val:
                            m_t = re.search(r'(\d+)\s*(?:min|dak|mnt)', str(p_val), re.IGNORECASE)
                            if m_t:
                                v_t = int(m_t.group(1))
                                if v_t > 0:
                                    target_min = v_t
                                    break

                st["target_min"] = target_min
                st["start_time"] = None
                st["end_time"] = None
                st["duration_seconds"] = None
                st["duration_text"] = None
                st["time_status"] = "WAITING"
                st["delta_text"] = f"Target: {target_min} min" if target_min else "Variabel"

                # Attach real sensor telemetry for this step (from unique_telemetry)
                step_pts = [p for p in unique_telemetry if p.get("step_no") == s_no]
                if step_pts:
                    pv_vals = [float(p["temp_pv"]) for p in step_pts if p.get("temp_pv") is not None]
                    sp_vals = [float(p["temp_sp"]) for p in step_pts if p.get("temp_sp") is not None]
                    t2_vals = [float(p["temp_pt100_t2"]) for p in step_pts if p.get("temp_pt100_t2") is not None]
                    pump_vals = [float(p["pump_speed_percent"]) for p in step_pts if p.get("pump_speed_percent") is not None]
                    reel_vals = [float(p["reel_speed_mpm"]) for p in step_pts if p.get("reel_speed_mpm") is not None]

                    # Periksa apakah langkah ini memang memiliki target suhu (heating/cooling/hold)
                    has_temp_target = False
                    st_type = str(st.get("type") or "").upper()
                    if st_type in ("HEAT", "COOL", "HOLD", "TEMP"):
                        has_temp_target = True
                    elif st.get("func_id") in (140, 141, 142, 145, 146, 121, 131, 150):
                        has_temp_target = True
                    else:
                        for sub in st.get("sub_steps", []):
                            sub_type = str(sub.get("type") or "").upper()
                            if sub_type in ("HEAT", "COOL", "HOLD", "TEMP") or sub.get("func_id") in (140, 141, 142, 145, 146, 121, 131, 150):
                                has_temp_target = True
                                break
                            if any(p.get("unit") == "°C" for p in sub.get("params", [])):
                                has_temp_target = True
                                break
                            if "°C" in str(sub.get("p1") or "") or "°C" in str(sub.get("p2") or ""):
                                has_temp_target = True
                                break
                    if not has_temp_target:
                        if "°C" in str(st.get("p1") or "") or "°C" in str(st.get("p2") or ""):
                            has_temp_target = True
                        elif any(p.get("unit") == "°C" for p in st.get("params", [])):
                            has_temp_target = True

                    st["has_temp_target"] = has_temp_target
                    st["telemetry"] = {
                        "point_count": len(step_pts),
                        "pv_start": round(pv_vals[0], 1) if pv_vals else None,
                        "pv_end": round(pv_vals[-1], 1) if pv_vals else None,
                        "pv_min": round(min(pv_vals), 1) if pv_vals else None,
                        "pv_max": round(max(pv_vals), 1) if pv_vals else None,
                        "pv_avg": round(sum(pv_vals) / len(pv_vals), 1) if pv_vals else None,
                        "sp": (round(sp_vals[-1], 1) if sp_vals else None) if has_temp_target else None,
                        "t2_avg": round(sum(t2_vals) / len(t2_vals), 1) if t2_vals else None,
                        "pump_avg": round(sum(pump_vals) / len(pump_vals), 1) if pump_vals else None,
                        "reel_avg": round(sum(reel_vals) / len(reel_vals), 1) if reel_vals else None,
                    }
                else:
                    st["has_temp_target"] = False
                    st["telemetry"] = None

                # Attach step-specific alarms & interventions
                st["alarms"] = [a for a in final_alarms if a.get("step_no") == s_no]
                step_invs = [i for i in active_interventions if i.get("step_no") == s_no]
                st["interventions"] = step_invs

                # Determine accurate target temperature (from recipe parameters or verified operator intervention)
                step_temp_sp = None
                if st.get("has_temp_target"):
                    # 1. Check recipe planned parameters directly (p1 / p2 string)
                    if st.get("p1") and "°C" in str(st.get("p1")):
                        m_p1 = re.search(r'[-+]?\d*\.?\d+', str(st.get("p1")))
                        if m_p1:
                            step_temp_sp = float(m_p1.group(0))

                    if step_temp_sp is None:
                        for p in st.get("params", []):
                            if p.get("unit") == "°C" or any(k in str(p.get("name", "")).lower() for k in ("temp", "suhu")):
                                try:
                                    step_temp_sp = float(p.get("value", 0))
                                    break
                                except Exception:
                                    pass

                    if step_temp_sp is None:
                        for sub in st.get("sub_steps", []):
                            if sub.get("p1") and "°C" in str(sub.get("p1")):
                                m_sub = re.search(r'[-+]?\d*\.?\d+', str(sub.get("p1")))
                                if m_sub:
                                    step_temp_sp = float(m_sub.group(0))
                                    break
                            for p in sub.get("params", []):
                                if p.get("unit") == "°C" or any(k in str(p.get("name", "")).lower() for k in ("temp", "suhu")):
                                    try:
                                        step_temp_sp = float(p.get("value", 0))
                                        break
                                    except Exception:
                                        pass
                            if step_temp_sp is not None:
                                break

                    # 2. Check operator intervention if no parameter found or explicitly adjusted
                    if step_temp_sp is None:
                        for inv in step_invs:
                            if any(k in str(inv.get("parameter_name", "")).lower() for k in ("temp", "suhu")):
                                if inv.get("value_after") is not None and abs(float(inv.get("value_after")) - 76.8) > 0.05:
                                    step_temp_sp = float(inv.get("value_after"))
                                    break

                    # 3. Fallback to telemetry SP only if valid (> 0 and not generic 90.0 or 76.8)
                    if step_temp_sp is None and step_pts:
                        sp_vals_curr = [float(p["temp_sp"]) for p in step_pts if p.get("temp_sp") is not None]
                        if sp_vals_curr:
                            last_sp = float(sp_vals_curr[-1])
                            if last_sp > 0 and abs(last_sp - 90.0) > 0.1 and abs(last_sp - 76.8) > 0.1:
                                step_temp_sp = round(last_sp, 1)

                if step_pts:
                    st["telemetry"]["sp"] = step_temp_sp

                # Step is in the future (WAITING) -> STRICTLY BLANK TIMINGS
                if s_no > curr_step_no:
                    continue

                if timing and timing.get("start"):
                    st["start_time"] = timing["start"]

                    if s_no < curr_step_no:
                        # Completed step
                        end_val = timing.get("end")
                        next_s = next((k for k in sorted_step_nums if k > s_no), None)
                        if next_s and step_timings.get(next_s, {}).get("start"):
                            next_start = step_timings[next_s]["start"]
                            if not end_val or end_val == timing["start"]:
                                end_val = next_start
                        st["end_time"] = end_val

                        if st["start_time"] and st["end_time"]:
                            try:
                                t1 = datetime.strptime(st["start_time"], "%Y-%m-%d %H:%M:%S")
                                t2 = datetime.strptime(st["end_time"], "%Y-%m-%d %H:%M:%S")
                                dur_sec = max(0, int((t2 - t1).total_seconds()))
                                if dur_sec > 14400:
                                    dur_sec = (target_min * 60) if target_min else 300

                                st["duration_seconds"] = dur_sec
                                if dur_sec < 60:
                                    st["duration_text"] = f"{dur_sec} dtk"
                                elif dur_sec < 3600:
                                    m = dur_sec // 60
                                    s = dur_sec % 60
                                    st["duration_text"] = f"{m} mnt {s} dtk" if s > 0 else f"{m} mnt"
                                else:
                                    h = dur_sec // 3600
                                    m = (dur_sec % 3600) // 60
                                    st["duration_text"] = f"{h} jam {m} mnt"

                                # Target vs Actual Comparison
                                if target_min:
                                    act_min = dur_sec / 60.0
                                    diff_min = round(act_min - target_min, 1)
                                    if diff_min >= 1.0:
                                        st["time_status"] = "SLOWER"  # Molor / Terlambat
                                        st["delta_text"] = f"+{int(round(diff_min))} mnt (Molor)"
                                    elif diff_min <= -1.0:
                                        st["time_status"] = "FASTER"  # Lebih Cepat
                                        st["delta_text"] = f"-{int(round(abs(diff_min)))} mnt (Cepat)"
                                    else:
                                        st["time_status"] = "ON_TRACK"
                                        st["delta_text"] = "Sesuai Target"
                                else:
                                    st["time_status"] = "VARIABLE"
                                    st["delta_text"] = "Variabel (Sensor)"
                            except Exception:
                                pass
                    elif s_no == curr_step_no:
                        # Active step: currently running
                        st["end_time"] = None
                        try:
                            # Use telemetry latest timestamp if available to prevent server timezone mismatch
                            ref_now = now_dt
                            if unique_telemetry and unique_telemetry[-1].get("timestamp"):
                                try:
                                    ref_now = datetime.strptime(unique_telemetry[-1]["timestamp"], "%Y-%m-%d %H:%M:%S")
                                except Exception:
                                    pass

                            t1 = datetime.strptime(st["start_time"], "%Y-%m-%d %H:%M:%S")
                            elapsed_sec = max(0, int((ref_now - t1).total_seconds()))

                            st["duration_seconds"] = elapsed_sec
                            if elapsed_sec < 60:
                                st["duration_text"] = f"{elapsed_sec} dtk"
                            elif elapsed_sec < 3600:
                                st["duration_text"] = f"{elapsed_sec // 60} mnt"
                            else:
                                st["duration_text"] = f"{elapsed_sec // 3600} jam {(elapsed_sec % 3600) // 60} mnt"

                            # Real-time Overtime / Remaining evaluation
                            if target_min:
                                act_min = elapsed_sec / 60.0
                                if act_min > target_min + 0.5:
                                    over_min = int(round(act_min - target_min))
                                    st["time_status"] = "OVERTIME"  # Molor saat ini
                                    st["delta_text"] = f"⚠️ Molor +{over_min} mnt"
                                else:
                                    rem_min = max(0, int(round(target_min - act_min)))
                                    st["time_status"] = "RUNNING"
                                    st["delta_text"] = f"Sisa ~{rem_min} mnt"
                            else:
                                st["time_status"] = "RUNNING"
                                st["delta_text"] = "Sedang Jalan"
                        except Exception:
                            pass
        except Exception as e_timings:
            logger.warning(f"Gagal memproses evaluasi waktu step: {e_timings}")

        # Map true setpoint from recipe/intervention to telemetry points to eliminate raw default 90.0
        step_sp_map = {s.get("no"): (s.get("telemetry") or {}).get("sp") for s in recipe_steps if s.get("no")}
        step_has_target = {s.get("no"): s.get("has_temp_target", False) for s in recipe_steps if s.get("no")}
        for pt in unique_telemetry:
            s_n = pt.get("step_no")
            if s_n in step_has_target:
                if not step_has_target[s_n]:
                    pt["temp_sp"] = None
                elif step_sp_map.get(s_n) is not None:
                    pt["temp_sp"] = step_sp_map[s_n]

        active_step_obj = next((s for s in recipe_steps if s.get("no") == machine.current_step), None)
        active_sp = None
        if active_step_obj:
            active_sp = (active_step_obj.get("telemetry") or {}).get("sp")
            if active_sp is None and active_step_obj.get("has_temp_target"):
                if active_step_obj.get("p1") and "°C" in str(active_step_obj.get("p1")):
                    m_p1 = re.search(r'[-+]?\d*\.?\d+', str(active_step_obj.get("p1")))
                    if m_p1:
                        active_sp = float(m_p1.group(0))
                if active_sp is None:
                    for p in active_step_obj.get("params", []):
                        if p.get("unit") == "°C":
                            try:
                                active_sp = float(p.get("value", 0))
                                break
                            except Exception:
                                pass

        return {
            "machine_no": machine.machine_no,
            "status": machine.status,
            "controller_type": "SETEX 797CE (Windows CE)" if is_797 else (machine.controller_type or "SECOM 777 (Windows CE)"),
            "controller_name": "SETEX Secom 797CE" if is_797 else "SETEX Secom 777",
            "share_folder_path": "/Flashdisk/SC797CE" if is_797 else (machine.share_folder_path or "/Storage/sc777ce"),
            "database_mode": "POSTGRES" if getattr(database, "IS_POSTGRES", False) else "SQLITE_OFFLINE",
            "is_live_hmi": status_info.get("is_ftp_source", False),
            "data_source": status_info.get("data_source", "LOCAL_STORAGE"),
            "hmi_ip": machine.ip_address,
            "hmi_port": machine.ftp_port or 21,
            "batch_no": batch_no,
            "prog_no": status_info.get("prog_no", 0),
            "program_code": status_info.get("program_code") or (f"M_{status_info.get('prog_no', 4):04d}" if status_info.get("prog_no") else "M_0004"),
            "program_name": status_info.get("program_name") or "PROGRAM VINIL",
            "current_step": machine.current_step,
            "function_code": status_info.get("function_code", 0),
            "current_temp": machine.current_temp,
            "current_sp": active_sp,
            "is_alarm_active": alarm_act.get("is_alarm_active", False),
            "active_alarms": alarm_act.get("active_alarms", []),
            "points_saved": points_inserted,
            "alarms_saved": alarms_inserted,
            "curve": unique_telemetry[-500:],  # Return up to 500 recent points for real-time chart
            "alarms": final_alarms,
            "steps": recipe_steps,
            "interventions": active_interventions,
            "iw_telemetry": iw_data,
            "iw_source": bool(iw_data and iw_data.get("online") and iw_t1 is not None),
            "iw_online": bool(iw_data and iw_data.get("online")),
            "iw_t1_pv": iw_t1,
            "iw_pump": iw_pump,
            "iw_reel": iw_reel,
            "iw_level": iw_level
        }

    @staticmethod
    def load_recipe_steps_from_db(
        db: Session,
        machine_no: str,
        prog_no: Optional[int] = None,
        program_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Loads recipe steps strictly from PostgreSQL/SQLite (program_components + steps +
        step_functions + step_function_parameters) without any FTP or local PRG download.
        """
        from ..models.schema_pg import ProgramComponent, Step, StepFunction, StepFunctionParameter

        clean_m = (machine_no or "").strip().upper()
        p_no_str = str(int(prog_no)) if prog_no and int(prog_no) > 0 else None
        clean_name = (program_name or "").strip().upper()

        comp = None
        if p_no_str:
            comp = (
                db.query(ProgramComponent)
                .filter(
                    ProgramComponent.level == 1,
                    ProgramComponent.machine_code == clean_m,
                    ProgramComponent.number == p_no_str,
                )
                .order_by(desc(ProgramComponent.modification_time), desc(ProgramComponent.id))
                .first()
            )
        if not comp and clean_name:
            comp = (
                db.query(ProgramComponent)
                .filter(
                    ProgramComponent.level == 1,
                    ProgramComponent.machine_code == clean_m,
                    ProgramComponent.name.ilike(clean_name),
                )
                .order_by(desc(ProgramComponent.modification_time), desc(ProgramComponent.id))
                .first()
            )
        if not comp and p_no_str:
            comp = (
                db.query(ProgramComponent)
                .filter(ProgramComponent.level == 1, ProgramComponent.number == p_no_str)
                .order_by(desc(ProgramComponent.modification_time), desc(ProgramComponent.id))
                .first()
            )
        if not comp:
            return []

        db_steps = (
            db.query(Step)
            .filter(Step.parent_component_id == comp.id)
            .order_by(Step.position.asc())
            .all()
        )
        if not db_steps:
            return []

        m_cat = SetexFolderReader.load_machine_catalog(clean_m) or {}
        func_cat = m_cat.get("functions") or SetexFolderReader.get_function_catalog() or {}
        res_cat = m_cat.get("resources") or SetexFolderReader._RESOURCES_CATALOG or {}

        out_steps: List[Dict[str, Any]] = []
        for st in db_steps:
            s_funcs = (
                db.query(StepFunction)
                .filter(StepFunction.step_id == st.id)
                .order_by(StepFunction.resource_number.asc(), StepFunction.id.asc())
                .all()
            )
            sub_steps = []
            main_func_id = 0
            main_name = st.label or f"Langkah #{st.position}"
            main_params = []
            has_temp = st.summary_temp is not None

            for sf in s_funcs:
                fid = int(sf.function_number or 0)
                slot_no = int(sf.resource_number or 1)
                f_meta = func_cat.get(str(fid), {})
                fname = sf.function_name or f_meta.get("name") or SetexFolderReader.FALLBACK_FUNCTION_NAMES.get(fid) or f"Func {fid}"
                res_name = (res_cat.get(str(slot_no), {}) or {}).get("name") or ("main tank" if slot_no == 1 else f"Resource {slot_no}")

                sf_params = (
                    db.query(StepFunctionParameter)
                    .filter(StepFunctionParameter.step_function_id == sf.id)
                    .order_by(StepFunctionParameter.function_parameter_number.asc())
                    .all()
                )
                p_specs = f_meta.get("params") or f_meta.get("parameters") or []
                params_list = []
                for idx_p, sfp in enumerate(sf_params):
                    val = float(sfp.value) if sfp.value is not None else 0.0
                    p_spec = p_specs[idx_p] if idx_p < len(p_specs) else {}
                    p_name = p_spec.get("name") or f"P{sfp.function_parameter_number}"
                    p_unit = (p_spec.get("unit") or "").strip()
                    if val == 0.0 and not p_spec:
                        continue
                    v_fmt = f"{int(val)}" if val.is_integer() else f"{val:.1f}"
                    formatted = f"{v_fmt} {p_unit}".strip()
                    if "°c" in p_unit.lower() or "temp" in p_name.lower():
                        has_temp = True
                    params_list.append({
                        "name": p_name,
                        "value": val,
                        "unit": p_unit,
                        "formatted": formatted,
                    })

                if slot_no == 1:
                    main_func_id = fid
                    main_name = fname
                    main_params = params_list

                sub_steps.append({
                    "line": slot_no,
                    "is_sub": slot_no != 1,
                    "func_id": fid,
                    "func_name": fname,
                    "name": fname,
                    "resource_name": res_name,
                    "params": params_list,
                    "p1": params_list[0]["formatted"] if len(params_list) > 0 else "0",
                    "p2": params_list[1]["formatted"] if len(params_list) > 1 else "0",
                    "p3": params_list[2]["formatted"] if len(params_list) > 2 else "0",
                })

            set_time_min = float(st.summary_time_min) if st.summary_time_min is not None else 0.0
            out_steps.append({
                "no": int(st.position),
                "func_id": main_func_id,
                "name": main_name,
                "icon": str(main_func_id or st.position),
                "type": "HEAT" if main_func_id in (140, 141, 142, 145, 146) else ("HOLD" if main_func_id == 121 else "PROCESS"),
                "comment": st.label or "",
                "set_time": set_time_min,
                "params": main_params,
                "p1": main_params[0]["formatted"] if len(main_params) > 0 else (f"{float(st.summary_temp):.0f} °C" if st.summary_temp else "0"),
                "p2": main_params[1]["formatted"] if len(main_params) > 1 else (f"{int(set_time_min)} min" if set_time_min > 0 else "0"),
                "p3": main_params[2]["formatted"] if len(main_params) > 2 else "0",
                "sub_steps": sub_steps,
                "has_temp_target": has_temp or main_func_id in (140, 141, 142, 145, 146, 121, 131, 150),
            })

        return out_steps

    @staticmethod
    def get_machine_live_from_db(db: Session, machine: Machine) -> Dict[str, Any]:
        """
        100% Database-Only Live Telemetry Reader for Process Analyser & Dashboard.
        Reads exclusively from PostgreSQL tables populated by `da-batch-worker` and `da-setex-collector`
        (`machines`, `live_iw_telemetry`, `batch_headers`, `datalog_cyclic_records`, `datalog_alarms`,
        `operator_interventions`, `program_components`, `machine_ftp_status`).
        NEVER opens any FTP or TCP socket to the controller.
        """
        from sqlalchemy import text as sa_text

        mach_no = (machine.machine_no or "").strip().upper()
        is_797 = (
            (machine.ip_address and machine.ip_address.strip() == "192.168.1.95")
            or (machine.controller_type and "797" in machine.controller_type.upper())
            or mach_no.startswith("DA")
        )

        # 1. Read live_iw_telemetry (populated by da-setex-collector & da-batch-worker via da-db-writer)
        live_row = None
        try:
            live_row = db.execute(
                sa_text("""
                    SELECT last_updated, connection_status, batch_no, step_no, program_no, telemetry_json
                    FROM live_iw_telemetry
                    WHERE UPPER(machine_id) = :m_no
                    LIMIT 1
                """),
                {"m_no": mach_no},
            ).fetchone()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass

        telemetry_json = {}
        live_conn_status = None
        live_batch = None
        live_step = None
        live_prog = None
        live_updated = None

        if live_row:
            live_updated = live_row[0]
            live_conn_status = live_row[1]
            live_batch = live_row[2]
            live_step = live_row[3]
            live_prog = live_row[4]
            if isinstance(live_row[5], dict):
                telemetry_json = live_row[5]

        # Extract key live metrics from telemetry_json
        def _extract_tag(suffixes):
            for k, v in telemetry_json.items():
                ku = str(k).upper()
                if any(ku.endswith(suf) for suf in suffixes):
                    if isinstance(v, dict) and v.get("value") is not None:
                        try:
                            return float(v["value"])
                        except Exception:
                            pass
            return None

        iw_t1 = _extract_tag((".TEMPERATURE_PV", ".MAIN_TANK.TEMPERATURE_PV", "TEMP_PV"))
        iw_sp = _extract_tag((".TEMPERATURE_SV", ".MAIN_TANK.TEMPERATURE_SV", "TEMP_SV"))
        iw_pump = _extract_tag((".MAIN_MOTOR.SPEED_PV", ".PUMP_SPEED_PV", ".SPEED_PV"))
        iw_reel = _extract_tag((".REEL_SPEED_PV", ".WINCH_SPEED_PV"))
        iw_level = _extract_tag((".MAIN_TANK.LEVEL_PV", ".LEVEL_PV"))

        # 2. Resolve active batch_no (priority: live_iw_telemetry -> machine.current_batch -> latest cyclic record)
        batch_no = (live_batch or machine.current_batch or "").strip()
        if not batch_no or batch_no.upper() == "UNKNOWN":
            latest_cyc = (
                db.query(DatalogCyclicRecord)
                .filter(DatalogCyclicRecord.machine_no == mach_no)
                .order_by(desc(DatalogCyclicRecord.log_timestamp))
                .first()
            )
            if latest_cyc and latest_cyc.batch_ref_no:
                batch_no = latest_cyc.batch_ref_no
            else:
                batch_no = "-"

        # 3. Load BatchHeader for program_no / recipe_name
        bh = None
        if batch_no and batch_no != "-":
            bh = (
                db.query(BatchHeader)
                .filter(BatchHeader.batch_ref_no == batch_no)
                .first()
            )
            if not bh:
                bh = (
                    db.query(BatchHeader)
                    .filter(BatchHeader.machine_no == mach_no)
                    .order_by(desc(BatchHeader.created_at))
                    .first()
                )

        prog_no = 0
        if live_prog and str(live_prog).isdigit():
            prog_no = int(live_prog)
        elif bh and bh.program_no:
            prog_no = int(bh.program_no)

        program_name = (bh.recipe_name if bh and bh.recipe_name else f"Program #{prog_no}" if prog_no else "-")
        program_code = f"M_{prog_no:04d}" if prog_no > 0 else "-"

        # 4. Load cyclic curve points from DB
        curve_q = db.query(DatalogCyclicRecord).filter(DatalogCyclicRecord.machine_no == mach_no)
        if batch_no and batch_no != "-":
            curve_q = curve_q.filter(DatalogCyclicRecord.batch_ref_no == batch_no)
        curve_rows = curve_q.order_by(desc(DatalogCyclicRecord.log_timestamp)).limit(500).all()
        curve_rows.reverse()

        curve = [
            {
                "timestamp": r.log_timestamp.strftime("%Y-%m-%d %H:%M:%S") if r.log_timestamp else "",
                "temp_pv": float(r.temp_pv) if r.temp_pv is not None else 0.0,
                "temp_sp": float(r.temp_sp) if r.temp_sp is not None else None,
                "temp_pt100_t2": float(r.temp_pt100_t2) if r.temp_pt100_t2 is not None else 0.0,
                "pump_speed_percent": float(r.pump_speed_percent) if r.pump_speed_percent is not None else 0.0,
                "reel_speed_mpm": float(r.reel_speed_mpm) if r.reel_speed_mpm is not None else 0.0,
                "step_no": int(r.step_no) if r.step_no is not None else 1,
            }
            for r in curve_rows
        ]

        # 5. Load alarms & interventions from DB
        alarm_q = db.query(DatalogAlarm).filter(DatalogAlarm.machine_no == mach_no)
        if batch_no and batch_no != "-":
            batch_alarms = alarm_q.filter(DatalogAlarm.batch_ref_no == batch_no).order_by(desc(DatalogAlarm.alarm_timestamp)).limit(50).all()
        else:
            batch_alarms = []
        if not batch_alarms:
            batch_alarms = alarm_q.order_by(desc(DatalogAlarm.alarm_timestamp)).limit(30).all()

        final_alarms = [
            {
                "timestamp": a.alarm_timestamp.strftime("%Y-%m-%d %H:%M:%S") if a.alarm_timestamp else "",
                "alarm_code": a.alarm_code,
                "alarm_text": a.alarm_text,
                "step_no": a.step_no,
                "severity": a.severity or "WARNING",
                "cleared_at": a.cleared_at.strftime("%Y-%m-%d %H:%M:%S") if a.cleared_at else None,
            }
            for a in batch_alarms
        ]
        active_alarms = [a for a in final_alarms if not a.get("cleared_at")]

        interv_q = db.query(OperatorIntervention).filter(OperatorIntervention.machine_no == mach_no)
        if batch_no and batch_no != "-":
            interv_q = interv_q.filter(OperatorIntervention.batch_no == batch_no)
        intervs = interv_q.order_by(desc(OperatorIntervention.timestamp)).limit(50).all()
        active_interventions = [
            {
                "id": iv.id,
                "timestamp": iv.timestamp.strftime("%Y-%m-%d %H:%M:%S") if iv.timestamp else "",
                "step_no": iv.step_no,
                "parameter_name": iv.parameter_name,
                "old_value": float(iv.old_value) if getattr(iv, "old_value", None) is not None else None,
                "new_value": float(iv.new_value) if getattr(iv, "new_value", None) is not None else None,
                "unit": getattr(iv, "unit", "") or "",
                "trigger_source": iv.trigger_source,
            }
            for iv in intervs
        ]

        # 6. Load recipe steps from DB & enrich with cyclic telemetry timings
        recipe_steps = LogIngestionService.load_recipe_steps_from_db(db, mach_no, prog_no=prog_no, program_name=program_name)

        step_times: Dict[int, Dict[str, Any]] = {}
        for r in curve_rows:
            s_no = int(r.step_no or 1)
            ts = r.log_timestamp
            if ts is None:
                continue
            if s_no not in step_times:
                step_times[s_no] = {"start": ts, "end": ts}
            else:
                if ts < step_times[s_no]["start"]:
                    step_times[s_no]["start"] = ts
                if ts > step_times[s_no]["end"]:
                    step_times[s_no]["end"] = ts

        if not recipe_steps and step_times:
            for s_no in sorted(step_times.keys()):
                recipe_steps.append({
                    "no": s_no,
                    "func_id": s_no,
                    "name": f"Langkah Proses #{s_no}",
                    "icon": str(s_no),
                    "type": "PROCESS",
                    "comment": "",
                    "params": [],
                    "p1": "0", "p2": "0", "p3": "0",
                    "sub_steps": [],
                    "has_temp_target": True,
                })

        curr_step = int(live_step or machine.current_step or (curve[-1]["step_no"] if curve else 1))
        for st in recipe_steps:
            s_no = int(st.get("no") or 1)
            st_info = step_times.get(s_no)
            if st_info:
                st["start_time"] = st_info["start"].strftime("%Y-%m-%d %H:%M:%S")
                st["end_time"] = None if s_no == curr_step else st_info["end"].strftime("%Y-%m-%d %H:%M:%S")
                dur = max(0, int((st_info["end"] - st_info["start"]).total_seconds()))
                st["duration_seconds"] = dur
                if dur < 60:
                    st["duration_text"] = f"{dur} dtk"
                elif dur < 3600:
                    st["duration_text"] = f"{dur // 60} mnt"
                else:
                    st["duration_text"] = f"{dur // 3600} jam {(dur % 3600) // 60} mnt"
                st["time_status"] = "RUNNING" if s_no == curr_step else "ON_TRACK"
                st["delta_text"] = "Sedang Jalan" if s_no == curr_step else "✓ Selesai"

            step_pts = [p for p in curve if p.get("step_no") == s_no]
            if step_pts:
                pv_vals = [float(p["temp_pv"]) for p in step_pts if p.get("temp_pv") is not None]
                sp_vals = [float(p["temp_sp"]) for p in step_pts if p.get("temp_sp") is not None]
                st["telemetry"] = {
                    "point_count": len(step_pts),
                    "pv_start": round(pv_vals[0], 1) if pv_vals else None,
                    "pv_end": round(pv_vals[-1], 1) if pv_vals else None,
                    "pv_max": round(max(pv_vals), 1) if pv_vals else None,
                    "sp": round(sp_vals[-1], 1) if sp_vals else None,
                }

        current_temp = iw_t1
        if current_temp is None and curve:
            current_temp = curve[-1].get("temp_pv")
        if current_temp is None and machine.current_temp is not None:
            current_temp = float(machine.current_temp)

        current_sp = iw_sp
        if current_sp is None and curve:
            current_sp = curve[-1].get("temp_sp")

        iw_online = bool(live_conn_status and str(live_conn_status).upper() in ("ONLINE", "RUNNING")) or bool(telemetry_json)
        status_str = machine.status or (live_conn_status or "OFFLINE")

        return {
            "machine_no": mach_no,
            "status": status_str,
            "controller_type": "SETEX 797CE (Windows CE)" if is_797 else (machine.controller_type or "SECOM 777 (Windows CE)"),
            "controller_name": "SETEX Secom 797CE" if is_797 else "SETEX Secom 777",
            "share_folder_path": machine.share_folder_path or ("/Flashdisk/SC797CE" if is_797 else "/Storage/sc777ce"),
            "database_mode": "POSTGRES" if getattr(database, "IS_POSTGRES", False) else "SQLITE_OFFLINE",
            "is_live_hmi": iw_online,
            "data_source": "DATABASE (da-batch-worker & da-setex-collector)",
            "hmi_ip": machine.ip_address,
            "hmi_port": machine.ftp_port or 21,
            "batch_no": batch_no,
            "prog_no": prog_no,
            "program_code": program_code,
            "program_name": program_name,
            "current_step": curr_step,
            "function_code": 0,
            "current_temp": current_temp,
            "current_sp": current_sp,
            "is_alarm_active": len(active_alarms) > 0,
            "active_alarms": active_alarms[:10],
            "points_saved": 0,
            "alarms_saved": 0,
            "curve": curve,
            "alarms": final_alarms,
            "steps": recipe_steps,
            "interventions": active_interventions,
            "iw_telemetry": {"online": iw_online, "last_updated": live_updated.isoformat() if live_updated else None, "tags_count": len(telemetry_json)},
            "iw_source": iw_online and iw_t1 is not None,
            "iw_online": iw_online,
            "iw_t1_pv": iw_t1,
            "iw_pump": iw_pump,
            "iw_reel": iw_reel,
            "iw_level": iw_level,
        }
