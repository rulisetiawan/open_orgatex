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
import re
import json
import time
import logging
import threading
from datetime import datetime
from typing import List, Optional, Dict, Any, Union

from fastapi import APIRouter, HTTPException, Depends, Header, Query, Body, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from ..database import get_db
from ..models.schema_pg import (
    Machine, BatchHeader, MachineQueue, Recipe, ProgramHeader, ProgramComponent,
    DatalogCyclicRecord, DatalogAlarm
)
from ..utils.secom_codec import colorref_to_hex

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


class OrgaTexImportBatchItem(BaseModel):
    """
    Payload kontrak pihak ketiga (ERP / Recipe System -> OpenOrgaTEX Batch Import).
    Mendukung seluruh field standar OrgaTEX Batch Import termasuk COLORREF 4-byte & Parameter1..20.
    """
    Dyelot: str = Field(..., min_length=1, description="Nomor data / Dyelot batch")
    Customer: Optional[str] = Field("", description="Nama Customer")
    Article: Optional[str] = Field("", description="Jenis Kain")
    ColourNo: Optional[str] = Field("", description="No Warna")
    ColourDescript: Optional[str] = Field("", description="Nama Warna")
    Color: Optional[int] = Field(
        None,
        ge=0,
        le=0x00FFFFFF,
        description="Windows COLORREF 4-byte RGB (bit 0..7=R, 8..15=G, 16..23=B, 24..31=0)"
    )
    Redye: int = Field(0, ge=0, description="Celupan ke berapa, mulai dari 0")
    Machine: str = Field(..., min_length=1, description="Nama / Kode Mesin")
    ProcedureNo: Union[str, int] = Field(..., description="Nama atau Nomor Program Celup")
    Weight: float = Field(..., ge=0, description="Berat Order")
    ImportState: int = Field(0, description="Isi 4 jika ingin langsung di-release (QUEUED)")
    LiquorQuantity: Optional[float] = Field(None, ge=0, description="Vlot Air (Liter)")
    Note1: Optional[str] = Field(None, description="List no data dalam 1 batch")
    TypeOfProcedureNo: int = Field(1, description="Tipe eksekusi program celup di OrgaTEX, default 1")
    ProcessType1: int = Field(1, description="Tipe Proses, default 1 (Dyeing)")
    ProcessType2: int = Field(1, description="Tipe Order, default 1")
    LiquorRatio: float = Field(6.0, ge=0, description="Liquor Ratio, default 6")
    Length: float = Field(200.0, ge=0, description="Panjang kain, default 200")
    Parameter11: Optional[float] = Field(2.0, description="Cycle Time")
    Parameter15: Optional[float] = Field(None, description="Soda Addition (hasil perhitungan resep)")
    Parameter16: Optional[float] = Field(None, description="Salt Addition (hasil perhitungan resep)")
    Parameter17: Optional[float] = Field(None, description="Dye Addition (hasil perhitungan resep)")
    Parameter18: Optional[float] = Field(None, description="Water Addition (hasil perhitungan resep)")
    Parameter20: Optional[float] = Field(6.0, description="Fabric Width")

    class Config:
        extra = "allow"


def _resolve_machine(db: Session, machine_raw: str, weight: float, liquor_ratio: float):
    """Mencocokkan nama/kode mesin ke tabel machines; auto-create bila belum terdaftar."""
    clean = machine_raw.strip()
    upper = clean.upper()

    m = db.query(Machine).filter(func.upper(Machine.machine_no) == upper).first()
    if m:
        return m, None

    m = db.query(Machine).filter(func.upper(Machine.display_name) == upper).first()
    if m:
        return m, None

    is_797 = upper in ("DA01", "M_95") or "797" in upper
    new_m = Machine(
        machine_no=upper,
        display_name=clean if clean != upper else (f"SETEX 797CE Mesin {upper}" if is_797 else f"Mesin {upper}"),
        ip_address="192.168.1.95" if is_797 else "172.16.110.100",
        tcp_port=50100 if is_797 else 50000,
        ftp_port=21,
        controller_type="SETEX 797CE (Windows CE)" if is_797 else "SECOM 777 (Windows CE)",
        os_family="WindowsCE",
        group_name="Dyeing Sample / DA" if is_797 else "Dyeing Section",
        capacity_kg=weight or 350.0,
        default_liquor_ratio=liquor_ratio or 6.0,
        share_folder_path="/Flashdisk/SC797CE" if is_797 else "/Storage/sc777ce",
        status="ONLINE",
        is_active=True
    )
    db.add(new_m)
    db.flush()
    return new_m, f"Mesin '{clean}' belum terdaftar di master, otomatis dibuat sebagai '{upper}'."


