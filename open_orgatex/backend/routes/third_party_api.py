"""
OpenOrgaTEX Third-Party Integration API (REST / JSON)
Reverse engineered from OrgaTEX WebService.exe, OtxWcfWebServiceLib.dll, and OtxBatchProvider.dll
Implements full parity with OrgaTEX IBatchService, IOnlineStatusService, and WebService.Controllers

Designed for 3rd-party integration:
- ERP Systems (SAP, Oracle, Odoo, Infor, Microsoft Dynamics, Custom ERP)
- MES / SCADA / Color Kitchen Dispensing Systems
- Realtime Dashboards and Plant Analytics
"""

import os
import json
import time
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Header, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..database import get_db
from ..models.schema_pg import (
    Machine, BatchHeader, Recipe, ProgramHeader,
    DatalogCyclicRecord, DatalogAlarm
)

logger = logging.getLogger("orgatex.third_party_api")

router = APIRouter(
    prefix="/api/v1/thirdparty",
    tags=["Third-Party Integration API (OrgaTEX Parity)"]
)

# ---------------------------------------------------------------------------
# Configuration & Authentication
# ---------------------------------------------------------------------------
API_KEY_ENV = os.getenv("ORGATEX_API_KEY", "otx-sec-key-777")
PLANNING_PATH = os.path.abspath("./open_orgatex/backend/data/planning.json")

def verify_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization")
):
    """
    Validates third-party API Key via X-API-Key or Authorization Bearer token.
    Set ORGATEX_API_KEY environment variable to customize, or 'none' to disable.
    """
    if API_KEY_ENV.lower() == "none":
        return True

    provided_key = None
    if x_api_key:
        provided_key = x_api_key.strip()
    elif authorization and authorization.lower().startswith("bearer "):
        provided_key = authorization[7:].strip()

    if not provided_key or provided_key != API_KEY_ENV:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key. Provide a valid 'X-API-Key' header or 'Authorization: Bearer <key>'."
        )
    return True

