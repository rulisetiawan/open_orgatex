"""
Logs & Telemetry Route
Handles On-The-Fly Reading and Permanent PostgreSQL Ingestion
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from ..database import get_db
from ..models.schema_pg import Machine, DatalogCyclicRecord, DatalogAlarm, BatchHeader, OperatorIntervention, BatchConsumption
from ..services.ingestion import LogIngestionService
from ..services.reader import SetexFolderReader
from ..services.setex_tcp_client import SetexTcpClient

router = APIRouter(prefix="/api/logs", tags=["Logs & Ingestion"])

@router.get("/live/{machine_no}")
def get_live_machine_telemetry(
    machine_no: str, 
    ip: Optional[str] = Query(None, description="Optional override IP HMI (e.g. 172.16.110.101)"),
    db: Session = Depends(get_db)
):
    """
    On-The-Fly Data Acquisition:
    Reads machine shared folder / HMI FTP directly, persists new telemetry permanently to PostgreSQL,
    and returns real-time curve, current temperature, and active alarm states.
    """
    mach_clean = machine_no.upper()
    is_797 = mach_clean in ("DA01", "M_95") or "797" in mach_clean or ip == "192.168.1.95"

    m = db.query(Machine).filter(Machine.machine_no == mach_clean).first()
    if not m:
        # Auto-create if not yet existing
        m = Machine(
            machine_no=mach_clean,
            display_name=f"SETEX 797CE Mesin {mach_clean}" if is_797 else f"SETEX Controller {mach_clean}",
            group_name="Dyeing Sample / DA" if is_797 else "Dyeing Section A",
            controller_type="SETEX 797CE (Windows CE)" if is_797 else "SECOM 777 (Windows CE)",
            ip_address=ip or ("192.168.1.95" if is_797 else "172.16.110.101"),
            ftp_port=21,
            share_folder_path="/Flashdisk/SC797CE" if is_797 else "/Storage/sc777ce",
            status="ONLINE"
        )
        db.add(m)
        db.commit()
        db.refresh(m)
    else:
        # Update IP and enforce 797CE if IP is 192.168.1.95 or machine is DA01/M_95
        needs_commit = False
        if is_797 or m.ip_address == "192.168.1.95":
            if m.controller_type != "SETEX 797CE (Windows CE)":
                m.controller_type = "SETEX 797CE (Windows CE)"
                needs_commit = True
            if not m.share_folder_path or "/Storage" in m.share_folder_path or "/app/STATUS" in m.share_folder_path:
                m.share_folder_path = "/Flashdisk/SC797CE"
                needs_commit = True
            if not m.display_name or "777" in m.display_name or m.display_name.startswith("SETEX Controller"):
                m.display_name = f"SETEX 797CE Mesin {mach_clean}"
                needs_commit = True
            if ip and m.ip_address != ip:
                m.ip_address = ip
                needs_commit = True
        else:
            if ip and m.ip_address != ip:
                m.ip_address = ip
                needs_commit = True
            elif m.ip_address in ("192.168.1.102", "127.0.0.1", "", None):
                m.ip_address = "172.16.110.101"
                m.ftp_port = 21
                needs_commit = True

        if needs_commit:
            db.commit()
            db.refresh(m)

    res = LogIngestionService.ingest_machine_on_the_fly(db, m)
    return res

@router.post("/sync/{machine_no}")
def sync_all_logs(machine_no: str, db: Session = Depends(get_db)):
    """
    Triggers complete scan and permanent synchronization of all historical logs
    and alarms from shared directory into PostgreSQL.
    """
    m = db.query(Machine).filter(Machine.machine_no == machine_no.upper()).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mesin tidak ditemukan")

    res = LogIngestionService.ingest_machine_on_the_fly(db, m)
    return {
        "status": "sync_completed",
        "machine_no": m.machine_no,
        "new_points_persisted": res.get("new_points_persisted", 0),
        "new_alarms_persisted": res.get("new_alarms_persisted", 0),
        "total_points_in_session": res.get("total_points", 0),
        "storage": "PostgreSQL (orgatex.datalog_cyclic_records)"
    }

@router.get("/history/{machine_no}")
def get_historical_telemetry(
    machine_no: str, 
    batch_no: Optional[str] = None,
    limit: int = Query(default=500, le=2000),
    db: Session = Depends(get_db)
):
    """
    Queries permanently stored telemetry curves from PostgreSQL.
    """
    query = db.query(DatalogCyclicRecord).filter(
        DatalogCyclicRecord.machine_no == machine_no.upper()
    )

    if batch_no:
        query = query.filter(DatalogCyclicRecord.batch_ref_no == batch_no)

    records = query.order_by(DatalogCyclicRecord.log_timestamp.asc()).limit(limit).all()

    return {
        "machine_no": machine_no.upper(),
        "total_records": len(records),
        "records": [
            {
                "timestamp": r.log_timestamp.strftime("%Y-%m-%d %H:%M:%S") if r.log_timestamp else "",
                "batch_no": r.batch_ref_no,
                "temp_pv": float(r.temp_pv) if r.temp_pv else 0.0,
                "temp_sp": float(r.temp_sp) if r.temp_sp else 0.0,
                "temp_pt100_t2": float(r.temp_pt100_t2) if r.temp_pt100_t2 else 0.0,
                "pump_speed_percent": float(r.pump_speed_percent) if r.pump_speed_percent else 0.0,
                "reel_speed_mpm": float(r.reel_speed_mpm) if r.reel_speed_mpm else 0.0,
                "step_no": r.step_no
            }
            for r in records
        ]
    }

@router.get("/batch-history")
def get_batch_history(
    machine_no: Optional[str] = Query(None, description="Filter kode mesin (misal: 1A, DA01, SEMUA)"),
    search: Optional[str] = Query(None, description="Pencarian nomor lot, resep, customer, artikel"),
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db)
):
    """
    Mengambil daftar batch yang sudah dikerjakan (riwayat batch)
    beserta statistik durasi, titik telemetri, suhu puncak, dan alarm.
    """
    # 1. Agregasi cyclic records per (batch_ref_no, machine_no)
    q = db.query(
        DatalogCyclicRecord.batch_ref_no,
        DatalogCyclicRecord.machine_no,
        func.min(DatalogCyclicRecord.log_timestamp).label("start_time"),
        func.max(DatalogCyclicRecord.log_timestamp).label("end_time"),
        func.count(DatalogCyclicRecord.log_timestamp).label("total_points"),
        func.max(DatalogCyclicRecord.temp_pv).label("max_temp")
    )
    if machine_no and machine_no.upper() not in ("SEMUA", "ALL", ""):
        q = q.filter(DatalogCyclicRecord.machine_no == machine_no.upper())
    
    q = q.group_by(DatalogCyclicRecord.batch_ref_no, DatalogCyclicRecord.machine_no)
    q = q.order_by(desc("end_time")).limit(limit)
    rows = q.all()

    # Pre-fetch BatchHeaders to avoid N+1 queries
    all_ref_nos = list({r.batch_ref_no for r in rows if r.batch_ref_no})
    b_headers = {}
    if all_ref_nos:
        bh_list = db.query(BatchHeader).filter(BatchHeader.batch_ref_no.in_(all_ref_nos)).all()
        for bh in bh_list:
            b_headers[bh.batch_ref_no] = bh

    # Pre-fetch Machines
    mach_dict = {m.machine_no: m for m in db.query(Machine).all()}

    results = []
    search_clean = (search or "").strip().lower()

    for r in rows:
        ref_no = r.batch_ref_no
        mach_no = r.machine_no
        bh = b_headers.get(ref_no)
        m_obj = mach_dict.get(mach_no)

        batch_display = bh.batch_no if bh and bh.batch_no else f"LOT-{ref_no}"
        recipe_name = bh.recipe_name if bh and bh.recipe_name else "Reactive Dyeing Standard"
        customer = bh.customer if bh and bh.customer else "PT. SMM JETFLOW"
        article = bh.article if bh and bh.article else "-"
        color_code = bh.color_code if bh and bh.color_code else "-"
        color_name = bh.color_name if bh and bh.color_name else "-"
        weight = float(bh.fabric_weight_kg) if bh and bh.fabric_weight_kg is not None else 350.0

        # Filter pencarian
        if search_clean:
            match_str = f"{batch_display} {ref_no} {mach_no} {recipe_name} {customer} {article} {color_name}".lower()
            if search_clean not in match_str:
                continue

        start_dt = r.start_time
        end_dt = r.end_time
        duration_sec = int((end_dt - start_dt).total_seconds()) if (start_dt and end_dt) else 0
        if duration_sec < 60:
            duration_text = f"{duration_sec} dtk"
        elif duration_sec < 3600:
            duration_text = f"{duration_sec // 60} mnt"
        else:
            duration_text = f"{duration_sec // 3600} jam {(duration_sec % 3600) // 60} mnt"

        results.append({
            "batch_ref_no": ref_no,
            "batch_no": batch_display,
            "machine_no": mach_no,
            "machine_name": m_obj.display_name if m_obj else f"Mesin {mach_no}",
            "recipe_name": recipe_name,
            "program_no": bh.program_no if bh and bh.program_no else 1,
            "program_code": f"M_{bh.program_no:04d}" if bh and bh.program_no else "M_0004",
            "customer": customer,
            "article": article,
            "color_code": color_code,
            "color_name": color_name,
            "fabric_weight_kg": weight,
            "start_time": start_dt.strftime("%Y-%m-%d %H:%M:%S") if start_dt else "-",
            "end_time": end_dt.strftime("%Y-%m-%d %H:%M:%S") if end_dt else "-",
            "date": end_dt.strftime("%Y-%m-%d") if end_dt else "-",
            "duration_seconds": duration_sec,
            "duration_text": duration_text,
            "total_points": r.total_points or 0,
            "max_temp": float(r.max_temp) if r.max_temp is not None else 0.0,
            "status": "COMPLETED"
        })

    return {
        "total": len(results),
        "batches": results
    }

@router.get("/batch-detail/{machine_no}/{batch_ref_no}")
def get_batch_history_detail(
    machine_no: str,
    batch_ref_no: str,
    db: Session = Depends(get_db)
):
    """
    Mengambil data detail lengkap batch yang sudah dikerjakan (riwayat),
    menghasilkan format data yang identik dengan /api/logs/live/ (active batch):
    - Curve telemetri lengkap (PV, SP, T2)
    - Timeline resep program beserta durasi aktual setiap langkah
    - Daftar alarm & intervensi operator
    """
    mach_clean = machine_no.upper()
    ref_clean = batch_ref_no.strip()

    m_obj = db.query(Machine).filter(Machine.machine_no == mach_clean).first()
    bh = db.query(BatchHeader).filter(BatchHeader.batch_ref_no == ref_clean).first()

    # Ambil kurva telemetri dari database
    records = db.query(DatalogCyclicRecord).filter(
        DatalogCyclicRecord.machine_no == mach_clean,
        DatalogCyclicRecord.batch_ref_no == ref_clean
    ).order_by(DatalogCyclicRecord.log_timestamp.asc()).all()

    if not records:
        # Fallback jika record dicatat tanpa filter machine_no tertentu
        records = db.query(DatalogCyclicRecord).filter(
            DatalogCyclicRecord.batch_ref_no == ref_clean
        ).order_by(DatalogCyclicRecord.log_timestamp.asc()).all()

    curve = [
        {
            "timestamp": r.log_timestamp.strftime("%Y-%m-%d %H:%M:%S") if r.log_timestamp else "",
            "temp_pv": float(r.temp_pv) if r.temp_pv is not None else 0.0,
            "temp_sp": float(r.temp_sp) if r.temp_sp is not None else 0.0,
            "temp_pt100_t2": float(r.temp_pt100_t2) if r.temp_pt100_t2 is not None else 0.0,
            "pump_speed_percent": float(r.pump_speed_percent) if r.pump_speed_percent is not None else 0.0,
            "reel_speed_mpm": float(r.reel_speed_mpm) if r.reel_speed_mpm is not None else 0.0,
            "step_no": r.step_no or 1
        }
        for r in records
    ]

    # Hitung waktu per step dari data telemetri
    step_times = {}
    for r in records:
        s_no = r.step_no or 1
        ts = r.log_timestamp
        if s_no not in step_times:
            step_times[s_no] = {"start": ts, "end": ts}
        else:
            if ts < step_times[s_no]["start"]:
                step_times[s_no]["start"] = ts
            if ts > step_times[s_no]["end"]:
                step_times[s_no]["end"] = ts

    # Ambil langkah resep program
    recipe_steps = []
    try:
        recipe_steps = SetexFolderReader.get_recipe_steps(
            batch_no=ref_clean,
            prog_no=bh.program_no if bh else None
        )
    except Exception:
        pass

    # Jika recipe_steps kosong, generate dari step_times yang ada di telemetri
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
                "sub_steps": []
            })

    # Perkualitasi info langkah resep dengan timing aktual
    max_step = max(step_times.keys()) if step_times else len(recipe_steps)
    for st in recipe_steps:
        s_no = st.get("no", 1)
        st_info = step_times.get(s_no)
        if st_info:
            s_start = st_info["start"]
            s_end = st_info["end"]
            st["start_time"] = s_start.strftime("%Y-%m-%d %H:%M:%S")
            st["end_time"] = s_end.strftime("%Y-%m-%d %H:%M:%S")
            dur = max(0, int((s_end - s_start).total_seconds()))
            st["duration_seconds"] = dur
            if dur < 60:
                st["duration_text"] = f"{dur} dtk"
            elif dur < 3600:
                st["duration_text"] = f"{dur // 60} mnt"
            else:
                st["duration_text"] = f"{dur // 3600} jam {(dur % 3600) // 60} mnt"
            st["time_status"] = "ON_TRACK"
            st["delta_text"] = "✓ Selesai"
        else:
            st["time_status"] = "ON_TRACK"
            st["delta_text"] = "✓ Selesai"

        # Attach telemetry data and determine if this step has temperature setpoint
        step_pts = [p for p in curve if p.get("step_no") == s_no]
        if step_pts:
            pv_vals = [float(p["temp_pv"]) for p in step_pts if p.get("temp_pv") is not None]
            sp_vals = [float(p["temp_sp"]) for p in step_pts if p.get("temp_sp") is not None]
            t2_vals = [float(p["temp_pt100_t2"]) for p in step_pts if p.get("temp_pt100_t2") is not None]
            pump_vals = [float(p["pump_speed_percent"]) for p in step_pts if p.get("pump_speed_percent") is not None]
            reel_vals = [float(p["reel_speed_mpm"]) for p in step_pts if p.get("reel_speed_mpm") is not None]

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

    # Ambil alarm untuk batch ini
    alarms_db = db.query(DatalogAlarm).filter(
        DatalogAlarm.batch_ref_no == ref_clean
    ).order_by(DatalogAlarm.alarm_timestamp.asc()).all()

    formatted_alarms = [
        {
            "id": a.id,
            "timestamp": a.alarm_timestamp.strftime("%Y-%m-%d %H:%M:%S") if a.alarm_timestamp else "",
            "date": a.alarm_timestamp.strftime("%Y-%m-%d") if a.alarm_timestamp else "",
            "time": a.alarm_timestamp.strftime("%H:%M:%S") if a.alarm_timestamp else "",
            "alarm_code": a.alarm_code,
            "alarm_text": a.alarm_text,
            "severity": a.severity or "WARNING",
            "step_no": a.step_no,
            "batch_no": a.batch_ref_no,
            "is_intervention": str(a.alarm_code) in ("0", "20", "256", "5899"),
            "category": "INTERVENTION" if str(a.alarm_code) in ("0", "20", "256", "5899") else "ALARM"
        }
        for a in alarms_db
    ]

    # Ambil intervensi untuk batch ini
    interventions_db = db.query(OperatorIntervention).filter(
        OperatorIntervention.batch_no == ref_clean
    ).order_by(OperatorIntervention.timestamp.asc()).all()

    formatted_interventions = [
        {
            "id": i.id,
            "timestamp": i.timestamp.strftime("%Y-%m-%d %H:%M:%S") if i.timestamp else "",
            "batch_no": i.batch_no,
            "step_no": i.step_no,
            "parameter_name": i.parameter_name,
            "unit": i.unit,
            "value_before": float(i.value_before) if i.value_before else 0.0,
            "value_after": float(i.value_after) if i.value_after else 0.0,
            "delta": float(i.delta) if i.delta else 0.0,
            "notes": i.notes
        }
        for i in interventions_db
    ]

    last_pv = curve[-1]["temp_pv"] if curve else 0.0
    last_sp = curve[-1]["temp_sp"] if curve else 0.0
    start_str = curve[0]["timestamp"] if curve else "-"
    end_str = curve[-1]["timestamp"] if curve else "-"

    # Ambil data konsumsi utilitas batch (Object 1035) jika ada
    consumption_db = db.query(BatchConsumption).filter(
        BatchConsumption.batch_ref_no == ref_clean
    ).order_by(desc(BatchConsumption.recorded_at)).first()

    consumption_data = {
        "water_liters": float(consumption_db.water_liters) if consumption_db and consumption_db.water_liters is not None else 0.0,
        "power_kwh": float(consumption_db.power_kwh) if consumption_db and consumption_db.power_kwh is not None else 0.0,
        "steam_kg": float(consumption_db.steam_kg) if consumption_db and consumption_db.steam_kg is not None else 0.0,
        "runtime_minutes": float(consumption_db.runtime_minutes) if consumption_db and consumption_db.runtime_minutes is not None else 0.0
    } if consumption_db else None

    batch_display = bh.batch_no if bh and bh.batch_no else f"LOT-{ref_clean}"
    recipe_display = bh.recipe_name if bh and bh.recipe_name else "Reactive Dyeing Standard"

    is_797 = mach_clean in ("DA01", "M_95") or "797" in mach_clean

    return {
        "machine_no": mach_clean,
        "batch_no": batch_display,
        "batch_ref_no": ref_clean,
        "status": "COMPLETED",
        "controller_type": "SETEX 797CE (Windows CE)" if is_797 else (m_obj.controller_type if m_obj else "SECOM 777 (Windows CE)"),
        "controller_name": "SETEX Secom 797CE" if is_797 else "SETEX Secom 777",
        "database_mode": "POSTGRES",
        "is_live_hmi": False,
        "is_archive": True,
        "prog_no": bh.program_no if bh and bh.program_no else 1,
        "program_code": f"M_{bh.program_no:04d}" if bh and bh.program_no else "M_0004",
        "program_name": recipe_display,
        "recipe_name": recipe_display,
        "customer": bh.customer if bh and bh.customer else "PT. SMM JETFLOW",
        "article": bh.article if bh and bh.article else "-",
        "color_code": bh.color_code if bh and bh.color_code else "-",
        "color_name": bh.color_name if bh and bh.color_name else "-",
        "fabric_weight_kg": float(bh.fabric_weight_kg) if bh and bh.fabric_weight_kg is not None else 350.0,
        "current_step": max_step,
        "current_temp": last_pv,
        "current_sp": last_sp,
        "start_time": start_str,
        "end_time": end_str,
        "is_alarm_active": False,
        "total_points": len(curve),
        "curve": curve,
        "steps": recipe_steps,
        "alarms": formatted_alarms,
        "interventions": formatted_interventions,
        "consumption": consumption_data
    }

@router.get("/alarms/{machine_no}")
def get_stored_alarms(
    machine_no: str,
    date: Optional[str] = Query(None, description="Filter tanggal spesifik (format: YYYY-MM-DD)"),
    start_date: Optional[str] = Query(None, description="Filter rentang awal tanggal (format: YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Filter rentang akhir tanggal (format: YYYY-MM-DD)"),
    order_by: str = Query("datetime", description="Kolom sorting: 'datetime' / 'alarm_timestamp'"),
    order: str = Query("desc", description="Arah urutan: 'desc' (terbaru) atau 'asc' (terlama)"),
    category: Optional[str] = Query(None, description="Filter kategori: 'ALL', 'ALARM', atau 'INTERVENTION'"),
    limit: int = Query(default=200, le=2000),
    db: Session = Depends(get_db)
):
    """
    Mengambil data riwayat alarm & intervensi operator HMI berdasarkan tanggal,
    diurutkan strictly dengan ORDER BY date time (DatalogAlarm.alarm_timestamp).
    """
    m_no = machine_no.upper()
    query = db.query(DatalogAlarm).filter(DatalogAlarm.machine_no == m_no)

    # Filter berdasarkan tanggal spesifik (YYYY-MM-DD)
    if isinstance(date, str) and date.strip():
        try:
            d_str = date.strip()
            d_start = datetime.strptime(f"{d_str} 00:00:00", "%Y-%m-%d %H:%M:%S")
            d_end = datetime.strptime(f"{d_str} 23:59:59", "%Y-%m-%d %H:%M:%S")
            query = query.filter(DatalogAlarm.alarm_timestamp >= d_start, DatalogAlarm.alarm_timestamp <= d_end)
        except ValueError:
            pass

    # Filter rentang tanggal awal
    if isinstance(start_date, str) and start_date.strip():
        try:
            s_dt = datetime.strptime(f"{start_date.strip()} 00:00:00", "%Y-%m-%d %H:%M:%S")
            query = query.filter(DatalogAlarm.alarm_timestamp >= s_dt)
        except ValueError:
            pass

    # Filter rentang tanggal akhir
    if isinstance(end_date, str) and end_date.strip():
        try:
            e_dt = datetime.strptime(f"{end_date.strip()} 23:59:59", "%Y-%m-%d %H:%M:%S")
            query = query.filter(DatalogAlarm.alarm_timestamp <= e_dt)
        except ValueError:
            pass

    # ORDER BY Date Time (DatalogAlarm.alarm_timestamp)
    is_asc = isinstance(order, str) and order.strip().lower() == "asc"
    if is_asc:
        query = query.order_by(DatalogAlarm.alarm_timestamp.asc(), DatalogAlarm.id.asc())
    else:
        query = query.order_by(DatalogAlarm.alarm_timestamp.desc(), DatalogAlarm.id.desc())

    limit_val = limit if isinstance(limit, int) else 200
    alarms = query.limit(limit_val).all()

    INTERVENTION_CODES = {"0", "20", "256", "5899"}
    INTERVENTION_KEYWORDS = ("OPERATOR", "INTERVENSI", "INTERVENTION", "CONFIRMATION", "CALL-OFF", "HOLD", "PAUSE", "MANUAL", "CLEARED")

    formatted = []
    for a in alarms:
        code_str = str(a.alarm_code)
        text_upper = (a.alarm_text or "").upper()
        is_intervention = code_str in INTERVENTION_CODES or any(k in text_upper for k in INTERVENTION_KEYWORDS)
        cat = "INTERVENTION" if is_intervention else "ALARM"

        if isinstance(category, str) and category.upper() not in ("ALL", "") and category.upper() != cat:
            continue

        formatted.append({
            "id": a.id,
            "timestamp": a.alarm_timestamp.strftime("%Y-%m-%d %H:%M:%S") if a.alarm_timestamp else "",
            "date": a.alarm_timestamp.strftime("%Y-%m-%d") if a.alarm_timestamp else "",
            "time": a.alarm_timestamp.strftime("%H:%M:%S") if a.alarm_timestamp else "",
            "alarm_code": a.alarm_code,
            "alarm_text": a.alarm_text,
            "severity": a.severity or ("INFO" if a.alarm_code == "0" else "WARNING"),
            "step_no": a.step_no,
            "batch_no": a.batch_ref_no,
            "is_intervention": is_intervention,
            "category": cat,
            "cleared_at": a.cleared_at.strftime("%Y-%m-%d %H:%M:%S") if a.cleared_at else None
        })

    # Available distinct dates for this machine to ease navigation
    date_rows = db.query(DatalogAlarm.alarm_timestamp).filter(
        DatalogAlarm.machine_no == m_no
    ).all()
    available_dates = sorted(list({r[0].strftime("%Y-%m-%d") for r in date_rows if r[0]}), reverse=True)

    return {
        "machine_no": m_no,
        "filter_date": date,
        "order_by": "datetime",
        "order": "asc" if is_asc else "desc",
        "total_alarms": len(formatted),
        "available_dates": available_dates,
        "alarms": formatted
    }

@router.get("/parse")
def parse_direct_log_file(filepath: str):
    """Direct read-only parser for arbitrary log file paths."""
    pts = SetexFolderReader.read_cyclic_log_file(filepath)
    return {"total_records": len(pts), "records": pts}

@router.get("/interventions/{machine_no}")
def get_recorded_interventions(
    machine_no: str,
    batch_no: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db)
):
    """
    Mengambil data riwayat modifikasi parameter & intervensi operator
    dari database PostgreSQL (tabel operator_interventions).
    """
    m_no = machine_no.upper()
    query = db.query(OperatorIntervention).filter(OperatorIntervention.machine_no == m_no)
    if batch_no:
        query = query.filter(OperatorIntervention.batch_no == batch_no)

    records = query.order_by(desc(OperatorIntervention.timestamp)).limit(limit).all()

    return {
        "machine_no": m_no,
        "total_records": len(records),
        "interventions": [
            {
                "id": r.id,
                "timestamp": r.timestamp.strftime("%Y-%m-%d %H:%M:%S") if r.timestamp else "",
                "batch_no": r.batch_no,
                "step_no": r.step_no,
                "parameter_name": r.parameter_name,
                "unit": r.unit,
                "value_before": float(r.value_before) if r.value_before else 0.0,
                "value_after": float(r.value_after) if r.value_after else 0.0,
                "delta": float(r.delta) if r.delta else 0.0,
                "notes": r.notes
            }
            for r in records
        ]
    }

@router.get("/iw/{machine_no}")
def get_live_machine_iw(
    machine_no: str,
    ip: Optional[str] = Query(None, description="Optional override IP"),
    count: int = Query(default=200, le=240, description="Jumlah register IW (1..240)"),
    all_objects: bool = Query(default=True, description="Ambil seluruh objek kontroler (1025 IW, 1009 SET, 1010 ACT, 1035 BATCH, Objek 6 FUNCTION)"),
    db: Session = Depends(get_db)
):
    """
    Mengambil data live register IW (Info Words / Objek 1025) serta seluruh objek kontroler
    (SET 1009, ACT 1010, BATCH 1035, FUNCTION 6) langsung dari Controller SETEX via TCP Port 50000.
    """
    mach_clean = machine_no.upper()
    m = db.query(Machine).filter(Machine.machine_no == mach_clean).first()
    host = ip or (m.ip_address if m else "172.16.110.101")
    port = (m.tcp_port if m and m.tcp_port else 50000)

    if all_objects:
        complete_data = SetexTcpClient.read_all_objects_snapshot(host, port, machine_no=mach_clean, timeout=2.5)
        return {
            "status": "success" if complete_data.get("online") else "error",
            "machine_no": mach_clean,
            "controller_ip": host,
            "controller_port": port,
            **complete_data
        }

    iw_data = SetexTcpClient.read_iw_telemetry(host, port, count=count, machine_no=mach_clean, timeout=2.5)
    return {
        "status": "success" if iw_data.get("online") else "error",
        "machine_no": mach_clean,
        "controller_ip": host,
        "controller_port": port,
        **iw_data
    }
