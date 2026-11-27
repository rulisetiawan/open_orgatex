"""
OpenOrgaTEX FTP Controller Communication & Remote File Manager
Enables direct communication with SETEX 777CE / Windows CE controller FTP servers (Port 21).
Provides directory browsing, file downloading, uploading, STATUS.ACT telemetry inspection,
and batch program dispatching.
"""

import os
import io
import ftplib
import socket
import base64
import json
import struct
import logging
import posixpath
import concurrent.futures
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Response, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.schema_pg import Machine, MachineFtpStatus
from ..services.reader import SetexFolderReader
from ..services.ftp_sync_service import _safe_write_file, sync_userconf_to_ftp
from ..utils.btd_codec import read_queue_btd, inspect_btd_refs, build_queue_btd_python
from ..utils.secom_codec import (
    create_batchref_binary,
    build_minimal_prg,
    generate_batch_zip,
    generate_queue_btd
)

logger = logging.getLogger("orgatex.ftp")
router = APIRouter(prefix="/api/ftp", tags=["FTP Controller"])

# Paths to planning and machines
PLANNING_PATH = os.path.abspath("./open_orgatex/backend/data/planning.json")

class FTPConnectRequest(BaseModel):
    ip: str = Field(..., description="Controller IP Address, e.g. 172.16.110.101")
    port: int = Field(21, description="FTP Port (default 21)")
    username: Optional[str] = Field("", description="Username (leave blank for anonymous)")
    password: Optional[str] = Field("", description="Password (leave blank for anonymous)")
    timeout: float = Field(5.0, description="Connection timeout in seconds")

class FTPBrowseRequest(BaseModel):
    ip: str
    port: int = 21
    username: Optional[str] = ""
    password: Optional[str] = ""
    remote_path: str = Field("/Storage/sc777ce", description="Remote folder path")
    timeout: float = 6.0

class FTPReadFileRequest(BaseModel):
    ip: str
    port: int = 21
    username: Optional[str] = ""
    password: Optional[str] = ""
    remote_path: str
    as_binary: bool = False
    timeout: float = 6.0

class FTPUploadRequest(BaseModel):
    ip: str
    port: int = 21
    username: Optional[str] = ""
    password: Optional[str] = ""
    target_dir: str = "/Storage/sc777ce"
    file_name: str
    content_base64: Optional[str] = None
    content_text: Optional[str] = None

class FTPDispatchBatchRequest(BaseModel):
    ip: str
    port: int = 21
    username: Optional[str] = ""
    password: Optional[str] = ""
    batch_id: str
    target_dir: Optional[str] = Field(None, description="Remote target directory for batch (e.g. /Flashdisk/SC797CE/BATCH or /Storage/sc777ce/BATCH)")
    controller_type: Optional[str] = None

class FTPBulkReplaceQueueRequest(BaseModel):
    machine_no: str = "DA01"
    ip: str = "192.168.1.95"
    port: int = 21
    username: Optional[str] = ""
    password: Optional[str] = ""
    timeout: float = 12.0

class FTPCopyPasteRequest(BaseModel):
    ip: str
    port: int = 21
    username: Optional[str] = ""
    password: Optional[str] = ""
    source_path: str
    target_dir: str
    new_name: Optional[str] = None
    is_cut: bool = False
    is_dir: bool = False
    timeout: float = 15.0

class FTPDeleteRequest(BaseModel):
    ip: str
    port: int = 21
    username: Optional[str] = ""
    password: Optional[str] = ""
    remote_path: str
    is_dir: bool = False
    timeout: float = 8.0

class FTPMkdirRequest(BaseModel):
    ip: str
    port: int = 21
    username: Optional[str] = ""
    password: Optional[str] = ""
    parent_dir: str
    folder_name: str
    timeout: float = 5.0

class FTPRenameRequest(BaseModel):
    ip: str
    port: int = 21
    username: Optional[str] = ""
    password: Optional[str] = ""
    old_path: str
    new_name: str
    timeout: float = 5.0

class LocalBrowseRequest(BaseModel):
    path: Optional[str] = ""

class LocalMkdirRequest(BaseModel):
    parent_dir: str
    folder_name: str

class LocalDeleteRequest(BaseModel):
    path: str
    is_dir: bool = False

class FTPTransferRequest(BaseModel):
    ip: str
    port: int = 21
    username: Optional[str] = ""
    password: Optional[str] = ""
    direction: str  # "local_to_remote" (Upload) or "remote_to_local" (Download)
    local_path: str
    remote_path: str
    timeout: float = 20.0

# Base local host root directory
LOCAL_HOST_ROOT = "/app/sc777ce_root" if os.path.exists("/app/sc777ce_root") else (
    os.path.abspath("./open_orgatex/..") if os.path.exists("./open_orgatex") else os.path.abspath(".")
)


def _safe_ftp_close(ftp: Optional[ftplib.FTP]):
    """Safely closes an FTP connection, ignoring Windows CE abrupt disconnects on QUIT."""
    if not ftp:
        return
    try:
        ftp.quit()
    except Exception:
        try:
            ftp.close()
        except Exception:
            pass


def _get_ftp_connection(ip: str, port: int = 21, username: str = "", password: str = "", timeout: float = 4.0) -> ftplib.FTP:
    """Helper to establish an authenticated or anonymous FTP connection."""
    try:
        ftp = ftplib.FTP(timeout=timeout)
        ftp.connect(ip, port)
        if username:
            ftp.login(username, password)
        else:
            ftp.login()
        return ftp
    except (socket.timeout, TimeoutError):
        raise HTTPException(
            status_code=504,
            detail=f"Koneksi ke kontroler {ip}:{port} Timeout (Waktu Habis). Kontroler tidak merespons. Pastikan kontroler menyala dan terhubung ke jaringan LAN."
        )
    except ConnectionRefusedError:
        raise HTTPException(
            status_code=502,
            detail=f"Koneksi ke {ip}:{port} Ditolak. Port FTP 21 pada kontroler tidak aktif atau diblokir."
        )
    except OSError as e:
        err = str(e).strip() or type(e).__name__
        raise HTTPException(
            status_code=500,
            detail=f"Gangguan jaringan ke {ip}:{port}: {err}. Periksa alamat IP kontroler dan kabel jaringan."
        )


@router.post("/test")
def test_ftp_connection(req: FTPConnectRequest):
    """
    Test FTP connectivity to a SETEX controller.
    Verifies port 21 availability and login authentication.
    """
    start_time = datetime.now()
    try:
        ftp = _get_ftp_connection(req.ip, req.port, req.username, req.password, req.timeout)
        welcome = ftp.getwelcome()
        current_dir = ftp.pwd()
        
        # Test directory listing on root
        items = []
        ftp.retrlines("LIST", items.append)
        _safe_ftp_close(ftp)
        
        latency_ms = round((datetime.now() - start_time).total_seconds() * 1000, 1)
        return {
            "status": "ONLINE",
            "ip": req.ip,
            "port": req.port,
            "latency_ms": latency_ms,
            "welcome_banner": welcome,
            "initial_directory": current_dir,
            "root_item_count": len(items),
            "message": f"Koneksi FTP ke {req.ip}:{req.port} berhasil ({latency_ms} ms)."
        }
    except Exception as e:
        latency_ms = round((datetime.now() - start_time).total_seconds() * 1000, 1)
        return {
            "status": "OFFLINE",
            "ip": req.ip,
            "port": req.port,
            "latency_ms": latency_ms,
            "error": str(e),
            "message": f"Koneksi FTP gagal: {str(e)}"
        }


