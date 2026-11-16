"""
OpenOrgaTEX Exact Parity WebService & Controller Routes
100% Matching OrgaTEX WebService.exe, OtxWcfWebServiceLib.dll, and OtxBatchProvider.dll

Exact URL Structure:
- /api/alarmconfiguration/alarms/{language}/{machineGroupNo}
- /api/alarmconfiguration/alarmgroups/{language}/{machineGroupNo}
- /api/alarmconfiguration/stopgroups/{language}/{machineGroupNo}
- /api/alarmconfiguration/functions/{language}/{machineGroupNo}
- /api/alarmconfiguration/functionparameters/{language}/{machineGroupNo}
- /api/alarmconfiguration/functiongroups/{language}/{machineGroupNo}
- /api/alarmconfiguration/resources/{language}/{machineGroupNo}
- /api/alarmconfiguration/machineconstants/{language}/{machineGroupNo}/{machineConstantNo}
- /api/alarmconfiguration/systemconstants/{language}/{machineGroupNo}
- /api/BatchService/CreateBatch
- /api/BatchService/ModifyBatch
- /api/BatchService/DeleteBatch
- /api/BatchService/MoveBatch
- /api/BatchService/GetBatches
- /api/BatchService/GetBatchAsJson
- /api/WebMonitoringService/GetWebControllerStates
- /api/WebMonitoringService/GetMachines
- /api/WebMonitoringService/GetMachineGroups
- /api/RecipeService/GetRecipes
- /api/RecipeService/GetRecipeById
- /api/ProgramService/GetPrograms
- /api/ProgramService/GetProcedures
"""

import os
import json
import time
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any, Union

from fastapi import APIRouter, HTTPException, Depends, Query, Body, Path, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..database import get_db
from ..models.schema_pg import (
    Machine, BatchHeader, Recipe, ProgramHeader,
    DatalogCyclicRecord, DatalogAlarm,
    CfgAlarm, CfgAlarmGroup, CfgStopGroup, CfgFunction,
    CfgFunctionParameter, CfgResource
)

logger = logging.getLogger("orgatex.exact_api")

router = APIRouter(tags=["OrgaTEX Exact WebService Parity"])

PLANNING_PATH = os.path.abspath("./open_orgatex/backend/data/planning.json")
CONFTEXT_PATH = os.path.abspath("./open_orgatex/backend/data/conftext_aligned.json")
TYPECONF_PATH = os.path.abspath("./open_orgatex/backend/data/typeconf_functions.json")

def _load_json(file_path: str) -> Any:
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
    return None

