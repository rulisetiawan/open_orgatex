"""
OpenOrgaTEX - Setpoints & Operator Intervention Audit Route
Provides:
- Live Setpoint & Info Word (IW) Acquisition from Port 50000
- Operator Intervention History (Before vs After comparisons)
- Message Broker Event Triggering
- Scaffolded Safe Setpoint Writing
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel

from ..database import get_db
from ..models.schema_pg import Machine, OperatorIntervention, BatchConsumption
from ..services.setex_tcp_client import SetexTcpClient
from ..services.intervention_service import InterventionService
from ..services.event_broker import broker

router = APIRouter(prefix="/api/setpoints", tags=["Setpoints & Interventions"])

class SetpointWriteRequest(BaseModel):
    obj: int = 1009  # 1009 = SET/SOLL, 1025 = IW, 1001 = LW
    address: int
    value: int
    parameter_name: Optional[str] = "Custom Setpoint"

class TriggerInterventionRequest(BaseModel):
    trigger_source: Optional[str] = "MANUAL_WEB_TRIGGER"
    alarm_code: Optional[int] = 256
    notes: Optional[str] = "Manual operator intervention test trigger"

class ParameterChangeRequest(BaseModel):
    param_id: int = 3  # Misal: 3 = Suhu (°C), 4 = Gradien (°C/min), 5 = Waktu (min)
    value: float
    parameter_name: Optional[str] = "Temperature MA"

# =============================================================================
# 1. Static Routes (Must be declared before dynamic /{machine_no} routes)
# =============================================================================

@router.get("/broker/diagnostics")
def get_broker_diagnostics():
    """
    Inspects message broker state, queue size, and recent message traffic.
    """
    stats = broker.get_stats()
    history = broker.get_history(limit=25)
    return {
        "broker_stats": stats,
        "recent_messages": history
    }

# =============================================================================
# 2. Dynamic Machine Routes
# =============================================================================

@router.get("/{machine_no}")
def get_live_setpoints(
    machine_no: str,
    ip: Optional[str] = Query(None, description="Optional override IP"),
    all_objects: bool = Query(False, description="Baca seluruh objek controller (SET 1009, ACT 1010, IW 1025, BATCH 1035, FUNC 6)"),
    db: Session = Depends(get_db)
):
    """
    Reads live Setpoint (Object 1009 / SET), Info Words (Object 1025 / IW),
    and active Function 141 (Temperature/Time) parameters directly from SETEX Controller TCP Port 50000.
    """
    m = db.query(Machine).filter(Machine.machine_no == machine_no.upper()).first()
    host = ip or (m.ip_address if m else "172.16.110.101")
    port = (m.tcp_port if m and m.tcp_port else 50000)

    if all_objects:
        complete_data = SetexTcpClient.read_all_objects_snapshot(host, port, machine_no.upper())
        return {
            "status": "success" if complete_data.get("online") else "error",
            "machine_no": machine_no.upper(),
            "controller_ip": host,
            "controller_port": port,
            **complete_data
        }

    # Acquire snapshot from controller
    snapshot = SetexTcpClient.read_setpoints_snapshot(host, port, machine_no.upper())

    # Return baseline comparison if available
    baseline = InterventionService.get_baseline(machine_no.upper())

    return {
        "status": "success",
        "machine_no": machine_no.upper(),
        "controller_ip": host,
        "controller_port": port,
        "is_online": snapshot.get("online", False),
        "setpoints": snapshot.get("setpoints", {}),
        "active_function": snapshot.get("active_function"),
        "info_words": snapshot.get("info_words", {}),
        "baseline_comparison": baseline,
        "error": snapshot.get("error")
    }

@router.get("/{machine_no}/all-objects")
def get_all_objects_telemetry(
    machine_no: str,
    ip: Optional[str] = Query(None, description="Optional override IP"),
    db: Session = Depends(get_db)
):
    """
    Mengambil data LENGKAP seluruh objek dari Kontroler SETEX (TCP Port 50000):
    - Objek 1009: SET (Seluruh Setpoint SOLL dari Parameter Kategori 2)
    - Objek 1010: ACT (Nilai Feedback Loop Aktual IST)
    - Objek 1025: IW (Telemetri Sensor Proses Kategori 10)
    - Objek 1035: BATCH (Akumulasi Konsumsi Air & Energi DWORD)
    - Objek 6: FUNCTION (Resep Langkah Proses Celup yang sedang aktif)
    """
    m = db.query(Machine).filter(Machine.machine_no == machine_no.upper()).first()
    host = ip or (m.ip_address if m else "172.16.110.101")
    port = (m.tcp_port if m and m.tcp_port else 50000)

    res = SetexTcpClient.read_all_objects_snapshot(host, port, machine_no.upper())
    return {
        "status": "success" if res.get("online") else "error",
        "machine_no": machine_no.upper(),
        "controller_ip": host,
        "controller_port": port,
        **res
    }

@router.get("/{machine_no}/interventions")
def get_intervention_history(
    machine_no: str,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """
    Retrieves the chronological audit log of all operator interventions,
    highlighting which parameter was modified, the value before, the value after, and the delta.
    """
    lim = limit if isinstance(limit, int) else getattr(limit, "default", 50)
    records = db.query(OperatorIntervention).filter(
        OperatorIntervention.machine_no == machine_no.upper()
    ).order_by(desc(OperatorIntervention.timestamp)).limit(lim).all()

    return {
        "machine_no": machine_no.upper(),
        "total_interventions": len(records),
        "interventions": [
            {
                "id": r.id,
                "timestamp": r.timestamp.strftime("%Y-%m-%d %H:%M:%S") if r.timestamp else "",
                "batch_no": r.batch_no,
                "step_no": r.step_no,
                "trigger_source": r.trigger_source,
                "alarm_code": r.alarm_code,
                "function_id": r.function_id,
                "parameter_name": r.parameter_name,
                "unit": r.unit,
                "value_before": float(r.value_before) if r.value_before is not None else None,
                "value_after": float(r.value_after) if r.value_after is not None else None,
                "delta": float(r.delta) if r.delta is not None else None,
                "notes": r.notes
            }
            for r in records
        ]
    }

@router.post("/{machine_no}/trigger-intervention-check")
def trigger_intervention_check(
    machine_no: str,
    payload: TriggerInterventionRequest = Body(...),
    db: Session = Depends(get_db)
):
    """
    Sends an event into the Message Broker (topic: 'machine.intervention').
    The background listener picks it up immediately, queries the controller,
    and checks if any setpoints have deviated from baseline.
    """
    # Publish message to broker
    broker.publish_sync("machine.intervention", {
        "machine_no": machine_no.upper(),
        "trigger_source": payload.trigger_source,
        "alarm_code": payload.alarm_code,
        "notes": payload.notes,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    })

    # Also evaluate directly for immediate HTTP feedback
    changes = InterventionService.evaluate_and_record(
        machine_no=machine_no.upper(),
        trigger_source=payload.trigger_source,
        alarm_code=payload.alarm_code,
        notes=payload.notes
    )

    return {
        "status": "event_published_to_broker",
        "topic": "machine.intervention",
        "machine_no": machine_no.upper(),
        "detected_changes": changes,
        "changes_count": len(changes)
    }

@router.get("/{machine_no}/consumption")
def get_batch_consumption(
    machine_no: str,
    ip: Optional[str] = Query(None, description="Optional override IP"),
    db: Session = Depends(get_db)
):
    """
    Tahap 1: Membaca Counter Konsumsi Utilitas Batch (Object 1035 - 32-bit DWORD)
    melalui TCP Port 50000. Data mencakup akumulasi konsumsi air (L), uap/steam,
    listrik (kWh), dan waktu operasi mesin per batch.
    """
    m = db.query(Machine).filter(Machine.machine_no == machine_no.upper()).first()
    host = ip or (m.ip_address if m else "172.16.110.101")
    port = (m.tcp_port if m and m.tcp_port else 50000)

    try:
        counters = SetexTcpClient.read_batch_consumption(host, port, start_index=1, count=10, timeout=3.0)
        metrics = {
            "water_liters": float(counters[0]) if len(counters) > 0 else 0.0,
            "power_kwh": round(float(counters[1]) / 10.0, 1) if len(counters) > 1 else 0.0,
            "steam_kg": float(counters[2]) if len(counters) > 2 else 0.0,
            "runtime_minutes": float(counters[3]) if len(counters) > 3 else 0.0,
        }

        # Simpan ke tabel batch_consumptions di database PostgreSQL / SQLite
        try:
            curr_b = m.current_batch if m and m.current_batch else "CURRENT"
            bc = BatchConsumption(
                machine_no=machine_no.upper(),
                batch_ref_no=curr_b,
                water_liters=metrics["water_liters"],
                power_kwh=metrics["power_kwh"],
                steam_kg=metrics["steam_kg"],
                runtime_minutes=metrics["runtime_minutes"],
                raw_counters=json.dumps(counters)
            )
            db.add(bc)
            db.commit()
        except Exception as dbe:
            db.rollback()

        return {
            "status": "success",
            "machine_no": machine_no.upper(),
            "controller_ip": host,
            "raw_counters": counters,
            "metrics": metrics
        }
    except Exception as e:
        return {
            "status": "offline_or_unsupported",
            "machine_no": machine_no.upper(),
            "controller_ip": host,
            "message": f"Tidak dapat membaca counter konsumsi Object 1035 dari {host}:{port}: {str(e)}",
            "raw_counters": [],
            "metrics": {
                "water_liters": 0,
                "power_kwh": 0.0,
                "steam_kg": 0,
                "runtime_minutes": 0,
            }
        }

@router.post("/{machine_no}/change-parameter")
def change_parameter_da01(
    machine_no: str,
    req: ParameterChangeRequest,
    db: Session = Depends(get_db)
):
    """
    Tahap 2: Pengaturan Parameter Jarak Jauh (Remote Intervent) via Service 137 / Object 41.
    
    RESTRIKSI KESELAMATAN KETAT:
    HANYA diizinkan untuk mesin pilot 'DA01'. Mesin produksi lainnya terkunci dalam mode Read-Only.
    """
    clean_mach = machine_no.strip().upper()
    if clean_mach != "DA01":
        raise HTTPException(
            status_code=403,
            detail=f"Akses Ditolak: Pengaturan parameter via web HANYA diizinkan untuk mesin uji pilot 'DA01'. "
                   f"Mesin '{clean_mach}' terkunci dalam mode Aman / Read-Only demi keselamatan produksi tekstil."
        )

    m = db.query(Machine).filter(Machine.machine_no == "DA01").first()
    host = m.ip_address if m else "192.168.1.95"
    port = m.tcp_port if (m and m.tcp_port) else 50000

    try:
        result = SetexTcpClient.change_parameter_da01_only(
            machine_no="DA01",
            host=host,
            port=port,
            param_id=req.param_id,
            value=req.value,
            parameter_name=req.parameter_name
        )

        # Catat intervensi ke database permanent audit log
        inv = OperatorIntervention(
            machine_no="DA01",
            batch_no=m.current_batch if m else "UNKNOWN",
            step_no=m.current_step if m else 1,
            trigger_source="WEB_REMOTE_DA01",
            function_id=141 if req.param_id in (3, 4, 5) else req.param_id,
            parameter_name=req.parameter_name or f"Param {req.param_id}",
            unit="°C" if req.param_id == 3 else ("°C/min" if req.param_id == 4 else ("min" if req.param_id == 5 else "")),
            value_before=0.0,
            value_after=float(req.value),
            delta=0.0,
            notes=f"Pengaturan Jarak Jauh Web (DA01): {req.parameter_name or req.param_id} diubah menjadi {req.value}"
        )
        db.add(inv)
        db.commit()

        return result
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengirim perubahan parameter ke mesin DA01: {str(e)}")

@router.post("/{machine_no}/write")
def write_setpoint(
    machine_no: str,
    req: SetpointWriteRequest,
    db: Session = Depends(get_db)
):
    """
    Scaffolded Setpoint Write Endpoint.
    Uses Service 2 (SV_WRITE) on Controller TCP Port 50000.
    Enforces OpenOrgaTEX safety policy: HANYA MESIN DA01.
    """
    clean_mach = machine_no.strip().upper()
    if clean_mach != "DA01":
        raise HTTPException(
            status_code=403,
            detail=f"Akses Ditolak: Penulisan langsung register ke kontroler HANYA diizinkan untuk mesin pilot 'DA01'."
        )

    m = db.query(Machine).filter(Machine.machine_no == "DA01").first()
    host = m.ip_address if m else "192.168.1.95"
    port = m.tcp_port if (m and m.tcp_port) else 50000

    result = SetexTcpClient.write_setpoint(
        host=host,
        port=port,
        obj=req.obj,
        address=req.address,
        value=req.value
    )
    return result
