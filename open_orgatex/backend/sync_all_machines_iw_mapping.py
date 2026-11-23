#!/usr/bin/env python3
"""
Sync All Machines IW Mapping to Database (pt_smm_jetflow & SQLite fallback)
Reads WORKSPACE_PROGRAM_MESIN/MESIN_{id}/02_CONFIG_SIAP_PAKAI/typeconf_iw_map.json
and populates cfg_machine_iw_tag_mapping with 1-based IW numbers (register_index == iw_number).
"""

import os
import re
import json
import logging
import psycopg2
from psycopg2.extras import execute_values

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sync_iw_mapping")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
WORKSPACE_DIR = os.path.join(BASE_DIR, "WORKSPACE_PROGRAM_MESIN")
PG_URL = os.getenv("DATABASE_URL", "postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow")

def machine_to_asset_id(mach: str) -> str:
    mach_clean = mach.upper().strip()
    match = re.match(r"^(\d+)([A-Z])$", mach_clean)
    if match:
        num, lane = match.groups()
        return f"JF-L{lane}-{int(num):02d}"
    if mach_clean == "DA01":
        return "JF-LB-01"
    return f"JF-LB-{mach_clean}"

def clean_tag_segment(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", text.strip())
    return cleaned.strip("_").upper()

def determine_tag_and_role(reg_num: int, name: str, asset_id: str):
    name_lower = name.lower()
    
    # Well-known registers
    if reg_num == 1 or "act.temp" in name_lower:
        return f"SMM.{asset_id}.MAIN_TANK.TEMPERATURE_PV", "act_temp", "PV"
    if reg_num == 2 or name_lower == "time":
        return f"SMM.{asset_id}.PROCESS.TIME_PV", "time", "PV"
    if reg_num == 10 or "set temperature" in name_lower:
        return f"SMM.{asset_id}.MAIN_TANK.TEMPERATURE_SV", "temp_setpoint", "SV"
    if reg_num == 11:
        return f"SMM.{asset_id}.CONTROLLER.LEVEL_MACHINE_DIG_PV", "level_machine_dig", "PV"
    if reg_num == 12 or "level machine (%)" in name_lower:
        return f"SMM.{asset_id}.MAIN_TANK.LEVEL_PV", "level_machine", "PV"
    if reg_num == 13:
        return f"SMM.{asset_id}.CONTROLLER.QUANTITY_MACHINE_L_PV", "quantity_machine_l", "PV"
    if reg_num == 14:
        return f"SMM.{asset_id}.WATER_INLET.FLOW_PV", "flow", "PV"
    if reg_num == 15 or "water counter" in name_lower:
        return f"SMM.{asset_id}.CONTROLLER.WATER_COUNTER_IW_PV", "water_counter_iw", "PV"
    if reg_num == 16 or "pressure machine" in name_lower:
        return f"SMM.{asset_id}.VESSEL.PRESSURE_PV", "pressure_machine", "PV"
    if reg_num == 17:
        return f"SMM.{asset_id}.MAIN_TANK.LEVEL_L_PV", "main_tank_level_l", "PV"
    if reg_num == 21 or "speed main pump" in name_lower:
        return f"SMM.{asset_id}.MAIN_MOTOR.SPEED_PV", "speed_main_pump", "PV"
    if reg_num == 22 or "winch speed" in name_lower:
        return f"SMM.{asset_id}.MAIN_MOTOR.WINCH_SPEED_PV", "winch_speed", "PV"
    if reg_num == 25:
        return f"SMM.{asset_id}.SERVICE_TANK.TEMPERATURE_PV", "temperature_st", "PV"
    if reg_num == 27:
        return f"SMM.{asset_id}.SERVICE_TANK.LEVEL_L_PV", "level_st_l", "PV"
    if reg_num == 28:
        return f"SMM.{asset_id}.SERVICE_TANK.LEVEL_PV", "level_st_pct", "PV"
    if reg_num == 30:
        return f"SMM.{asset_id}.ADDITION_TANK.TEMPERATURE_PV", "temperature_at", "PV"
    if reg_num == 32:
        return f"SMM.{asset_id}.ADDITION_TANK.LEVEL_L_PV", "level_at_l", "PV"
    if reg_num == 33:
        return f"SMM.{asset_id}.ADDITION_TANK.LEVEL_PV", "level_at_pct", "PV"
    if reg_num == 36:
        return f"SMM.{asset_id}.DOSING_TANK_01.START_DOSING_AMO_AT1_PV", "start_dosing_amo_at1", "PV"
    if reg_num == 39:
        return f"SMM.{asset_id}.CONTROLLER.ACTIVE_TANK_PV", "active_tank", "PV"
    if reg_num == 40:
        return f"SMM.{asset_id}.DOSING_TANK_01.TEMPERATURE_PV", "temperature_at1", "PV"
    if reg_num == 42:
        return f"SMM.{asset_id}.DOSING_TANK_01.LEVEL_L_PV", "level_at1_l", "PV"
    if reg_num == 43:
        return f"SMM.{asset_id}.DOSING_TANK_01.LEVEL_PV", "level_at1_pct", "PV"
    if reg_num == 45:
        return f"SMM.{asset_id}.DOSING_TANK_02.TEMPERATURE_PV", "temperature_at2", "PV"
    if reg_num == 47:
        return f"SMM.{asset_id}.DOSING_TANK_02.LEVEL_L_PV", "level_at2_l", "PV"
    if reg_num == 48:
        return f"SMM.{asset_id}.DOSING_TANK_02.LEVEL_PV", "level_at2_pct", "PV"

    # Generic categorization
    role = "SV" if "set" in name_lower or "sp" in name_lower else "PV"
    
    if "at1" in name_lower:
        section = "DOSING_TANK_01"
    elif "at2" in name_lower:
        section = "DOSING_TANK_02"
    elif "at" in name_lower:
        section = "ADDITION_TANK"
    elif "st" in name_lower:
        section = "SERVICE_TANK"
    elif "temp" in name_lower:
        section = "MAIN_TANK"
    elif "pump" in name_lower or "winch" in name_lower:
        section = "MAIN_MOTOR"
    elif "press" in name_lower:
        section = "VESSEL"
    else:
        section = "CONTROLLER"
        
    clean_name = clean_tag_segment(name)
    tag_name = f"SMM.{asset_id}.{section}.{clean_name}_{role}"
    field_name = clean_name.lower()
    return tag_name, field_name, role

def sync_machine(mach_id: str, json_path: str, conn):
    asset_id = machine_to_asset_id(mach_id)
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = []
    for k_str, meta in data.items():
        try:
            reg_num = int(k_str)
        except ValueError:
            continue
            
        # Skip dummy / corrupted index 0
        if reg_num <= 0:
            continue

        name = meta.get("name", f"IW {reg_num}")
        name_local = meta.get("name_local", "")
        unit = meta.get("unit", "")
        if unit in ["dak", "dk", "dak."]:
            unit = "min"
        elif unit in ["m/dak", "m/dk"]:
            unit = "m/min"
        elif unit in ["d/dak", "d/dk"]:
            unit = "rpm"
        elif unit in ["Lt", "lt", "LT"]:
            unit = "L"

        raw_min = float(meta.get("y1", 0.0))
        raw_max = float(meta.get("y2", 1000.0))
        eng_min = float(meta.get("x1", 0.0))
        eng_max = float(meta.get("x2", 100.0))
        factor = float(meta.get("factor", 1.0))

        tag_name, field_name, role = determine_tag_and_role(reg_num, name, asset_id)
        notes = f"{name} ({name_local}) [IW {reg_num}]".strip() if name_local else f"{name} [IW {reg_num}]"

        # IMPORTANT: register_index == iw_number == reg_num
        records.append((
            mach_id,
            asset_id,
            reg_num,        # register_index
            reg_num,        # iw_number (1-based, exact match)
            tag_name,
            role,
            field_name,
            unit,
            "FLOAT",
            raw_min,
            raw_max,
            eng_min,
            eng_max,
            factor,
            True,          # is_active (boolean)
            notes
        ))

    # Standard Setpoints from Object 1009 (SET)
    setpoints = [
        (10092, 10092, f"SMM.{asset_id}.PROCESS.HOLDING_TIME_SV", "SV", "holding_time_setpoint", "min", 0.0, 180.0, 0.0, 180.0, 1.0, "Target Holding Time Setpoint"),
        (10093, 10093, f"SMM.{asset_id}.PROCESS.GRADIENT_SV", "SV", "gradient_setpoint", "°C/min", 0.0, 10.0, 0.0, 10.0, 1.0, "Target Temperature Gradient Setpoint"),
        (10094, 10094, f"SMM.{asset_id}.MAIN_MOTOR.SPEED_SV", "SV", "speed_setpoint", "%", 0.0, 100.0, 0.0, 100.0, 1.0, "Target Pump / Winch Speed Setpoint"),
        (10098, 10098, f"SMM.{asset_id}.MAIN_TANK.LEVEL_SV", "SV", "level_setpoint", "L", 0.0, 5000.0, 0.0, 5000.0, 1.0, "Target Fill Volume / Level Setpoint"),
    ]
    for sp in setpoints:
        records.append((
            mach_id, asset_id, sp[0], sp[1], sp[2], sp[3], sp[4], sp[5],
            "FLOAT", sp[6], sp[7], sp[8], sp[9], sp[10], True, sp[11]
        ))

    cur = conn.cursor()
    # Delete existing mappings for this machine
    cur.execute("DELETE FROM cfg_machine_iw_tag_mapping WHERE machine_id = %s;", (mach_id,))
    
    # Bulk insert
    insert_sql = """
        INSERT INTO cfg_machine_iw_tag_mapping (
            machine_id, asset_id, register_index, iw_number,
            tag_name, tag_role, field_name, unit, data_type,
            raw_min, raw_max, eng_min, eng_max, scale_factor,
            is_active, notes, updated_at
        ) VALUES %s
        ON CONFLICT (machine_id, register_index) DO UPDATE SET
            iw_number = EXCLUDED.iw_number,
            tag_name = EXCLUDED.tag_name,
            tag_role = EXCLUDED.tag_role,
            field_name = EXCLUDED.field_name,
            unit = EXCLUDED.unit,
            raw_min = EXCLUDED.raw_min,
            raw_max = EXCLUDED.raw_max,
            eng_min = EXCLUDED.eng_min,
            eng_max = EXCLUDED.eng_max,
            scale_factor = EXCLUDED.scale_factor,
            notes = EXCLUDED.notes,
            updated_at = NOW();
    """
    
    template = "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())"
    execute_values(cur, insert_sql, records, template=template)
    conn.commit()
    logger.info(f"Synced {len(records)} registers for {mach_id} ({asset_id})")

def main():
    if not os.path.exists(WORKSPACE_DIR):
        logger.error(f"Workspace directory not found: {WORKSPACE_DIR}")
        return

    try:
        conn = psycopg2.connect(PG_URL)
        logger.info(f"Connected to PostgreSQL database: {PG_URL.split('@')[-1]}")
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")
        return

    synced_count = 0
    for entry in sorted(os.listdir(WORKSPACE_DIR)):
        if not entry.startswith("MESIN_"):
            continue
        mach_id = entry.replace("MESIN_", "")
        json_path = os.path.join(WORKSPACE_DIR, entry, "02_CONFIG_SIAP_PAKAI", "typeconf_iw_map.json")
        if os.path.exists(json_path):
            try:
                sync_machine(mach_id, json_path, conn)
                synced_count += 1
            except Exception as e:
                logger.error(f"Failed to sync {mach_id}: {e}")
                conn.rollback()

    conn.close()
    logger.info(f"Successfully synchronized {synced_count} machines to cfg_machine_iw_tag_mapping!")

if __name__ == "__main__":
    main()