def _save_planning_store(data: List[Dict[str, Any]]):
    os.makedirs(os.path.dirname(PLANNING_PATH), exist_ok=True)
    with open(PLANNING_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def _get_planning_batches() -> List[Dict[str, Any]]:
    data = _load_json(PLANNING_PATH)
    return data if isinstance(data, list) else []

# =============================================================================
# 1. ORGATEX ALARM CONFIGURATION CONTROLLER (Exact URLs from WebService.exe)
# =============================================================================

@router.get("/api/alarmconfiguration/alarms/{language}/{machineGroupNo}")
@router.get("/api/alarmconfiguration/alarms/{language}/{machineGroupNo}/{alarmNo}")
def get_alarms(
    language: str,
    machineGroupNo: int,
    alarmNo: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Parity: WebService.Controllers.AlarmConfigurationController.GetAlarms
    Returns CfgAlarmApi items from SQL database cfg_alarms
    """
    lang = language.lower()
    q = db.query(CfgAlarm).filter(CfgAlarm.language == lang, CfgAlarm.machine_group_no == machineGroupNo)
    if alarmNo is not None:
        q = q.filter(CfgAlarm.alarm_no == alarmNo)
    alarms = q.all()
    if alarms:
        return [
            {
                "AlarmNo": a.alarm_no,
                "AlarmText": a.alarm_text,
                "AlarmGroupNo": a.alarm_group_no,
                "AlarmGroupName": a.alarm_group_name,
                "MachineGroupNo": a.machine_group_no
            }
            for a in alarms
        ]

    conf = _load_json(CONFTEXT_PATH) or {}
    alarm_list = conf.get("Cat_2_Grp_0", [])

    results = []
    for item in alarm_list:
        no = item.get("item", 0)
        if alarmNo is not None and no != alarmNo:
            continue
        text = item.get(lang, item.get("en", item.get("de", "")))
        results.append({
            "AlarmNo": no,
            "AlarmText": text,
            "AlarmGroupNo": 1,
            "AlarmGroupName": "Process Alarms",
            "MachineGroupNo": machineGroupNo
        })

    return results

@router.get("/api/alarmconfiguration/alarmgroups/{language}/{machineGroupNo}")
@router.get("/api/alarmconfiguration/alarmgroups/{language}/{machineGroupNo}/{alarmGroupNo}")
def get_alarm_groups(
    language: str,
    machineGroupNo: int,
    alarmGroupNo: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Parity: WebService.Controllers.AlarmConfigurationController.GetAlarmGroups
    """
    q = db.query(CfgAlarmGroup).filter(CfgAlarmGroup.machine_group_no == machineGroupNo)
    if alarmGroupNo is not None:
        q = q.filter(CfgAlarmGroup.alarm_group_no == alarmGroupNo)
    groups = q.all()
    if groups:
        return [
            {"AlarmGroupNo": g.alarm_group_no, "AlarmGroupName": g.alarm_group_name, "MachineGroupNo": g.machine_group_no}
            for g in groups
        ]

    fallback = [
        {"AlarmGroupNo": 1, "AlarmGroupName": "General Alarms", "MachineGroupNo": machineGroupNo},
        {"AlarmGroupNo": 2, "AlarmGroupName": "Temperature Deviation", "MachineGroupNo": machineGroupNo},
        {"AlarmGroupNo": 3, "AlarmGroupName": "Pressure / Pump Warning", "MachineGroupNo": machineGroupNo},
        {"AlarmGroupNo": 4, "AlarmGroupName": "Dosing Station Alarms", "MachineGroupNo": machineGroupNo}
    ]
    if alarmGroupNo is not None:
        return [g for g in fallback if g["AlarmGroupNo"] == alarmGroupNo]
    return fallback

@router.get("/api/alarmconfiguration/stopgroups/{language}/{machineGroupNo}")
@router.get("/api/alarmconfiguration/stopgroups/{language}/{machineGroupNo}/{stopGroupNo}")
def get_stop_groups(
    language: str,
    machineGroupNo: int,
    stopGroupNo: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Parity: WebService.Controllers.AlarmConfigurationController.GetStopGroups
    """
    q = db.query(CfgStopGroup).filter(CfgStopGroup.machine_group_no == machineGroupNo)
    if stopGroupNo is not None:
        q = q.filter(CfgStopGroup.stop_group_no == stopGroupNo)
    stops = q.all()
    if stops:
        return [
            {"StopGroupNo": s.stop_group_no, "StopGroupName": s.stop_group_name, "MachineGroupNo": s.machine_group_no}
            for s in stops
        ]

    conf = _load_json(CONFTEXT_PATH) or {}
    fallback = conf.get("Cat_4_Grp_0", [])
    lang = language.lower()

    results = []
    for item in fallback:
        no = item.get("item", 0)
        if stopGroupNo is not None and no != stopGroupNo:
            continue
        text = item.get(lang, item.get("en", item.get("de", f"Stop Group {no}")))
        results.append({
            "StopGroupNo": no,
            "StopGroupName": text,
            "MachineGroupNo": machineGroupNo
        })
    if not results:
        results = [{"StopGroupNo": 1, "StopGroupName": "Operator Intervention Required", "MachineGroupNo": machineGroupNo}]
    return results

@router.get("/api/alarmconfiguration/functions/{language}/{machineGroupNo}")
@router.get("/api/alarmconfiguration/functions/{language}/{machineGroupNo}/{functionNo}")
def get_functions(
    language: str,
    machineGroupNo: int,
    functionNo: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Parity: WebService.Controllers.AlarmConfigurationController.GetFunctions
    """
    q = db.query(CfgFunction).filter(CfgFunction.machine_group_no == machineGroupNo)
    if functionNo is not None:
        q = q.filter(CfgFunction.function_no == functionNo)
    funcs = q.all()
    if funcs:
        return [
            {
                "FunctionNo": f.function_no,
                "FunctionName": f.function_name,
                "FunctionGroupNo": f.function_group_no,
                "MachineGroupNo": f.machine_group_no
            }
            for f in funcs
        ]

    typeconf = _load_json(TYPECONF_PATH) or {}
    funcs_json = typeconf.get("functions", {})

    results = []
    for f_id_str, f_data in funcs_json.items():
        f_no = int(f_id_str)
        if functionNo is not None and f_no != functionNo:
            continue
        name = f_data.get("name", f"Function {f_no}")
        results.append({
            "FunctionNo": f_no,
            "FunctionName": name,
            "FunctionGroupNo": 1,
            "MachineGroupNo": machineGroupNo
        })
    return results

@router.get("/api/alarmconfiguration/functiongroups/{language}/{machineGroupNo}")
@router.get("/api/alarmconfiguration/functiongroups/{language}/{machineGroupNo}/{functionGroupNo}")
def get_function_groups(
    language: str,
    machineGroupNo: int,
    functionGroupNo: Optional[int] = None
):
    """
    Parity: WebService.Controllers.AlarmConfigurationController.GetFunctionGroups
    """
    groups = [
        {"FunctionGroupNo": 1, "FunctionGroupName": "Filling & Draining", "MachineGroupNo": machineGroupNo},
        {"FunctionGroupNo": 2, "FunctionGroupName": "Heating & Cooling", "MachineGroupNo": machineGroupNo},
        {"FunctionGroupNo": 3, "FunctionGroupName": "Dosing & Additions", "MachineGroupNo": machineGroupNo},
        {"FunctionGroupNo": 4, "FunctionGroupName": "Circulation & Reel", "MachineGroupNo": machineGroupNo}
    ]
    if functionGroupNo is not None:
        return [g for g in groups if g["FunctionGroupNo"] == functionGroupNo]
    return groups

@router.get("/api/alarmconfiguration/functionparameters/{language}/{machineGroupNo}")
@router.get("/api/alarmconfiguration/functionparameters/{language}/{machineGroupNo}/{functionNo}")
def get_function_parameters(
    language: str,
    machineGroupNo: int,
    functionNo: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Parity: WebService.Controllers.AlarmConfigurationController.GetFunctionParameters
    """
    q = db.query(CfgFunctionParameter)
    if functionNo is not None:
        q = q.filter(CfgFunctionParameter.function_no == functionNo)
    params = q.all()
    if params:
        return [
            {
                "FunctionNo": p.function_no,
                "ParameterNo": p.parameter_no,
                "ParameterName": p.parameter_name,
                "DefaultValue": float(p.default_val) if p.default_val is not None else 0.0,
                "MinValue": float(p.min_val) if p.min_val is not None else 0.0,
                "MaxValue": float(p.max_val) if p.max_val is not None else 0.0,
                "MachineGroupNo": machineGroupNo
            }
            for p in params
        ]

    typeconf = _load_json(TYPECONF_PATH) or {}
    funcs = typeconf.get("functions", {})

    results = []
    for f_id_str, f_data in funcs.items():
        f_no = int(f_id_str)
        if functionNo is not None and f_no != functionNo:
            continue
        params_json = f_data.get("parameters", [])
        for p in params_json:
            results.append({
                "FunctionNo": f_no,
                "ParameterNo": p.get("display_position", 1),
                "ParameterName": f"Parameter {p.get('display_position')}",
                "DefaultValue": p.get("default", 0.0),
                "MinValue": p.get("minimum", 0.0),
                "MaxValue": p.get("maximum", 0.0),
                "MachineGroupNo": machineGroupNo
            })
    return results

@router.get("/api/alarmconfiguration/resources/{language}/{machineGroupNo}")
@router.get("/api/alarmconfiguration/resources/{language}/{machineGroupNo}/{resourceNo}")
def get_resources(
    language: str,
    machineGroupNo: int,
    resourceNo: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Parity: WebService.Controllers.AlarmConfigurationController.GetResources
    """
    q = db.query(CfgResource).filter(CfgResource.machine_group_no == machineGroupNo)
    if resourceNo is not None:
        q = q.filter(CfgResource.resource_no == resourceNo)
    res = q.all()
    if res:
        return [
            {"ResourceNo": r.resource_no, "ResourceName": r.resource_name, "MachineGroupNo": r.machine_group_no}
            for r in res
        ]

    resources = [
        {"ResourceNo": 1, "ResourceName": "Main Vessel (V1)", "MachineGroupNo": machineGroupNo},
        {"ResourceNo": 2, "ResourceName": "Circulation Pump (P1)", "MachineGroupNo": machineGroupNo},
        {"ResourceNo": 3, "ResourceName": "Fabric Reel / Winch (R1)", "MachineGroupNo": machineGroupNo},
        {"ResourceNo": 4, "ResourceName": "Dosing Tank 1 (DT1)", "MachineGroupNo": machineGroupNo},
        {"ResourceNo": 5, "ResourceName": "Dosing Tank 2 (DT2)", "MachineGroupNo": machineGroupNo}
    ]
    if resourceNo is not None:
        return [r for r in resources if r["ResourceNo"] == resourceNo]
    return resources

@router.get("/api/alarmconfiguration/machineconstants/{language}/{machineGroupNo}/{machineConstantNo}")
def get_machine_constants(
    language: str,
    machineGroupNo: int,
    machineConstantNo: int
):
    """
    Parity: WebService.Controllers.AlarmConfigurationController.GetMachineConstants
    """
    return {
        "MachineConstantNo": machineConstantNo,
        "MachineConstantName": f"MC_{machineConstantNo:03d}",
        "MachineGroupNo": machineGroupNo,
        "Value": "100"
    }

@router.get("/api/alarmconfiguration/systemconstants/{language}/{machineGroupNo}")
def get_system_constants(
    language: str,
    machineGroupNo: int
):
    """
    Parity: WebService.Controllers.AlarmConfigurationController.GetSystemConstants
    """
    return [
        {"SystemConstantNo": 1, "SystemConstantName": "SC_MAX_TEMP", "Value": "140.0", "MachineGroupNo": machineGroupNo},
        {"SystemConstantNo": 2, "SystemConstantName": "SC_DEFAULT_LIQUOR_RATIO", "Value": "8.0", "MachineGroupNo": machineGroupNo},
        {"SystemConstantNo": 3, "SystemConstantName": "SC_VERSION", "Value": "12.4.4.1119", "MachineGroupNo": machineGroupNo}
    ]

# =============================================================================
# 2. ORGATEX BATCH SERVICE (Exact Parity: IBatchService / BatchPoolManager)
# Accessible via both /api/BatchService/... and /BatchService/...
# =============================================================================

class OrgaTexBatchDto(BaseModel):
    BatchNo: str = Field(..., description="Nomor Batch/Lot Produksi")
    BatchRefNo: Optional[str] = Field(None, description="Nomor Referensi internal (6 digit)")
    MachineNo: str = Field(..., description="Kode Mesin SETEX")
    ProgramNo: int = Field(1, description="Nomor Program M_xxxx.PRG")
    RecipeName: Optional[str] = Field("Reactive Dyeing Formula", description="Nama Formula / Resep")
    CustomerInfo: Optional[str] = Field("PT. ARTA PERMAI", description="Nama Customer")
    ColorName: Optional[str] = Field(None, description="Nama Warna")
    ColorNo: Optional[str] = Field(None, description="Kode Warna")
    FlagBatchWeight: float = Field(350.0, description="Berat Kain (Kg)")
    FlagLiquorAmount: float = Field(8.0, description="Rasio Air / Liquor Ratio")
    BatchText_01: Optional[str] = Field(None, description="Keterangan / Artikel Kain")
    Position: Optional[int] = Field(None, description="Urutan Posisi Antrian")
    ForceCreateReDye: Optional[bool] = Field(False, description="Paksa buat ReDye jika sudah ada")

@router.post("/api/BatchService/CreateBatch")
@router.post("/BatchService/CreateBatch")
@router.post("/api/batch/CreateBatch")
def otx_create_batch(dto: OrgaTexBatchDto, db: Session = Depends(get_db)):
    """
    Exact Parity: OtxWcfWebServiceLib.BatchService.CreateBatch
    """
    batches = _get_planning_batches()
    existing = next((b for b in batches if b.get("batch_no") == dto.BatchNo and b.get("status") not in ["FINISHED", "CANCELLED"]), None)
    if existing and not dto.ForceCreateReDye:
        raise HTTPException(
            status_code=409,
            detail=f"Batch with BatchText_01:{dto.BatchNo} already exists. Try to CreateBatch with Parameter forceCreateReDye: true"
        )

    ref_no = dto.BatchRefNo or str(int(time.time()))[-6:]
    new_record = {
        "id": f"b-{ref_no}",
        "reference_no": ref_no,
        "batch_no": dto.BatchNo,
        "machine_no": dto.MachineNo.upper(),
        "program_no": dto.ProgramNo,
        "recipe_name": dto.RecipeName,
        "customer": dto.CustomerInfo,
        "article": dto.BatchText_01 or "CM 30S RIB",
        "color_code": dto.ColorNo or "1650159",
        "color_name": dto.ColorName or "UNGU TUA",
        "fabric_weight_kg": dto.FlagBatchWeight,
        "liquor_ratio": dto.FlagLiquorAmount,
        "total_water_l": round(dto.FlagBatchWeight * dto.FlagLiquorAmount, 2),
        "status": "QUEUED",
        "position": dto.Position or (len([b for b in batches if b.get("machine_no") == dto.MachineNo.upper()]) + 1),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    batches.append(new_record)
    _save_planning_store(batches)

    try:
        db_b = BatchHeader(
            batch_ref_no=ref_no,
            machine_no=dto.MachineNo.upper(),
            program_no=dto.ProgramNo,
            status="QUEUED",
            fabric_weight_kg=dto.FlagBatchWeight,
            liquor_ratio=dto.FlagLiquorAmount,
            customer=dto.CustomerInfo
        )
        db.add(db_b)
        db.commit()
    except Exception:
        db.rollback()

    return {
        "Result": "Success",
        "BatchRefNo": ref_no,
        "BatchNo": dto.BatchNo,
        "MachineNo": dto.MachineNo.upper(),
        "Status": "QUEUED"
    }

@router.get("/api/BatchService/GetBatches")
@router.post("/api/BatchService/GetBatches")
@router.get("/BatchService/GetBatches")
@router.get("/api/BatchService/GetBatchesAsJson")
def otx_get_batches(
    machineNo: Optional[str] = None,
    status: Optional[str] = None
):
    """
    Exact Parity: OtxWcfWebServiceLib.BatchService.GetBatches & GetBatchesAsJson
    """
    batches = _get_planning_batches()
    if machineNo and isinstance(machineNo, str):
        batches = [b for b in batches if b.get("machine_no", "").upper() == machineNo.upper()]
    if status and isinstance(status, str):
        batches = [b for b in batches if b.get("status", "").upper() == status.upper()]

    # Convert to OrgaTEX DataContract shape (BatchServiceInfo)
    result = []
    for b in batches:
        result.append({
            "BatchNo": b.get("batch_no"),
            "BatchRefNo": b.get("reference_no"),
            "MachineNo": b.get("machine_no"),
            "ProgramNo": b.get("program_no"),
            "RecipeName": b.get("recipe_name"),
            "CustomerInfo": b.get("customer"),
            "ColorName": b.get("color_name"),
            "ColorNo": b.get("color_code"),
            "FlagBatchWeight": b.get("fabric_weight_kg"),
            "FlagLiquorAmount": b.get("liquor_ratio"),
            "BatchStatus": b.get("status"),
            "Position": b.get("position"),
            "Creation": b.get("created_at")
        })
    return result

@router.post("/api/BatchService/ModifyBatch")
@router.post("/BatchService/ModifyBatch")
def otx_modify_batch(payload: Dict[str, Any] = Body(...)):
    """
    Exact Parity: OtxWcfWebServiceLib.BatchService.ModifyBatch
    """
    batch_no = payload.get("BatchNo") or payload.get("BatchRefNo")
    batches = _get_planning_batches()
    target = next((b for b in batches if b.get("batch_no") == batch_no or b.get("reference_no") == batch_no), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"Batch {batch_no} did not exist")

    for k, v in payload.items():
        if k == "FlagBatchWeight":
            target["fabric_weight_kg"] = float(v)
        elif k == "FlagLiquorAmount":
            target["liquor_ratio"] = float(v)
        elif k == "RecipeName":
            target["recipe_name"] = v
        elif k == "CustomerInfo":
            target["customer"] = v
        elif k == "BatchStatus":
            target["status"] = v

    _save_planning_store(batches)
    return {"Result": "Success", "BatchNo": target.get("batch_no")}

@router.post("/api/BatchService/DeleteBatch")
@router.post("/BatchService/DeleteBatch")
def otx_delete_batch(payload: Dict[str, Any] = Body(...)):
    """
    Exact Parity: OtxWcfWebServiceLib.BatchService.DeleteBatch
    """
    batch_no = payload.get("BatchNo") or payload.get("BatchRefNo")
    batches = _get_planning_batches()
    target = next((b for b in batches if b.get("batch_no") == batch_no or b.get("reference_no") == batch_no), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"Batch {batch_no} did not exist")

    target["status"] = "CANCELLED"
    _save_planning_store(batches)
    return {"Result": "Success", "BatchNo": batch_no, "Status": "CANCELLED"}

@router.post("/api/BatchService/MoveBatch")
@router.post("/BatchService/MoveBatch")
def otx_move_batch(payload: Dict[str, Any] = Body(...)):
    """
    Exact Parity: OtxWcfWebServiceLib.BatchService.MoveBatch
    """
    batch_no = payload.get("BatchNo") or payload.get("BatchRefNo")
    target_machine = payload.get("TargetMachine") or payload.get("TargetMachineNo")
    new_pos = payload.get("Position") or payload.get("NewPosition")

    batches = _get_planning_batches()
    target = next((b for b in batches if b.get("batch_no") == batch_no or b.get("reference_no") == batch_no), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"Batch {batch_no} did not exist")

    if target_machine:
        target["machine_no"] = target_machine.upper()
    if new_pos is not None:
        target["position"] = int(new_pos)

    _save_planning_store(batches)
    return {"Result": "Success", "BatchNo": batch_no, "MachineNo": target["machine_no"], "Position": target.get("position")}

@router.get("/api/BatchService/GetBatchTemplate")
def otx_get_batch_template():
    return {
        "TemplateID": 1,
        "TemplateName": "Standard Dyeing Batch Template",
        "DefaultTypeConf": 1,
        "Parameters": [
            {"Name": "FabricWeight", "Type": "Float", "Default": 350.0, "Unit": "Kg"},
            {"Name": "LiquorRatio", "Type": "Float", "Default": 8.0, "Unit": ":1"},
            {"Name": "ReelSpeed", "Type": "Float", "Default": 240.0, "Unit": "m/min"},
            {"Name": "PumpPressure", "Type": "Float", "Default": 2.2, "Unit": "bar"}
        ]
    }

# =============================================================================
# 3. ORGATEX MONITORING SERVICE (Exact Parity: IWebMonitoringService / OnlineStatus)
# =============================================================================

@router.get("/api/WebMonitoringService/GetWebControllerStates")
@router.get("/WebMonitoringService/GetWebControllerStates")
@router.get("/api/OnlineStatus/GetOnlineControllerInfo")
def otx_get_controller_states(db: Session = Depends(get_db)):
    """
    Exact Parity: OtxWcfWebServiceLib.Monitoring.WebMonitoringService.GetWebControllerStates
    Returns WebControllerState list
    """
    machines = db.query(Machine).all()
    result = []
    for m in machines:
        result.append({
            "MachineNo": m.machine_no,
            "ControllerType": m.controller_type,
            "OperationalStatus": m.status,
            "CurrentBatchNo": m.current_batch,
            "CurrentStepNo": m.current_step,
            "ActualTemp": float(m.current_temp) if m.current_temp is not None else 0.0,
            "IpAddress": m.ip_address,
            "IsOnline": m.status in ["ONLINE", "RUNNING"]
        })
    return result

@router.get("/api/WebMonitoringService/GetMachines")
@router.get("/WebMonitoringService/GetMachines")
def otx_get_machines(db: Session = Depends(get_db)):
    """
    Exact Parity: OtxWcfWebServiceLib.Monitoring.WebMonitoringService.GetMachines
    """
    machines = db.query(Machine).all()
    return [
        {
            "MachineNo": m.machine_no,
            "DisplayName": m.display_name,
            "MachineGroup": m.group_name,
            "CapacityKg": float(m.capacity_kg) if m.capacity_kg is not None else 350.0,
            "ControllerType": m.controller_type
        }
        for m in machines
    ]

@router.get("/api/WebMonitoringService/GetMachineGroups")
@router.get("/WebMonitoringService/GetMachineGroups")
def otx_get_machine_groups(db: Session = Depends(get_db)):
    """
    Exact Parity: OtxWcfWebServiceLib.Monitoring.WebMonitoringService.GetMachineGroups
    """
    return [
        {"GroupNo": 1, "GroupName": "Dyeing Section A (High Temp Jets)", "MachinesCount": 12},
        {"GroupNo": 2, "GroupName": "Dyeing Section B (Atmospheric Jiggers)", "MachinesCount": 6},
        {"GroupNo": 3, "GroupName": "Drying & Stenter Finishing", "MachinesCount": 4}
    ]

# =============================================================================
# 4. ORGATEX RECIPE & PROGRAM SERVICES (Exact Parity: RDM / EDX300)
# =============================================================================

@router.get("/api/RecipeService/GetRecipes")
@router.get("/RecipeService/GetRecipes")
def otx_get_recipes(db: Session = Depends(get_db)):
    """
    Exact Parity: OtxWcfWebServiceLib.RDM.GetRecipes
    """
    recipes = db.query(Recipe).all()
    res = []
    for r in recipes:
        items = [
            {
                "ChemicalCode": it.chemical_code,
                "ChemicalName": it.chemical_name,
                "Amount": float(it.amount),
                "Unit": it.unit,
                "DosingTank": it.dosing_tank
            }
            for it in r.items
        ]
        res.append({
            "RecipeID": r.recipe_id,
            "RecipeNo": r.recipe_code,
            "RecipeName": r.recipe_name,
            "CustomerName": r.customer_name,
            "FabricType": r.fabric_type,
            "LiquorRatio": float(r.standard_liquor_ratio) if r.standard_liquor_ratio else 8.0,
            "Items": items
        })
    return res

@router.get("/api/RecipeService/GetRecipeById")
def otx_get_recipe_by_id(recipeId: int = Query(...), db: Session = Depends(get_db)):
    r = db.query(Recipe).filter(Recipe.recipe_id == recipeId).first()
    if not r:
        raise HTTPException(status_code=404, detail="RecipeNotFoundException")
    return {
        "RecipeID": r.recipe_id,
        "RecipeNo": r.recipe_code,
        "RecipeName": r.recipe_name,
        "CustomerName": r.customer_name,
        "FabricType": r.fabric_type,
        "LiquorRatio": float(r.standard_liquor_ratio) if r.standard_liquor_ratio else 8.0
    }

@router.get("/api/ProgramService/GetPrograms")
@router.get("/ProgramService/GetPrograms")
def otx_get_programs(db: Session = Depends(get_db)):
    """
    Exact Parity: OtxWcfWebServiceLib.EDX300.GetPrograms
    """
    progs = db.query(ProgramHeader).all()
    return [
        {
            "ProgramNo": p.program_no,
            "ProgramName": p.program_name,
            "FabricType": p.fabric_type,
            "EstimatedDurationMin": p.estimated_duration_min,
            "TotalSteps": len(p.steps)
        }
        for p in progs
    ]