@router.post("/browse")
def browse_ftp_directory(req: FTPBrowseRequest):
    """
    List contents of a remote directory on the SETEX controller.
    Parses file names, sizes, directories, and timestamps.
    """
    try:
        ftp = _get_ftp_connection(req.ip, req.port, req.username, req.password, req.timeout)
        target_path = req.remote_path.strip() or "/"
        
        try:
            ftp.cwd(target_path)
        except Exception as e:
            _safe_ftp_close(ftp)
            raise HTTPException(status_code=404, detail=f"Direktori remote tidak ditemukan: {target_path} ({e})")

        current_path = ftp.pwd()
        raw_lines = []
        ftp.retrlines("LIST", raw_lines.append)
        _safe_ftp_close(ftp)

        entries = []
        for line in raw_lines:
            line_str = line.strip()
            if not line_str:
                continue

            # Standard Unix or Windows CE FTP line parsing
            # Windows CE format example: "08-14-22 09:15AM <DIR> STATUS" or "08-14-22 09:15AM 762 BATCHREF.REF"
            # Unix format: "drwxr-xr-x 2 ftp ftp 4096 Nov 12 08:30 STATUS"
            is_dir = False
            size = 0
            name = ""
            date_str = ""

            tokens = line_str.split(None, 8)
            if "<DIR>" in line_str.upper():
                is_dir = True
                # Windows CE style
                parts = line_str.split()
                if len(parts) >= 4:
                    date_str = f"{parts[0]} {parts[1]}"
                    name = " ".join(parts[3:])
                else:
                    name = parts[-1]
            elif line_str.startswith("d") and len(tokens) >= 9:
                is_dir = True
                date_str = f"{tokens[5]} {tokens[6]} {tokens[7]}"
                name = tokens[8]
            elif line_str.startswith("-") and len(tokens) >= 9:
                is_dir = False
                try:
                    size = int(tokens[4])
                except Exception:
                    size = 0
                date_str = f"{tokens[5]} {tokens[6]} {tokens[7]}"
                name = tokens[8]
            else:
                # Windows CE standard file: "MM-DD-YY  HH:MM(AM|PM)       SIZE FILENAME"
                parts = line_str.split()
                if len(parts) >= 4:
                    date_str = f"{parts[0]} {parts[1]}"
                    try:
                        size = int(parts[2].replace(",", ""))
                    except Exception:
                        size = 0
                    name = " ".join(parts[3:])
                else:
                    name = parts[-1]

            if name in (".", ".."):
                continue

            # Detect file type category
            ext = os.path.splitext(name)[1].upper()
            file_category = "OTHER"
            if is_dir:
                file_category = "DIRECTORY"
            elif ext in (".PRG", ".AWL"):
                file_category = "PROGRAM"
            elif ext in (".ACT", ".STATUS"):
                file_category = "STATUS"
            elif ext in (".REF", ".BTD"):
                file_category = "BATCH"
            elif ext in (".LOG", ".ERR"):
                file_category = "LOG"
            elif ext in (".CFG", ".INI", ".CNF"):
                file_category = "CONFIG"

            entries.append({
                "name": name,
                "is_dir": is_dir,
                "size": size,
                "date": date_str,
                "category": file_category,
                "full_path": posixpath.join(current_path, name)
            })

        # Sort: directories first, then alphabetical
        entries.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))

        return {
            "status": "success",
            "current_path": current_path,
            "ip": req.ip,
            "entries_count": len(entries),
            "entries": entries
        }

    except Exception as e:
        logger.error(f"Error browsing FTP {req.ip}:{req.port}: {e}")
        raise HTTPException(status_code=500, detail=f"Gagal membaca direktori FTP: {str(e)}")


@router.post("/read-file")
def read_remote_file(req: FTPReadFileRequest):
    """
    Read file content from controller over FTP.
    If the file is STATUS.ACT, it also automatically decodes the live Setex telemetry!
    """
    try:
        ftp = _get_ftp_connection(req.ip, req.port, req.username, req.password, req.timeout)
        bio = io.BytesIO()
        remote_clean = req.remote_path.replace("\\", "/")
        r_dir = posixpath.dirname(remote_clean)
        r_file = posixpath.basename(remote_clean)
        if r_dir:
            try:
                ftp.cwd(r_dir)
            except Exception:
                try:
                    ftp.cwd(r_dir.replace("/", "\\"))
                except Exception:
                    pass
        ftp.retrbinary(f"RETR {r_file}", bio.write)
        _safe_ftp_close(ftp)

        raw_bytes = bio.getvalue()
        file_name = os.path.basename(req.remote_path).upper()

        response_data: Dict[str, Any] = {
            "status": "success",
            "file_name": os.path.basename(req.remote_path),
            "remote_path": req.remote_path,
            "size_bytes": len(raw_bytes),
        }

        # If reading STATUS.ACT, decode Setex binary structure
        if "STATUS.ACT" in file_name or "STATUS" in file_name:
            decoded = SetexFolderReader.read_status_act(ip=req.ip, ftp_port=req.port, raw_bytes=raw_bytes)
            response_data["decoded_telemetry"] = decoded

        # Decode content as text or hex preview
        try:
            text_content = raw_bytes.decode("utf-8")
            response_data["content_type"] = "text/plain"
            response_data["text"] = text_content[:10000] # Cap preview
        except UnicodeDecodeError:
            try:
                text_content = raw_bytes.decode("latin1")
                response_data["content_type"] = "text/latin1"
                response_data["text"] = text_content[:10000]
            except Exception:
                response_data["content_type"] = "application/octet-stream"
                response_data["hex_preview"] = raw_bytes[:512].hex()

        return response_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal membaca file remote: {str(e)}")


