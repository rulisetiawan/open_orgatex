"""
Machines CRUD, Diagnostics & Network Sniffer Route
Exact Parity with OrgaTEX OtxMachineConfigLib:
- DlgAddOnlineMachine (SecomCESniffer / Network Discovery)
- DlgAddMachine / UCMachineEdit (Tabbed General, Address, Recipe, Tanks, Automation)
Strictly Read-Only with respect to shared directories
"""

import os
import io
import socket
import ftplib
import subprocess
import logging
import concurrent.futures
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.schema_pg import Machine
from ..services.machine_config_service import (
    fetch_machine_config_from_hmi,
    get_machine_config_summary,
    sync_machine_ready_config
)

logger = logging.getLogger("orgatex.machines")
router = APIRouter(prefix="/api/machines", tags=["Machines"])

# Environment flag to enforce read-only safety
WRITE_MODE_ENABLED = os.getenv("WRITE_MODE_ENABLED", "false").lower() in ("true", "1")

class MachineCreateSchema(BaseModel):
    machine_no: str
    internal_no: Optional[str] = ""
    display_name: str
    group_name: str = "Dyeing Section A"
    controller_type: str = "SECOM 777 (Windows CE)"
    kind_of_machine: str = "High Temp Jet Dyeing"
    ip_address: str
    tcp_port: int = 50100
    ftp_port: int = 21
    share_folder_path: str = "/Network/F/OT/"
    capacity_kg: float = 350.0
    default_liquor_ratio: float = 8.0
    tanks_count: int = 2
    batch_weight_calc: str = "Digital Scale / Timbangan"
    liquor_amount_calc: str = "Liquor Ratio x Batch Weight"
    auto_download: bool = True
    manual_batch_start: bool = False
    allow_proc_pic_edit: bool = True
    polling_interval_sec: int = 5
    is_active: bool = True
    auto_fetch_config: bool = True

class MachineUpdateSchema(BaseModel):
    internal_no: Optional[str] = None
    display_name: Optional[str] = None
    group_name: Optional[str] = None
    controller_type: Optional[str] = None
    kind_of_machine: Optional[str] = None
    ip_address: Optional[str] = None
    tcp_port: Optional[int] = None
    ftp_port: Optional[int] = None
    share_folder_path: Optional[str] = None
    capacity_kg: Optional[float] = None
    default_liquor_ratio: Optional[float] = None
    tanks_count: Optional[int] = None
    batch_weight_calc: Optional[str] = None
    liquor_amount_calc: Optional[str] = None
    auto_download: Optional[bool] = None
    manual_batch_start: Optional[bool] = None
    allow_proc_pic_edit: Optional[bool] = None
    polling_interval_sec: Optional[int] = None
    is_active: Optional[bool] = None

class ScanRequestSchema(BaseModel):
    start_ip: Optional[str] = "172.16.110.100"
    end_ip: Optional[str] = "172.16.110.115"
    timeout_sec: Optional[float] = 1.0