# ---------------------------------------------------------------------------
# Internal Helpers for File Storage Synchronization
# ---------------------------------------------------------------------------
def _load_planning_store() -> List[Dict[str, Any]]:
    if os.path.exists(PLANNING_PATH):
        try:
            with open(PLANNING_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading planning store: {e}")
    return []

def _save_planning_store(data: List[Dict[str, Any]]):
    os.makedirs(os.path.dirname(PLANNING_PATH), exist_ok=True)
    with open(PLANNING_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ---------------------------------------------------------------------------
# Pydantic Request & Response Schemas (OrgaTEX DataContract Parity)
# ---------------------------------------------------------------------------
class BatchCreateRequest(BaseModel):
    batch_no: str = Field(..., description="Nomor Batch/Lot Produksi (cth: LOT2026-001)")
    machine_no: str = Field(..., description="Kode Mesin SETEX (cth: TD12, B012)")
    program_no: int = Field(1, description="Nomor Program Mesin SETEX (M_xxxx.PRG)")
    recipe_name: Optional[str] = Field("Reactive Dyeing Formula", description="Nama/Kode Resep")
    customer: Optional[str] = Field("PT. ARTA PERMAI", description="Nama Pelanggan")
    article: Optional[str] = Field("CM 30S RIB", description="Jenis Bahan/Kain")
    color_code: Optional[str] = Field("1650159", description="Kode Warna")
    color_name: Optional[str] = Field("UNGU TUA", description="Nama Warna")
    fabric_weight_kg: float = Field(350.0, description="Berat Kain / Batch (Kg)")
    liquor_ratio: float = Field(8.0, description="Rasio Air (Liquor Ratio :1)")
    reference_no: Optional[str] = Field(None, description="Nomor Referensi OrgaTEX internal (opsional)")
    priority: Optional[int] = Field(1, description="Prioritas Antrian (1=Tertinggi)")
    note: Optional[str] = Field(None, description="Catatan Tambahan untuk Operator")

class BatchStatusUpdateRequest(BaseModel):
    status: str = Field(..., description="Status Baru (QUEUED, RUNNING, HOLD, CANCELLED, FINISHED)")
    note: Optional[str] = Field(None, description="Alasan Perubahan Status")

class BatchMoveRequest(BaseModel):
    target_machine_no: Optional[str] = Field(None, description="Pindah ke Mesin Lain")
    new_position: Optional[int] = Field(None, description="Urutan Posisi Baru di Antrian")

# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@router.get("/info", dependencies=[Depends(verify_api_key)])
def get_service_info():
    """
    Informasi Layanan OpenOrgaTEX API & Status Kompatibilitas Sistem.
    """
    return {
        "service": "OpenOrgaTEX Third-Party Integration API",
        "version": "2.2.0",
        "protocol_parity": "OrgaTEX WebService / IBatchService / IOnlineStatusService",
        "supported_controllers": ["SETEX SECOM 777 (Windows CE)", "SECOM 737", "SECOM 500"],
        "authentication": "API-Key Protected",
        "status": "OPERATIONAL",
        "server_time": datetime.now().isoformat()
    }

# ===========================================================================
# 1. BATCH MANAGEMENT (Parity: IBatchService / BatchPoolManager)
# ===========================================================================

@router.post("/batches", status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_api_key)])
def create_batch(req: BatchCreateRequest, db: Session = Depends(get_db)):
    """
    [ERP -> OrgaTEX] Menerima Inject Order Produksi / Lot Celup dari Sistem Luar (ERP/SAP).
    Data otomatis didaftarkan ke antrian mesin (Batch Queue & Planning).
    """
    batches = _load_planning_store()
    
    # Cek duplikasi nomor batch pada status aktif/antrian
    existing = next((b for b in batches if b.get("batch_no") == req.batch_no and b.get("status") not in ["FINISHED", "CANCELLED"]), None)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Batch dengan nomor '{req.batch_no}' sudah terdaftar pada mesin '{existing.get('machine_no')}' dengan status '{existing.get('status')}'."
        )

    # Buat reference number unik (format 6-digit sesuai OrgaTEX)
    ref_no = req.reference_no or str(int(time.time()))[-6:]
    total_water = round(req.fabric_weight_kg * req.liquor_ratio, 2)
    new_id = f"b-{ref_no}"

    # Hitung posisi antrian terakhir untuk mesin target
    machine_batches = [b for b in batches if b.get("machine_no") == req.machine_no]
    next_position = len(machine_batches) + 1

    new_batch_record = {
        "id": new_id,
        "reference_no": ref_no,
        "batch_no": req.batch_no,
        "machine_no": req.machine_no.upper(),
        "program_no": req.program_no,
        "recipe_name": req.recipe_name,
        "customer": req.customer,
        "article": req.article,
        "color_code": req.color_code,
        "color_name": req.color_name,
        "fabric_weight_kg": req.fabric_weight_kg,
        "liquor_ratio": req.liquor_ratio,
        "total_water_l": total_water,
        "status": "QUEUED",
        "position": next_position,
        "priority": req.priority,
        "note": req.note,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "THIRD_PARTY_API"
    }

    # Simpan ke Planning Store
    batches.append(new_batch_record)
    _save_planning_store(batches)

    # Sinkronisasi ke Database PostgreSQL jika tersedia
    try:
        db_batch = BatchHeader(
            batch_ref_no=ref_no,
            machine_no=req.machine_no.upper(),
            program_no=req.program_no,
            status="QUEUED",
            fabric_weight_kg=req.fabric_weight_kg,
            liquor_ratio=req.liquor_ratio,
            customer=req.customer
        )
        db.add(db_batch)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"DB Header sync fallback: {e}")

    return {
        "status": "success",
        "message": f"Batch '{req.batch_no}' berhasil dijadwalkan pada mesin '{req.machine_no.upper()}'.",
        "data": new_batch_record
    }

@router.get("/batches", dependencies=[Depends(verify_api_key)])
def list_batches(
    machine_no: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """
    [ERP <- OrgaTEX] Mengambil Daftar Antrian & Riwayat Batch.
    Mendukung filter mesin, status, dan pagination.
    """
    batches = _load_planning_store()

    if machine_no and isinstance(machine_no, str):
        batches = [b for b in batches if b.get("machine_no", "").upper() == machine_no.upper()]

    if status and isinstance(status, str):
        batches = [b for b in batches if b.get("status", "").upper() == status.upper()]

    total_count = len(batches)
    paged = batches[offset:offset + limit]

    return {
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "batches": paged
    }

@router.get("/batches/{batch_no}", dependencies=[Depends(verify_api_key)])
def get_batch_detail(batch_no: str, db: Session = Depends(get_db)):
    """
    [ERP <- OrgaTEX] Mendapatkan Detail Status & Progress Realtime Suatu Batch.
    """
    batches = _load_planning_store()
    target = next((b for b in batches if b.get("batch_no") == batch_no or b.get("reference_no") == batch_no or b.get("id") == batch_no), None)

    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch '{batch_no}' tidak ditemukan di sistem."
        )

    # Ambil live machine status jika batch sedang berjalan
    live_info = {}
    if target.get("status") in ["RUNNING", "ACTIVE"]:
        machine_no = target.get("machine_no")
        m = db.query(Machine).filter(Machine.machine_no == machine_no).first()
        if m:
            live_info = {
                "current_step": m.current_step,
                "current_temp": float(m.current_temp) if m.current_temp is not None else None,
                "machine_status": m.status,
                "last_update": m.last_ping_time.isoformat() if m.last_ping_time else None
            }

    return {
        "batch": target,
        "telemetry": live_info
    }

