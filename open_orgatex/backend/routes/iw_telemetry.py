import os
import json
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..database import get_db

logger = logging.getLogger("orgatex.iw_telemetry")

router = APIRouter(
    prefix="/api/iw-telemetry",
    tags=["IW Telemetry & Tag Mapping"]
)

@router.get("/machines")
def get_iw_machines(db: Session = Depends(get_db)):
    """
    Mengambil daftar mesin berserta ringkasan status mapping tag IW dan live status.
    """
    try:
        query = text("""
            SELECT 
                m.machine_no,
                m.display_name,
                m.ip_address,
                m.status as machine_status,
                m.current_batch,
                m.current_step,
                COUNT(c.id) as total_mapped_tags,
                l.connection_status,
                l.last_updated,
                l.telemetry_json
            FROM machines m
            LEFT JOIN cfg_machine_iw_tag_mapping c ON m.machine_no = c.machine_id
            LEFT JOIN live_iw_telemetry l ON m.machine_no = l.machine_id
            GROUP BY m.machine_no, m.display_name, m.ip_address, m.status, m.current_batch, m.current_step, 
                     l.connection_status, l.last_updated, l.telemetry_json
            ORDER BY m.machine_no ASC;
        """)
        rows = db.execute(query).fetchall()
        
        result = []
        for r in rows:
            telemetry = r[9] if r[9] else {}
            result.append({
                "machine_no": r[0],
                "display_name": r[1],
                "ip_address": r[2],
                "machine_status": r[3],
                "current_batch": r[4],
                "current_step": r[5],
                "total_mapped_tags": r[6],
                "connection_status": r[7] or ("ONLINE" if r[6] > 0 else "NO_CONFIG"),
                "last_updated": r[8].isoformat() if r[8] else None,
                "sample_metrics": {
                    "temp_pv": telemetry.get("SMM.JF-LB-10.MAIN_TANK.TEMPERATURE_PV", {}).get("value") if isinstance(telemetry, dict) else None,
                    "temp_sv": telemetry.get("SMM.JF-LB-10.MAIN_TANK.TEMPERATURE_SV", {}).get("value") if isinstance(telemetry, dict) else None,
                    "level_pv": telemetry.get("SMM.JF-LB-10.MAIN_TANK.LEVEL_PV", {}).get("value") if isinstance(telemetry, dict) else None,
                }
            })
        return {"status": "success", "count": len(result), "data": result}
    except Exception as e:
        logger.error(f"Error fetching IW machines: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/mapping/{machine_id}")
def get_machine_tag_mapping(machine_id: str, db: Session = Depends(get_db)):
    """
    Mengambil seluruh daftar mapping register IW ke Tag SCADA untuk mesin tertentu,
    dilengkapi nilai aktual/live terkini jika service pengumpul sedang aktif.
    """
    try:
        # 1. Ambil data live telemetry
        live_query = text("""
            SELECT last_updated, connection_status, batch_no, step_no, program_no, telemetry_json
            FROM live_iw_telemetry
            WHERE machine_id = :machine_id;
        """)
        live_row = db.execute(live_query, {"machine_id": machine_id}).fetchone()
        
        live_meta = None
        telemetry_map = {}
        if live_row:
            live_meta = {
                "last_updated": live_row[0].isoformat() if live_row[0] else None,
                "connection_status": live_row[1],
                "batch_no": live_row[2],
                "step_no": live_row[3],
                "program_no": live_row[4]
            }
            if isinstance(live_row[5], dict):
                telemetry_map = live_row[5]

        # 2. Ambil daftar konfigurasi tag
        map_query = text("""
            SELECT 
                id,
                machine_id,
                asset_id,
                register_index,
                iw_number,
                tag_name,
                tag_role,
                field_name,
                unit,
                data_type,
                raw_min,
                raw_max,
                eng_min,
                eng_max,
                scale_factor,
                is_active,
                notes,
                updated_at
            FROM cfg_machine_iw_tag_mapping
            WHERE machine_id = :machine_id
            ORDER BY register_index ASC;
        """)
        rows = db.execute(map_query, {"machine_id": machine_id}).fetchall()
        
        mappings = []
        for r in rows:
            tag_name = r[5]
            live_info = telemetry_map.get(tag_name, {}) if isinstance(telemetry_map, dict) else {}
            
            mappings.append({
                "id": r[0],
                "machine_id": r[1],
                "asset_id": r[2],
                "register_index": r[3],
                "iw_number": r[4],
                "tag_name": tag_name,
                "tag_role": r[6],
                "field_name": r[7],
                "unit": r[8] or "",
                "data_type": r[9],
                "raw_min": r[10],
                "raw_max": r[11],
                "eng_min": r[12],
                "eng_max": r[13],
                "scale_factor": r[14],
                "is_active": r[15],
                "notes": r[16],
                "updated_at": r[17].isoformat() if r[17] else None,
                "live_value": live_info.get("value"),
                "live_raw": live_info.get("raw"),
                "quality": live_info.get("quality", 192)
            })

        return {
            "status": "success",
            "machine_id": machine_id,
            "total_tags": len(mappings),
            "live_meta": live_meta,
            "data": mappings
        }
    except Exception as e:
        logger.error(f"Error fetching mapping for {machine_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/live/{machine_id}")
def get_live_telemetry(machine_id: str, db: Session = Depends(get_db)):
    """
    Mengambil data live telemetry lengkap (snapshot JSON) untuk mesin tertentu.
    """
    try:
        query = text("""
            SELECT last_updated, connection_status, batch_no, step_no, program_no, raw_buffer_hex, telemetry_json
            FROM live_iw_telemetry
            WHERE machine_id = :machine_id;
        """)
        row = db.execute(query, {"machine_id": machine_id}).fetchone()
        if not row:
            return {
                "status": "not_found",
                "machine_id": machine_id,
                "message": f"Belum ada data telemetry aktif untuk mesin {machine_id}."
            }
        
        return {
            "status": "success",
            "machine_id": machine_id,
            "last_updated": row[0].isoformat() if row[0] else None,
            "connection_status": row[1],
            "batch_no": row[2],
            "step_no": row[3],
            "program_no": row[4],
            "total_tags": len(row[6]) if isinstance(row[6], dict) else 0,
            "telemetry": row[6]
        }
    except Exception as e:
        logger.error(f"Error fetching live telemetry for {machine_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
