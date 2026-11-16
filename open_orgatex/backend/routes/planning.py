"""
Production Planning & Batch Dispatch Route (OrgaTEX SCX620 Parity)
STRICTLY SAFE MODE: File writing to shared network folders is DISABLED.
All batch records are managed locally and can be exported as offline ZIP bundles.
"""

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import os
import json
import time

try:
    from ..utils.secom_codec import (
        create_batchref_binary,
        build_minimal_prg,
        generate_batch_zip,
        generate_multi_batch_zip
    )
except (ImportError, ValueError):
    from utils.secom_codec import (
        create_batchref_binary,
        build_minimal_prg,
        generate_batch_zip,
        generate_multi_batch_zip
    )

try:
    from .programs import get_compiled_prg_bytes
except Exception:
    get_compiled_prg_bytes = None

router = APIRouter(prefix="/api/planning", tags=["Planning"])

PLANNING_PATH = os.path.abspath("./open_orgatex/backend/data/planning.json")
TYPECONF_PATH = os.path.abspath("./open_orgatex/backend/data/typeconf_functions.json")
os.makedirs(os.path.dirname(PLANNING_PATH), exist_ok=True)

class CreateBatchRequest(BaseModel):
    batch_no: str = Field(..., description="Nomor Lot/Batch Produksi, misal PJT026")
    machine_no: str = Field(..., description="Kode Mesin, misal TD12, B012, TD13")
    program_no: int = Field(1, description="Nomor Program M_xxxx.PRG")
    recipe_name: str = Field("Reactive Dyeing Formula", description="Nama Resep")
    customer: Optional[str] = "PT. ARTA PERMAI"
    article: Optional[str] = "CM 30S RIB"
    color_code: Optional[str] = "1650159"
    color_name: Optional[str] = "UNGU TUA"
    fabric_weight_kg: float = 350.0
    liquor_ratio: float = 8.0
    reference_no: Optional[str] = None
    status: str = "QUEUED"

class UpdateBatchStatusRequest(BaseModel):
    status: str
    position: Optional[int] = None

class ReorderRequest(BaseModel):
    machine_no: str
    ordered_ids: List[str]

def _get_default_batches():
    return [
        {
            "id": "b-062340",
            "reference_no": "062340",
            "batch_no": "PJT026",
            "machine_no": "TD12",
            "program_no": 401,
            "recipe_name": "Reactive Violet 30S",
            "customer": "PT. ARTA PERMAI",
            "article": "CM 30S RIB",
            "color_code": "1650159",
            "color_name": "UNGU TUA",
            "fabric_weight_kg": 325.85,
            "liquor_ratio": 8.0,
            "total_water_l": 2606.8,
            "status": "RUNNING",
            "position": 1,
            "created_at": "2026-11-12 08:30:00"
        },
        {
            "id": "b-062341",
            "reference_no": "062341",
            "batch_no": "PJT027",
            "machine_no": "TD12",
            "program_no": 182,
            "recipe_name": "Cotton Scouring & Bleach",
            "customer": "PT. SUKSES MAKMUR",
            "article": "TC 45S COMBED",
            "color_code": "WHITE-01",
            "color_name": "PUTIH BLEACH",
            "fabric_weight_kg": 400.0,
            "liquor_ratio": 7.5,
            "total_water_l": 3000.0,
            "status": "WAITING_LA",
            "position": 2,
            "created_at": "2026-11-12 09:15:00"
        },
        {
            "id": "b-062342",
            "reference_no": "062342",
            "batch_no": "PJT028",
            "machine_no": "TD12",
            "program_no": 502,
            "recipe_name": "Disperse Black Polyester",
            "customer": "PT. SAMATEX INDAH",
            "article": "POLY MICRO 75D",
            "color_code": "BK-9901",
            "color_name": "JET BLACK",
            "fabric_weight_kg": 380.0,
            "liquor_ratio": 8.0,
            "total_water_l": 3040.0,
            "status": "QUEUED",
            "position": 3,
            "created_at": "2026-11-12 10:00:00"
        },
        {
            "id": "b-062343",
            "reference_no": "062343",
            "batch_no": "PJT029",
            "machine_no": "TD13",
            "program_no": 401,
            "recipe_name": "Direct Yellow Cotton",
            "customer": "PT. CITRA TEX",
            "article": "BABY TERRY 20S",
            "color_code": "YL-4002",
            "color_name": "KUNING LEMON",
            "fabric_weight_kg": 300.0,
            "liquor_ratio": 8.5,
            "total_water_l": 2550.0,
            "status": "QUEUED",
            "position": 1,
            "created_at": "2026-11-12 11:20:00"
        }
    ]

