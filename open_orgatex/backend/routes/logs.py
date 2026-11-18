"""
Logs & Telemetry Route
Handles On-The-Fly Reading and Permanent PostgreSQL Ingestion
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..database import get_db
from ..models.schema_pg import Machine, DatalogCyclicRecord, DatalogAlarm, BatchHeader, OperatorIntervention
from ..services.ingestion import LogIngestionService
from ..services.reader import SetexFolderReader

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