@router.patch("/batches/{batch_no}/status", dependencies=[Depends(verify_api_key)])
def update_batch_status(batch_no: str, req: BatchStatusUpdateRequest, db: Session = Depends(get_db)):
    """
    [ERP -> OrgaTEX] Mengubah Status Batch (cth: HOLD, CANCELLED, QUEUED).
    """
    batches = _load_planning_store()
    target = next((b for b in batches if b.get("batch_no") == batch_no or b.get("reference_no") == batch_no), None)

    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Batch '{batch_no}' tidak ditemukan.")

    old_status = target.get("status")
    new_status = req.status.upper()
    target["status"] = new_status
    target["status_updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if req.note:
        target["status_note"] = req.note

    _save_planning_store(batches)

    # Update di DB jika ada
    try:
        db_b = db.query(BatchHeader).filter(BatchHeader.batch_ref_no == target.get("reference_no")).first()
        if db_b:
            db_b.status = new_status
            db.commit()
    except Exception:
        db.rollback()

    return {
        "status": "success",
        "batch_no": batch_no,
        "previous_status": old_status,
        "current_status": new_status,
        "updated_at": target["status_updated_at"]
    }

@router.post("/batches/{batch_no}/move", dependencies=[Depends(verify_api_key)])
def move_batch(batch_no: str, req: BatchMoveRequest):
    """
    [ERP -> OrgaTEX] Memindahkan Batch ke Mesin Lain atau Mengubah Urutan Antrian.
    (Parity dengan MoveBatch di OrgaTEX OtxWcfWebServiceLib)
    """
    batches = _load_planning_store()
    target = next((b for b in batches if b.get("batch_no") == batch_no or b.get("reference_no") == batch_no), None)

    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Batch '{batch_no}' tidak ditemukan.")

    if target.get("status") == "RUNNING":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Batch yang sedang RUNNING tidak dapat dipindahkan.")

    if req.target_machine_no:
        target["machine_no"] = req.target_machine_no.upper()

    if req.new_position is not None:
        target["position"] = req.new_position

    _save_planning_store(batches)

    return {
        "status": "success",
        "message": f"Batch '{batch_no}' berhasil diperbarui.",
        "machine_no": target["machine_no"],
        "position": target.get("position")
    }

# ===========================================================================
# 2. MACHINE MONITORING & TELEMETRY (Parity: IOnlineStatusService / WebSocket)
# ===========================================================================

@router.get("/machines", dependencies=[Depends(verify_api_key)])
def list_machines(db: Session = Depends(get_db)):
    """
    [ERP <- OrgaTEX] Mendapatkan Daftar Seluruh Mesin Celup dan Kondisi Operasional Terkini.
    """
    machines = db.query(Machine).all()
    result = []
    for m in machines:
        result.append({
            "machine_no": m.machine_no,
            "display_name": m.display_name,
            "group_name": m.group_name,
            "controller_type": m.controller_type,
            "ip_address": m.ip_address,
            "status": m.status,
            "current_batch": m.current_batch,
            "current_step": m.current_step,
            "current_temp": float(m.current_temp) if m.current_temp is not None else None,
            "capacity_kg": float(m.capacity_kg) if m.capacity_kg is not None else None,
            "last_ping_time": m.last_ping_time.isoformat() if m.last_ping_time else None
        })
    return {"count": len(result), "machines": result}

@router.get("/machines/{machine_no}/telemetry", dependencies=[Depends(verify_api_key)])
def get_machine_telemetry(machine_no: str, limit: int = 20, db: Session = Depends(get_db)):
    """
    [ERP <- OrgaTEX] Mengambil Riwayat Siklus Sensor & Telemetri Realtime Terakhir (Suhu, Tekanan, Step, dll).
    """
    m = db.query(Machine).filter(Machine.machine_no == machine_no.upper()).first()
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Mesin '{machine_no}' tidak ditemukan.")

    records = db.query(DatalogCyclicRecord)\
        .filter(DatalogCyclicRecord.machine_no == machine_no.upper())\
        .order_by(desc(DatalogCyclicRecord.log_timestamp))\
        .limit(limit)\
        .all()

    telemetry_data = []
    for r in records:
        telemetry_data.append({
            "timestamp": r.log_timestamp.isoformat(),
            "batch_ref_no": r.batch_ref_no,
            "temp_pv": float(r.temp_pv) if r.temp_pv is not None else None,
            "temp_sp": float(r.temp_sp) if r.temp_sp is not None else None,
            "pump_speed_percent": float(r.pump_speed_percent) if r.pump_speed_percent is not None else None,
            "reel_speed_mpm": float(r.reel_speed_mpm) if r.reel_speed_mpm is not None else None,
            "vessel_pressure_bar": float(r.vessel_pressure_bar) if r.vessel_pressure_bar is not None else None,
            "step_no": r.step_no
        })

    return {
        "machine_no": machine_no.upper(),
        "current_status": m.status,
        "current_batch": m.current_batch,
        "count": len(telemetry_data),
        "telemetry": telemetry_data
    }

# ===========================================================================
# 3. RECIPES & PROGRAMS (Parity: GetRecipes / GetPrograms)
# ===========================================================================

@router.get("/recipes", dependencies=[Depends(verify_api_key)])
def list_recipes(db: Session = Depends(get_db)):
    """
    [ERP <- OrgaTEX] Sinkronisasi Master Resep dan Formula Kimia / Pewarna.
    """
    recipes = db.query(Recipe).all()
    res = []
    for r in recipes:
        items = []
        for it in r.items:
            items.append({
                "chemical_code": it.chemical_code,
                "chemical_name": it.chemical_name,
                "amount": float(it.amount),
                "unit": it.unit,
                "dosing_tank": it.dosing_tank
            })
        res.append({
            "recipe_id": r.recipe_id,
            "recipe_code": r.recipe_code,
            "recipe_name": r.recipe_name,
            "customer_name": r.customer_name,
            "fabric_type": r.fabric_type,
            "standard_liquor_ratio": float(r.standard_liquor_ratio) if r.standard_liquor_ratio is not None else 8.0,
            "items_count": len(items),
            "chemicals": items
        })
    return {"count": len(res), "recipes": res}

@router.get("/programs", dependencies=[Depends(verify_api_key)])
def list_programs(db: Session = Depends(get_db)):
    """
    [ERP <- OrgaTEX] Sinkronisasi Master Program Kontroler SETEX (M_xxxx.PRG).
    """
    programs = db.query(ProgramHeader).all()
    res = []
    for p in programs:
        res.append({
            "program_no": p.program_no,
            "program_name": p.program_name,
            "fabric_type": p.fabric_type,
            "estimated_duration_min": p.estimated_duration_min,
            "total_steps": len(p.steps)
        })
    return {"count": len(res), "programs": res}

# ===========================================================================
# 4. ALARMS & INCIDENTS (Parity: AlarmConfigurationController)
# ===========================================================================

@router.get("/alarms", dependencies=[Depends(verify_api_key)])
def list_alarms(
    machine_no: Optional[str] = None,
    order: str = "desc",
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    [ERP <- OrgaTEX] Mengambil Riwayat Alarm & Gangguan Mesin Celup.
    Diurutkan strictly berdasarkan date time (alarm_timestamp).
    """
    q = db.query(DatalogAlarm)
    if machine_no and isinstance(machine_no, str):
        q = q.filter(DatalogAlarm.machine_no == machine_no.upper())

    if order.lower() == "asc":
        q = q.order_by(DatalogAlarm.alarm_timestamp.asc(), DatalogAlarm.id.asc())
    else:
        q = q.order_by(desc(DatalogAlarm.alarm_timestamp), desc(DatalogAlarm.id))

    alarms = q.limit(limit).all()

    res = []
    for a in alarms:
        res.append({
            "id": a.id,
            "machine_no": a.machine_no,
            "batch_ref_no": a.batch_ref_no,
            "alarm_code": a.alarm_code,
            "alarm_text": a.alarm_text,
            "severity": a.severity,
            "step_no": a.step_no,
            "timestamp": a.alarm_timestamp.isoformat(),
            "cleared_at": a.cleared_at.isoformat() if a.cleared_at else None
        })

    return {"count": len(res), "alarms": res}
