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
import logging
import posixpath
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from ..services.reader import SetexFolderReader
from ..utils.secom_codec import (
    create_batchref_binary,
    build_minimal_prg,
    generate_batch_zip
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


def _get_ftp_connection(ip: str, port: int = 21, username: str = "", password: str = "", timeout: float = 5.0) -> ftplib.FTP:
    """Helper to establish an authenticated or anonymous FTP connection."""
    ftp = ftplib.FTP(timeout=timeout)
    ftp.connect(ip, port)
    if username:
        ftp.login(username, password)
    else:
        ftp.login()
    return ftp


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
        ftp.quit()
        
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
            ftp.quit()
            raise HTTPException(status_code=404, detail=f"Direktori remote tidak ditemukan: {target_path} ({e})")

        current_path = ftp.pwd()
        raw_lines = []
        ftp.retrlines("LIST", raw_lines.append)
        ftp.quit()

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
        ftp.quit()

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


@router.post("/dispatch-batch")
def dispatch_batch_via_ftp(req: FTPDispatchBatchRequest):
    """
    Dispatches a production batch directly to the controller via FTP.
    Uploads:
    1. BATCHREF.REF (762-byte Secom binary structure)
    2. M_{program_no:04d}.PRG (SECOM 777 execution program)
    """
    # Load batch details from planning.json
    if not os.path.exists(PLANNING_PATH):
        raise HTTPException(status_code=404, detail="Data planning belum ada")

    try:
        with open(PLANNING_PATH, "r", encoding="utf-8") as f:
            batches = json.load(f)
    except Exception:
        batches = []

    target_batch = next((b for b in batches if b["id"] == req.batch_id or b.get("reference_no") == req.batch_id), None)
    if not target_batch:
        raise HTTPException(status_code=404, detail=f"Batch dengan ID '{req.batch_id}' tidak ditemukan")

    ref_no = target_batch.get("reference_no", "000000")
    prog_no = target_batch.get("program_no", 1)
    prg_name = f"M_{int(prog_no):04d}.PRG"

    # Generate binary files in memory
    batchref_bytes = create_batchref_binary(target_batch)
    prg_bytes = build_minimal_prg(prog_no, target_batch.get("recipe_name", "Reactive Dyeing"))

    try:
        ftp = _get_ftp_connection(req.ip, req.port, req.username, req.password)
        
        # Determine target directory based on IP and controller type
        # Special rule: IP 192.168.1.95 or SETEX 797CE defaults to /Flashdisk/SC797CE/BATCH
        is_797 = (
            req.ip.strip() == "192.168.1.95" or 
            (req.controller_type and "797" in req.controller_type.upper()) or
            (req.target_dir and "SC797" in req.target_dir.upper())
        )

        primary_dir = req.target_dir.rstrip("/\\") if req.target_dir else ("/Flashdisk/SC797CE/BATCH" if is_797 else "/Storage/sc777ce/BATCH")

        # Prepare candidate directories with automatic fallback between 797 and 777
        candidate_dirs = [primary_dir, primary_dir.replace("/", "\\"), primary_dir.replace("\\", "/")]
        if is_797:
            candidate_dirs.extend([
                "/Flashdisk/SC797CE/BATCH",
                "\\Flashdisk\\SC797CE\\BATCH",
                "/flashdisk/sc797ce/batch",
                "/Flashdisk/SC797CE/Batch",
                "/Flashdisk/sc797ce/BATCH",
                "/Storage/sc777ce/BATCH",
                "\\Storage\\sc777ce\\BATCH"
            ])
        else:
            candidate_dirs.extend([
                "/Storage/sc777ce/BATCH",
                "\\Storage\\sc777ce\\BATCH",
                "/Storage/SC777CE/BATCH",
                "/Flashdisk/SC797CE/BATCH",
                "\\Flashdisk\\SC797CE\\BATCH",
                "/flashdisk/sc797ce/batch"
            ])

        resolved_target_dir = None
        for cand in candidate_dirs:
            try:
                ftp.cwd(cand)
                resolved_target_dir = cand
                break
            except Exception:
                continue

        if not resolved_target_dir:
            # Try to create directory if not existing
            try:
                ftp.mkd(primary_dir)
                ftp.cwd(primary_dir)
                resolved_target_dir = primary_dir
            except Exception:
                resolved_target_dir = primary_dir

        # 1. Upload BATCHREF.REF
        ftp.storbinary("STOR BATCHREF.REF", io.BytesIO(batchref_bytes))

        # 2. Upload Program M_xxxx.PRG
        ftp.storbinary(f"STOR {prg_name}", io.BytesIO(prg_bytes))
        
        ftp.quit()

        # Update batch status in planning.json
        target_batch["status"] = "WAITING_LA"
        target_batch["dispatched_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        target_batch["dispatched_to_ip"] = req.ip
        with open(PLANNING_PATH, "w", encoding="utf-8") as f:
            json.dump(batches, f, indent=2)

        return {
            "status": "success",
            "message": f"Batch {target_batch.get('batch_no')} (Ref: {ref_no}) berhasil dikirim ke Controller {req.ip} ({resolved_target_dir}) via FTP!",
            "uploaded_files": ["BATCHREF.REF", prg_name],
            "destination_dir": resolved_target_dir,
            "ip": req.ip,
            "controller_type": "SETEX 797CE" if is_797 else "SETEX 777",
            "batch": target_batch
        }

    except Exception as e:
        logger.error(f"FTP dispatch failed: {e}")
        raise HTTPException(status_code=500, detail=f"Pengiriman batch via FTP gagal: {str(e)}")


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
        ftp.quit()

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
        ftp.quit()

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
                ftp.quit()
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
                    ftp.quit()
                    return {
                        "status": "success",
                        "action": "cut",
                        "message": f"'{base_name}' berhasil dipindahkan ke '{target_dir}' (via copy-delete).",
                        "source": src_path,
                        "destination": target_path
                    }
                ftp.quit()
                raise rename_err
        else:
            # Copy file
            if req.is_dir:
                try:
                    ftp.mkd(target_path)
                except Exception:
                    pass
                ftp.quit()
                return {
                    "status": "success",
                    "action": "copy",
                    "message": f"Direktori '{base_name}' berhasil dibuat di '{target_dir}'.",
                    "source": src_path,
                    "destination": target_path
                }
            else:
                _copy_ftp_single_file(ftp, src_path, target_path)
                ftp.quit()
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
                ftp.quit()
                raise HTTPException(status_code=400, detail=f"Gagal menghapus direktori (pastikan direktori kosong): {str(e)}")
        else:
            ftp.delete(req.remote_path)
        ftp.quit()
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
        ftp.quit()
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
        ftp.quit()
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
                ftp.quit()
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

            ftp.quit()
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

            ftp.quit()
            return {
                "status": "success",
                "direction": "remote_to_local",
                "message": f"Berkas '{file_name}' berhasil diunduh dari Remote ke Lokal '{local_target_file.replace(chr(92), '/')}'.",
                "source": req.remote_path,
                "destination": local_target_file.replace("\\", "/")
            }
        else:
            ftp.quit()
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