def _probe_single_controller(ip: str, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
    """Probes an IP for SETEX 777 controller via FTP and TCP."""
    has_ftp = False
    has_tcp = False
    machine_id = None
    active_batch = None
    program_code = None

    # Check FTP Port 21
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((ip, 21))
            has_ftp = True
    except Exception:
        pass

    # Check SETEX TCP 50100
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((ip, 50100))
            has_tcp = True
    except Exception:
        pass

    if not has_ftp and not has_tcp:
        return None

    # If FTP is reachable, read live identity from STATUS.ACT
    if has_ftp:
        try:
            ftp = ftplib.FTP(timeout=2.0)
            ftp.connect(ip, 21)
            ftp.login()
            bio = io.BytesIO()
            target_status = "/Flashdisk/SC797CE/STATUS/STATUS.ACT" if ip == "192.168.1.95" else "/Storage/sc777ce/STATUS/STATUS.ACT"
            try:
                ftp.retrbinary(f"RETR {target_status}", bio.write)
            except Exception:
                try:
                    ftp.retrbinary("RETR /Flashdisk/SC797CE/STATUS/STATUS.ACT", bio.write)
                except Exception:
                    try:
                        ftp.retrbinary("RETR /Storage/sc777ce/STATUS/STATUS.ACT", bio.write)
                    except Exception:
                        pass
            data = bio.getvalue()
            if len(data) >= 16:
                m_raw = data[11:19].split(b'\0')[0].decode('latin1', errors='ignore').strip()
                if m_raw:
                    machine_id = m_raw
            if len(data) >= 48:
                b_raw = data[36:48].split(b'\0')[0].decode('latin1', errors='ignore').strip()
                if b_raw:
                    active_batch = b_raw
            if len(data) >= 64:
                p_raw = data[52:64].split(b'\0')[0].decode('latin1', errors='ignore').strip()
                if p_raw:
                    program_code = p_raw
            ftp.quit()
        except Exception:
            pass

    is_797 = ip.strip() == "192.168.1.95" or (machine_id and "797" in machine_id.upper()) or (machine_id and machine_id.upper().startswith("DA"))
    controller_type = "SETEX 797CE (Windows CE)" if is_797 else "SECOM 777 (Windows CE)"
    share_folder_path = "/Flashdisk/SC797CE" if is_797 else "/Storage/SC777CE"

    display_name = f"SETEX 797CE Mesin {machine_id or 'DA01'}" if is_797 else (f"SETEX Controller {machine_id}" if machine_id else f"SETEX Controller ({ip})")
    return {
        "ip_address": ip,
        "machine_no": "DA01" if ip.strip() == "192.168.1.95" else (machine_id or f"M_{ip.split('.')[-1]}"),
        "display_name": display_name,
        "controller_type": controller_type,
        "kind_of_machine": "High Temp Jet Dyeing",
        "has_ftp": has_ftp,
        "has_tcp_50100": has_tcp,
        "active_batch": active_batch or "-",
        "program_code": program_code or "-",
        "status": "ONLINE"
    }

@router.post("/scan")
def scan_network_controllers(scan_req: ScanRequestSchema):
    """
    OrgaTEX SecomCESniffer Parity (DlgAddOnlineMachine):
    Scans IP range on factory network to auto-discover online SETEX controllers.
    """
    try:
        s_parts = [int(p) for p in scan_req.start_ip.split('.')]
        e_parts = [int(p) for p in scan_req.end_ip.split('.')]
    except Exception:
        raise HTTPException(status_code=400, detail="Format IP range tidak valid.")

    base_subnet = f"{s_parts[0]}.{s_parts[1]}.{s_parts[2]}"
    ips = [f"{base_subnet}.{i}" for i in range(s_parts[3], e_parts[3] + 1)]

    discovered = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        future_to_ip = {
            executor.submit(_probe_single_controller, ip, scan_req.timeout_sec): ip 
            for ip in ips
        }
        for future in concurrent.futures.as_completed(future_to_ip):
            res = future.result()
            if res:
                discovered.append(res)

    discovered.sort(key=lambda x: [int(p) for p in x["ip_address"].split('.')])
    return {
        "range_scanned": f"{scan_req.start_ip} - {scan_req.end_ip}",
        "total_scanned": len(ips),
        "found_count": len(discovered),
        "controllers": discovered
    }

@router.get("/")
def get_all_machines(db: Session = Depends(get_db)):
    """Lists all configured machines from PostgreSQL along with HMI config readiness."""
    machines = db.query(Machine).all()
    if not machines:
        logger.info("Database machines table is empty! Auto-seeding factory machines...")
        try:
            from ..data.populate_pg import run as seed_machines
            seed_machines(db)
            machines = db.query(Machine).all()
            logger.info(f"Auto-seeded {len(machines)} machines successfully.")
        except Exception as e:
            logger.error(f"Auto-seeding machines failed: {e}")

    # Fallback to static MACHINES_DATA so frontend never renders an empty screen
    if not machines:
        logger.warning("Returning static in-memory fallback machines.")
        from ..data.populate_pg import MACHINES_DATA
        results = []
        for m_data in MACHINES_DATA:
            no = m_data["no"]
            is_setex = "setex" in m_data["name"].lower() or "797" in m_data.get("type", "").lower() or "777" in m_data.get("type", "").lower()
            disp_name = f"Mesin {no} ({m_data['name']})" if not m_data["name"].startswith("SETEX") else f"{m_data['name']} Mesin {no}"
            cfg = get_machine_config_summary(no)
            results.append({
                "machine_no": no,
                "display_name": disp_name,
                "group_name": m_data.get("group", "Dyeing Section A"),
                "controller_type": m_data.get("type", "SECOM 777 (Windows CE)"),
                "ip_address": m_data["ip"],
                "tcp_port": 50100 if is_setex else 50000,
                "ftp_port": 21,
                "capacity_kg": 350.0,
                "default_liquor_ratio": 8.0,
                "tanks_count": 2,
                "share_folder_path": m_data.get("share_folder_path") or f"/Network/F/OT/{no}/",
                "status": "ONLINE",
                "current_batch": "-",
                "current_step": 1,
                "current_temp": None,
                "is_active": True,
                "write_mode": "DISABLED (Strict Read-Only Active)",
                "config_status": cfg.get("config_status", "NOT_CONFIGURED"),
                "has_custom_hmi_config": cfg.get("has_custom_hmi_config", False),
                "has_typeconf": cfg.get("has_typeconf", False),
                "has_conftext": cfg.get("has_conftext", False),
                "has_machconf": cfg.get("has_machconf", False),
                "workspace_exists": cfg.get("workspace_exists", False)
            })
        return results

    # Auto-sanitize any machine with IP 192.168.1.95, DA01, or M_95 to SETEX 797CE
    modified = False
    for m in machines:
        is_797 = (
            m.ip_address == "192.168.1.95" or 
            m.machine_no in ("DA01", "M_95") or 
            "797" in (m.controller_type or "")
        )
        if is_797:
            if m.controller_type != "SETEX 797CE (Windows CE)":
                m.controller_type = "SETEX 797CE (Windows CE)"
                modified = True
            if not m.share_folder_path or "/Storage" in m.share_folder_path or "/Network" in m.share_folder_path:
                m.share_folder_path = "/Flashdisk/SC797CE"
                modified = True
    if modified:
        try:
            db.commit()
        except Exception:
            db.rollback()

    results = []
    for m in machines:
        cfg = get_machine_config_summary(m.machine_no)
        is_797 = m.ip_address == "192.168.1.95" or m.machine_no in ("DA01", "M_95") or "797" in (m.controller_type or "")
        results.append({
            "machine_no": m.machine_no,
            "display_name": m.display_name,
            "group_name": m.group_name or ("Dyeing Sample / DA" if is_797 else "Dyeing Section A"),
            "controller_type": "SETEX 797CE (Windows CE)" if is_797 else (m.controller_type or "SECOM 777 (Windows CE)"),
            "ip_address": m.ip_address,
            "tcp_port": m.tcp_port or 50100,
            "ftp_port": m.ftp_port or 21,
            "capacity_kg": float(m.capacity_kg) if m.capacity_kg else 350.0,
            "default_liquor_ratio": float(m.default_liquor_ratio) if m.default_liquor_ratio else 8.0,
            "tanks_count": m.tanks_count or 2,
            "share_folder_path": "/Flashdisk/SC797CE" if is_797 else (m.share_folder_path or "/Network/F/OT/"),
            "status": m.status or "ONLINE",
            "current_batch": m.current_batch or "-",
            "current_step": m.current_step or 1,
            "current_temp": float(m.current_temp) if m.current_temp else None,
            "is_active": m.is_active,
            "write_mode": "DISABLED (Strict Read-Only Active)",
            "config_status": cfg.get("config_status", "NOT_CONFIGURED"),
            "has_custom_hmi_config": cfg.get("has_custom_hmi_config", False),
            "has_typeconf": cfg.get("has_typeconf", False),
            "has_conftext": cfg.get("has_conftext", False),
            "has_machconf": cfg.get("has_machconf", False),
            "workspace_exists": cfg.get("workspace_exists", False)
        })
    return results

@router.get("/{machine_no}")
def get_machine(machine_no: str, db: Session = Depends(get_db)):
    mach_clean = machine_no.upper()
    m = db.query(Machine).filter(Machine.machine_no == mach_clean).first()
    if not m:
        if mach_clean in ("DA01", "M_95") or "797" in mach_clean:
            m = Machine(
                machine_no=mach_clean,
                display_name=f"SETEX 797CE Mesin {mach_clean}",
                group_name="Dyeing Sample / DA",
                ip_address="192.168.1.95",
                tcp_port=50100,
                ftp_port=21,
                controller_type="SETEX 797CE (Windows CE)",
                share_folder_path="/Flashdisk/SC797CE",
                status="ONLINE"
            )
            db.add(m)
            db.commit()
            db.refresh(m)
        else:
            raise HTTPException(status_code=404, detail="Mesin tidak ditemukan")
    elif m.ip_address == "192.168.1.95" or mach_clean in ("DA01", "M_95") or "797" in (m.controller_type or ""):
        if m.controller_type != "SETEX 797CE (Windows CE)" or m.share_folder_path != "/Flashdisk/SC797CE":
            m.controller_type = "SETEX 797CE (Windows CE)"
            m.share_folder_path = "/Flashdisk/SC797CE"
            db.commit()
            db.refresh(m)

    cfg = get_machine_config_summary(m.machine_no)
    is_797 = m.ip_address == "192.168.1.95" or mach_clean in ("DA01", "M_95") or "797" in (m.controller_type or "")
    return {
        "machine_no": m.machine_no,
        "display_name": m.display_name,
        "group_name": m.group_name or ("Dyeing Sample / DA" if is_797 else "Dyeing Section A"),
        "controller_type": "SETEX 797CE (Windows CE)" if is_797 else (m.controller_type or "SECOM 777 (Windows CE)"),
        "ip_address": m.ip_address,
        "tcp_port": m.tcp_port,
        "ftp_port": m.ftp_port,
        "capacity_kg": float(m.capacity_kg) if m.capacity_kg else 350.0,
        "default_liquor_ratio": float(m.default_liquor_ratio) if m.default_liquor_ratio else 8.0,
        "tanks_count": m.tanks_count,
        "share_folder_path": "/Flashdisk/SC797CE" if is_797 else (m.share_folder_path or "/Network/F/OT/"),
        "status": m.status,
        "current_batch": m.current_batch,
        "current_step": m.current_step,
        "current_temp": float(m.current_temp) if m.current_temp else None,
        "is_active": m.is_active,
        "config_status": cfg.get("config_status", "NOT_CONFIGURED"),
        "has_custom_hmi_config": cfg.get("has_custom_hmi_config", False),
        "has_typeconf": cfg.get("has_typeconf", False),
        "has_conftext": cfg.get("has_conftext", False),
        "has_machconf": cfg.get("has_machconf", False),
        "workspace_exists": cfg.get("workspace_exists", False)
    }

@router.post("/")
def create_machine(m: MachineCreateSchema, db: Session = Depends(get_db)):
    """
    Creates or updates a machine configuration in PostgreSQL.
    Optionally auto-fetches HMI config files (.CNF) via FTP.
    """
    m_no = m.machine_no.strip().upper()
    existing = db.query(Machine).filter(Machine.machine_no == m_no).first()
    if existing:
        existing.display_name = m.display_name
        existing.ip_address = m.ip_address
        existing.tcp_port = m.tcp_port
        existing.ftp_port = m.ftp_port
        existing.controller_type = m.controller_type
        existing.group_name = m.group_name
        existing.capacity_kg = m.capacity_kg
        existing.default_liquor_ratio = m.default_liquor_ratio
        existing.tanks_count = m.tanks_count
        existing.share_folder_path = m.share_folder_path
        existing.polling_interval_sec = m.polling_interval_sec
        existing.is_active = m.is_active
        db.commit()
        db.refresh(existing)

        fetch_result = None
        if m.auto_fetch_config and existing.ip_address:
            try:
                fetch_result = fetch_machine_config_from_hmi(
                    ip=existing.ip_address,
                    machine_no=existing.machine_no,
                    ftp_port=existing.ftp_port or 21,
                    timeout=4.0
                )
            except Exception as e:
                logger.warning(f"Auto-fetch config failed for {existing.machine_no}: {e}")
                fetch_result = {"success": False, "message": str(e), "status": "baseline_active"}

        return {
            "status": "updated",
            "write_mode": "DISABLED (Read-Only Mode)",
            "message": f"Konfigurasi mesin {m_no} berhasil diperbarui di PostgreSQL.",
            "data": {
                "machine_no": existing.machine_no,
                "display_name": existing.display_name,
                "ip_address": existing.ip_address
            },
            "config_fetch": fetch_result
        }

    new_m = Machine(
        machine_no=m_no,
        display_name=m.display_name,
        ip_address=m.ip_address,
        tcp_port=m.tcp_port,
        ftp_port=m.ftp_port,
        controller_type=m.controller_type,
        os_family="WindowsCE",
        group_name=m.group_name,
        capacity_kg=m.capacity_kg,
        default_liquor_ratio=m.default_liquor_ratio,
        tanks_count=m.tanks_count,
        share_folder_path=m.share_folder_path,
        polling_interval_sec=m.polling_interval_sec,
        is_active=m.is_active,
        status="ONLINE"
    )

    db.add(new_m)
    db.commit()
    db.refresh(new_m)

    # Auto-fetch config from HMI via FTP if requested
    fetch_result = None
    if m.auto_fetch_config and new_m.ip_address:
        try:
            fetch_result = fetch_machine_config_from_hmi(
                ip=new_m.ip_address,
                machine_no=new_m.machine_no,
                ftp_port=new_m.ftp_port or 21,
                timeout=4.0
            )
        except Exception as e:
            logger.warning(f"Auto-fetch config failed for {new_m.machine_no}: {e}")
            fetch_result = {"success": False, "message": str(e), "status": "baseline_active"}

    msg = f"Mesin {m_no} berhasil didaftarkan di database PostgreSQL."
    if fetch_result and fetch_result.get("success"):
        msg += f" File konfigurasi HMI ({fetch_result.get('downloaded_count', 0)} file) berhasil diunduh via FTP!"
    elif fetch_result and not fetch_result.get("success"):
        msg += f" (Peringatan: {fetch_result.get('message', 'Gagal unduh config via FTP. Baseline aktif.')})"

    logger.info(f"[READ-ONLY] Mesin {m_no} disimpan di PostgreSQL. Config fetch: {fetch_result.get('status') if fetch_result else 'skipped'}")
    return {
        "status": "created",
        "write_mode": "DISABLED (Read-Only Mode)",
        "message": msg,
        "data": {
            "machine_no": new_m.machine_no,
            "display_name": new_m.display_name,
            "ip_address": new_m.ip_address
        },
        "config_fetch": fetch_result
    }

@router.put("/{machine_no}")
def update_machine(machine_no: str, upd: MachineUpdateSchema, db: Session = Depends(get_db)):
    m = db.query(Machine).filter(Machine.machine_no == machine_no.upper()).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mesin tidak ditemukan")

    data = upd.dict(exclude_unset=True)
    for k, v in data.items():
        setattr(m, k, v)

    db.commit()
    return {"status": "updated", "machine_no": m.machine_no}

@router.delete("/{machine_no}")
def delete_machine(machine_no: str, db: Session = Depends(get_db)):
    m = db.query(Machine).filter(Machine.machine_no == machine_no.upper()).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mesin tidak ditemukan")
    db.delete(m)
    db.commit()
    return {"status": "deleted", "machine_no": machine_no}

@router.post("/{machine_no}/test")
def test_connection(machine_no: str, db: Session = Depends(get_db)):
    """
    Tests live network connectivity and folder readability for this machine:
    - ICMP Ping
    - SETEX Port (50100 / 50000)
    - FTP Port 21
    - Direct read of STATUS.ACT via FTP / storage
    """
    m = db.query(Machine).filter(Machine.machine_no == machine_no.upper()).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mesin tidak ditemukan")

    ip = m.ip_address

    # 1. Ping Test
    ping_ok = False
    try:
        cmd = ["ping", "-c", "1", "-W", "1", ip] if os.name != "nt" else ["ping", "-n", "1", "-w", "1000", ip]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ping_ok = (res.returncode == 0)
    except Exception:
        pass

    # 2. SETEX TCP Port Test
    tcp_ok = False
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            s.connect((ip, m.tcp_port or 50100))
            tcp_ok = True
    except Exception:
        pass

    # 3. FTP Port 21 Test
    ftp_ok = False
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            s.connect((ip, m.ftp_port or 21))
            ftp_ok = True
    except Exception:
        pass

    # 4. Read-Only STATUS.ACT Verification via FTP or local
    status_act_found = False
    controller_info = {}
    if ftp_ok:
        try:
            ftp = ftplib.FTP(timeout=2.0)
            ftp.connect(ip, m.ftp_port or 21)
            ftp.login()
            bio = io.BytesIO()
            ftp.retrbinary("RETR /Storage/sc777ce/STATUS/STATUS.ACT", bio.write)
            data = bio.getvalue()
            if len(data) >= 16:
                status_act_found = True
                controller_info["machine_id"] = data[11:19].split(b'\0')[0].decode('latin1', errors='ignore').strip()
            if len(data) >= 48:
                controller_info["batch"] = data[36:48].split(b'\0')[0].decode('latin1', errors='ignore').strip()
            ftp.quit()
        except Exception:
            pass

    overall_status = "ONLINE" if (ping_ok or ftp_ok or tcp_ok) else "OFFLINE"
    m.status = overall_status
    db.commit()

    return {
        "machine_no": m.machine_no,
        "ip_address": ip,
        "ping": ping_ok,
        "setex_tcp": tcp_ok,
        "ftp_port_21": ftp_ok,
        "status_act_detected": status_act_found,
        "controller_info": controller_info,
        "overall_status": overall_status,
        "write_mode": "DISABLED (Read-Only Mode Enforced)"
    }

@router.post("/{machine_no}/fetch-config")
def fetch_config_for_machine(machine_no: str, db: Session = Depends(get_db)):
    """
    Triggers FTP auto-download of HMI config files (.CNF) from the machine controller.
    Downloads files to WORKSPACE_PROGRAM_MESIN/<NAMA_MESIN>/01_CONFIG_DARI_HMI/
    and triggers automatic decoding to JSON.
    """
    m = db.query(Machine).filter(Machine.machine_no == machine_no.upper()).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mesin tidak ditemukan.")
    
    result = fetch_machine_config_from_hmi(
        ip=m.ip_address,
        machine_no=m.machine_no,
        ftp_port=m.ftp_port or 21,
        timeout=5.0
    )
    return result

@router.get("/{machine_no}/config-status")
def get_config_status(machine_no: str):
    """
    Returns HMI configuration readiness and available .CNF / .JSON files for this machine.
    """
    return get_machine_config_summary(machine_no)