@router.post("/dispatch-batch", include_in_schema=False)
@router.post("/dispatch-batch/")
def dispatch_batch_via_ftp(req: FTPDispatchBatchRequest):
    """
    Dispatches a production batch directly to the controller via FTP.
    Uploads:
    1. BATCHREF.REF (762-byte Secom binary structure)
    2. M_{program_no:04d}.PRG (SECOM 777 execution program)
    """
    # 1. Load batch details from planning.json or Database
    batches = []
    if os.path.exists(PLANNING_PATH):
        try:
            with open(PLANNING_PATH, "r", encoding="utf-8") as f:
                batches = json.load(f)
        except Exception:
            batches = []

    clean_id = str(req.batch_id).strip()
    clean_ref = clean_id.replace("b-", "")
    target_batch = next((
        b for b in batches 
        if b.get("id") == clean_id 
        or b.get("reference_no") == clean_ref
        or b.get("batch_no") == clean_id
        or str(b.get("db_id")) == clean_id
    ), None)

    # Database fallback if not in planning.json
    if not target_batch:
        try:
            from ..database import get_db
            from ..models.schema_pg import BatchHeader
            from .planning import _batch_to_dict
            for db in get_db():
                b_obj = db.query(BatchHeader).filter(
                    (BatchHeader.batch_ref_no == clean_ref) |
                    (BatchHeader.batch_no == clean_id)
                ).first()
                if b_obj:
                    target_batch = _batch_to_dict(b_obj)
                break
        except Exception:
            pass

    if not target_batch:
        raise HTTPException(status_code=404, detail=f"Batch dengan ID '{req.batch_id}' tidak ditemukan di sistem")

    # Semua mesin HMI kini diizinkan menerima pengiriman batch (dengan 2x konfirmasi di UI)
    mach_code = str(target_batch.get("machine_no", "DA01")).strip().upper()
    resolved_ip = (req.ip or "").strip()
    resolved_port = int(req.port or 21)
    try:
        from ..database import get_db
        from ..models.schema_pg import Machine
        for db in get_db():
            m_obj = db.query(Machine).filter(Machine.machine_no == mach_code).first()
            if m_obj and m_obj.ip_address:
                if not resolved_ip or (resolved_ip == "192.168.1.95" and mach_code not in ("DA01", "M_95")):
                    resolved_ip = m_obj.ip_address.strip()
                if m_obj.ftp_port:
                    resolved_port = int(m_obj.ftp_port)
            break
    except Exception:
        pass
    if not resolved_ip:
        raise HTTPException(status_code=400, detail=f"IP Address FTP untuk mesin '{mach_code}' tidak ditemukan.")

    ref_no = str(target_batch.get("reference_no", clean_ref)).zfill(6)
    prog_no = int(target_batch.get("program_no", 1))
    prg_name = f"M_{prog_no:04d}.PRG"

    try:
        # Generate binary files in memory (evaluasi formula parameter batch jika ada)
        prg_bytes = None
        try:
            from .programs import get_compiled_prg_bytes, get_compiled_prg_bytes_for_batch
            prg_bytes = get_compiled_prg_bytes_for_batch(prog_no, target_batch, machine_code=mach_code)
            if not prg_bytes or len(prg_bytes) < 65:
                prg_bytes = get_compiled_prg_bytes(prog_no, machine_code=mach_code)
        except Exception:
            pass
        if not prg_bytes or len(prg_bytes) < 65:
            prg_bytes = build_minimal_prg(prog_no, target_batch.get("recipe_name", "Reactive Dyeing"))

        batchref_bytes = create_batchref_binary(
            reference_no=ref_no,
            machine_no=target_batch.get("machine_no", "DA01"),
            batch_no=target_batch.get("batch_no", f"LOT-{ref_no}"),
            program_no=prog_no,
            recipe_no=target_batch.get("recipe_name", ""),
            customer=target_batch.get("customer", ""),
            article=target_batch.get("article", ""),
            color_code=target_batch.get("color_code", ""),
            color_name=target_batch.get("color_name", ""),
            fabric_weight=float(target_batch.get("fabric_weight_kg", 350.0)),
            program_title=target_batch.get("recipe_name", f"Prog {prog_no}")
        )

        ftp = _get_ftp_connection(resolved_ip, resolved_port, req.username, req.password)
        try:
            ftp.set_pasv(True)
        except Exception:
            pass
        
        # Determine target architecture:
        # Standard OrgaTEX Central Network Share: /Network/F/OT/BATCH/<ref_no>/ and /Network/F/OT/MACHINES/<machine>/BATCHES/
        is_797 = "797" in (req.controller_type or "").upper() or "SC797" in (req.target_dir or "").upper() or req.ip.strip() == "192.168.1.95"
        is_network_ot = (
            "NETWORK" in (req.target_dir or "").upper() or
            "NETWORK" in (req.controller_type or "").upper() or
            req.ip.strip() == "192.168.1.95" or
            not req.target_dir
        )

        resolved_target_dir = None
        uploaded_files = []

        if is_network_ot:
            # 1. Standard OrgaTEX Share: /Network/F/OT/BATCH/<ref_no>/
            base_batch_dir = "/Network/F/OT/BATCH"
            target_batch_folder = f"{base_batch_dir}/{ref_no}"

            # Ensure /Network/F/OT/BATCH/<ref_no> directory exists
            try:
                ftp.cwd(base_batch_dir)
            except Exception:
                try:
                    ftp.mkd("/Network")
                    ftp.mkd("/Network/F")
                    ftp.mkd("/Network/F/OT")
                    ftp.mkd(base_batch_dir)
                    ftp.cwd(base_batch_dir)
                except Exception:
                    pass

            # Pastikan USERCONF.CNF terunggah ke /Network/F/OT/PROCEDUR/100/ agar tidak error di HMI
            try:
                from ..services.ftp_sync_service import sync_userconf_to_ftp
                sync_userconf_to_ftp(ftp)
            except Exception:
                pass

            try:
                ftp.mkd(target_batch_folder)
            except Exception:
                pass

            ftp.cwd(target_batch_folder)
            resolved_target_dir = target_batch_folder

            # Upload BATCHREF.REF and Program inside the batch folder
            ftp.storbinary("STOR BATCHREF.REF", io.BytesIO(batchref_bytes))
            uploaded_files.append(f"{target_batch_folder}/BATCHREF.REF")

            ftp.storbinary(f"STOR {prg_name}", io.BytesIO(prg_bytes))
            uploaded_files.append(f"{target_batch_folder}/{prg_name}")

            # =========================================================================
            # 2. Dynamic QUEUE.BTD Generation (APPEND MODE) & Database Sync
            # =========================================================================
            mach_code = str(target_batch.get("machine_no", "DA01")).strip().upper()
            mach_queue_dir = f"/Network/F/OT/MACHINES/{mach_code}/BATCHES"
            try:
                ftp.cwd(mach_queue_dir)
            except Exception:
                for p in ["/Network", "/Network/F", "/Network/F/OT", "/Network/F/OT/MACHINES", f"/Network/F/OT/MACHINES/{mach_code}", mach_queue_dir]:
                    try: ftp.mkd(p)
                    except Exception: pass
                try: ftp.cwd(mach_queue_dir)
                except Exception: pass

            # A. Coba baca QUEUE.BTD yang sudah ada di remote kontroler HMI via Python
            remote_existing_records = []
            try:
                remote_btd_bio = io.BytesIO()
                ftp.cwd(mach_queue_dir)
                ftp.retrbinary("RETR QUEUE.BTD", remote_btd_bio.write)
                remote_data = remote_btd_bio.getvalue()
                if remote_data and len(remote_data) >= 1024:
                    remote_existing_records = read_queue_btd(remote_data)
            except Exception:
                remote_existing_records = []

            # Buat record 759-byte untuk batch yang baru dikirim
            new_batch_rec = bytearray(batchref_bytes[:759])

            q_records = []
            found_in_remote = False
            for r in remote_existing_records:
                if r.get("ref") == ref_no:
                    # Update record jika batch sudah ada sebelumnya di antrean
                    q_records.append(new_batch_rec)
                    found_in_remote = True
                else:
                    # Pertahankan record lama dari remote
                    raw = r.get("raw_record")
                    if raw and len(raw) >= 759:
                        q_records.append(bytearray(raw[:759]))

            if not found_in_remote:
                # Batch baru: tambahkan di akhir antrean (APPEND)
                q_records.append(new_batch_rec)

            # Re-index posisi 1..N pada offset 755..758
            final_records_759 = []
            for idx, rec in enumerate(q_records, start=1):
                struct.pack_into("<HH", rec, 755, 0, idx)
                final_records_759.append(bytes(rec))

            # B. Kompilasi Btrieve QUEUE.BTD biner secara murni di Python (tanpa QueueTool)
            btd_data = generate_queue_btd(final_records_759, mach_code)

            # Simpan cermin lokal
            local_btd_path = os.path.abspath(f"./open_orgatex/backend/data/OT/MACHINES/{mach_code}/BATCHES/QUEUE.BTD")
            if btd_data:
                _safe_write_file(local_btd_path, btd_data)

            # C. Unggah berkas QUEUE.BTD hasil append ke FTP Controller
            if btd_data:
                try:
                    ftp.cwd(mach_queue_dir)
                    ftp.storbinary("STOR QUEUE.BTD", io.BytesIO(btd_data))
                    uploaded_files.append(f"{mach_queue_dir}/QUEUE.BTD ({len(final_records_759)} batch dalam antrean)")
                    logger.info(f"Berhasil mengunggah QUEUE.BTD ke {mach_queue_dir} dengan {len(final_records_759)} antrean batch.")
                except Exception as e:
                    logger.warning(f"Notice: Failed to upload QUEUE.BTD in {mach_queue_dir}: {e}")

            # D. Update database (MachineQueue & BatchHeader)
            try:
                from ..database import get_db
                from ..models.schema_pg import BatchHeader, MachineQueue

                for db in get_db():
                    # Update status di BatchHeader
                    b_rec = db.query(BatchHeader).filter(
                        (BatchHeader.batch_ref_no == clean_ref) |
                        (BatchHeader.batch_no == clean_id)
                    ).first()
                    if b_rec:
                        b_rec.status = "WAITING_LA"
                        b_rec.machine_no = mach_code

                    # Update atau insert ke MachineQueue
                    mq_item = db.query(MachineQueue).filter(
                        MachineQueue.machine_no == mach_code,
                        MachineQueue.batch_ref_no == clean_ref
                    ).first()

                    if mq_item:
                        mq_item.status = "WAITING_LA"
                        mq_item.position = len(final_records_759) if not found_in_remote else mq_item.position
                        mq_item.dispatched_at = datetime.now()
                        mq_item.dispatched_to_ip = req.ip
                    else:
                        mq_item = MachineQueue(
                            machine_no=mach_code,
                            batch_ref_no=clean_ref,
                            batch_no=target_batch.get("batch_no") or f"LOT-{clean_ref}",
                            program_no=prog_no,
                            recipe_name=target_batch.get("recipe_name"),
                            customer=target_batch.get("customer"),
                            article=target_batch.get("article"),
                            color_code=target_batch.get("color_code"),
                            color_name=target_batch.get("color_name"),
                            fabric_weight_kg=float(target_batch.get("fabric_weight_kg") or 350.0),
                            liquor_ratio=float(target_batch.get("liquor_ratio") or 8.0),
                            total_water_l=float(target_batch.get("total_water_l") or 2800.0),
                            position=len(final_records_759),
                            status="WAITING_LA",
                            dispatched_at=datetime.now(),
                            dispatched_to_ip=req.ip
                        )
                        db.add(mq_item)
                    if b_rec and mq_item:
                        b_rec.position = mq_item.position

                    db.commit()
                    break
            except Exception as q_err:
                logger.warning(f"Database queue update warning: {q_err}")

        else:
            # Standalone Local Controller Fallback (e.g. /Flashdisk/SC797CE/BATCH or /Storage/sc777ce/BATCH)
            is_797 = "797" in (req.controller_type or "").upper() or "SC797" in (req.target_dir or "").upper()
            primary_dir = req.target_dir.rstrip("/\\") if req.target_dir else ("/Flashdisk/SC797CE/BATCH" if is_797 else "/Storage/sc777ce/BATCH")

            candidate_dirs = [primary_dir, primary_dir.replace("/", "\\"), primary_dir.replace("\\", "/")]
            for cand in candidate_dirs:
                try:
                    ftp.cwd(cand)
                    resolved_target_dir = cand
                    break
                except Exception:
                    continue

            if not resolved_target_dir:
                try:
                    ftp.mkd(primary_dir)
                    ftp.cwd(primary_dir)
                    resolved_target_dir = primary_dir
                except Exception:
                    resolved_target_dir = primary_dir

            # Upload BATCHREF.REF & M_xxxx.PRG
            ftp.storbinary("STOR BATCHREF.REF", io.BytesIO(batchref_bytes))
            uploaded_files.append("BATCHREF.REF")

            ftp.storbinary(f"STOR {prg_name}", io.BytesIO(prg_bytes))
            uploaded_files.append(prg_name)

            # Update Database & Upload QUEUE.BTD ke controller lokal
            mach_code = str(target_batch.get("machine_no", "DA01")).upper()
            queue_records_db = []
            try:
                from ..database import get_db
                from ..models.schema_pg import BatchHeader, MachineQueue

                for db in get_db():
                    b_rec = db.query(BatchHeader).filter(
                        (BatchHeader.batch_ref_no == clean_ref) |
                        (BatchHeader.batch_no == clean_id)
                    ).first()
                    if b_rec:
                        b_rec.status = "WAITING_LA"
                        b_rec.machine_no = mach_code

                    mq_item = db.query(MachineQueue).filter(
                        MachineQueue.machine_no == mach_code,
                        MachineQueue.batch_ref_no == clean_ref
                    ).first()

                    if mq_item:
                        mq_item.status = "WAITING_LA"
                        mq_item.dispatched_at = datetime.now()
                        mq_item.dispatched_to_ip = req.ip
                        if b_rec:
                            b_rec.position = mq_item.position
                    else:
                        max_pos = db.query(func.max(MachineQueue.position)).filter(
                            MachineQueue.machine_no == mach_code
                        ).scalar() or 0
                        new_pos = max_pos + 1
                        mq_item = MachineQueue(
                            machine_no=mach_code,
                            batch_ref_no=clean_ref,
                            batch_no=target_batch.get("batch_no") or f"LOT-{clean_ref}",
                            program_no=prog_no,
                            recipe_name=target_batch.get("recipe_name"),
                            customer=target_batch.get("customer"),
                            article=target_batch.get("article"),
                            color_code=target_batch.get("color_code"),
                            color_name=target_batch.get("color_name"),
                            fabric_weight_kg=float(target_batch.get("fabric_weight_kg") or 350.0),
                            liquor_ratio=float(target_batch.get("liquor_ratio") or 8.0),
                            total_water_l=float(target_batch.get("total_water_l") or 2800.0),
                            position=new_pos,
                            status="WAITING_LA",
                            dispatched_at=datetime.now(),
                            dispatched_to_ip=req.ip
                        )
                        db.add(mq_item)
                        if b_rec:
                            b_rec.position = new_pos

                    db.commit()

                    queue_records_db = db.query(MachineQueue).filter(
                        MachineQueue.machine_no == mach_code,
                        MachineQueue.status.in_(["QUEUED", "WAITING_LA", "RUNNING"])
                    ).order_by(MachineQueue.position.asc(), MachineQueue.id.asc()).all()
                    break
            except Exception as q_err:
                logger.warning(f"Database queue update warning (standalone): {q_err}")

            q_records = []
            if queue_records_db:
                for idx, q in enumerate(queue_records_db, start=1):
                    q_ref = str(q.batch_ref_no).zfill(6)
                    q_prog = int(q.program_no or 1)
                    q_bref = create_batchref_binary(
                        reference_no=q_ref,
                        machine_no=mach_code,
                        batch_no=str(q.batch_no or f"LOT-{q_ref}"),
                        program_no=q_prog,
                        recipe_no=q.recipe_name or "",
                        customer=q.customer or "",
                        article=q.article or "",
                        color_code=q.color_code or "",
                        color_name=q.color_name or "",
                        fabric_weight=float(q.fabric_weight_kg or 350.0),
                        program_title=q.recipe_name or f"Prog {q_prog}"
                    )
                    q_rec = bytearray(q_bref[:759])
                    struct.pack_into("<HH", q_rec, 755, 0, idx)
                    q_records.append(bytes(q_rec))

            btd_data = None
            if q_records:
                try:
                    btd_data = generate_queue_btd(q_records, mach_code)
                except Exception as e:
                    logger.warning(f"Gagal generate_queue_btd: {e}")

            local_btd_path = os.path.abspath(f"./open_orgatex/backend/data/OT/MACHINES/{mach_code}/BATCHES/QUEUE.BTD")
            if btd_data:
                os.makedirs(os.path.dirname(local_btd_path), exist_ok=True)
                with open(local_btd_path, "wb") as f_btd:
                    f_btd.write(btd_data)
            elif os.path.exists(local_btd_path):
                with open(local_btd_path, "rb") as f_btd:
                    btd_data = f_btd.read()

            if btd_data:
                try:
                    ftp.storbinary("STOR QUEUE.BTD", io.BytesIO(btd_data))
                    uploaded_files.append(f"QUEUE.BTD ({len(q_records)} batch dalam antrean)")
                except Exception as e:
                    logger.warning(f"Notice: Upload QUEUE.BTD skipped: {e}")
        
        _safe_ftp_close(ftp)

        # Update batch status in planning.json & sync local queue files
        target_batch["status"] = "WAITING_LA"
        target_batch["dispatched_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        target_batch["dispatched_to_ip"] = req.ip

        try:
            from .planning import _sync_planning_json, _batch_to_dict
            from ..database import get_db
            from ..models.schema_pg import BatchHeader
            for db in get_db():
                all_batches = [_batch_to_dict(b) for b in db.query(BatchHeader).all()]
                _sync_planning_json(all_batches)
                break
        except Exception:
            with open(PLANNING_PATH, "w", encoding="utf-8") as f:
                json.dump(batches, f, indent=2)

        return {
            "status": "success",
            "message": f"Batch {target_batch.get('batch_no')} (Ref: {ref_no}) berhasil dikirim ke {resolved_target_dir} ({req.ip}) via FTP!",
            "uploaded_files": uploaded_files,
            "destination_dir": resolved_target_dir,
            "ip": req.ip,
            "controller_type": "OrgaTEX Network Share" if is_network_ot else ("SETEX 797CE" if is_797 else "SETEX 777"),
            "batch": target_batch
        }

    except HTTPException:
        raise
    except Exception as e:
        err_msg = str(e).strip() or f"{type(e).__name__} (Koneksi ke {req.ip}:{req.port} terputus atau kontroler tidak merespons)"
        logger.error(f"FTP dispatch failed: {err_msg}")
        raise HTTPException(status_code=500, detail=f"Pengiriman batch via FTP gagal: {err_msg}")


@router.post("/upload")
def upload_file_to_ftp(req: FTPUploadRequest):
    """Uploads a file to the SETEX controller via FTP using Base64 or plain text."""
    try:
        if req.content_base64:
            content = base64.b64decode(req.content_base64)
        elif req.content_text:
            content = req.content_text.encode("latin1", errors="ignore")
        else:
            raise HTTPException(status_code=400, detail="Tidak ada konten berkas yang diberikan")

        ftp = _get_ftp_connection(req.ip, req.port, req.username, req.password)
        
        target_dir = req.target_dir.rstrip("/")
        try:
            ftp.cwd(target_dir)
        except Exception:
            try:
                ftp.mkd(target_dir)
                ftp.cwd(target_dir)
            except Exception:
                pass

        file_name = req.file_name
        ftp.storbinary(f"STOR {file_name}", io.BytesIO(content))
        _safe_ftp_close(ftp)

        return {
            "status": "success",
            "message": f"Berkas '{file_name}' ({len(content)} bytes) berhasil diunggah ke '{target_dir}'.",
            "file_name": file_name,
            "target_dir": target_dir,
            "size_bytes": len(content)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengunggah file via FTP: {str(e)}")


@router.get("/download")
def download_file_from_ftp(ip: str, remote_path: str, port: int = 21, username: str = "", password: str = ""):
    """Downloads a file from the controller over FTP as a direct browser attachment."""
    try:
        ftp = _get_ftp_connection(ip, port, username, password)
        bio = io.BytesIO()
        remote_clean = remote_path.replace("\\", "/")
        r_dir = posixpath.dirname(remote_clean)
        r_file = posixpath.basename(remote_clean)
        if r_dir:
            try:
                ftp.cwd(r_dir)
            except Exception:
                try:
                    ftp.cwd(r_dir.replace("/", "\\"))
                except Exception:
                    pass
        ftp.retrbinary(f"RETR {r_file}", bio.write)
        _safe_ftp_close(ftp)

        file_bytes = bio.getvalue()
        file_name = r_file

        return Response(
            content=file_bytes,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename={file_name}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengunduh file via FTP: {str(e)}")


@router.get("/live-status")
def get_live_controller_status(ip: str, port: int = 21):
    """Directly queries and decodes STATUS.ACT from the controller over FTP."""
    status_data = SetexFolderReader.read_status_act(ip=ip, ftp_port=port)
    return {
        "status": "success",
        "ip": ip,
        "port": port,
        "telemetry": status_data
    }


def _copy_ftp_single_file(ftp: ftplib.FTP, src: str, dst: str):
    """Stream file from src and save to dst using in-memory buffer."""
    bio = io.BytesIO()
    src_clean = src.replace("\\", "/")
    src_dir = posixpath.dirname(src_clean)
    src_file = posixpath.basename(src_clean)
    if src_dir:
        try:
            ftp.cwd(src_dir)
        except Exception:
            pass
    ftp.retrbinary(f"RETR {src_file}", bio.write)
    bio.seek(0)
    dst_clean = dst.replace("\\", "/")
    dst_dir = posixpath.dirname(dst_clean)
    dst_file = posixpath.basename(dst_clean)
    if dst_dir:
        try:
            ftp.cwd(dst_dir)
        except Exception:
            pass
    ftp.storbinary(f"STOR {dst_file}", bio)


@router.post("/copy-paste")
def copy_paste_ftp(req: FTPCopyPasteRequest):
    """
    Copy or Move (Cut) file/directory within the remote FTP controller.
    Supports duplicate rename if source and target have identical paths.
    """
    try:
        ftp = _get_ftp_connection(req.ip, req.port, req.username, req.password, req.timeout)
        src_path = req.source_path.strip()
        target_dir = req.target_dir.rstrip("/") or "/"
        base_name = req.new_name or os.path.basename(src_path)
        target_path = posixpath.join(target_dir, base_name)

        # Prevent overwriting same file by appending _copy
        if src_path == target_path and not req.is_cut:
            name, ext = os.path.splitext(base_name)
            base_name = f"{name}_copy{ext}"
            target_path = posixpath.join(target_dir, base_name)

        # Ensure target directory exists
        try:
            ftp.cwd(target_dir)
        except Exception:
            try:
                ftp.mkd(target_dir)
            except Exception:
                pass

        if req.is_cut:
            # Cut/Move: Rename is instant on FTP
            try:
                ftp.rename(src_path, target_path)
                _safe_ftp_close(ftp)
                return {
                    "status": "success",
                    "action": "cut",
                    "message": f"'{base_name}' berhasil dipindahkan ke '{target_dir}'.",
                    "source": src_path,
                    "destination": target_path
                }
            except Exception as rename_err:
                # Fallback to copy + delete if rename fails
                if not req.is_dir:
                    _copy_ftp_single_file(ftp, src_path, target_path)
                    ftp.delete(src_path)
                    _safe_ftp_close(ftp)
                    return {
                        "status": "success",
                        "action": "cut",
                        "message": f"'{base_name}' berhasil dipindahkan ke '{target_dir}' (via copy-delete).",
                        "source": src_path,
                        "destination": target_path
                    }
                _safe_ftp_close(ftp)
                raise rename_err
        else:
            # Copy file
            if req.is_dir:
                try:
                    ftp.mkd(target_path)
                except Exception:
                    pass
                _safe_ftp_close(ftp)
                return {
                    "status": "success",
                    "action": "copy",
                    "message": f"Direktori '{base_name}' berhasil dibuat di '{target_dir}'.",
                    "source": src_path,
                    "destination": target_path
                }
            else:
                _copy_ftp_single_file(ftp, src_path, target_path)
                _safe_ftp_close(ftp)
                return {
                    "status": "success",
                    "action": "copy",
                    "message": f"Berkas '{base_name}' berhasil disalin ke '{target_dir}'.",
                    "source": src_path,
                    "destination": target_path
                }
    except Exception as e:
        logger.error(f"Error copy-paste FTP: {e}")
        raise HTTPException(status_code=500, detail=f"Gagal melakukan copy/paste: {str(e)}")


@router.post("/delete")
def delete_ftp_item(req: FTPDeleteRequest):
    """Delete a file or directory from the controller via FTP."""
    try:
        ftp = _get_ftp_connection(req.ip, req.port, req.username, req.password, req.timeout)
        if req.is_dir:
            try:
                ftp.rmd(req.remote_path)
            except Exception as e:
                _safe_ftp_close(ftp)
                raise HTTPException(status_code=400, detail=f"Gagal menghapus direktori (pastikan direktori kosong): {str(e)}")
        else:
            ftp.delete(req.remote_path)
        _safe_ftp_close(ftp)
        return {
            "status": "success",
            "message": f"'{os.path.basename(req.remote_path)}' berhasil dihapus.",
            "path": req.remote_path
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal menghapus: {str(e)}")


@router.post("/mkdir")
def create_ftp_folder(req: FTPMkdirRequest):
    """Create a new folder in remote directory."""
    try:
        ftp = _get_ftp_connection(req.ip, req.port, req.username, req.password, req.timeout)
        target_path = posixpath.join(req.parent_dir.rstrip("/"), req.folder_name.strip())
        ftp.mkd(target_path)
        _safe_ftp_close(ftp)
        return {
            "status": "success",
            "message": f"Direktori '{req.folder_name}' berhasil dibuat.",
            "path": target_path
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal membuat direktori: {str(e)}")


@router.post("/rename")
def rename_ftp_item(req: FTPRenameRequest):
    """Rename a file or folder on FTP controller."""
    try:
        ftp = _get_ftp_connection(req.ip, req.port, req.username, req.password, req.timeout)
        parent_dir = os.path.dirname(req.old_path)
        new_path = posixpath.join(parent_dir, req.new_name.strip())
        ftp.rename(req.old_path, new_path)
        _safe_ftp_close(ftp)
        return {
            "status": "success",
            "message": f"Berhasil diubah nama menjadi '{req.new_name}'.",
            "new_path": new_path
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengubah nama: {str(e)}")


def resolve_target_local_path(req_path: Optional[str]) -> str:
    p = (req_path or "").strip().replace("\\", "/")
    if not p:
        return LOCAL_HOST_ROOT
    
    # Windows drive translation if running inside container with mounted host drives
    if os.path.exists("/host_c"):
        if p.upper().startswith("C:/"):
            p = "/host_c/" + p[3:].lstrip("/")
        elif p.upper() in ("C:", "C:/"):
            p = "/host_c"
    if os.path.exists("/host_d"):
        if p.upper().startswith("D:/"):
            p = "/host_d/" + p[3:].lstrip("/")
        elif p.upper() in ("D:", "D:/"):
            p = "/host_d"

    if os.path.isabs(p) and os.path.exists(p):
        return p

    rel = os.path.normpath(os.path.join(LOCAL_HOST_ROOT, p.lstrip("/\\"))).replace("\\", "/")
    if os.path.exists(rel):
        return rel

    if os.path.exists(p):
        return p
    return LOCAL_HOST_ROOT


@router.post("/local/browse")
def browse_local_directory(req: LocalBrowseRequest):
    """Browse files and folders on the local host / server machine."""
    try:
        target = resolve_target_local_path(req.path)

        entries = []
        try:
            items = os.listdir(target)
        except PermissionError:
            raise HTTPException(status_code=403, detail=f"Akses ditolak ke direktori '{target}'")

        for item in items:
            item_path = os.path.join(target, item)
            try:
                is_dir = os.path.isdir(item_path)
            except Exception:
                is_dir = False

            try:
                size = 0 if is_dir else os.path.getsize(item_path)
            except Exception:
                size = 0

            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(item_path)).strftime('%m-%d-%y %H:%M')
            except Exception:
                mtime = "-"

            ext = os.path.splitext(item)[1].upper()
            file_category = "OTHER"
            if is_dir:
                file_category = "DIRECTORY"
            elif ext in (".PRG", ".AWL"):
                file_category = "PROGRAM"
            elif ext in (".ACT", ".STATUS"):
                file_category = "STATUS"
            elif ext in (".REF", ".BTD"):
                file_category = "BATCH"
            elif ext in (".LOG", ".ERR"):
                file_category = "LOG"
            elif ext in (".CFG", ".INI", ".CNF"):
                file_category = "CONFIG"

            entries.append({
                "name": item,
                "is_dir": is_dir,
                "size": size,
                "date": mtime,
                "category": file_category,
                "full_path": item_path.replace("\\", "/")
            })

        entries.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
        
        norm_target = target.replace("\\", "/").rstrip("/")
        if not norm_target or norm_target in ("/", "C:", "D:"):
            parent_path = ""
        else:
            parent_path = os.path.dirname(norm_target).replace("\\", "/") or "/"

        # Available quick host locations
        locations = [
            {"name": "📂 Proyek DA-TEX (Root)", "path": LOCAL_HOST_ROOT.replace("\\", "/")},
            {"name": "📂 Programs (PRG Resep)", "path": posixpath.join(LOCAL_HOST_ROOT.replace("\\", "/"), "Programs")},
            {"name": "📂 OrgaTex_Share", "path": posixpath.join(LOCAL_HOST_ROOT.replace("\\", "/"), "OrgaTex_Share")},
            {"name": "📂 STATUS Telemetri", "path": posixpath.join(LOCAL_HOST_ROOT.replace("\\", "/"), "STATUS")},
            {"name": "📂 plain_export", "path": posixpath.join(LOCAL_HOST_ROOT.replace("\\", "/"), "plain_export")}
        ]
        if os.path.exists("/host_c"):
            locations.append({"name": "💻 Drive C:\\ (Seluruh Host PC)", "path": "/host_c"})
        if os.path.exists("/host_d"):
            locations.append({"name": "💻 Drive D:\\ (Host Drive)", "path": "/host_d"})
        if os.path.exists("/app"):
            locations.append({"name": "📁 Folder Aplikasi (/app)", "path": "/app"})

        return {
            "status": "success",
            "current_path": target.replace("\\", "/"),
            "parent_path": parent_path,
            "root_path": LOCAL_HOST_ROOT.replace("\\", "/"),
            "available_locations": locations,
            "entries_count": len(entries),
            "entries": entries
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error browsing local directory: {e}")
        raise HTTPException(status_code=500, detail=f"Gagal membaca folder lokal: {str(e)}")


@router.post("/transfer")
def transfer_ftp_file(req: FTPTransferRequest):
    """Transfer file between local host and remote FTP controller (Upload / Download)."""
    try:
        ftp = _get_ftp_connection(req.ip, req.port, req.username, req.password, req.timeout)
        
        if req.direction == "local_to_remote":
            # Upload from local host to remote FTP controller
            local_src = resolve_target_local_path(req.local_path)
            if not os.path.isfile(local_src):
                _safe_ftp_close(ftp)
                raise HTTPException(status_code=404, detail=f"Berkas lokal '{req.local_path}' tidak ditemukan.")

            file_name = os.path.basename(local_src)
            remote_target_dir = req.remote_path.rstrip("/") or "/"
            remote_target_file = posixpath.join(remote_target_dir, file_name)

            try:
                ftp.cwd(remote_target_dir)
            except Exception:
                try:
                    ftp.mkd(remote_target_dir)
                    ftp.cwd(remote_target_dir)
                except Exception:
                    pass

            with open(local_src, "rb") as f:
                ftp.storbinary(f"STOR {file_name}", f)

            _safe_ftp_close(ftp)
            return {
                "status": "success",
                "direction": "local_to_remote",
                "message": f"Berkas '{file_name}' berhasil diunggah dari Lokal ke Remote '{remote_target_dir}'.",
                "source": req.local_path,
                "destination": remote_target_file
            }

        elif req.direction == "remote_to_local":
            # Download from remote FTP controller to local host
            remote_clean = req.remote_path.replace("\\", "/")
            file_name = posixpath.basename(remote_clean)
            remote_dir = posixpath.dirname(remote_clean)
            local_target_dir = resolve_target_local_path(req.local_path)

            if os.path.isdir(local_target_dir):
                local_target_file = os.path.join(local_target_dir, file_name)
            else:
                local_target_file = local_target_dir

            os.makedirs(os.path.dirname(local_target_file), exist_ok=True)

            if remote_dir:
                try:
                    ftp.cwd(remote_dir)
                except Exception:
                    try:
                        ftp.cwd(remote_dir.replace("/", "\\"))
                    except Exception:
                        pass

            with open(local_target_file, "wb") as f:
                ftp.retrbinary(f"RETR {file_name}", f.write)

            _safe_ftp_close(ftp)
            return {
                "status": "success",
                "direction": "remote_to_local",
                "message": f"Berkas '{file_name}' berhasil diunduh dari Remote ke Lokal '{local_target_file.replace(chr(92), '/')}'.",
                "source": req.remote_path,
                "destination": local_target_file.replace("\\", "/")
            }
        else:
            _safe_ftp_close(ftp)
            raise HTTPException(status_code=400, detail=f"Arah transfer tidak valid: {req.direction}")

    except Exception as e:
        logger.error(f"Error transferring file: {e}")
        raise HTTPException(status_code=500, detail=f"Gagal transfer berkas: {str(e)}")


@router.post("/local/mkdir")
def create_local_folder(req: LocalMkdirRequest):
    """Create directory on local host."""
    try:
        parent = os.path.normpath(req.parent_dir)
        target = os.path.join(parent, req.folder_name.strip())
        os.makedirs(target, exist_ok=True)
        return {
            "status": "success",
            "message": f"Folder lokal '{req.folder_name}' berhasil dibuat.",
            "path": target.replace("\\", "/")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal membuat folder lokal: {str(e)}")


@router.post("/local/delete")
def delete_local_item(req: LocalDeleteRequest):
    """Delete file or directory on local host."""
    try:
        target = os.path.normpath(req.path)
        if req.is_dir:
            import shutil
            shutil.rmtree(target)
        else:
            os.remove(target)
        return {
            "status": "success",
            "message": f"'{os.path.basename(target)}' berhasil dihapus dari folder lokal."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal menghapus file lokal: {str(e)}")


@router.post("/sync-all-batch-folders")
def sync_all_batch_folders():
    """
    Sinkronisasi seluruh batch_ref_no dari database menjadi folder baru di:
    ftp://192.168.1.95/Network/F/OT/BATCH/<batch_ref_no>/
    dengan isi:
      - BATCHREF.REF (762-byte Secom biner)
      - M_<program_no:04d>.PRG (program celup biner)
    Serta dicadangkan di open_orgatex/backend/data/OT/BATCH/<batch_ref_no>/
    """
    try:
        try:
            from ..services.ftp_sync_service import sync_all_batches_to_ftp
        except ImportError:
            try:
                from open_orgatex.backend.services.ftp_sync_service import sync_all_batches_to_ftp
            except ImportError:
                from sync_batches_to_ftp import sync_all_batches_to_ftp

        results = sync_all_batches_to_ftp()
        synced_count = sum(1 for r in results if r.get("ftp_synced"))
        return {
            "status": "success",
            "total_batches": len(results),
            "ftp_synced_count": synced_count,
            "batches": results,
            "message": f"Berhasil memproses {len(results)} folder batch. {synced_count} folder berhasil disinkronkan ke FTP 192.168.1.95!"
        }
    except Exception as e:
        logger.error(f"Gagal sinkronisasi batch folder: {e}")
        raise HTTPException(status_code=500, detail=f"Gagal sinkronisasi batch folder: {str(e)}")


@router.post("/bulk-replace-queue")
def bulk_replace_machine_queue(req: FTPBulkReplaceQueueRequest):
    """
    Mengirim seluruh antrean aktif (QUEUED, WAITING_LA, RUNNING) untuk mesin ke HMI secara bulk.
    Mengunggah folder batch (BATCHREF.REF & M_xxxx.PRG) dan mereplace berkas QUEUE.BTD di kontroler.
    Berlaku untuk seluruh mesin HMI (dilindungi 2x konfirmasi di UI).
    """
    clean_mach = req.machine_no.strip().upper()

    from ..database import get_db
    from ..models.schema_pg import BatchHeader, MachineQueue, Machine
    from ..utils.secom_codec import create_batchref_binary, build_minimal_prg, generate_queue_btd
    from .programs import get_compiled_prg_bytes, get_compiled_prg_bytes_for_batch

    # Resolve IP & port mesin dari database jika tidak diisi atau masih default DA01
    for db in get_db():
        m_obj = db.query(Machine).filter(Machine.machine_no == clean_mach).first()
        if m_obj and m_obj.ip_address:
            if not req.ip or (req.ip.strip() == "192.168.1.95" and clean_mach not in ("DA01", "M_95")):
                req.ip = m_obj.ip_address.strip()
            if m_obj.ftp_port:
                req.port = int(m_obj.ftp_port)
        break

    batches = []
    for db in get_db():
        # Ambil seluruh batch aktif (QUEUED, WAITING_LA, RUNNING) untuk mesin ini dari BatchHeader
        bh_items = db.query(BatchHeader).filter(
            BatchHeader.machine_no == clean_mach,
            BatchHeader.status.in_(["QUEUED", "WAITING_LA", "RUNNING"])
        ).order_by(BatchHeader.position.asc(), BatchHeader.id.asc()).all()

        if not bh_items:
            break

        # Simpan ke list of dict murni agar terbebas dari detached session SQLAlchemy
        for idx, bh in enumerate(bh_items, start=1):
            batches.append({
                "batch_ref_no": str(bh.batch_ref_no).strip().zfill(6),
                "program_no": int(bh.program_no or 1),
                "recipe_name": bh.recipe_name or "",
                "batch_no": bh.batch_no or f"LOT-{bh.batch_ref_no}",
                "customer": bh.customer or "",
                "article": bh.article or "",
                "color_code": bh.color_code or "",
                "color_name": bh.color_name or "",
                "fabric_weight_kg": float(bh.fabric_weight_kg or 350.0),
                "status": bh.status or "QUEUED",
                "position": idx
            })
            bh.position = idx

        # Sinkronisasi ke MachineQueue (REPLACE: bersihkan antrean lama untuk mesin ini dan pasang antrean baru)
        db.query(MachineQueue).filter(MachineQueue.machine_no == clean_mach).delete(synchronize_session=False)
        for b_dict in batches:
            db.add(MachineQueue(
                machine_no=clean_mach,
                batch_ref_no=b_dict["batch_ref_no"],
                batch_no=b_dict["batch_no"],
                program_no=b_dict["program_no"],
                recipe_name=b_dict["recipe_name"],
                customer=b_dict["customer"],
                article=b_dict["article"],
                color_code=b_dict["color_code"],
                color_name=b_dict["color_name"],
                fabric_weight_kg=b_dict["fabric_weight_kg"],
                liquor_ratio=8.0,
                total_water_l=2800.0,
                position=b_dict["position"],
                status=b_dict["status"]
            ))
        db.commit()
        break

    if not batches:
        raise HTTPException(
            status_code=400, 
            detail=f"Tidak ada batch antrean aktif (QUEUED / WAITING_LA / RUNNING) untuk mesin {clean_mach} di database."
        )

    # Buka koneksi FTP ke kontroler
    ftp = _get_ftp_connection(req.ip, req.port, req.username, req.password, timeout=req.timeout)
    try:
        ftp.set_pasv(True)
    except Exception:
        pass

    uploaded_folders = []
    q_records = []
    base_batch_dir = "/Network/F/OT/BATCH"

    try:
        try:
            ftp.cwd(base_batch_dir)
        except Exception:
            for part in ["/Network", "/Network/F", "/Network/F/OT", base_batch_dir]:
                try: ftp.mkd(part)
                except Exception: pass
            ftp.cwd(base_batch_dir)

        # Pastikan USERCONF.CNF selalu terunggah ke /Network/F/OT/PROCEDUR/100/
        try:
            from ..services.ftp_sync_service import sync_userconf_to_ftp
            sync_userconf_to_ftp(ftp)
        except Exception:
            pass

        # 1. Unggah folder batch (BATCHREF.REF & M_xxxx.PRG) untuk setiap antrean
        for idx, b in enumerate(batches, start=1):
            ref_no = str(b["batch_ref_no"]).strip().zfill(6)
            prog_no = int(b["program_no"] or 1)
            prg_name = f"M_{prog_no:04d}.PRG"
            recipe_title = b["recipe_name"] or f"Prog {prog_no}"
            batch_no = b["batch_no"] or f"LOT-{ref_no}"

            batchref_bytes = create_batchref_binary(
                reference_no=ref_no,
                machine_no=clean_mach,
                batch_no=batch_no,
                program_no=prog_no,
                recipe_no=b["recipe_name"] or "",
                customer=b["customer"] or "",
                article=b["article"] or "",
                color_code=b["color_code"] or "",
                color_name=b["color_name"] or "",
                fabric_weight=float(b["fabric_weight_kg"] or 350.0),
                program_title=recipe_title
            )

            prg_bytes = None
            try:
                prg_bytes = get_compiled_prg_bytes_for_batch(prog_no, b, machine_code=clean_mach)
            except Exception:
                pass
            if (not prg_bytes or len(prg_bytes) < 65) and get_compiled_prg_bytes:
                try:
                    prg_bytes = get_compiled_prg_bytes(prog_no, machine_code=clean_mach)
                except Exception:
                    pass
            if not prg_bytes or len(prg_bytes) < 65:
                prg_bytes = build_minimal_prg(prog_no, recipe_title)

            # Simpan mirror lokal
            local_target_folder = os.path.abspath(f"./open_orgatex/backend/data/OT/BATCH/{ref_no}")
            _safe_write_file(os.path.join(local_target_folder, "BATCHREF.REF"), batchref_bytes)
            _safe_write_file(os.path.join(local_target_folder, prg_name), prg_bytes)

            # Upload ke FTP /Network/F/OT/BATCH/<ref_no>/
            target_ftp_dir = f"{base_batch_dir}/{ref_no}"
            try:
                ftp.mkd(target_ftp_dir)
            except Exception:
                pass
            ftp.cwd(target_ftp_dir)
            ftp.storbinary("STOR BATCHREF.REF", io.BytesIO(batchref_bytes))
            ftp.storbinary(f"STOR {prg_name}", io.BytesIO(prg_bytes))
            uploaded_folders.append(f"{ref_no} ({batch_no})")

            # Susun 759-byte record berurutan
            q_rec = bytearray(batchref_bytes[:759])
            struct.pack_into("<HH", q_rec, 755, 0, idx)
            q_records.append(bytes(q_rec))

        # 2. Kompilasi Btrieve QUEUE.BTD untuk DA01
        q_bytes = generate_queue_btd(q_records, clean_mach)
        if not q_bytes:
            _safe_ftp_close(ftp)
            raise HTTPException(
                status_code=500,
                detail="Gagal mengompilasi berkas biner QUEUE.BTD secara murni di Python. Pastikan berkas template QUEUE_50.template.BTD tersedia."
            )

        # Simpan mirror lokal
        local_mach_btd = os.path.abspath(f"./open_orgatex/backend/data/OT/MACHINES/{clean_mach}/BATCHES/QUEUE.BTD")
        _safe_write_file(local_mach_btd, q_bytes)

        # 3. Upload QUEUE.BTD ke /Network/F/OT/MACHINES/DA01/BATCHES/QUEUE.BTD
        mach_queue_dir = f"/Network/F/OT/MACHINES/{clean_mach}/BATCHES"
        try:
            ftp.cwd(mach_queue_dir)
        except Exception:
            for part in ["/Network", "/Network/F", "/Network/F/OT", "/Network/F/OT/MACHINES", f"/Network/F/OT/MACHINES/{clean_mach}", mach_queue_dir]:
                try: ftp.mkd(part)
                except Exception: pass
            ftp.cwd(mach_queue_dir)

        ftp.storbinary("STOR QUEUE.BTD", io.BytesIO(q_bytes))
        _safe_ftp_close(ftp)

    except Exception as e:
        _safe_ftp_close(ftp)
        logger.error(f"Bulk replace queue gagal: {e}")
        raise HTTPException(status_code=500, detail=f"Gagal mengirim bulk antrean ke HMI {clean_mach}: {str(e)}")

    # 4. Update status batch di database & sync planning backup
    for db in get_db():
        for b_item in batches:
            r_no = b_item["batch_ref_no"]
            new_st = "WAITING_LA" if b_item["status"] == "QUEUED" else b_item["status"]
            db.query(MachineQueue).filter(MachineQueue.machine_no == clean_mach, MachineQueue.batch_ref_no == r_no).update({
                "status": new_st,
                "dispatched_at": datetime.now(),
                "dispatched_to_ip": req.ip
            })
            db.query(BatchHeader).filter(BatchHeader.batch_ref_no == r_no).update({
                "status": new_st
            })
        db.commit()
        from .planning import _sync_planning_json, _batch_to_dict
        all_b = [_batch_to_dict(x) for x in db.query(BatchHeader).all()]
        _sync_planning_json(all_b)
        break

    return {
        "status": "success",
        "message": f"Berhasil mereplace dan mengirim {len(q_records)} batch antrean ke HMI mesin {clean_mach} secara bulk!",
        "machine_no": clean_mach,
        "total_batches": len(q_records),
        "batches": uploaded_folders,
        "destination_file": f"{mach_queue_dir}/QUEUE.BTD"
    }


# ==============================================================================
# MONITOR STATUS BACA FTP DARI DA-BATCH-WORKER (ZERO EXTRA FTP CONNECTIONS)
# ==============================================================================

def _load_machines_for_ftp_status(db: Session, include_inactive: bool = False) -> List[Dict[str, Any]]:
    """Loads factory machines from DB with fallback to static MACHINES_DATA."""
    query = db.query(Machine)
    if not include_inactive:
        query = query.filter(Machine.is_active == True)
    rows = query.order_by(Machine.machine_no.asc()).all()

    machines_list: List[Dict[str, Any]] = []
    if rows:
        for m in rows:
            machines_list.append({
                "machine_no": str(m.machine_no or "").strip(),
                "display_name": str(m.display_name or m.machine_no or "").strip(),
                "group_name": str(m.group_name or "Dyeing Section").strip(),
                "ip_address": str(m.ip_address or "").strip(),
                "ftp_port": int(m.ftp_port or 21),
                "tcp_port": int(m.tcp_port or 50000),
                "controller_type": str(m.controller_type or "SECOM 777").strip(),
                "is_active": bool(m.is_active),
                "db_status": str(m.status or "").strip().upper(),
                "last_ping_time": m.last_ping_time,
            })
    else:
        try:
            from ..data.populate_pg import MACHINES_DATA
            for m_data in MACHINES_DATA:
                machines_list.append({
                    "machine_no": str(m_data.get("no") or "").strip(),
                    "display_name": str(m_data.get("name") or m_data.get("no") or "").strip(),
                    "group_name": str(m_data.get("group") or "Dyeing Section").strip(),
                    "ip_address": str(m_data.get("ip") or "").strip(),
                    "ftp_port": 21,
                    "tcp_port": 50000,
                    "controller_type": str(m_data.get("type") or "SECOM 777").strip(),
                    "is_active": True,
                    "db_status": "",
                    "last_ping_time": None,
                })
        except Exception as e:
            logger.warning(f"Fallback MACHINES_DATA load error: {e}")

    return machines_list


@router.get("/worker-status")
def get_batch_worker_ftp_status(
    include_inactive: bool = Query(False, description="Sertakan mesin dengan status non-aktif"),
    db: Session = Depends(get_db),
):
    """
    Membaca status hasil polling FTP per mesin yang dicatat oleh da-batch-worker
    di tabel `machine_ftp_status`. Tidak membuka koneksi FTP baru ke kontroler.
    """
    machines_list = _load_machines_for_ftp_status(db, include_inactive=include_inactive)

    # Baca status terakhir dari tabel machine_ftp_status (aman jika tabel belum terisi)
    status_map: Dict[str, MachineFtpStatus] = {}
    try:
        rows = db.query(MachineFtpStatus).all()
        for r in rows:
            status_map[str(r.machine_no or "").strip().upper()] = r
    except Exception as e:
        logger.debug(f"machine_ftp_status table not ready yet: {e}")
        try:
            db.rollback()
        except Exception:
            pass

    now_utc = datetime.now(timezone.utc)
    results: List[Dict[str, Any]] = []
    latest_checked_at: Optional[datetime] = None
    worker_name = "DA-Batch-Worker-24x7"

    for m in machines_list:
        m_key = m["machine_no"].upper()
        st = status_map.get(m_key)

        # Cek apakah telemetri kontroler aktif berdasarkan data DB (tanpa buka socket baru)
        last_ping = m.get("last_ping_time")
        telemetry_online = False
        if last_ping is not None:
            try:
                lp = last_ping if last_ping.tzinfo is not None else last_ping.replace(tzinfo=timezone.utc)
                telemetry_online = (now_utc - lp).total_seconds() <= 300
            except Exception:
                telemetry_online = m.get("db_status") in ("ONLINE", "RUNNING")
        else:
            telemetry_online = m.get("db_status") in ("ONLINE", "RUNNING")

        if st is not None:
            if st.last_checked_at:
                st_dt = st.last_checked_at if st.last_checked_at.tzinfo else st.last_checked_at.replace(tzinfo=timezone.utc)
                if latest_checked_at is None or st_dt > latest_checked_at:
                    latest_checked_at = st_dt
            if st.worker_name:
                worker_name = st.worker_name

            results.append({
                "machine_no": m["machine_no"],
                "display_name": m["display_name"],
                "group_name": m["group_name"],
                "ip_address": st.ip_address or m["ip_address"],
                "ftp_port": int(st.ftp_port or m["ftp_port"] or 21),
                "controller_type": m["controller_type"],
                "is_active": m["is_active"],
                "can_read_ftp": bool(st.can_read_ftp),
                "ftp_status": str(st.ftp_status or ("OK" if st.can_read_ftp else "FAILED")),
                "failure_category": str(st.failure_category or "UNKNOWN"),
                "error_detail": str(st.error_detail or ""),
                "status_act_readable": bool(st.status_act_readable),
                "telemetry_online": telemetry_online,
                "active_batch": st.active_batch,
                "current_step": st.current_step,
                "curve_points": int(st.curve_points or 0),
                "latency_ms": float(st.latency_ms or 0.0),
                "consecutive_failures": int(st.consecutive_failures or 0),
                "last_checked_at": st.last_checked_at.isoformat() if st.last_checked_at else None,
                "last_success_at": st.last_success_at.isoformat() if st.last_success_at else None,
            })
        else:
            results.append({
                "machine_no": m["machine_no"],
                "display_name": m["display_name"],
                "group_name": m["group_name"],
                "ip_address": m["ip_address"],
                "ftp_port": m["ftp_port"],
                "controller_type": m["controller_type"],
                "is_active": m["is_active"],
                "can_read_ftp": False,
                "ftp_status": "PENDING",
                "failure_category": "NO_WORKER_DATA",
                "error_detail": "Belum ada laporan dari da-batch-worker. Pastikan service da-batch-worker sudah di-restart untuk memproses semua mesin.",
                "status_act_readable": False,
                "telemetry_online": telemetry_online,
                "active_batch": None,
                "current_step": None,
                "curve_points": 0,
                "latency_ms": 0.0,
                "consecutive_failures": 0,
                "last_checked_at": None,
                "last_success_at": None,
            })

    # Urutkan: FAILED dulu -> PARTIAL -> PENDING -> OK
    status_order = {"FAILED": 0, "PARTIAL": 1, "PENDING": 2, "OK": 3}
    results.sort(key=lambda r: (status_order.get(r["ftp_status"], 9), -r["consecutive_failures"], r["machine_no"]))

    ok_count = sum(1 for r in results if r["ftp_status"] == "OK")
    partial_count = sum(1 for r in results if r["ftp_status"] == "PARTIAL")
    failed_count = sum(1 for r in results if r["ftp_status"] == "FAILED")
    pending_count = sum(1 for r in results if r["ftp_status"] == "PENDING")
    unreadable_count = sum(1 for r in results if r["ftp_status"] in ("FAILED", "PARTIAL"))

    return {
        "source": "da-batch-worker",
        "worker_name": worker_name,
        "last_cycle_at": latest_checked_at.isoformat() if latest_checked_at else None,
        "summary": {
            "total_machines": len(results),
            "ftp_ok_count": ok_count,
            "ftp_partial_count": partial_count,
            "ftp_failed_count": failed_count,
            "ftp_pending_count": pending_count,
            "ftp_unreadable_count": unreadable_count,
        },
        "machines": results,
    }

