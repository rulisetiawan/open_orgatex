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
from ..models.schema_pg import Machine, OperatorIntervention
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
    db: Session = Depends(get_db)
):
    """
    Reads live Setpoint (Object 1009 / SET), Info Words (Object 1025 / IW),
    and active Function 141 (Temperature/Time) parameters directly from SETEX Controller TCP Port 50000.
    """
    m = db.query(Machine).filter(Machine.machine_no == machine_no.upper()).first()
    host = ip or (m.ip_address if m else "172.16.110.101")
    port = (m.tcp_port if m and m.tcp_port else 50000)

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

@router.post("/{machine_no}/write")
def write_setpoint(
    machine_no: str,
    req: SetpointWriteRequest,
    db: Session = Depends(get_db)
):
    """
    Scaffolded Setpoint Write Endpoint.
    Uses Service 2 (SV_WRITE) on Controller TCP Port 50000.
    Enforces OpenOrgaTEX safety policy (WRITE_MODE_ENABLED flag).
    """
    m = db.query(Machine).filter(Machine.machine_no == machine_no.upper()).first()
    host = m.ip_address if m else "172.16.110.101"
    port = m.tcp_port if (m and m.tcp_port) else 50000

    result = SetexTcpClient.write_setpoint(
        host=host,
        port=port,
        obj=req.obj,
        address=req.address,
        value=req.value
    )
    return result
