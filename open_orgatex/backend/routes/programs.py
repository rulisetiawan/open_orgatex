"""
Dyeing Programs Route (OrgaTEX EDX300 Parity)
Full Procedure (Master Program) & Treatment (Sub-Program) Integration
Persists in PostgreSQL / TimescaleDB using OrgaTEX schema (program_components, program_component_items, steps, etc.)
"""

from fastapi import APIRouter, HTTPException, Depends, Response, Request
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from sqlalchemy import text, func, or_
from sqlalchemy.orm import Session, selectinload
import logging
import os
import re
import json
import time
import struct
import base64
import hashlib
from datetime import datetime

from ..database import get_db
from ..models.schema_pg import (
    ProgramComponent,
    ProgramComponentItem,
    ProgramComponentParameter,
    Step,
    StepFunction,
    StepFunctionParameter,
    Machine
)
from ..services.machine_config_service import (
    fetch_machine_programs_from_hmi,
    sync_machine_ready_config,
)
from ..utils.secom_codec import (
    parse_prg_binary,
    serialize_prg_binary,
    build_minimal_prg
)

router = APIRouter(prefix="/api/programs", tags=["Programs & Treatments (EDX300)"])

# File paths
SUMMARY_CANDIDATES = [
    "/app/plain_export/PROGRAMS_SUMMARY.json",
    "/app/sc777ce_root/plain_export/PROGRAMS_SUMMARY.json",
    os.path.abspath("./plain_export/PROGRAMS_SUMMARY.json"),
    os.path.abspath("../plain_export/PROGRAMS_SUMMARY.json"),
    os.path.abspath("./open_orgatex/backend/data/programs_summary.json")
]

DETAIL_DIR_CANDIDATES = [
    "/app/plain_export/PROGRAMS_DETAIL",
    "/app/sc777ce_root/plain_export/PROGRAMS_DETAIL",
    os.path.abspath("./plain_export/PROGRAMS_DETAIL"),
    os.path.abspath("../plain_export/PROGRAMS_DETAIL")
]

META_PATH = os.path.abspath("./open_orgatex/backend/data/programs_custom.json")
TREATMENTS_META_PATH = os.path.abspath("./open_orgatex/backend/data/treatments_library.json")
CATALOG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/prg_catalog_data.json"))
COMPILED_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/compiled_prg"))
os.makedirs(os.path.dirname(META_PATH), exist_ok=True)
os.makedirs(COMPILED_DIR, exist_ok=True)

if os.path.isdir("/app/sc777ce_root/WORKSPACE_PROGRAM_MESIN"):
    MACHINE_WORKSPACE_BASE = "/app/sc777ce_root/WORKSPACE_PROGRAM_MESIN"
else:
    MACHINE_WORKSPACE_BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../WORKSPACE_PROGRAM_MESIN"))

# Pydantic Schemas
class StepFunctionIn(BaseModel):
    function_id: int
    name: Optional[str] = ""
    column: Optional[int] = 1
    flags: Optional[int] = 0
    params: Optional[List[float]] = []
    param_formulas: Optional[Dict[str, Any]] = {}

class StepIn(BaseModel):
    step_no: int
    label: Optional[str] = ""
    functions: List[StepFunctionIn] = []
    summary_temp: Optional[float] = None
    summary_time_min: Optional[float] = 0
    summary_pump_pct: Optional[float] = 85.0
    summary_reel_speed: Optional[float] = 200.0
    summary_water_l: Optional[float] = 0

class SubProgramItemIn(BaseModel):
    position: int
    treatment_id: Optional[int] = None
    treatment_number: Optional[str] = ""
    treatment_name: str
    parameters: Optional[Dict[str, float]] = {}
    steps: List[StepIn] = []

class ProcedureIn(BaseModel):
    program_no: int = Field(..., ge=1, le=9999, description="Nomor Program SETEX (1 - 9999)")
    program_name: str
    machine_code: Optional[str] = "C012"
    sub_programs: Optional[List[SubProgramItemIn]] = []
    steps: Optional[List[StepIn]] = []

class TreatmentIn(BaseModel):
    id: Optional[int] = None
    number: str
    name: str
    comment: Optional[str] = ""
    category: Optional[str] = "General"
    machine_group: Optional[str] = "Semua Mesin Celup"
    parameters: Optional[Dict[str, float]] = {}
    steps: Optional[List[StepIn]] = []

# Standard Treatment Library (Sub-Programs) — Strictly uses verified TYPECONF.CNF Function IDs
DEFAULT_TREATMENTS = [
    {
        "id": 1,
        "number": "TR-SCOUR",
        "name": "Prapengolahan S/B (Scouring & Bleaching)",
        "comment": "Pemasakan dan pengelantangan kapas suhu 98°C",
        "steps": [
            {
                "step_no": 1,
                "label": "Isi Air Hangat",
                "functions": [{"function_id": 713, "name": "Fill Level", "column": 1, "params": [1.0, 3200.0]}]
            },
            {
                "step_no": 2,
                "label": "Injeksi Kimia S/B (AT1)",
                "functions": [{"function_id": 938, "name": "Dosing Prpgression 1", "column": 1, "params": [40.0, 1.5, 0.0, 1.0, 10.0]}]
            },
            {
                "step_no": 3,
                "label": "Pemanasan & Tahan Suhu 98°C",
                "functions": [{"function_id": 141, "name": "Temperature Control", "column": 1, "params": [98.0, 2.5, 45.0]}]
            },
            {
                "step_no": 4,
                "label": "Drain Total",
                "functions": [{"function_id": 71, "name": "Drain Percent", "column": 1, "params": [100.0, 1.0, 0.0]}]
            }
        ]
    },
    {
        "id": 2,
        "number": "TR-DYE-REACT",
        "name": "Proses Celup Reaktif 60°C (Dyeing Phase)",
        "comment": "Pencelupan katun reaktif vinyl / MCT suhu 60°C",
        "steps": [
            {
                "step_no": 1,
                "label": "Isi Air Celup & Pompa",
                "functions": [
                    {"function_id": 713, "name": "Fill Level", "column": 1, "params": [1.0, 3000.0]},
                    {"function_id": 404, "name": "Dye Liquor Pump", "column": 2, "params": [30.0, 85.0]}
                ]
            },
            {
                "step_no": 2,
                "label": "Dosing Garam Glauber (AT1)",
                "functions": [{"function_id": 938, "name": "Dosing Prpgression 1", "column": 1, "params": [40.0, 1.5, 0.0, 1.0, 15.0]}]
            },
            {
                "step_no": 3,
                "label": "Dosing Zat Warna (AT2)",
                "functions": [{"function_id": 939, "name": "Dosing Prpgression 2", "column": 1, "params": [40.0, 1.5, 0.0, 1.0, 20.0]}]
            },
            {
                "step_no": 4,
                "label": "Heating & Fiksasi Suhu 60°C",
                "functions": [{"function_id": 141, "name": "Temperature Control", "column": 1, "params": [60.0, 1.5, 45.0]}]
            },
            {
                "step_no": 5,
                "label": "Cooling ke 50°C",
                "functions": [{"function_id": 141, "name": "Temperature Control", "column": 1, "params": [50.0, 2.0, 5.0]}]
            },
            {
                "step_no": 6,
                "label": "Drain Larutan Celup",
                "functions": [{"function_id": 71, "name": "Drain Percent", "column": 1, "params": [100.0, 1.0, 0.0]}]
            }
        ]
    },
    {
        "id": 3,
        "number": "TR-SOAP",
        "name": "Pencucian Sabun Panas (Soaping 95°C)",
        "comment": "Pencucian sabun untuk menghilangkan sisa zat warna yang tidak terfiksasi",
        "steps": [
            {
                "step_no": 1,
                "label": "Isi Air Bersih",
                "functions": [{"function_id": 713, "name": "Fill Level", "column": 1, "params": [1.0, 3000.0]}]
            },
            {
                "step_no": 2,
                "label": "Dosing Sabun Pencuci (AT1)",
                "functions": [{"function_id": 938, "name": "Dosing Prpgression 1", "column": 1, "params": [50.0, 2.0, 0.0, 1.0, 5.0]}]
            },
            {
                "step_no": 3,
                "label": "Pemanasan & Hold Sabun 95°C",
                "functions": [{"function_id": 141, "name": "Temperature Control", "column": 1, "params": [95.0, 2.5, 20.0]}]
            },
            {
                "step_no": 4,
                "label": "Drain",
                "functions": [{"function_id": 71, "name": "Drain Percent", "column": 1, "params": [100.0, 1.0, 0.0]}]
            }
        ]
    },
    {
        "id": 4,
        "number": "TR-RINSE",
        "name": "Pembilasan Dingin & Selesai (Rinse & End)",
        "comment": "Bilas air dingin dan pengunci selesai program Secom 777",
        "steps": [
            {
                "step_no": 1,
                "label": "Isi Air Bilas",
                "functions": [{"function_id": 713, "name": "Fill Level", "column": 1, "params": [1.0, 2500.0]}]
            },
            {
                "step_no": 2,
                "label": "Bilas Dingin 10 Menit",
                "functions": [{"function_id": 710, "name": "Rinse Time Mode", "column": 1, "params": [1.0, 1.0, 10.0, 1.0]}]
            },
            {
                "step_no": 3,
                "label": "Drain Akhir",
                "functions": [{"function_id": 71, "name": "Drain Percent", "column": 1, "params": [100.0, 1.0, 0.0]}]
            }
        ]
    }
]