def _load_planning() -> List[Dict[str, Any]]:
    if os.path.exists(PLANNING_PATH):
        try:
            with open(PLANNING_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    defaults = _get_default_batches()
    _save_planning(defaults)
    return defaults

def _save_planning(data: List[Dict[str, Any]]):
    with open(PLANNING_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

@router.get("/")
def get_batches():
    """Mengambil seluruh daftar batch dalam antrean perencanaan OrgaTEX."""
    return _load_planning()

@router.get("/typeconf-functions")
def get_typeconf_functions():
    """Mengambil kamus 105 fungsi Secom 777 hasil ekstraksi TYPECONF.CNF."""
    if os.path.exists(TYPECONF_PATH):
        try:
            with open(TYPECONF_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"functions": {}, "parameters": {}}

@router.post("/")
def create_batch(req: CreateBatchRequest):
    """
    Menambahkan batch baru ke antrean mesin.
    Otomatis menghasilkan 6-digit referensi OrgaTEX unik dan menentukan posisi antrean.
    """
    batches = _load_planning()

    # Generate next 6-digit reference number
    if req.reference_no and req.reference_no.strip():
        ref_no = req.reference_no.strip().zfill(6)
    else:
        existing_refs = [int(b.get("reference_no", 0)) for b in batches if str(b.get("reference_no", "")).isdigit()]
        max_ref = max(existing_refs) if existing_refs else 62339
        ref_no = str(max_ref + 1).zfill(6)

    # Cek duplikasi referensi
    if any(b.get("reference_no") == ref_no for b in batches):
        raise HTTPException(status_code=400, detail=f"Nomor Referensi {ref_no} sudah digunakan dalam antrean.")

    # Hitung posisi antrean berikutnya untuk mesin terkait
    mach = req.machine_no.upper()
    mach_batches = [b for b in batches if b.get("machine_no") == mach]
    next_position = len(mach_batches) + 1

    total_water = round(req.fabric_weight_kg * req.liquor_ratio, 1)

    new_batch = {
        "id": f"b-{ref_no}",
        "reference_no": ref_no,
        "batch_no": req.batch_no.strip().upper(),
        "machine_no": mach,
        "program_no": req.program_no,
        "recipe_name": req.recipe_name,
        "customer": req.customer or "-",
        "article": req.article or "-",
        "color_code": req.color_code or "-",
        "color_name": req.color_name or "-",
        "fabric_weight_kg": req.fabric_weight_kg,
        "liquor_ratio": req.liquor_ratio,
        "total_water_l": total_water,
        "status": req.status,
        "position": next_position,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    batches.append(new_batch)
    _save_planning(batches)

    return {
        "status": "success",
        "message": f"Batch {new_batch['batch_no']} (Ref: {ref_no}) berhasil ditambahkan ke mesin {mach}.",
        "batch": new_batch
    }

@router.put("/{batch_id}")
def update_batch(batch_id: str, req: UpdateBatchStatusRequest):
    """Mengubah status atau posisi antrean batch."""
    batches = _load_planning()
    target = next((b for b in batches if b["id"] == batch_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Batch tidak ditemukan")

    target["status"] = req.status
    if req.position is not None:
        target["position"] = req.position

    _save_planning(batches)
    return {"status": "success", "batch": target}

@router.delete("/{batch_id}")
def delete_batch(batch_id: str):
    """Menghapus batch dari antrean."""
    batches = _load_planning()
    initial_len = len(batches)
    batches = [b for b in batches if b["id"] != batch_id]
    if len(batches) == initial_len:
        raise HTTPException(status_code=404, detail="Batch tidak ditemukan")
    _save_planning(batches)
    return {"status": "success", "message": f"Batch {batch_id} telah dihapus."}

@router.post("/reorder")
def reorder_machine_queue(req: ReorderRequest):
    """Mengatur ulang posisi urutan (1, 2, 3...) untuk satu mesin tertentu."""
    batches = _load_planning()
    mach = req.machine_no.upper()

    for idx, b_id in enumerate(req.ordered_ids, start=1):
        for b in batches:
            if b["id"] == b_id and b.get("machine_no") == mach:
                b["position"] = idx

    _save_planning(batches)
    return {"status": "success", "message": f"Urutan antrean mesin {mach} berhasil diperbarui."}

class MultiExportRequest(BaseModel):
    batch_ids: Optional[List[str]] = None

@router.get("/export-zip/{batch_id}")
def export_batch_zip(batch_id: str):
    """
    Mengunduh berkas offline ZIP paket batch OrgaTEX:
      - OT/BATCH/{ref}/BATCHREF.REF (762 byte Secom biner)
      - OT/BATCH/{ref}/M_{prog:04d}.PRG (SECOM 777 process program)
      - OT/MACHINES/{machine}/BATCHES/QUEUE.BTD (Database antrean mesin)
      - planning-manifest.json
    MODE AMAN: Operasi ini 100% lokal di memory dan TIDAK menulis ke folder jaringan mesin.
    """
    batches = _load_planning()
    target = next((b for b in batches if b["id"] == batch_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Batch tidak ditemukan")

    prog_no = int(target.get("program_no", 1))
    prg_bytes = None
    if get_compiled_prg_bytes:
        try:
            prg_bytes = get_compiled_prg_bytes(prog_no)
        except Exception:
            pass

    zip_bytes = generate_batch_zip(target, prg_bytes=prg_bytes, include_queue=True)
    ref = target.get("reference_no", "000000")
    filename = f"Batch_{ref}_{target.get('batch_no', 'PLAN')}.zip"

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.post("/export-multi-zip")
def export_multi_batches(req: Optional[MultiExportRequest] = None):
    """
    Mengunduh berkas offline ZIP paket multi-batch OrgaTEX:
      - OT/BATCH/{ref}/BATCHREF.REF untuk tiap batch
      - OT/BATCH/{ref}/M_{prog}.PRG untuk tiap program
      - OT/MACHINES/{machine}/BATCHES/QUEUE.BTD (antrean gabungan per mesin)
      - planning-manifest.json
    """
    batches = _load_planning()
    if req and req.batch_ids:
        selected = [b for b in batches if b["id"] in req.batch_ids]
    else:
        selected = batches

    if not selected:
        raise HTTPException(status_code=400, detail="Tidak ada batch yang dipilih untuk diekspor.")

    prg_map = {}
    if get_compiled_prg_bytes:
        for b in selected:
            p_no = int(b.get("program_no", 1))
            if p_no not in prg_map:
                try:
                    prg_map[p_no] = get_compiled_prg_bytes(p_no)
                except Exception:
                    pass

    zip_bytes = generate_multi_batch_zip(selected, prg_map=prg_map)
    filename = f"OrgaTEX_MultiBatch_Package_{time.strftime('%Y%m%d_%H%M%S')}.zip"

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.post("/dispatch")
def dispatch_to_machine(batch_no: str):
    """
    Simulasi aksi dispatch batch ke mesin.
    PERINGATAN: Penulisan file biner ke network share mesin DINONAKTIFKAN demi keamanan produksi.
    """
    batches = _load_planning()
    b = next((x for x in batches if x["batch_no"] == batch_no or x.get("reference_no") == batch_no), None)
    if not b:
        raise HTTPException(status_code=404, detail="Batch tidak ditemukan")

    b["status"] = "WAITING_LA"
    _save_planning(batches)

    return {
        "status": "dispatched_virtual",
        "write_mode": "STRICT_READ_ONLY (Safe Mode Active)",
        "message": f"Status Batch {b['batch_no']} (Ref: {b['reference_no']}) diubah ke 'WAITING_LA'. Penulisan langsung ke folder bersama mesin dinonaktifkan.",
        "batch": b
    }