def _resolve_procedure_no(db: Session, procedure_raw: Union[str, int]):
    """
    Resolusi ProcedureNo (nama program celup atau kode angka) ke numeric program_no (1..9999)
    untuk kompilasi M_xxxx.PRG.
    """
    proc_str = str(procedure_raw).strip()
    if not proc_str:
        return 1, "", "ProcedureNo kosong, fallback ke program_no=1."

    # 1. Jika langsung angka murni (misal 401 atau "0401")
    if proc_str.isdigit():
        return int(proc_str), proc_str, None

    # 2. Cari di ProgramComponent (Level 1 = Procedure) berdasarkan name atau number
    proc_upper = proc_str.upper()
    comp = db.query(ProgramComponent).filter(
        ProgramComponent.level == 1,
        (func.upper(ProgramComponent.name) == proc_upper) | (func.upper(ProgramComponent.number) == proc_upper)
    ).first()
    if comp:
        digits = re.sub(r"\D", "", str(comp.number or ""))
        prog_no = int(digits) if digits else int(comp.id)
        return prog_no, proc_str, None

    # 3. Cari di ProgramHeader berdasarkan program_name
    hdr = db.query(ProgramHeader).filter(func.upper(ProgramHeader.program_name) == proc_upper).first()
    if hdr:
        return int(hdr.program_no), proc_str, None

    # 4. Coba pola seperti "M_0401" atau "PRG 401"
    m = re.match(r"^(?:M_|PRG[\s_-]*)(\d{1,4})(?:\.PRG)?$", proc_upper)
    if m:
        return int(m.group(1)), proc_str, None

    return 1, proc_str, f"ProcedureNo '{proc_str}' tidak ditemukan di master program, menggunakan fallback program_no=1."


def _extract_batch_parameters(item: OrgaTexImportBatchItem) -> Dict[str, float]:
    """Mengumpulkan Parameter1..Parameter20 dari payload (termasuk field ekstra dinamis)."""
    params: Dict[str, float] = {}
    raw_dict = item.model_dump() if hasattr(item, "model_dump") else item.dict()
    for key, val in raw_dict.items():
        if val is None:
            continue
        m = re.match(r"^Parameter(\d{1,2})$", str(key), re.IGNORECASE)
        if m:
            slot = int(m.group(1))
            if 1 <= slot <= 20:
                params[str(slot)] = float(val)
    return params


