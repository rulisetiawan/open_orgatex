"""
Production Planning & Batch Dispatch Route (OrgaTEX SCX620 Parity)
Fully Integrated with Database (PostgreSQL pt_smm_jetflow.public & local SQLite orgatex_local.db)
"""

from fastapi import APIRouter, HTTPException, Depends, Response
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, text
import os
import json
import time
import struct
from datetime import datetime

from ..database import get_db, IS_POSTGRES
from ..models.schema_pg import BatchHeader, Machine, MachineQueue

try:
    from ..utils.secom_codec import (
        create_batchref_binary,
        build_batchref_custom_params,
        colorref_to_hex,
        build_minimal_prg,
        generate_batch_zip,
        generate_multi_batch_zip,
        generate_queue_btd
    )
except (ImportError, ValueError):
    from utils.secom_codec import (
        create_batchref_binary,
        build_batchref_custom_params,
        colorref_to_hex,
        build_minimal_prg,
        generate_batch_zip,
        generate_multi_batch_zip,
        generate_queue_btd
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
    batch_no: str = Field(..., description="Nomor Lot/Batch Produksi, misal PJT030, LOT-95-01")
    machine_no: str = Field(..., description="Kode Mesin, misal M_95, DA01, 10B, TD12")
    program_no: int = Field(1, description="Nomor Program M_xxxx.PRG")
    recipe_name: str = Field("Reactive Dyeing Standard Formula", description="Nama Resep")
    customer: Optional[str] = "PT. ARTA PERMAI"
    article: Optional[str] = "CM 30S RIB 100% Cotton"
    color_code: Optional[str] = "1650159"
    color_name: Optional[str] = "UNGU TUA"
    fabric_weight_kg: float = 350.0
    liquor_ratio: float = 8.0
    reference_no: Optional[str] = None
    status: str = "PLANNING"

class UpdateBatchStatusRequest(BaseModel):
    status: Optional[str] = None
    position: Optional[int] = None
    machine_no: Optional[str] = None

class ReorderRequest(BaseModel):
    machine_no: str
    ordered_ids: List[str]

class MultiExportRequest(BaseModel):
    batch_ids: Optional[List[str]] = None

def _batch_to_dict(b: BatchHeader, position: Optional[int] = None) -> Dict[str, Any]:
    weight = float(b.fabric_weight_kg) if b.fabric_weight_kg is not None else 350.0
    lr = float(b.liquor_ratio) if b.liquor_ratio is not None else 8.0
    water = float(b.total_water_l) if b.total_water_l is not None else round(weight * lr, 1)
    
    created_str = ""
    if b.created_at:
        try:
            created_str = b.created_at.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            created_str = str(b.created_at)[:19]

    pos = position if position is not None else (b.position or 1)
    params_dict: Dict[str, Any] = {}
    if getattr(b, "parameters_json", None):
        try:
            params_dict = json.loads(b.parameters_json)
        except Exception:
            params_dict = {}

    color_rgb = getattr(b, "color_rgb", None)
    color_hex = None
    if color_rgb is not None:
        try:
            color_hex = colorref_to_hex(color_rgb)
        except Exception:
            color_hex = None

    return {
        "id": f"b-{b.batch_ref_no}",
        "db_id": b.id,
        "reference_no": b.batch_ref_no,
        "batch_no": b.batch_no or f"LOT-{b.batch_ref_no}",
        "redye": getattr(b, "redye", 0) or 0,
        "machine_no": b.machine_no,
        "program_no": b.program_no or 1,
        "procedure_no": getattr(b, "procedure_no", None),
        "recipe_name": b.recipe_name or "Reactive Dyeing Standard Formula",
        "customer": b.customer or "-",
        "article": b.article or "-",
        "color_code": b.color_code or "-",
        "color_name": b.color_name or "-",
        "color_rgb": color_rgb,
        "color_hex": color_hex,
        "fabric_weight_kg": weight,
        "liquor_ratio": lr,
        "total_water_l": water,
        "fabric_length": float(b.fabric_length) if getattr(b, "fabric_length", None) is not None else 200.0,
        "import_state": getattr(b, "import_state", 0) or 0,
        "note1": getattr(b, "note1", None),
        "type_of_procedure_no": getattr(b, "type_of_procedure_no", 1) or 1,
        "process_type_1": getattr(b, "process_type_1", 1) or 1,
        "process_type_2": getattr(b, "process_type_2", 1) or 1,
        "parameters": params_dict,
        "status": b.status or "QUEUED",
        "position": pos,
        "created_at": created_str
    }

def sync_local_queue_files(batches_list: List[Dict[str, Any]]):
    """
    Automatically generates and synchronizes:
    1. live QUEUE.BTD (12,288 bytes) for each machine on local disk:
       open_orgatex/backend/data/OT/MACHINES/{machine}/BATCHES/QUEUE.BTD
    2. Batch folders per batch_ref_no on local disk:
       open_orgatex/backend/data/OT/BATCH/{batch_ref_no}/
       containing BATCHREF.REF and M_{prog_no:04d}.PRG
    """
    try:
        data_dir = os.path.dirname(PLANNING_PATH)
        machine_map: Dict[str, List[Dict[str, Any]]] = {}
        for b in batches_list:
            mach = str(b.get("machine_no", "")).strip().upper()
            if mach:
                machine_map.setdefault(mach, []).append(b)

        base_batch_dir = os.path.join(data_dir, "OT", "BATCH")
        os.makedirs(base_batch_dir, exist_ok=True)

        for mach, b_list in machine_map.items():
            # Hanya batch aktif dalam antrean produksi (QUEUED, WAITING_LA, RUNNING) yang masuk QUEUE.BTD
            b_active = [b for b in b_list if str(b.get("status", "")).upper() in ("QUEUED", "WAITING_LA", "RUNNING")]
            # Sort by position, then created_at/id
            b_list_sorted = sorted(b_active, key=lambda x: (int(x.get("position", 1) or 1), str(x.get("id", ""))))
            q_records = []
            for idx, b in enumerate(b_list_sorted, start=1):
                ref_no = str(b.get("reference_no", "062340")).zfill(6)
                prog_no = int(b.get("program_no", 1))
                prg_name = f"M_{prog_no:04d}.PRG"
                recipe_name = b.get("recipe_name", f"Prog {prog_no}")
                
                custom_params = build_batchref_custom_params(
                    fabric_weight=float(b.get("fabric_weight_kg", 350.0)),
                    parameters=b.get("parameters")
                )
                custom_texts = {8: str(b["note1"])} if b.get("note1") else None
                batchref_bin = create_batchref_binary(
                    reference_no=ref_no,
                    machine_no=mach,
                    batch_no=str(b.get("batch_no", f"LOT-{ref_no}")),
                    program_no=prog_no,
                    recipe_no=b.get("recipe_name", ""),
                    customer=b.get("customer", ""),
                    article=b.get("article", ""),
                    color_code=b.get("color_code", ""),
                    color_name=b.get("color_name", ""),
                    fabric_weight=float(b.get("fabric_weight_kg", 350.0)),
                    program_title=recipe_name,
                    custom_texts=custom_texts,
                    custom_params=custom_params
                )
                q_rec = bytearray(batchref_bin[:759])
                struct.pack_into("<HH", q_rec, 755, 0, idx)
                q_records.append(bytes(q_rec))

                # Mirror batch folder locally: OT/BATCH/{ref_no}/
                batch_folder = os.path.join(base_batch_dir, ref_no)
                os.makedirs(batch_folder, exist_ok=True)
                try:
                    with open(os.path.join(batch_folder, "BATCHREF.REF"), "wb") as f_ref:
                        f_ref.write(batchref_bin)
                except Exception:
                    pass

                prg_bytes = None
                if get_compiled_prg_bytes:
                    try:
                        prg_bytes = get_compiled_prg_bytes(prog_no)
                    except Exception:
                        pass
                if not prg_bytes or len(prg_bytes) < 65:
                    prg_bytes = build_minimal_prg(prog_no, recipe_name)

                try:
                    with open(os.path.join(batch_folder, prg_name), "wb") as f_prg:
                        f_prg.write(prg_bytes)
                except Exception:
                    pass

            q_bytes = generate_queue_btd(q_records, mach)
            if q_bytes:
                mach_queue_dir = os.path.join(data_dir, "OT", "MACHINES", mach, "BATCHES")
                os.makedirs(mach_queue_dir, exist_ok=True)
                queue_path = os.path.join(mach_queue_dir, "QUEUE.BTD")
                try:
                    with open(queue_path, "wb") as f:
                        f.write(q_bytes)
                except Exception:
                    pass
    except Exception as e:
        print(f"Notice: local QUEUE.BTD / BATCH sync skipped: {e}")

def _sync_planning_json(batches_list: List[Dict[str, Any]]):
    """Keep local JSON backup and QUEUE.BTD files in sync."""
    try:
        with open(PLANNING_PATH, "w", encoding="utf-8") as f:
            json.dump(batches_list, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
    sync_local_queue_files(batches_list)

def _find_batch(db: Session, batch_id: str) -> Optional[BatchHeader]:
    clean_id = str(batch_id).strip()
    # Try exact reference number match
    ref = clean_id.replace("b-", "")
    target = db.query(BatchHeader).filter(BatchHeader.batch_ref_no == ref).first()
    if target:
        return target
    
    # Try by numeric ID
    if clean_id.isdigit():
        target = db.query(BatchHeader).filter(BatchHeader.id == int(clean_id)).first()
        if target:
            return target

    # Try by batch_no (Lot No)
    target = db.query(BatchHeader).filter(BatchHeader.batch_no == clean_id).first()
    return target

@router.get("", include_in_schema=False)
@router.get("/")
def get_batches(
    machine_no: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Mengambil seluruh daftar batch dalam antrean perencanaan OrgaTEX
    langsung dari Database (PostgreSQL pt_smm_jetflow.public / SQLite lokal).
    """
    query = db.query(BatchHeader)
    if machine_no and machine_no != "SEMUA":
        query = query.filter(BatchHeader.machine_no == machine_no.upper())
    if status and status != "SEMUA":
        query = query.filter(BatchHeader.status == status.upper())

    # Urutkan berdasarkan position lalu created_at descending
    batch_records = query.order_by(BatchHeader.position.asc(), BatchHeader.created_at.desc()).all()
    results = [_batch_to_dict(b) for b in batch_records]

    return results

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

@router.post("", include_in_schema=False)
@router.post("/")
def create_batch(req: CreateBatchRequest, db: Session = Depends(get_db)):
    """
    Menambahkan batch baru ke antrean mesin pada database.
    Otomatis menghasilkan 6-digit referensi OrgaTEX unik dan menentukan posisi antrean.
    """
    mach = req.machine_no.strip().upper()

    # Pastikan mesin terdaftar di database machines
    machine_obj = db.query(Machine).filter(Machine.machine_no == mach).first()
    if not machine_obj:
        # Auto-create entry for new machine if not yet created
        is_797 = mach in ("DA01", "M_95") or "797" in mach
        machine_obj = Machine(
            machine_no=mach,
            display_name=f"SETEX 797CE Mesin {mach}" if is_797 else f"Mesin {mach}",
            ip_address="192.168.1.95" if is_797 else "172.16.110.100",
            tcp_port=50100 if is_797 else 50000,
            ftp_port=21,
            controller_type="SETEX 797CE (Windows CE)" if is_797 else "SECOM 777 (Windows CE)",
            os_family="WindowsCE",
            group_name="Dyeing Sample / DA" if is_797 else "Dyeing Section",
            capacity_kg=req.fabric_weight_kg or 350.0,
            default_liquor_ratio=req.liquor_ratio or 8.0,
            share_folder_path="/Flashdisk/SC797CE" if is_797 else "/Storage/sc777ce",
            status="ONLINE",
            is_active=True
        )
        db.add(machine_obj)
        db.commit()

    # Tentukan 6-digit nomor referensi unik
    if req.reference_no and req.reference_no.strip():
        ref_no = req.reference_no.strip().zfill(6)
    else:
        # Ambil max reference_no yang numerik dari database
        all_refs = db.query(BatchHeader.batch_ref_no).all()
        existing_numeric = [
            int(r[0]) for r in all_refs 
            if r[0] and str(r[0]).isdigit()
        ]
        max_ref = max(existing_numeric) if existing_numeric else 62343
        ref_no = str(max_ref + 1).zfill(6)

    # Cek duplikasi referensi
    existing_ref = db.query(BatchHeader).filter(BatchHeader.batch_ref_no == ref_no).first()
    if existing_ref:
        raise HTTPException(status_code=400, detail=f"Nomor Referensi {ref_no} sudah digunakan dalam antrean database.")

    # Hitung posisi antrean berikutnya untuk mesin terkait
    max_pos = db.query(func.max(BatchHeader.position)).filter(BatchHeader.machine_no == mach).scalar()
    next_position = (max_pos or 0) + 1

    total_water = round(req.fabric_weight_kg * req.liquor_ratio, 1)

    new_batch = BatchHeader(
        batch_ref_no=ref_no,
        batch_no=req.batch_no.strip().upper(),
        machine_no=mach,
        program_no=req.program_no,
        recipe_name=req.recipe_name,
        customer=req.customer or "-",
        article=req.article or "-",
        color_code=req.color_code or "-",
        color_name=req.color_name or "-",
        fabric_weight_kg=req.fabric_weight_kg,
        liquor_ratio=req.liquor_ratio,
        total_water_l=total_water,
        status=req.status or "QUEUED",
        position=next_position
    )

    db.add(new_batch)

    # Simpan juga ke antrean mesin database (MachineQueue)
    existing_mq = db.query(MachineQueue).filter(
        MachineQueue.machine_no == mach,
        MachineQueue.batch_ref_no == ref_no
    ).first()
    if not existing_mq:
        db.add(MachineQueue(
            machine_no=mach,
            batch_ref_no=ref_no,
            batch_no=req.batch_no.strip().upper(),
            program_no=req.program_no,
            recipe_name=req.recipe_name,
            customer=req.customer or "-",
            article=req.article or "-",
            color_code=req.color_code or "-",
            color_name=req.color_name or "-",
            fabric_weight_kg=req.fabric_weight_kg,
            liquor_ratio=req.liquor_ratio,
            total_water_l=total_water,
            status=req.status or "QUEUED",
            position=next_position
        ))

    db.commit()
    db.refresh(new_batch)

    # Sinkronisasi real-time ke SQLite lokal
    try:
        from ..services.db_sync_service import DBSyncService
        DBSyncService.mirror_batch_to_sqlite(new_batch)
    except Exception:
        pass

    import threading

    # Sinkronisasi planning.json backup di background thread agar respons HTTP instan (<50ms)
    all_batches = [_batch_to_dict(b) for b in db.query(BatchHeader).order_by(BatchHeader.created_at.desc()).all()]
    threading.Thread(target=_sync_planning_json, args=(all_batches,), daemon=True).start()

    # Sinkronisasi ke FTP Controller OrgaTEX (192.168.1.95) di background thread khusus mesin DA01
    if mach == "DA01" and (req.status or "QUEUED").upper() in ("QUEUED", "WAITING_LA", "RUNNING"):
        def _bg_ftp_sync():
            try:
                from ..services.ftp_sync_service import sync_single_batch_to_ftp
                sync_single_batch_to_ftp(ref_no)
            except Exception as fe:
                print(f"Warning: background FTP sync on create_batch skipped: {fe}")
        threading.Thread(target=_bg_ftp_sync, daemon=True).start()

    batch_dict = _batch_to_dict(new_batch)
    return {
        "status": "success",
        "message": f"Batch {batch_dict['batch_no']} (Ref: {ref_no}) berhasil ditambahkan ke mesin {mach} di database.",
        "batch": batch_dict
    }

@router.put("/{batch_id}")
def update_batch(batch_id: str, req: UpdateBatchStatusRequest, db: Session = Depends(get_db)):
    """Mengubah status, posisi antrean, atau mesin target batch pada database."""
    target = _find_batch(db, batch_id)
    if not target:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' tidak ditemukan di database.")

    if req.status is not None:
        target.status = req.status
    if req.position is not None:
        target.position = req.position
    if req.machine_no is not None:
        new_mach = req.machine_no.strip().upper()
        # Ensure target machine exists
        m_obj = db.query(Machine).filter(Machine.machine_no == new_mach).first()
        if not m_obj:
            is_797 = new_mach in ("DA01", "M_95") or "797" in new_mach
            m_obj = Machine(
                machine_no=new_mach,
                display_name=f"SETEX 797CE Mesin {new_mach}" if is_797 else f"Mesin {new_mach}",
                ip_address="192.168.1.95" if is_797 else "172.16.110.100",
                controller_type="SETEX 797CE (Windows CE)" if is_797 else "SECOM 777 (Windows CE)",
                status="ONLINE",
                is_active=True
            )
            db.add(m_obj)
            db.commit()
        target.machine_no = new_mach

    # Sinkronisasi ke MachineQueue di database
    mq = db.query(MachineQueue).filter(MachineQueue.batch_ref_no == target.batch_ref_no).first()
    if mq:
        if req.status is not None:
            mq.status = req.status
        if req.position is not None:
            mq.position = req.position
        if req.machine_no is not None:
            mq.machine_no = target.machine_no

    db.commit()
    db.refresh(target)

    # Sinkronisasi real-time ke SQLite lokal
    try:
        from ..services.db_sync_service import DBSyncService
        DBSyncService.mirror_batch_to_sqlite(target)
    except Exception:
        pass

    import threading
    all_batches = [_batch_to_dict(b) for b in db.query(BatchHeader).all()]
    threading.Thread(target=_sync_planning_json, args=(all_batches,), daemon=True).start()

    return {"status": "success", "batch": _batch_to_dict(target)}

@router.delete("/{batch_id}")
def delete_batch(batch_id: str, db: Session = Depends(get_db)):
    """Menghapus batch dari database antrean."""
    target = _find_batch(db, batch_id)
    if not target:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' tidak ditemukan di database.")

    b_info = f"{target.batch_no} (Ref: {target.batch_ref_no})"
    b_ref = target.batch_ref_no
    b_no = target.batch_no
    db.delete(target)
    
    # Hapus juga dari MachineQueue di database
    db.query(MachineQueue).filter(
        (MachineQueue.batch_ref_no == b_ref) | (MachineQueue.batch_no == b_no)
    ).delete()
    db.commit()

    # Hapus juga dari SQLite lokal
    try:
        from ..services.db_sync_service import DBSyncService
        sq_eng = DBSyncService.get_sqlite_engine()
        with sq_eng.connect() as conn:
            conn.execute(text("DELETE FROM batch_headers WHERE batch_ref_no = :ref OR batch_no = :bno"), 
                         {"ref": b_ref, "bno": b_no})
            conn.execute(text("DELETE FROM machine_queues WHERE batch_ref_no = :ref OR batch_no = :bno"), 
                         {"ref": b_ref, "bno": b_no})
            conn.commit()
    except Exception:
        pass

    import threading
    all_batches = [_batch_to_dict(b) for b in db.query(BatchHeader).all()]
    threading.Thread(target=_sync_planning_json, args=(all_batches,), daemon=True).start()

    return {"status": "success", "message": f"Batch {b_info} telah berhasil dihapus dari database."}

@router.post("/reorder", include_in_schema=False)
@router.post("/reorder/")
def reorder_machine_queue(req: ReorderRequest, db: Session = Depends(get_db)):
    """Mengatur ulang posisi urutan (1, 2, 3...) untuk satu mesin tertentu di database."""
    mach = req.machine_no.upper()

    for idx, b_id in enumerate(req.ordered_ids, start=1):
        target = _find_batch(db, b_id)
        if target and target.machine_no == mach:
            target.position = idx
            mq = db.query(MachineQueue).filter(
                MachineQueue.machine_no == mach,
                MachineQueue.batch_ref_no == target.batch_ref_no
            ).first()
            if mq:
                mq.position = idx

    db.commit()
    import threading
    all_batches = [_batch_to_dict(b) for b in db.query(BatchHeader).all()]
    threading.Thread(target=_sync_planning_json, args=(all_batches,), daemon=True).start()

    # Sinkronisasi antrean ke FTP Controller untuk mesin DA01 di background thread
    if mach == "DA01":
        def _bg_reorder_ftp():
            try:
                from ..services.ftp_sync_service import sync_all_batches_to_ftp
                sync_all_batches_to_ftp()
            except Exception as fe:
                print(f"Warning: background FTP sync on reorder skipped: {fe}")
        threading.Thread(target=_bg_reorder_ftp, daemon=True).start()

    return {"status": "success", "message": f"Urutan antrean mesin {mach} berhasil diperbarui di database."}

@router.get("/queue/{machine_no}")
def get_machine_queue(machine_no: str, db: Session = Depends(get_db)):
    """
    Mengambil daftar antrean aktif untuk satu mesin langsung dari database (tabel machine_queues).
    """
    mach = machine_no.upper()
    q_items = db.query(MachineQueue).filter(
        MachineQueue.machine_no == mach
    ).order_by(MachineQueue.position.asc(), MachineQueue.id.asc()).all()

    return [
        {
            "id": q.id,
            "machine_no": q.machine_no,
            "batch_ref_no": q.batch_ref_no,
            "batch_no": q.batch_no,
            "program_no": q.program_no,
            "recipe_name": q.recipe_name,
            "position": q.position,
            "status": q.status,
            "dispatched_at": q.dispatched_at.strftime("%Y-%m-%d %H:%M:%S") if q.dispatched_at else None,
            "dispatched_to_ip": q.dispatched_to_ip
        }
        for q in q_items
    ]

@router.get("/export-zip/{batch_id}")
def export_batch_zip(batch_id: str, db: Session = Depends(get_db)):
    """
    Mengunduh berkas offline ZIP paket batch OrgaTEX dari database:
      - OT/BATCH/{ref}/BATCHREF.REF (762 byte Secom biner)
      - OT/BATCH/{ref}/M_{prog:04d}.PRG (SECOM 777 process program)
      - OT/MACHINES/{machine}/BATCHES/QUEUE.BTD (Database antrean mesin)
      - planning-manifest.json
    """
    target = _find_batch(db, batch_id)
    if not target:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' tidak ditemukan.")

    batch_dict = _batch_to_dict(target)
    prog_no = int(target.program_no or 1)
    prg_bytes = None
    if get_compiled_prg_bytes:
        try:
            prg_bytes = get_compiled_prg_bytes(prog_no)
        except Exception:
            pass

    zip_bytes = generate_batch_zip(batch_dict, prg_bytes=prg_bytes, include_queue=True)
    ref = target.batch_ref_no
    lot = target.batch_no or "PLAN"
    filename = f"Batch_{ref}_{lot}.zip"

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/export-queue-btd/{machine_no}")
def export_machine_queue_btd(machine_no: str, db: Session = Depends(get_db)):
    """
    Mengunduh langsung berkas biner QUEUE.BTD (12.288 byte) untuk satu mesin tertentu.
    """
    mach = machine_no.upper()
    batches = db.query(BatchHeader).filter(
        BatchHeader.machine_no == mach,
        BatchHeader.status.in_(["QUEUED", "WAITING_LA", "RUNNING"])
    ).all()
    if not batches:
        raise HTTPException(status_code=404, detail=f"Tidak ada batch antrean aktif (QUEUED/WAITING_LA/RUNNING) untuk mesin '{mach}'.")

    batches_dicts = [_batch_to_dict(b) for b in batches]
    batches_dicts.sort(key=lambda x: (int(x.get("position", 1) or 1), str(x.get("id", ""))))

    q_records = []
    for idx, b in enumerate(batches_dicts, start=1):
        ref_no = str(b.get("reference_no", "062340")).zfill(6)
        prog_no = int(b.get("program_no", 1))
        custom_params = build_batchref_custom_params(
            fabric_weight=float(b.get("fabric_weight_kg", 350.0)),
            parameters=b.get("parameters")
        )
        custom_texts = {8: str(b["note1"])} if b.get("note1") else None
        batchref_bin = create_batchref_binary(
            reference_no=ref_no,
            machine_no=mach,
            batch_no=str(b.get("batch_no", f"LOT-{ref_no}")),
            program_no=prog_no,
            recipe_no=b.get("recipe_name", ""),
            customer=b.get("customer", ""),
            article=b.get("article", ""),
            color_code=b.get("color_code", ""),
            color_name=b.get("color_name", ""),
            fabric_weight=float(b.get("fabric_weight_kg", 350.0)),
            program_title=b.get("recipe_name", f"Prog {prog_no}"),
            custom_texts=custom_texts,
            custom_params=custom_params
        )
        q_rec = bytearray(batchref_bin[:759])
        struct.pack_into("<HH", q_rec, 755, 0, idx)
        q_records.append(bytes(q_rec))

    q_bytes = generate_queue_btd(q_records, mach)
    if not q_bytes:
        raise HTTPException(
            status_code=500,
            detail="Gagal mengompilasi berkas QUEUE.BTD dengan QueueTool.exe. Pastikan backend dijalankan di lingkungan Windows (native) karena QueueTool & BtrieveInterface.dll memerlukan subsistem Windows 32-bit."
        )

    return Response(
        content=q_bytes,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename=QUEUE_{mach}.BTD"}
    )

@router.get("/export-multi-zip", include_in_schema=False)
@router.get("/export-multi-zip/")
@router.post("/export-multi-zip", include_in_schema=False)
@router.post("/export-multi-zip/")
def export_multi_batches(req: Optional[MultiExportRequest] = None, db: Session = Depends(get_db)):
    """
    Mengunduh berkas offline ZIP paket multi-batch OrgaTEX:
      - OT/BATCH/{ref}/BATCHREF.REF untuk tiap batch
      - OT/BATCH/{ref}/M_{prog}.PRG untuk tiap program
      - OT/MACHINES/{machine}/BATCHES/QUEUE.BTD (antrean gabungan per mesin)
      - planning-manifest.json
    """
    all_records = db.query(BatchHeader).all()
    all_dicts = [_batch_to_dict(b) for b in all_records]

    if req and req.batch_ids:
        clean_ids = [str(x).strip() for x in req.batch_ids]
        selected = [
            b for b in all_dicts 
            if b["id"] in clean_ids or b["reference_no"] in clean_ids or str(b["db_id"]) in clean_ids
        ]
    else:
        selected = all_dicts

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

@router.post("/dispatch", include_in_schema=False)
@router.post("/dispatch/")
def dispatch_to_machine(batch_no: str, db: Session = Depends(get_db)):
    """
    Dispatch status batch ke 'WAITING_LA' di database.
    """
    target = _find_batch(db, batch_no)
    if not target:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_no}' tidak ditemukan di database.")

    target.status = "WAITING_LA"
    db.commit()

    import threading
    all_batches = [_batch_to_dict(b) for b in db.query(BatchHeader).all()]
    threading.Thread(target=_sync_planning_json, args=(all_batches,), daemon=True).start()

    # Sinkronisasi ke FTP Controller untuk mesin DA01 di background thread
    mach_code = str(target.machine_no or "DA01").strip().upper()
    if mach_code == "DA01":
        ref_to_sync = str(target.batch_ref_no).strip().zfill(6)
        def _bg_dispatch_ftp():
            try:
                from ..services.ftp_sync_service import sync_single_batch_to_ftp
                sync_single_batch_to_ftp(ref_to_sync)
            except Exception as fe:
                print(f"Warning: background FTP sync on dispatch skipped: {fe}")
        threading.Thread(target=_bg_dispatch_ftp, daemon=True).start()

    b_dict = _batch_to_dict(target)
    return {
        "status": "dispatched_virtual",
        "write_mode": "DATABASE_MANAGED",
        "message": f"Status Batch {b_dict['batch_no']} (Ref: {b_dict['reference_no']}) diubah ke 'WAITING_LA'.",
        "batch": b_dict
    }