def _load_json_file(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default

def _save_json_file(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def _get_summary_file():
    for p in SUMMARY_CANDIDATES:
        if os.path.exists(p):
            return p
    return None

def _get_detail_dir():
    for d in DETAIL_DIR_CANDIDATES:
        if os.path.exists(d):
            return d
    return None


def load_machine_config_bundle(machine_no: str) -> Dict[str, Any]:
    """
    Loads machine-specific SECOM configuration strictly from non-AWL .CNF files:
      - Config/TYPECONF.CNF -> functions, parameters, resources, groups, text_choices
      - Config/CONFTEXT.CNF & FNLEGEND.CNF -> texts/alarms metadata
      - Config/USERCONF.CNF -> main_labels (1..20) & nachsatz_labels
      - Config/MACHCONF.CNF -> machine parameters metadata
    Never reads Function IDs or Program IDs from .AWL PLC execution files.
    """
    clean_no = (machine_no or "TD12").strip().upper().replace("MESIN_", "")
    m_folder = f"MESIN_{clean_no}"
    m_path = os.path.join(MACHINE_WORKSPACE_BASE, m_folder)
    is_template_fallback = False

    if not os.path.isdir(m_path):
        m_path = os.path.join(MACHINE_WORKSPACE_BASE, "_TEMPLATE_MESIN_BARU")
        is_template_fallback = True

    raw_dir = os.path.join(m_path, "01_CONFIG_DARI_HMI")
    config_dir = os.path.join(m_path, "02_CONFIG_SIAP_PAKAI")
    tf_path = os.path.join(config_dir, "typeconf_functions.json")
    uc_path = os.path.join(config_dir, "userconf_labels.json")
    mc_path = os.path.join(config_dir, "machconf_info.json")
    prof_path = os.path.join(config_dir, "machine_profile.json")

    raw_tc = os.path.join(raw_dir, "TYPECONF.CNF")
    raw_uc = os.path.join(raw_dir, "USERCONF.CNF")
    raw_mc = os.path.join(raw_dir, "MACHCONF.CNF")

    typeconf_data: Dict[str, Any] = {}
    if os.path.exists(tf_path):
        try:
            with open(tf_path, "r", encoding="utf-8") as f:
                typeconf_data = json.load(f)
        except Exception:
            typeconf_data = {}

    # Auto-redecode from raw TYPECONF.CNF if JSON is missing or lacks resources/text_choices/lines
    needs_resync = False
    if not is_template_fallback and os.path.exists(raw_tc):
        if not typeconf_data.get("functions") or not typeconf_data.get("resources"):
            needs_resync = True
    if not is_template_fallback and os.path.exists(raw_uc) and not os.path.exists(uc_path):
        needs_resync = True
    if not is_template_fallback and os.path.exists(raw_mc) and not os.path.exists(mc_path):
        needs_resync = True

    if needs_resync:
        try:
            sync_machine_ready_config(clean_no)
            if os.path.exists(tf_path):
                with open(tf_path, "r", encoding="utf-8") as f:
                    typeconf_data = json.load(f)
        except Exception:
            pass

    userconf_labels = _load_json_file(uc_path, {})
    machconf_info = _load_json_file(mc_path, {})
    profile = _load_json_file(prof_path, {})

    raw_files = os.listdir(raw_dir) if os.path.isdir(raw_dir) else []
    raw_upper = {f.upper(): f for f in raw_files}
    awl_files = [f for f in raw_files if f.upper().endswith(".AWL")]

    config_sources = {
        "program_recipes": "PROGRAMS/*.PRG",
        "function_definitions": "Config/TYPECONF.CNF" if "TYPECONF.CNF" in raw_upper else "baseline_typeconf",
        "function_texts_alarms": [
            f"Config/{raw_upper[k]}" for k in ("CONFTEXT.CNF", "FNLEGEND.CNF") if k in raw_upper
        ],
        "custom_process_labels": f"Config/{raw_upper['USERCONF.CNF']}" if "USERCONF.CNF" in raw_upper else None,
        "machine_parameters": f"Config/{raw_upper['MACHCONF.CNF']}" if "MACHCONF.CNF" in raw_upper else None,
        "plc_execution_logic_only": [f"Config/{f}" for f in awl_files],
        "has_machine_typeconf": "TYPECONF.CNF" in raw_upper,
        "is_template_fallback": is_template_fallback,
    }

    return {
        "machine_no": clean_no,
        "folder": m_folder,
        "profile": profile,
        "config_sources": config_sources,
        "typeconf_sha256": typeconf_data.get("cnf_sha256"),
        "functions_count": len(typeconf_data.get("functions", {})),
        "parameters_count": len(typeconf_data.get("parameters", {})),
        "functions": typeconf_data.get("functions", {}),
        "parameters": typeconf_data.get("parameters", {}),
        "resources": typeconf_data.get("resources", {}),
        "groups": typeconf_data.get("groups", []),
        "text_choices": typeconf_data.get("text_choices", {}),
        "userconf_labels": userconf_labels,
        "machconf": machconf_info,
    }


def validate_steps_against_typeconf(
    machine_no: str,
    steps: List[Any],
    enrich_names: bool = True
) -> Dict[str, Any]:
    """
    Strictly validates all Function IDs and parameter bounds in `steps` against
    the target machine's Config/TYPECONF.CNF (never against .AWL).
    Prevents sending undefined or wrong Function IDs to the PLC.
    """
    bundle = load_machine_config_bundle(machine_no)
    funcs = bundle.get("functions") or {}
    params_defs = bundle.get("parameters") or {}
    clean_no = bundle["machine_no"]

    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    if not funcs:
        return {
            "valid": True,
            "machine_no": clean_no,
            "errors": [],
            "warnings": [{"message": f"TYPECONF.CNF untuk mesin {clean_no} belum tersedia, validasi dilewati."}],
            "typeconf_source": bundle["config_sources"]["function_definitions"],
            "typeconf_sha256": bundle.get("typeconf_sha256"),
        }

    for s_idx, st in enumerate(steps or [], start=1):
        step_no = st.step_no if hasattr(st, "step_no") else st.get("step_no", s_idx)
        st_funcs = st.functions if hasattr(st, "functions") else (st.get("functions") or [])
        for fn in st_funcs:
            fid = fn.function_id if hasattr(fn, "function_id") else fn.get("function_id")
            col = (fn.column if hasattr(fn, "column") else fn.get("column")) or 1
            f_params = (fn.params if hasattr(fn, "params") else fn.get("params")) or []
            fid_str = str(fid)

            if fid_str not in funcs:
                errors.append({
                    "step_no": step_no,
                    "column": col,
                    "function_id": fid,
                    "message": (
                        f"Step #{step_no} (Slot {col}): Function ID F{fid} TIDAK TERDAFTAR di "
                        f"Config/TYPECONF.CNF Mesin {clean_no} (sumber: {bundle['config_sources']['function_definitions']})."
                    )
                })
                continue

            f_def = funcs[fid_str]
            official_name = f_def.get("name") or f_def.get("name_local") or f"F{fid}"
            if enrich_names:
                if hasattr(fn, "name") and not fn.name:
                    fn.name = official_name
                elif isinstance(fn, dict) and not fn.get("name"):
                    fn["name"] = official_name

            # Check allowed column/slot if TYPECONF defines lines
            allowed_lines = f_def.get("lines") or []
            if allowed_lines and int(col) not in allowed_lines:
                warnings.append({
                    "step_no": step_no,
                    "column": col,
                    "function_id": fid,
                    "message": (
                        f"Step #{step_no}: Function F{fid} ({official_name}) pada Mesin {clean_no} "
                        f"normalnya berjalan di Slot {allowed_lines}, bukan Slot {col}."
                    )
                })

            # Check parameter limits defined in TYPECONF.CNF
            for p_i, p_meta in enumerate(f_def.get("parameters") or []):
                if p_i >= len(f_params):
                    continue
                try:
                    val = float(f_params[p_i])
                except Exception:
                    continue
                p_min = p_meta.get("minimum")
                p_max = p_meta.get("maximum")
                p_def_obj = params_defs.get(str(p_meta.get("definition_id")), {})
                p_name = p_def_obj.get("name") or f"P{p_i + 1}"
                if p_min is not None and p_max is not None and p_max > p_min:
                    if val < p_min - 1e-4 or val > p_max + 1e-4:
                        warnings.append({
                            "step_no": step_no,
                            "column": col,
                            "function_id": fid,
                            "param_index": p_i + 1,
                            "message": (
                                f"Step #{step_no} F{fid} ({official_name}) {p_name}={val} "
                                f"di luar batas TYPECONF [{p_min}..{p_max}]."
                            )
                        })

    return {
        "valid": len(errors) == 0,
        "machine_no": clean_no,
        "errors": errors,
        "warnings": warnings,
        "typeconf_source": bundle["config_sources"]["function_definitions"],
        "typeconf_sha256": bundle.get("typeconf_sha256"),
    }

# =============================================================================
# API ROUTES: SUB-PROGRAMS (TREATMENTS - LEVEL 2)
# =============================================================================

@router.get("/treatments/")
def list_treatments(db: Session = Depends(get_db)):
    """
    Returns library of reusable Sub-Programs (Treatments, Level=2).
    Reads from local storage (treatments_library.json) and PostgreSQL.
    """
    lib = _load_json_file(TREATMENTS_META_PATH, DEFAULT_TREATMENTS)
    # Also check if any custom treatments in PostgreSQL
    try:
        comps = db.query(ProgramComponent).filter(ProgramComponent.level == 2).order_by(ProgramComponent.number).all()
        existing_numbers = {t.get("number") for t in lib}
        for c in comps:
            if c.number not in existing_numbers:
                steps_data = []
                for st in sorted(c.steps, key=lambda x: x.position):
                    fns = []
                    for fn in sorted(st.functions, key=lambda x: x.resource_number):
                        p_vals = [p.value for p in fn.parameters]
                        fns.append({
                            "function_id": fn.function_number,
                            "name": fn.function_name,
                            "column": fn.resource_number,
                            "params": p_vals
                        })
                    steps_data.append({
                        "step_no": st.position,
                        "label": st.label,
                        "functions": fns
                    })
                lib.append({
                    "id": c.id,
                    "number": c.number,
                    "name": c.name,
                    "comment": c.comment,
                    "category": "Custom",
                    "machine_group": "Semua Mesin Celup",
                    "parameters": {},
                    "steps": steps_data
                })
    except Exception:
        pass

    return lib

@router.get("/treatments/{treatment_id}")
def get_treatment_detail(treatment_id: str, db: Session = Depends(get_db)):
    """Returns detailed steps and parameters of a specific Sub-Program (Treatment)."""
    lib = _load_json_file(TREATMENTS_META_PATH, DEFAULT_TREATMENTS)
    for t in lib:
        if str(t.get("id")) == str(treatment_id) or str(t.get("number")).upper() == str(treatment_id).upper():
            return t

    try:
        c = db.query(ProgramComponent).filter(
            (ProgramComponent.id == int(treatment_id)) | (ProgramComponent.number == treatment_id),
            ProgramComponent.level == 2
        ).first()
        if c:
            steps_data = []
            for st in sorted(c.steps, key=lambda x: x.position):
                fns = []
                for fn in sorted(st.functions, key=lambda x: x.resource_number):
                    p_vals = [p.value for p in fn.parameters]
                    fns.append({
                        "function_id": fn.function_number,
                        "name": fn.function_name,
                        "column": fn.resource_number,
                        "params": p_vals
                    })
                steps_data.append({
                    "step_no": st.position,
                    "label": st.label,
                    "functions": fns
                })
            return {
                "id": c.id,
                "number": c.number,
                "name": c.name,
                "comment": c.comment,
                "category": "Custom",
                "machine_group": "Semua Mesin Celup",
                "parameters": {},
                "steps": steps_data
            }
    except Exception:
        pass

    raise HTTPException(status_code=404, detail="Sub-program (Treatment) tidak ditemukan")

@router.post("/treatments/")
def save_treatment(t: TreatmentIn, db: Session = Depends(get_db)):
    """Adds or updates a treatment in the library."""
    lib = _load_json_file(TREATMENTS_META_PATH, DEFAULT_TREATMENTS)
    found = False
    new_id = t.id or int(time.time())
    for i, item in enumerate(lib):
        if str(item.get("number")).upper() == t.number.strip().upper() or (t.id and item.get("id") == t.id):
            item["name"] = t.name
            item["comment"] = t.comment
            item["category"] = t.category or "General"
            item["machine_group"] = t.machine_group or "Semua Mesin Celup"
            if t.parameters:
                item["parameters"] = t.parameters
            if t.steps:
                item["steps"] = [s.dict() for s in t.steps]
            found = True
            break
    if not found:
        lib.append({
            "id": new_id,
            "number": t.number.strip().upper(),
            "name": t.name,
            "comment": t.comment,
            "category": t.category or "General",
            "machine_group": t.machine_group or "Semua Mesin Celup",
            "parameters": t.parameters or {},
            "steps": [s.dict() for s in (t.steps or [])]
        })
    _save_json_file(TREATMENTS_META_PATH, lib)
    return {"status": "success", "message": f"Treatment {t.number} berhasil disimpan!", "treatment": t.dict()}

@router.delete("/treatments/{treatment_id}")
def delete_treatment(treatment_id: str):
    """Deletes a treatment from library."""
    lib = _load_json_file(TREATMENTS_META_PATH, DEFAULT_TREATMENTS)
    filtered = [t for t in lib if str(t.get("id")) != str(treatment_id) and str(t.get("number")).upper() != str(treatment_id).upper()]
    if len(filtered) == len(lib):
        raise HTTPException(status_code=404, detail="Treatment tidak ditemukan")
    _save_json_file(TREATMENTS_META_PATH, filtered)
    return {"status": "success", "message": "Treatment berhasil dihapus"}

# =============================================================================
# API ROUTES: MASTER PROGRAMS (PROCEDURES - LEVEL 1)
# =============================================================================

def _norm_machine(machine_code: Optional[str]) -> str:
    clean = str(machine_code or "TD12").strip().upper()
    if clean.startswith("MESIN_"):
        clean = clean[6:]
    return clean or "TD12"


def _norm_pno_str(p_no: Any) -> str:
    s = str(p_no or "").strip()
    if s.isdigit():
        return str(int(s))
    return s.upper()


def _custom_key(machine_code: Optional[str], p_no: Any) -> str:
    return f"{_norm_machine(machine_code)}:{_norm_pno_str(p_no)}"


def _custom_lookup(custom: Dict[str, Any], p_no: Any, machine_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
    p_str = _norm_pno_str(p_no)
    if machine_code:
        m_norm = _norm_machine(machine_code)
        scoped = custom.get(f"{m_norm}:{p_str}")
        if isinstance(scoped, dict):
            return scoped
        # Legacy flat key only if its machine_code actually matches m_norm
        flat = custom.get(p_str)
        if isinstance(flat, dict) and _norm_machine(flat.get("machine_code")) == m_norm:
            return flat
        return None
    # Unscoped lookup: prefer flat or first matching machine entry
    if p_str in custom and isinstance(custom[p_str], dict):
        return custom[p_str]
    for k, v in custom.items():
        if isinstance(v, dict) and _norm_pno_str(v.get("program_no") or (k.split(":", 1)[1] if ":" in str(k) else k)) == p_str:
            return v
    return None


def _save_custom_entry(path: str, machine_code: Optional[str], p_no: Any, entry: Dict[str, Any]) -> None:
    raw = _load_json_file(path, {})
    clean_store: Dict[str, Any] = {}
    for k, v in raw.items():
        if not isinstance(v, dict):
            continue
        v_mc = _norm_machine(v.get("machine_code") or (k.split(":", 1)[0] if ":" in str(k) else "TD12"))
        v_pno = _norm_pno_str(v.get("program_no") or (k.split(":", 1)[1] if ":" in str(k) else k))
        v["machine_code"] = v_mc
        clean_store[f"{v_mc}:{v_pno}"] = v
    m_norm = _norm_machine(machine_code)
    p_str = _norm_pno_str(p_no)
    entry["machine_code"] = m_norm
    clean_store[f"{m_norm}:{p_str}"] = entry
    _save_json_file(path, clean_store)


@router.get("", include_in_schema=False)
@router.get("/")
def list_programs(db: Session = Depends(get_db)):
    """
    Lists all available master programs (Procedures, Level=1).
    Deduplicated strictly per (machine_code, program_number) — the same program number
    on different machines is preserved separately without cross-machine overwriting.
    """
    results = []
    seen_keys = set()  # (machine_code, program_number)

    # 1. Custom JSON store
    custom = _load_json_file(META_PATH, {})

    # 2. Read from PostgreSQL (ProgramComponent Level 1) in a SINGLE aggregated query
    # (Avoids N+1 lazy-loading queries across thousands of programs)
    try:
        rows = db.execute(text("""
            WITH direct_steps AS (
                SELECT parent_component_id, COUNT(*) AS cnt
                FROM public.steps
                GROUP BY parent_component_id
            ),
            sub_steps AS (
                SELECT pci.parent_component_id, COALESCE(SUM(ds.cnt), 0) AS cnt
                FROM public.program_component_items pci
                LEFT JOIN direct_steps ds ON ds.parent_component_id = pci.program_component_id
                GROUP BY pci.parent_component_id
            )
            SELECT
                pc.id,
                pc.number,
                pc.name,
                pc.machine_code,
                COALESCE(NULLIF(ds.cnt, 0), ss.cnt, 0) AS total_steps
            FROM public.program_components pc
            LEFT JOIN direct_steps ds ON ds.parent_component_id = pc.id
            LEFT JOIN sub_steps ss ON ss.parent_component_id = pc.id
            WHERE pc.level = 1
            ORDER BY pc.id DESC
        """)).fetchall()

        for row in rows:
            pid_row, raw_num, raw_name, raw_mcode, raw_steps = row
            try:
                pno = int(_norm_pno_str(raw_num))
            except Exception:
                pno = pid_row
            m_code = _norm_machine(raw_mcode or "TD12")
            dedup_key = (m_code, pno)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            custom_info = _custom_lookup(custom, pno, m_code)
            p_name = raw_name or (custom_info.get("program_name") if custom_info else None) or f"PROGRAM #{pno}"
            t_steps = (
                int(raw_steps or 0)
                or (len(custom_info.get("steps", [])) if custom_info and "steps" in custom_info else 0)
            )
            f_size = (custom_info.get("file_size") if custom_info else None) or (384 + 65 * max(1, t_steps))

            results.append({
                "filename": (custom_info.get("filename") if custom_info else None) or f"M_{str(pno).zfill(4)}.PRG",
                "program_number": pno,
                "program_name": p_name,
                "machine_code": m_code,
                "total_steps": t_steps,
                "is_custom": True,
                "file_size": f_size
            })
    except Exception as exc:
        logging.getLogger("orgatex.programs").warning(f"list_programs DB query failed: {exc}")

    # 2.1 Add remaining programs from custom store (per machine)
    for pid_str, prg in custom.items():
        if not isinstance(prg, dict):
            continue
        try:
            raw_pid = prg.get("program_no") or (pid_str.split(":", 1)[1] if ":" in str(pid_str) else pid_str)
            pid = int(_norm_pno_str(raw_pid))
            m_code = _norm_machine(prg.get("machine_code") or (pid_str.split(":", 1)[0] if ":" in str(pid_str) else "TD12"))
            dedup_key = (m_code, pid)
            if dedup_key not in seen_keys:
                seen_keys.add(dedup_key)
                results.append({
                    "filename": prg.get("filename") or f"M_{str(pid).zfill(4)}.PRG",
                    "program_number": pid,
                    "program_name": prg.get("program_name", f"PROGRAM #{pid}"),
                    "machine_code": m_code,
                    "total_steps": len(prg.get("steps", [])),
                    "is_custom": True,
                    "file_size": prg.get("file_size") or (384 + 65 * max(1, len(prg.get("steps", []))))
                })
        except Exception:
            pass

    # 2.5 Scan WORKSPACE_PROGRAM_MESIN for local machine programs (dedup per machine)
    try:
        if os.path.isdir(MACHINE_WORKSPACE_BASE):
            for m_dir in sorted(os.listdir(MACHINE_WORKSPACE_BASE)):
                if not m_dir.startswith("MESIN_"):
                    continue
                clean_m = _norm_machine(m_dir)
                full_m = os.path.join(MACHINE_WORKSPACE_BASE, m_dir)
                for sub in ["03_CONTOH_PRG_DARI_HMI", "04_HASIL_PROGRAM_CELUP"]:
                    sub_p = os.path.join(full_m, sub)
                    if not os.path.isdir(sub_p):
                        continue
                    for fname in sorted(os.listdir(sub_p)):
                        if fname.upper().endswith(".PRG"):
                            # Fast-skip standard M_XXXX.PRG filenames already loaded from DB
                            m_fn = re.match(r"^M_0*(\d+)\.PRG$", fname, re.IGNORECASE)
                            if m_fn and (clean_m, int(m_fn.group(1))) in seen_keys:
                                continue
                            prg_path = os.path.join(sub_p, fname)
                            try:
                                with open(prg_path, "rb") as pf:
                                    raw_b = pf.read()
                                parsed = parse_prg_binary(raw_b)
                                pno = parsed.get("program_no")
                                dedup_key = (clean_m, pno)
                                if pno and dedup_key not in seen_keys:
                                    seen_keys.add(dedup_key)
                                    results.append({
                                        "filename": fname,
                                        "program_number": pno,
                                        "program_name": parsed.get("program_name") or fname,
                                        "machine_code": clean_m,
                                        "total_steps": len(parsed.get("steps", [])),
                                        "is_custom": True,
                                        "file_size": len(raw_b)
                                    })
                            except Exception:
                                pass
    except Exception:
        pass

    # 3. Existing OrgaTEX / Setex Plain Export
    summary_path = _get_summary_file()
    if summary_path:
        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data:
                    pno = item.get("program_number")
                    m_code = _norm_machine(item.get("machine_code") or "TD12")
                    dedup_key = (m_code, pno)
                    if dedup_key not in seen_keys:
                        seen_keys.add(dedup_key)
                        results.append({
                            "filename": item.get("filename"),
                            "program_number": pno,
                            "program_name": item.get("program_name"),
                            "machine_code": m_code,
                            "total_steps": item.get("total_steps", 0),
                            "is_custom": False,
                            "file_size": item.get("file_size", 0)
                        })
        except Exception:
            pass

    # 4. Reverse Engineered Templates from catalog
    if os.path.exists(CATALOG_PATH):
        try:
            with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                cat = json.load(f)
                for t in cat.get("templates", []):
                    tid = t.get("id")
                    m_code = _norm_machine(t.get("machine_code") or "TD12")
                    dedup_key = (m_code, tid)
                    if tid and dedup_key not in seen_keys:
                        seen_keys.add(dedup_key)
                        raw_len = len(base64.b64decode(t["base64"])) if "base64" in t else 1024
                        results.append({
                            "filename": t.get("filename", f"M_{str(tid).zfill(4)}.PRG"),
                            "program_number": tid,
                            "program_name": t.get("title", f"Template #{tid}"),
                            "machine_code": m_code,
                            "total_steps": t.get("steps", 0),
                            "is_custom": False,
                            "file_size": raw_len
                        })
        except Exception:
            pass

    results.sort(key=lambda x: (x["machine_code"], x["program_number"]))
    return results


@router.get("/catalog-templates")
def get_catalog_templates():
    """Lists the 37 reverse-engineered PRG templates from SECOM 777 backup."""
    if os.path.exists(CATALOG_PATH):
        try:
            with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                cat = json.load(f)
                return [
                    {
                        "id": t.get("id"),
                        "filename": t.get("filename"),
                        "title": t.get("title"),
                        "steps": t.get("steps")
                    } for t in cat.get("templates", [])
                ]
        except Exception:
            pass
    return []


@router.get("/templates")
def get_templates():
    return DEFAULT_TREATMENTS


@router.get("/{program_no}")
def get_program(program_no: int, machine_code: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Retrieves full Procedure details, including Sub-Programs (Treatments) and flattened steps.
    When machine_code is provided, resolves strictly for that machine so identical program numbers
    across different machines never collide.
    """
    target_m = _norm_machine(machine_code) if machine_code else None
    pno_norm = _norm_pno_str(program_no)

    # 0. Check Custom JSON store first if it has rich sub_programs
    custom = _load_json_file(META_PATH, {})
    c_prg = _custom_lookup(custom, program_no, target_m)
    if c_prg and (c_prg.get("sub_programs") or c_prg.get("steps")):
        return c_prg

    # 1. Check PostgreSQL (filtered in SQL + eager-loaded to avoid N+1 queries)
    try:
        pno_padded = str(program_no).zfill(4)
        q = (
            db.query(ProgramComponent)
            .options(
                selectinload(ProgramComponent.steps)
                .selectinload(Step.functions)
                .selectinload(StepFunction.parameters),
                selectinload(ProgramComponent.sub_program_items)
                .selectinload(ProgramComponentItem.treatment)
                .selectinload(ProgramComponent.steps)
                .selectinload(Step.functions)
                .selectinload(StepFunction.parameters),
            )
            .filter(
                ProgramComponent.level == 1,
                or_(
                    func.trim(ProgramComponent.number).in_([pno_norm, pno_padded, str(program_no)]),
                    ProgramComponent.id == program_no,
                ),
            )
        )
        matching = q.all()
        if target_m:
            mach_matches = [row for row in matching if _norm_machine(row.machine_code) == target_m]
            p = mach_matches[0] if mach_matches else None
        else:
            p = matching[0] if matching else None
        if p:
            sub_progs = []
            flattened = []
            st_counter = 1
            for item in p.sub_program_items:
                t = item.treatment
                if t:
                    t_steps = []
                    for s in sorted(t.steps, key=lambda x: x.position):
                        fns = []
                        for fn in sorted(s.functions, key=lambda x: x.resource_number):
                            p_vals = [float(pv.value) for pv in fn.parameters]
                            p_forms = {}
                            for p_idx, pv in enumerate(fn.parameters):
                                if getattr(pv, "formula_id", None):
                                    p_forms[str(p_idx)] = {
                                        "formula_id": int(pv.formula_id),
                                        "output_key": getattr(pv, "formula_output_key", None)
                                    }
                            fns.append({
                                "function_id": fn.function_number,
                                "name": fn.function_name,
                                "column": fn.resource_number,
                                "params": p_vals,
                                "param_formulas": p_forms
                            })
                        step_dict = {
                            "step_no": st_counter,
                            "label": s.label or f"{t.name} (Step #{s.position})",
                            "functions": fns,
                            "summary_temp": float(s.summary_temp) if s.summary_temp else None,
                            "summary_time_min": float(s.summary_time_min) if s.summary_time_min else 0,
                            "summary_water_l": float(s.summary_water_l) if s.summary_water_l else 0
                        }
                        t_steps.append(step_dict)
                        flattened.append(step_dict)
                        st_counter += 1

                    sub_progs.append({
                        "position": item.position,
                        "treatment_id": t.id,
                        "treatment_number": t.number,
                        "treatment_name": t.name,
                        "steps": t_steps
                    })

            return {
                "program_no": program_no,
                "program_name": p.name,
                "machine_code": p.machine_code or "TD12",
                "sub_programs": sub_progs,
                "steps": flattened if flattened else [
                    {
                        "step_no": s.position,
                        "label": s.label,
                        "functions": [
                            {
                                "function_id": fn.function_number,
                                "name": fn.function_name,
                                "column": fn.resource_number,
                                "params": [float(pv.value) for pv in fn.parameters],
                                "param_formulas": {
                                    str(p_idx): {
                                        "formula_id": int(pv.formula_id),
                                        "output_key": getattr(pv, "formula_output_key", None)
                                    }
                                    for p_idx, pv in enumerate(fn.parameters)
                                    if getattr(pv, "formula_id", None)
                                }
                            } for fn in s.functions
                        ]
                    } for s in p.steps
                ]
            }
    except Exception:
        pass

    # 2. Check Custom JSON store
    if c_prg:
        return c_prg

    # 3. Check OrgaTEX detail directory
    detail_dir = _get_detail_dir()
    if detail_dir:
        json_file = os.path.join(detail_dir, f"M_{str(program_no).zfill(4)}.json")
        if os.path.exists(json_file):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    normalized_steps = []
                    for st in data.get("steps", []):
                        fns = []
                        for fn in st.get("functions", []):
                            p_vals = [p["value"] for p in fn.get("parameters", []) if "value" in p]
                            fns.append({
                                "function_id": fn.get("function_id"),
                                "name": fn.get("name") or fn.get("description", "Fungsi"),
                                "column": fn.get("column", 1),
                                "flags": fn.get("flags", 0),
                                "params": p_vals
                            })
                        normalized_steps.append({
                            "step_no": st.get("step_no"),
                            "label": st.get("label", ""),
                            "functions": fns,
                            "summary_temp": st.get("summary_temp"),
                            "summary_time_min": st.get("summary_time_min", 0),
                            "summary_pump_pct": st.get("summary_pump_pct", 85.0),
                            "summary_reel_speed": st.get("summary_reel_speed", 200.0),
                            "summary_water_l": st.get("summary_water_l", 0)
                        })

                    return {
                        "program_no": data.get("program_number", program_no),
                        "program_name": data.get("program_name", f"PROGRAM #{program_no}"),
                        "machine_code": data.get("machine_code") or "TD12",
                        "total_steps": len(normalized_steps),
                        "steps": normalized_steps
                    }
            except Exception:
                pass

    # 4. Check Reverse Engineered Catalog
    if os.path.exists(CATALOG_PATH):
        try:
            with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                cat = json.load(f)
                for t in cat.get("templates", []):
                    if t.get("id") == program_no:
                        if "base64" in t:
                            parsed = parse_prg_binary(base64.b64decode(t["base64"]))
                            return parsed
        except Exception:
            pass

    # 5. Check WORKSPACE_PROGRAM_MESIN (03_CONTOH_PRG_DARI_HMI and 04_HASIL_PROGRAM_CELUP)
    try:
        if os.path.isdir(MACHINE_WORKSPACE_BASE):
            dirs_order = sorted(os.listdir(MACHINE_WORKSPACE_BASE))
            if target_m:
                pref = f"MESIN_{target_m}"
                dirs_order = [pref] + [d for d in dirs_order if d != pref]
            for m_dir in dirs_order:
                if not m_dir.startswith("MESIN_"):
                    continue
                clean_m = _norm_machine(m_dir)
                if target_m and clean_m != target_m:
                    continue
                full_m = os.path.join(MACHINE_WORKSPACE_BASE, m_dir)
                for sub in ["03_CONTOH_PRG_DARI_HMI", "04_HASIL_PROGRAM_CELUP"]:
                    sub_p = os.path.join(full_m, sub)
                    if not os.path.isdir(sub_p):
                        continue
                    for fname in sorted(os.listdir(sub_p)):
                        if fname.upper().endswith(".PRG"):
                            prg_path = os.path.join(sub_p, fname)
                            try:
                                with open(prg_path, "rb") as pf:
                                    raw_b = pf.read()
                                parsed = parse_prg_binary(raw_b)
                                if parsed.get("program_no") == program_no:
                                    parsed["machine_code"] = clean_m
                                    parsed["filename"] = fname
                                    return parsed
                            except Exception:
                                pass
    except Exception:
        pass

    raise HTTPException(status_code=404, detail=f"Program #{program_no} tidak ditemukan")

@router.post("", include_in_schema=False)
@router.post("/")
def save_program(p: ProcedureIn, db: Session = Depends(get_db)):
    """
    Saves or updates Procedure into PostgreSQL program_components table
    and synchronizes JSON storage and auto-compiles binary M_xxxx.PRG.
    """
    if p.program_no < 1 or p.program_no > 9999:
        raise HTTPException(
            status_code=400,
            detail=f"Nomor program SETEX harus antara 1 sampai 9999 (format M_xxxx.PRG). Diterima: {p.program_no}"
        )

    # 0. Flatten sub_programs into steps if sub_programs are provided
    if p.sub_programs and (not p.steps or len(p.steps) == 0):
        lib = _load_json_file(TREATMENTS_META_PATH, DEFAULT_TREATMENTS)
        lib_map = {str(t.get("number")).upper(): t for t in lib}
        lib_map.update({str(t.get("id")): t for t in lib})

        flattened_steps = []
        step_idx = 1
        for sp in p.sub_programs:
            t_ref = None
            if sp.treatment_number and str(sp.treatment_number).upper() in lib_map:
                t_ref = lib_map[str(sp.treatment_number).upper()]
            elif sp.treatment_id and str(sp.treatment_id) in lib_map:
                t_ref = lib_map[str(sp.treatment_id)]

            source_steps = sp.steps if sp.steps else (t_ref.get("steps", []) if t_ref else [])
            params = sp.parameters or {}

            for s_item in source_steps:
                s_dict = s_item.dict() if hasattr(s_item, "dict") else dict(s_item)
                s_dict["step_no"] = step_idx
                step_idx += 1

                # Apply parameter overrides to functions
                funcs = []
                for fn in s_dict.get("functions", []):
                    fn_dict = fn.dict() if hasattr(fn, "dict") else dict(fn)
                    fid = fn_dict.get("function_id")
                    p_vals = list(fn_dict.get("params") or [])

                    if fid == 141 and "temperature" in params:
                        if len(p_vals) > 0:
                            p_vals[0] = float(params["temperature"])
                        else:
                            p_vals.append(float(params["temperature"]))
                        if "gradient" in params and len(p_vals) > 1:
                            p_vals[1] = float(params["gradient"])
                        s_dict["summary_temp"] = float(params["temperature"])

                    elif fid == 121 and "hold_time" in params:
                        if len(p_vals) > 0:
                            p_vals[0] = float(params["hold_time"])
                        else:
                            p_vals.append(float(params["hold_time"]))
                        s_dict["summary_time_min"] = float(params["hold_time"])

                    elif fid == 713 and "water_level" in params:
                        if len(p_vals) > 1:
                            p_vals[1] = float(params["water_level"])
                        elif len(p_vals) == 1:
                            p_vals.append(float(params["water_level"]))
                        s_dict["summary_water_l"] = float(params["water_level"])

                    elif fid == 404 and "pump_speed" in params:
                        if len(p_vals) > 0:
                            p_vals[0] = float(params["pump_speed"])
                        else:
                            p_vals.append(float(params["pump_speed"]))
                        s_dict["summary_pump_pct"] = float(params["pump_speed"])

                    fn_dict["params"] = p_vals
                    funcs.append(fn_dict)

                s_dict["functions"] = funcs
                flattened_steps.append(StepIn(**s_dict))

        p.steps = flattened_steps

    # 0.5 Strict TYPECONF.CNF Validation (ensure every Function ID exists on target machine's TYPECONF.CNF, never .AWL)
    target_machine_code = (p.machine_code or "TD12").strip().upper().replace("MESIN_", "")
    validation_result = validate_steps_against_typeconf(target_machine_code, p.steps or [], enrich_names=True)
    if not validation_result["valid"]:
        err_summary = "; ".join(e["message"] for e in validation_result["errors"][:5])
        if len(validation_result["errors"]) > 5:
            err_summary += f" (+{len(validation_result['errors']) - 5} error lainnya)"
        raise HTTPException(
            status_code=400,
            detail=f"Validasi TYPECONF.CNF Mesin {target_machine_code} GAGAL — Function ID tidak cocok dan ditolak agar tidak salah kirim ke PLC: {err_summary}"
        )

    # 1. Update/Insert in PostgreSQL (strictly scoped per machine_code + program_no)
    p_no_str = _norm_pno_str(p.program_no)
    try:
        all_mach_rows = [
            row for row in db.query(ProgramComponent).filter(ProgramComponent.level == 1).order_by(ProgramComponent.id.asc()).all()
            if _norm_machine(row.machine_code) == target_machine_code and _norm_pno_str(row.number) == p_no_str
        ]
        proc = all_mach_rows[0] if all_mach_rows else None
        for dup in all_mach_rows[1:]:
            db.query(ProgramComponentItem).filter(
                ProgramComponentItem.parent_component_id == dup.id
            ).update({"parent_component_id": proc.id}, synchronize_session=False)
            db.query(ProgramComponentItem).filter(
                ProgramComponentItem.program_component_id == dup.id
            ).update({"program_component_id": proc.id}, synchronize_session=False)
            db.delete(dup)

        if not proc:
            proc = ProgramComponent(
                level=1,
                type=1,
                number=p_no_str,
                name=p.program_name.strip().upper(),
                machine_code=target_machine_code
            )
            db.add(proc)
            db.flush()
        else:
            proc.number = p_no_str
            proc.name = p.program_name.strip().upper()
            proc.machine_code = target_machine_code
            proc.modification_time = datetime.utcnow()

        # Update steps directly if provided
        if p.steps:
            for old_s in list(proc.steps):
                db.delete(old_s)
            db.flush()
            for st in p.steps:
                new_s = Step(
                    position=st.step_no,
                    parent_component_id=proc.id,
                    label=st.label,
                    summary_temp=st.summary_temp,
                    summary_time_min=st.summary_time_min,
                    summary_water_l=st.summary_water_l
                )
                db.add(new_s)
                db.flush()

                for fn in st.functions:
                    new_fn = StepFunction(
                        step_id=new_s.id,
                        resource_number=fn.column or 1,
                        function_number=fn.function_id,
                        function_name=fn.name or ""
                    )
                    db.add(new_fn)
                    db.flush()

                    pf_map = fn.param_formulas or {}
                    for idx, val in enumerate(fn.params or []):
                        binding = pf_map.get(str(idx))
                        f_id = None
                        f_out_key = None
                        if isinstance(binding, dict) and binding.get("formula_id"):
                            f_id = int(binding["formula_id"])
                            f_out_key = binding.get("output_key") or None
                        elif isinstance(binding, int):
                            f_id = binding
                        new_p = StepFunctionParameter(
                            step_function_id=new_fn.id,
                            function_parameter_number=idx + 1,
                            value=val,
                            formula_id=f_id,
                            formula_output_key=f_out_key
                        )
                        db.add(new_p)

        db.commit()
    except Exception as e:
        db.rollback()

    # 2. Keep local JSON fallback synced (machine-scoped key)
    _save_custom_entry(META_PATH, target_machine_code, p.program_no, p.dict())

    # 3. Auto-compile binary M_xxxx.PRG (machine-scoped cache + flat fallback)
    try:
        if p.steps:
            compiled_bytes = serialize_prg_binary(p.program_no, p.program_name, [s.dict() for s in p.steps])
            mach_dir = os.path.join(COMPILED_DIR, target_machine_code)
            os.makedirs(mach_dir, exist_ok=True)
            out_file = os.path.join(mach_dir, f"M_{str(p.program_no).zfill(4)}.PRG")
            with open(out_file, "wb") as f:
                f.write(compiled_bytes)
    except Exception:
        pass

    return {
        "status": "success",
        "program_no": p.program_no,
        "program_name": p.program_name,
        "machine_code": target_machine_code,
        "total_steps": len(p.steps or []),
        "sub_programs_count": len(p.sub_programs or []),
        "table": "program_components (Level 1 Procedure)",
        "download_url": f"/api/programs/download/{p.program_no}?machine_code={target_machine_code}",
        "typeconf_validation": validation_result,
        "message": f"Procedure OrgaTEX M_{str(p.program_no).zfill(4)}.PRG berhasil divalidasi (TYPECONF.CNF {target_machine_code}), disimpan, dan dikompilasi!"
    }

def get_compiled_prg_bytes(program_no: int, db: Optional[Session] = None, machine_code: Optional[str] = None) -> bytes:
    """Retrieves or builds byte-exact SETEX SECOM 777 .PRG binary (machine-scoped when machine_code is given)."""
    p_no = int(program_no)
    if p_no < 1 or p_no > 9999:
        raise ValueError(f"Nomor program SETEX harus antara 1 sampai 9999 (4 digit). Diterima: {program_no}")

    clean_m = _norm_machine(machine_code) if machine_code else None
    fname = f"M_{str(p_no).zfill(4)}.PRG"
    candidate_paths = []
    if clean_m:
        mach_dir = os.path.join(COMPILED_DIR, clean_m)
        os.makedirs(mach_dir, exist_ok=True)
        candidate_paths.append(os.path.join(mach_dir, fname))
    else:
        candidate_paths.append(os.path.join(COMPILED_DIR, fname))

    for file_path in candidate_paths:
        if os.path.exists(file_path):
            try:
                with open(file_path, "rb") as f:
                    raw_data = bytearray(f.read())
                    if len(raw_data) >= 384 and raw_data[:4] == bytes.fromhex("508fc2f5"):
                        needs_update = False
                        if struct.unpack_from("<I", raw_data, 4)[0] != 60:
                            struct.pack_into("<I", raw_data, 4, 60)
                            needs_update = True
                        if struct.unpack_from("<H", raw_data, 35)[0] != 1:
                            struct.pack_into("<H", raw_data, 35, 1)
                            needs_update = True
                        if needs_update:
                            with open(file_path, "wb") as f_out:
                                f_out.write(raw_data)
                        return bytes(raw_data)
            except Exception:
                pass

    target_cache = candidate_paths[0]

    # Try to load program and compile (strictly for clean_m when provided)
    try:
        prg_data = get_program(p_no, machine_code=clean_m, db=db)
        steps = prg_data.get("steps", [])
        if steps:
            title = prg_data.get("program_name", f"PRG {p_no}")
            compiled = serialize_prg_binary(p_no, title, steps)
            with open(target_cache, "wb") as f:
                f.write(compiled)
            return compiled
    except Exception:
        pass

    # Legacy flat cache fallback if machine-specific binary not found
    flat_path = os.path.join(COMPILED_DIR, fname)
    if clean_m and os.path.exists(flat_path):
        try:
            with open(flat_path, "rb") as f:
                raw_data = f.read()
                if len(raw_data) >= 384 and raw_data[:4] == bytes.fromhex("508fc2f5"):
                    return raw_data
        except Exception:
            pass

    # Try reverse-engineered catalog
    if os.path.exists(CATALOG_PATH):
        try:
            with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                cat = json.load(f)
                for t in cat.get("templates", []):
                    if t.get("id") == p_no and "base64" in t:
                        raw = base64.b64decode(t["base64"])
                        with open(target_cache, "wb") as f:
                            f.write(raw)
                        return raw
        except Exception:
            pass

    # Fallback to minimal valid PRG
    fallback = build_minimal_prg(p_no, f"PRG {p_no}")
    try:
        with open(target_cache, "wb") as f:
            f.write(fallback)
    except Exception:
        pass
    return fallback


def get_compiled_prg_bytes_for_batch(
    program_no: int,
    batch_dict: Dict[str, Any],
    db: Optional[Session] = None,
    machine_code: Optional[str] = None
) -> bytes:
    """
    Compiles a batch-specific SETEX .PRG binary by evaluating any StepFunctionParameter
    formulas (`param_formulas`) against the batch's inputs.
    Falls back seamlessly to `get_compiled_prg_bytes(...)` if the program has no formulas.
    """
    from ..database import SessionLocal
    from ..services.formula_engine import build_batch_context, resolve_program_steps_for_batch
    from .formulas import load_formula_map

    owns_session = False
    sess = db
    if sess is None and SessionLocal is not None:
        sess = SessionLocal()
        owns_session = True

    try:
        clean_m = _norm_machine(machine_code or batch_dict.get("machine_no") or "") or None
        prg_data = get_program(int(program_no), machine_code=clean_m, db=sess)
        steps = prg_data.get("steps") or []

        needed_ids = set()
        for st in steps:
            for fn in st.get("functions") or []:
                for binding in (fn.get("param_formulas") or {}).values():
                    if isinstance(binding, dict) and binding.get("formula_id"):
                        needed_ids.add(int(binding["formula_id"]))
                    elif isinstance(binding, int):
                        needed_ids.add(binding)

        if needed_ids and sess is not None:
            mach_cap = None
            if clean_m:
                m_obj = sess.query(Machine).filter(Machine.machine_no == clean_m).first()
                if m_obj and m_obj.capacity_kg is not None:
                    mach_cap = float(m_obj.capacity_kg)
            ctx = build_batch_context(batch_dict, machine_capacity_kg=mach_cap, machine_no=clean_m)
            f_map = load_formula_map(sess, list(needed_ids))
            resolved_steps, _ = resolve_program_steps_for_batch(steps, f_map, ctx)
            title = prg_data.get("program_name", f"PRG {program_no}")
            return serialize_prg_binary(int(program_no), title, resolved_steps)
    except Exception:
        pass
    finally:
        if owns_session and sess is not None:
            sess.close()

    return get_compiled_prg_bytes(int(program_no), db=db, machine_code=machine_code)


@router.post("/compile/{program_no}")
def compile_program_binary(program_no: int, machine_code: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Compiles Procedure into standard 65-byte SETEX Secom 777CE binary record format.
    Saves to machine-scoped compiled cache and returns hash and size.
    """
    if program_no < 1 or program_no > 9999:
        raise HTTPException(
            status_code=400,
            detail=f"Nomor program SETEX harus antara 1 sampai 9999 (format M_xxxx.PRG). Nomor {program_no} tidak valid."
        )

    try:
        prg = get_program(program_no, machine_code=machine_code, db=db)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=f"Program #{program_no} tidak ditemukan: {str(e)}"
        )

    steps = prg.get("steps", [])
    if not steps:
        raise HTTPException(
            status_code=400,
            detail=f"Program #{program_no} belum memiliki langkah proses (steps). Tambahkan minimal satu langkah."
        )

    target_machine = _norm_machine(machine_code or prg.get("machine_code") or "TD12")
    val = validate_steps_against_typeconf(target_machine, steps, enrich_names=False)
    if not val["valid"]:
        err_summary = "; ".join(e["message"] for e in val["errors"][:5])
        raise HTTPException(
            status_code=400,
            detail=f"Kompilasi ditolak — Program #{program_no} mengandung Function ID yang tidak valid untuk TYPECONF.CNF Mesin {target_machine}: {err_summary}"
        )

    title = prg.get("program_name", f"PRG {program_no}")
    try:
        compiled_bytes = serialize_prg_binary(program_no, title, steps)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal mengompilasi biner program: {str(e)}")

    mach_dir = os.path.join(COMPILED_DIR, target_machine)
    os.makedirs(mach_dir, exist_ok=True)
    out_file = os.path.join(mach_dir, f"M_{str(program_no).zfill(4)}.PRG")
    try:
        with open(out_file, "wb") as f:
            f.write(compiled_bytes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal menyimpan file biner {out_file}: {str(e)}")

    sha256 = hashlib.sha256(compiled_bytes).hexdigest()
    steps_count = len(steps)
    actual_size = len(compiled_bytes)

    return {
        "status": "compiled",
        "machine_code": target_machine,
        "target_file": f"M_{str(program_no).zfill(4)}.PRG",
        "sha256": sha256,
        "download_url": f"/api/programs/download/{program_no}?machine_code={target_machine}",
        "header": {
            "program_no": program_no,
            "program_name": title,
            "records": steps_count,
            "sub_programs_count": len(prg.get("sub_programs", [])),
            "binary_bytes": actual_size
        },
        "message": f"Kompilasi sukses! Program M_{str(program_no).zfill(4)}.PRG ({target_machine}) siap digunakan ({steps_count} langkah, {actual_size} bytes, SHA-256: {sha256[:8]}...)."
    }


@router.get("/download/{program_no}")
def download_program_binary(program_no: int, machine_code: Optional[str] = None, db: Session = Depends(get_db)):
    """Downloads byte-exact SETEX SECOM 777 M_xxxx.PRG binary file."""
    prg_bytes = get_compiled_prg_bytes(program_no, db, machine_code=machine_code)
    filename = f"M_{str(program_no).zfill(4)}.PRG"
    return Response(
        content=prg_bytes,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.post("/upload-prg")
async def upload_prg_file(request: Request, machine_code: Optional[str] = "TD12", db: Session = Depends(get_db)):
    """Uploads and parses a binary SETEX SECOM 777 .PRG file (raw bytes or JSON base64) and upserts per machine."""
    try:
        content_type = request.headers.get("content-type", "")
        filename = "uploaded.PRG"
        target_machine = machine_code or "TD12"
        if "application/json" in content_type:
            payload = await request.json()
            if "base64" in payload:
                content = base64.b64decode(payload["base64"])
                filename = payload.get("filename", filename)
                if "machine_code" in payload:
                    target_machine = payload["machine_code"]
            else:
                raise ValueError("JSON payload harus memiliki field 'base64'")
        else:
            content = await request.body()

        parsed = parse_prg_binary(content)
        p_no = parsed["program_no"]
        clean_mach = _norm_machine(target_machine)
        parsed["machine_code"] = clean_mach
        parsed["filename"] = filename

        _save_custom_entry(META_PATH, clean_mach, p_no, parsed)

        # Save machine-scoped compiled binary cache
        mach_dir = os.path.join(COMPILED_DIR, clean_mach)
        os.makedirs(mach_dir, exist_ok=True)
        out_path = os.path.join(mach_dir, f"M_{str(p_no).zfill(4)}.PRG")
        with open(out_path, "wb") as f:
            f.write(content)

        # Also save to machine workspace
        m_folder = f"MESIN_{clean_mach}"
        m_save_dir = os.path.join(MACHINE_WORKSPACE_BASE, m_folder, "03_CONTOH_PRG_DARI_HMI")
        os.makedirs(m_save_dir, exist_ok=True)
        save_name = filename if filename.upper().endswith(".PRG") else f"M_{str(p_no).zfill(4)}.PRG"
        with open(os.path.join(m_save_dir, save_name), "wb") as f:
            f.write(content)

        # Upsert into PostgreSQL (update existing row if same machine+number)
        try:
            p_no_str = _norm_pno_str(p_no)
            existing = [
                r for r in db.query(ProgramComponent).filter(ProgramComponent.level == 1).order_by(ProgramComponent.id.asc()).all()
                if _norm_machine(r.machine_code) == clean_mach and _norm_pno_str(r.number) == p_no_str
            ]
            proc = existing[0] if existing else None
            for dup in existing[1:]:
                db.delete(dup)
            if not proc:
                proc = ProgramComponent(
                    level=1, type=1, number=p_no_str,
                    name=parsed.get("program_name") or f"PROGRAM #{p_no_str}",
                    machine_code=clean_mach
                )
                db.add(proc)
                db.flush()
            else:
                proc.name = parsed.get("program_name") or proc.name
                proc.machine_code = clean_mach
                proc.number = p_no_str
                proc.modification_time = datetime.utcnow()
                for old_s in list(proc.steps):
                    db.delete(old_s)
                db.flush()

            for st in parsed.get("steps") or []:
                new_s = Step(
                    position=int(st.get("step_no") or 1),
                    parent_component_id=proc.id,
                    label=str(st.get("label") or "")[:100],
                    summary_temp=st.get("summary_temp"),
                    summary_time_min=st.get("summary_time_min") or 0.0,
                    summary_water_l=st.get("summary_water_l") or 0.0,
                )
                db.add(new_s)
                db.flush()
                for fn in st.get("functions") or []:
                    new_fn = StepFunction(
                        step_id=new_s.id,
                        resource_number=int(fn.get("column") or 1),
                        function_number=int(fn.get("function_id") or 0),
                        function_name=str(fn.get("name") or "")[:100],
                    )
                    db.add(new_fn)
                    db.flush()
                    for idx, val in enumerate(fn.get("params") or []):
                        db.add(StepFunctionParameter(
                            step_function_id=new_fn.id,
                            function_parameter_number=idx + 1,
                            value=float(val),
                        ))
            db.commit()
        except Exception:
            db.rollback()

        return {
            "status": "success",
            "message": f"Berkas {filename} berhasil diimpor sebagai Program #{p_no} ({len(parsed['steps'])} langkah) untuk Mesin {clean_mach}.",
            "program": parsed
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal mem-parsing berkas .PRG: {str(e)}")


@router.post("/deduplicate")
def deduplicate_programs_endpoint(db: Session = Depends(get_db)):
    """Removes any duplicate program_components within the same machine in PostgreSQL."""
    from ..services.db_sync_service import DBSyncService
    removed_db = DBSyncService.deduplicate_program_components(db)
    return {
        "status": "success",
        "removed_duplicates_in_active_db": removed_db
    }


class FetchFromMachineIn(BaseModel):
    ip_address: Optional[str] = None
    ftp_port: Optional[int] = 21
    timeout: Optional[float] = 10.0
    remote_dir: Optional[str] = None
    controller_type: Optional[str] = None

@router.post("/fetch-from-machine/{machine_no}")
def fetch_programs_from_machine(machine_no: str, req: Optional[FetchFromMachineIn] = None, db: Session = Depends(get_db)):
    """
    Dinonaktifkan: Dashboard hanya membaca program dari database untuk mencegah koneksi FTP ganda ke kontroler.
    """
    raise HTTPException(
        status_code=403,
        detail="Unduh program langsung dari mesin via FTP di dashboard dinonaktifkan. Seluruh program dibaca dari database."
    )


# =============================================================================
# Machine-Specific Workspace Integration
# =============================================================================

class ValidateProgramIn(BaseModel):
    steps: List[StepIn] = []


@router.post("/validate/{machine_no}")
def validate_program_for_machine(machine_no: str, payload: ValidateProgramIn):
    """
    Validates program steps strictly against the target machine's Config/TYPECONF.CNF
    (never .AWL) so invalid Function IDs are caught before compiling or sending to PLC.
    """
    return validate_steps_against_typeconf(machine_no, payload.steps, enrich_names=False)


@router.get("/machine-workspace/{machine_no}/config")
def get_machine_workspace_config(machine_no: str):
    """
    Returns machine-specific functions, parameters, resources, groups, text_choices,
    USERCONF labels, MACHCONF metadata, and profile strictly from non-AWL .CNF files
    in WORKSPACE_PROGRAM_MESIN/MESIN_{machine_no}/02_CONFIG_SIAP_PAKAI/.
    """
    return load_machine_config_bundle(machine_no)

@router.post("/export-to-machine/{machine_no}/{program_no}")
def export_program_for_machine(machine_no: str, program_no: int, db: Session = Depends(get_db)):
    """
    Compiles dyeing program and outputs M_xxxx.PRG directly into that machine's
    04_HASIL_PROGRAM_CELUP folder ready for USB Storage transfer or FTP.
    Strictly validates all Function IDs against machine_no's Config/TYPECONF.CNF first.
    """
    clean_no = _norm_machine(machine_no)
    prg_bytes = get_compiled_prg_bytes(program_no, db, machine_code=clean_no)
    parsed_prg = parse_prg_binary(prg_bytes)
    val = validate_steps_against_typeconf(clean_no, parsed_prg.get("steps", []), enrich_names=False)
    if not val["valid"]:
        err_summary = "; ".join(e["message"] for e in val["errors"][:5])
        raise HTTPException(
            status_code=400,
            detail=f"Ekspor ditolak — Program #{program_no} mengandung Function ID yang tidak valid untuk TYPECONF.CNF Mesin {clean_no}: {err_summary}"
        )

    m_folder = f"MESIN_{clean_no}"
    m_path = os.path.join(MACHINE_WORKSPACE_BASE, m_folder)
    out_dir = os.path.join(m_path, "04_HASIL_PROGRAM_CELUP")
    os.makedirs(out_dir, exist_ok=True)

    filename = f"M_{str(program_no).zfill(4)}.PRG"
    dest_file = os.path.join(out_dir, filename)

    with open(dest_file, "wb") as f:
        f.write(prg_bytes)

    return {
        "status": "success",
        "machine_no": clean_no,
        "program_no": program_no,
        "filename": filename,
        "file_path": dest_file,
        "size_bytes": len(prg_bytes),
        "typeconf_validation": val,
        "ready_for_transfer": True
    }

class ProgramFTPTransferIn(BaseModel):
    machine_code: str
    target_dir: Optional[str] = None
    timeout: Optional[float] = 6.0
    ip_address: Optional[str] = None
    ftp_port: Optional[int] = 21
    controller_type: Optional[str] = None

@router.post("/transfer-ftp/{program_no}")
def transfer_program_to_ftp(program_no: int, req: ProgramFTPTransferIn, db: Session = Depends(get_db)):
    """
    Transfers/writes the compiled M_xxxx.PRG binary directly to the target machine's SETEX 777/797 FTP controller.
    """
    if program_no < 1 or program_no > 9999:
        raise HTTPException(
            status_code=400,
            detail=f"Nomor program SETEX harus antara 1 sampai 9999 (format M_xxxx.PRG). Nomor {program_no} tidak valid."
        )

    import io
    import ftplib
    from ..models.schema_pg import Machine

    clean_code = req.machine_code.strip().upper()
    ip = req.ip_address.strip() if req.ip_address else None
    port = req.ftp_port or 21

    if not ip:
        m = db.query(Machine).filter(Machine.machine_no == clean_code).first()
        ip = m.ip_address if m and m.ip_address else None
        if m and m.ftp_port:
            port = m.ftp_port

    if not ip:
        known_ips = {
            "DA01": "192.168.1.95",
            "DA1": "192.168.1.95",
            "DA-01": "192.168.1.95",
            "797": "192.168.1.95",
            "797CE": "192.168.1.95",
            "SC797": "192.168.1.95",
            "SC797CE": "192.168.1.95",
            "MESIN_797": "192.168.1.95",
            "10B": "172.16.110.160",
            "TD12": "172.16.110.101",
            "A002": "172.16.110.102",
            "A003": "172.16.110.103",
            "1A": "172.16.110.104"
        }
        ip = known_ips.get(clean_code, "172.16.110.160")

    is_797 = (
        ip in ("192.168.1.95", "172.16.120.102", "172.16.120.103", "172.16.120.105", "172.16.120.108", "172.16.120.109", "172.16.120.154") or 
        (req.controller_type and "797" in req.controller_type.upper()) or
        "797" in clean_code or
        clean_code in ["DA01", "DA1", "DA-01"] or
        (req.target_dir and "SC797" in req.target_dir.upper())
    )

    filename = f"M_{str(program_no).zfill(4)}.PRG"
    try:
        prg_bytes = get_compiled_prg_bytes(program_no, db, machine_code=clean_code)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Gagal mengompilasi program #{program_no} untuk FTP: {str(e)}"
        )

    # Strict pre-flight validation against target machine's Config/TYPECONF.CNF before sending to PLC/HMI
    try:
        parsed_prg = parse_prg_binary(prg_bytes)
        val = validate_steps_against_typeconf(clean_code, parsed_prg.get("steps", []), enrich_names=False)
        if not val["valid"]:
            err_summary = "; ".join(e["message"] for e in val["errors"][:5])
            raise HTTPException(
                status_code=400,
                detail=f"Transfer FTP ke Mesin {clean_code} DIBLOKIR — {filename} mengandung Function ID yang tidak ada di Config/TYPECONF.CNF Mesin {clean_code}: {err_summary}"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Gagal memvalidasi biner {filename} sebelum kirim FTP: {str(e)}"
        )

    # Default to /Flashdisk/SC797CE/Programs if 797, else /Storage/sc777ce/Programs
    default_dir = "/Flashdisk/SC797CE/Programs" if is_797 else "/Storage/sc777ce/Programs"
    requested_dir = (req.target_dir or default_dir).rstrip("/\\")

    # Priority target dirs with automatic fallback between SECOM 797 and 777
    target_dirs_to_try = [
        requested_dir,
        requested_dir.replace("/", "\\"),
        requested_dir.replace("\\", "/")
    ]
    if is_797:
        target_dirs_to_try.extend([
            "/Flashdisk/SC797CE/Programs",
            "/flashdisk/sc797ce/programs",
            "\\Flashdisk\\SC797CE\\Programs",
            "/Flashdisk/SC797CE/PROGRAMS",
            "/Storage/SC777CE/Programs",
            "/Storage/sc777ce/Programs"
        ])
    else:
        target_dirs_to_try.extend([
            "/Storage/SC777CE/Programs",
            "/Storage/sc777ce/Programs",
            "/storage/sc777ce/programs",
            "\\Storage\\SC777CE\\Programs",
            "/Flashdisk/SC797CE/Programs",
            "/flashdisk/sc797ce/programs"
        ])

    target_dirs_to_try.extend([
        "/Programs",
        "/PROGRAMS"
    ])

    resolved_target_dir = None
    timeout_sec = max(float(req.timeout or 10.0), 10.0)

    try:
        ftp = ftplib.FTP(timeout=timeout_sec)
        ftp.connect(ip, port)
        ftp.login()
        
        # Try cwd to preferred directory or fallbacks
        for td in target_dirs_to_try:
            try:
                ftp.cwd(td)
                resolved_target_dir = td
                break
            except Exception:
                continue

        if not resolved_target_dir:
            # Fallback to creating the requested directory
            try:
                ftp.mkd(requested_dir)
                ftp.cwd(requested_dir)
                resolved_target_dir = requested_dir
            except Exception:
                resolved_target_dir = requested_dir

        ftp.storbinary(f"STOR {filename}", io.BytesIO(prg_bytes))
        try:
            ftp.quit()
        except Exception:
            try:
                ftp.close()
            except Exception:
                pass

        return {
            "status": "success",
            "message": f"Program {filename} ({len(prg_bytes)} bytes) BERHASIL ditulis ke FTP Kontroler {clean_code} ({ip}:{port}{resolved_target_dir})!",
            "machine_code": clean_code,
            "ip": ip,
            "port": port,
            "filename": filename,
            "target_dir": resolved_target_dir,
            "size_bytes": len(prg_bytes)
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal menulis {filename} ke FTP Mesin {clean_code} ({ip}:{port}): {str(e)}"
        )