def process_orgatex_batch_import(
    items: List[OrgaTexImportBatchItem],
    db: Session
) -> Dict[str, Any]:
    """
    Core processor untuk bulk/single import batch dari sistem pihak ketiga.
    Menulis ke PostgreSQL/SQLite (BatchHeader & MachineQueue), sync local BATCHREF.REF/QUEUE.BTD,
    dan trigger FTP sync untuk batch DA01 yang langsung di-release (ImportState == 4).
    """
    if not items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload batch tidak boleh kosong."
        )

    # Tentukan nomor referensi 6-digit berikutnya secara aman untuk seluruh item di batch array
    all_refs = db.query(BatchHeader.batch_ref_no).all()
    existing_numeric = [int(r[0]) for r in all_refs if r[0] and str(r[0]).isdigit()]
    next_ref_counter = (max(existing_numeric) if existing_numeric else 62343) + 1

    imported: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    created_objects: List[BatchHeader] = []
    da01_released_refs: List[str] = []

    for idx, item in enumerate(items):
        dyelot = item.Dyelot.strip()
        dyelot_upper = dyelot.upper()
        item_warnings: List[str] = []

        try:
            # Cek duplikasi kombinasi aktif (Dyelot, Redye)
            dup = db.query(BatchHeader).filter(
                func.upper(BatchHeader.batch_no) == dyelot_upper,
                BatchHeader.redye == item.Redye,
                ~BatchHeader.status.in_(["FINISHED", "COMPLETED", "CANCELLED"])
            ).first()
            if dup:
                errors.append({
                    "index": idx,
                    "dyelot": dyelot,
                    "redye": item.Redye,
                    "error": f"Dyelot '{dyelot}' (Redye {item.Redye}) sudah terdaftar aktif di mesin '{dup.machine_no}' (Ref: {dup.batch_ref_no}, Status: {dup.status})."
                })
                continue

            machine_obj, mach_warn = _resolve_machine(db, item.Machine, item.Weight, item.LiquorRatio)
            if mach_warn:
                item_warnings.append(mach_warn)
            mach_no = machine_obj.machine_no

            prog_no, proc_str, proc_warn = _resolve_procedure_no(db, item.ProcedureNo)
            if proc_warn:
                item_warnings.append(proc_warn)

            ref_no = str(next_ref_counter).zfill(6)
            next_ref_counter += 1

            # ImportState == 4 -> langsung release ke antrean mesin (QUEUED), selain itu PLANNING
            batch_status = "QUEUED" if item.ImportState == 4 else "PLANNING"

            max_pos = db.query(func.max(BatchHeader.position)).filter(BatchHeader.machine_no == mach_no).scalar()
            next_position = (max_pos or 0) + 1

            total_water = (
                float(item.LiquorQuantity)
                if item.LiquorQuantity is not None
                else round(float(item.Weight) * float(item.LiquorRatio), 2)
            )
            params_dict = _extract_batch_parameters(item)
            params_json = json.dumps(params_dict) if params_dict else None
            color_hex = colorref_to_hex(item.Color) if item.Color is not None else None

            new_batch = BatchHeader(
                batch_ref_no=ref_no,
                batch_no=dyelot_upper,
                machine_no=mach_no,
                program_no=prog_no,
                procedure_no=proc_str,
                recipe_name=proc_str or f"Program {prog_no}",
                customer=(item.Customer or "-").strip() or "-",
                article=(item.Article or "-").strip() or "-",
                color_code=(item.ColourNo or "-").strip() or "-",
                color_name=(item.ColourDescript or "-").strip() or "-",
                color_rgb=item.Color,
                redye=item.Redye,
                fabric_weight_kg=item.Weight,
                liquor_ratio=item.LiquorRatio,
                total_water_l=total_water,
                fabric_length=item.Length,
                import_state=item.ImportState,
                note1=item.Note1,
                type_of_procedure_no=item.TypeOfProcedureNo,
                process_type_1=item.ProcessType1,
                process_type_2=item.ProcessType2,
                parameters_json=params_json,
                status=batch_status,
                position=next_position
            )
            db.add(new_batch)

            if batch_status == "QUEUED":
                db.add(MachineQueue(
                    machine_no=mach_no,
                    batch_ref_no=ref_no,
                    batch_no=dyelot_upper,
                    program_no=prog_no,
                    recipe_name=proc_str or f"Program {prog_no}",
                    customer=(item.Customer or "-").strip() or "-",
                    article=(item.Article or "-").strip() or "-",
                    color_code=(item.ColourNo or "-").strip() or "-",
                    color_name=(item.ColourDescript or "-").strip() or "-",
                    fabric_weight_kg=item.Weight,
                    liquor_ratio=item.LiquorRatio,
                    total_water_l=total_water,
                    status=batch_status,
                    position=next_position
                ))

            db.commit()
            db.refresh(new_batch)
            created_objects.append(new_batch)

            if mach_no == "DA01" and batch_status == "QUEUED":
                da01_released_refs.append(ref_no)

            imported.append({
                "index": idx,
                "batch_ref_no": ref_no,
                "dyelot": dyelot_upper,
                "redye": item.Redye,
                "machine_no": mach_no,
                "procedure_no": proc_str,
                "program_no": prog_no,
                "weight": float(item.Weight),
                "liquor_ratio": float(item.LiquorRatio),
                "liquor_quantity": total_water,
                "length": float(item.Length),
                "import_state": item.ImportState,
                "status": batch_status,
                "position": next_position,
                "color_rgb": item.Color,
                "color_hex": color_hex,
                "note1": item.Note1,
                "parameters": params_dict,
                "warnings": item_warnings
            })

        except Exception as e:
            db.rollback()
            logger.error(f"Error importing batch index={idx} dyelot={dyelot}: {e}")
            errors.append({
                "index": idx,
                "dyelot": dyelot,
                "redye": item.Redye,
                "error": str(e)
            })

    # Sinkronisasi file QUEUE.BTD / BATCHREF.REF
    if created_objects:
        try:
            from .planning import _batch_to_dict, _sync_planning_json
            all_batches = [_batch_to_dict(b) for b in db.query(BatchHeader).order_by(BatchHeader.created_at.desc()).all()]
            threading.Thread(target=_sync_planning_json, args=(all_batches,), daemon=True).start()
        except Exception as pe:
            logger.warning(f"Local planning/QUEUE.BTD sync on import skipped: {pe}")

        if da01_released_refs:
            def _bg_ftp_sync_imported(refs: List[str]):
                try:
                    from ..services.ftp_sync_service import sync_single_batch_to_ftp
                    for r in refs:
                        sync_single_batch_to_ftp(r)
                except Exception as fe:
                    logger.warning(f"Background FTP sync on import skipped: {fe}")

            threading.Thread(target=_bg_ftp_sync_imported, args=(da01_released_refs,), daemon=True).start()

    overall_status = "success"
    if errors and imported:
        overall_status = "partial_success"
    elif errors and not imported:
        overall_status = "failed"

    return {
        "status": overall_status,
        "total_received": len(items),
        "total_imported": len(imported),
        "total_failed": len(errors),
        "imported": imported,
        "errors": errors
    }

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

@router.post("/batches/import", status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_api_key)])
def import_batches(
    payload: Union[List[OrgaTexImportBatchItem], OrgaTexImportBatchItem] = Body(...),
    db: Session = Depends(get_db)
):
    """
    [ERP / Recipe System -> OrgaTEX] Bulk / Single Batch Import.
    Menerima array JSON `[{Dyelot, Customer, Article, ColourNo, ColourDescript, Color, Redye, Machine,
    ProcedureNo, Weight, ImportState, LiquorQuantity, Note1, TypeOfProcedureNo, ProcessType1,
    ProcessType2, LiquorRatio, Length, Parameter11, Parameter15..18, Parameter20}]`.

    - `Color`: 4-byte Windows COLORREF RGB (bit 0..7=R, 8..15=G, 16..23=B, 24..31=0).
    - `ImportState = 4`: otomatis release ke status `QUEUED` (masuk antrean mesin & QUEUE.BTD).
    - `Parameter11, 15..18, 20`: otomatis ditulis ke slot parameter float32 `BATCHREF.REF`.
    """
    items = payload if isinstance(payload, list) else [payload]
    return process_orgatex_batch_import(items, db)


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
