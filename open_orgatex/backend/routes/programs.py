"""
Dyeing Programs Route (OrgaTEX EDX300 Parity)
Full Procedure (Master Program) & Treatment (Sub-Program) Integration
Persists in PostgreSQL / TimescaleDB using OrgaTEX schema (program_components, program_component_items, steps, etc.)
"""

from fastapi import APIRouter, HTTPException, Depends, Response, Request
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from sqlalchemy.orm import Session
import os
import json
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
from ..services.machine_config_service import fetch_machine_programs_from_hmi
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

# Pydantic Schemas
class StepFunctionIn(BaseModel):
    function_id: int
    name: Optional[str] = ""
    column: Optional[int] = 1
    flags: Optional[int] = 0
    params: Optional[List[float]] = []

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
    program_no: int
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

# Standard Treatment Library (Sub-Programs)
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
                "functions": [{"function_id": 713, "name": "Water Fill", "column": 1, "params": [1.0, 3200.0]}]
            },
            {
                "step_no": 2,
                "label": "Injeksi Kimia S/B (Kostik & H2O2)",
                "functions": [{"function_id": 85, "name": "Dosing Tank 1", "column": 1, "params": [10.0, 100.0]}]
            },
            {
                "step_no": 3,
                "label": "Pemanasan ke 98°C",
                "functions": [{"function_id": 141, "name": "Heating", "column": 1, "params": [98.0, 2.5]}]
            },
            {
                "step_no": 4,
                "label": "Tahan Suhu 98°C",
                "functions": [{"function_id": 121, "name": "Hold", "column": 1, "params": [45.0]}]
            },
            {
                "step_no": 5,
                "label": "Drain Total",
                "functions": [{"function_id": 61, "name": "Drain", "column": 1, "params": []}]
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
                    {"function_id": 713, "name": "Water Fill", "column": 1, "params": [1.0, 3000.0]},
                    {"function_id": 404, "name": "Circulation Pump", "column": 2, "params": [85.0]}
                ]
            },
            {
                "step_no": 2,
                "label": "Dosing Garam Glauber (Tank 1)",
                "functions": [{"function_id": 85, "name": "Dosing Tank 1", "column": 1, "params": [15.0, 100.0]}]
            },
            {
                "step_no": 3,
                "label": "Dosing Zat Warna (Tank 2)",
                "functions": [{"function_id": 86, "name": "Dosing Tank 2", "column": 1, "params": [20.0, 100.0]}]
            },
            {
                "step_no": 4,
                "label": "Heating ke Suhu 60°C",
                "functions": [{"function_id": 141, "name": "Heating", "column": 1, "params": [60.0, 1.5]}]
            },
            {
                "step_no": 5,
                "label": "Penahanan Suhu & Fiksasi 60°C",
                "functions": [{"function_id": 121, "name": "Hold", "column": 1, "params": [45.0]}]
            },
            {
                "step_no": 6,
                "label": "Cooling ke 50°C",
                "functions": [{"function_id": 144, "name": "Cooling", "column": 1, "params": [50.0, 2.0]}]
            },
            {
                "step_no": 7,
                "label": "Drain Larutan Celup",
                "functions": [{"function_id": 61, "name": "Drain", "column": 1, "params": []}]
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
                "functions": [{"function_id": 713, "name": "Water Fill", "column": 1, "params": [1.0, 3000.0]}]
            },
            {
                "step_no": 2,
                "label": "Dosing Sabun Pencuci (Tank 1)",
                "functions": [{"function_id": 85, "name": "Dosing Tank 1", "column": 1, "params": [5.0, 100.0]}]
            },
            {
                "step_no": 3,
                "label": "Pemanasan ke 95°C",
                "functions": [{"function_id": 141, "name": "Heating", "column": 1, "params": [95.0, 2.5]}]
            },
            {
                "step_no": 4,
                "label": "Hold Sabun 95°C",
                "functions": [{"function_id": 121, "name": "Hold", "column": 1, "params": [20.0]}]
            },
            {
                "step_no": 5,
                "label": "Drain",
                "functions": [{"function_id": 61, "name": "Drain", "column": 1, "params": []}]
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
                "functions": [{"function_id": 713, "name": "Water Fill", "column": 1, "params": [1.0, 2500.0]}]
            },
            {
                "step_no": 2,
                "label": "Bilas Dingin 10 Menit",
                "functions": [{"function_id": 127, "name": "Rinse", "column": 1, "params": [10.0]}]
            },
            {
                "step_no": 3,
                "label": "Drain Akhir & Selesai",
                "functions": [
                    {"function_id": 61, "name": "Drain", "column": 1, "params": []},
                    {"function_id": 2, "name": "End of Program", "column": 2, "params": []}
                ]
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

@router.get("/")
def list_programs(db: Session = Depends(get_db)):
    """
    Lists all available master programs (Procedures, Level=1).
    Combines PostgreSQL records, OrgaTEX plain export, and custom programs.
    """
    results = []
    seen_ids = set()

    # 1. Read from PostgreSQL (ProgramComponent Level 1)
    try:
        procs = db.query(ProgramComponent).filter(ProgramComponent.level == 1).order_by(ProgramComponent.number).all()
        for p in procs:
            try:
                pno = int(p.number)
            except Exception:
                pno = p.id
            seen_ids.add(pno)
            results.append({
                "filename": f"M_{str(pno).zfill(4)}.PRG",
                "program_number": pno,
                "program_name": p.name,
                "machine_code": p.machine_code or "TD12",
                "total_steps": len(p.steps) or sum(len(sub.treatment.steps) for sub in p.sub_program_items if sub.treatment),
                "is_custom": True,
                "file_size": 1024 * (len(p.steps) or 1)
            })
    except Exception:
        pass

    # 2. Custom JSON store
    custom = _load_json_file(META_PATH, {})
    for pid_str, prg in custom.items():
        try:
            pid = int(pid_str)
            if pid not in seen_ids:
                seen_ids.add(pid)
                results.append({
                    "filename": prg.get("filename") or f"M_{str(pid).zfill(4)}.PRG",
                    "program_number": pid,
                    "program_name": prg.get("program_name", f"PROGRAM #{pid}"),
                    "machine_code": prg.get("machine_code") or "TD12",
                    "total_steps": len(prg.get("steps", [])),
                    "is_custom": True,
                    "file_size": 1024 * (len(prg.get("steps", [])) or 1)
                })
        except Exception:
            pass

    # 2.5 Scan WORKSPACE_PROGRAM_MESIN for local machine programs
    try:
        if os.path.isdir(MACHINE_WORKSPACE_BASE):
            for m_dir in sorted(os.listdir(MACHINE_WORKSPACE_BASE)):
                if not m_dir.startswith("MESIN_"):
                    continue
                clean_m = m_dir.replace("MESIN_", "")
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
                                pno = parsed.get("program_no")
                                if pno and pno not in seen_ids:
                                    seen_ids.add(pno)
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
                    if pno not in seen_ids:
                        seen_ids.add(pno)
                        results.append({
                            "filename": item.get("filename"),
                            "program_number": pno,
                            "program_name": item.get("program_name"),
                            "machine_code": item.get("machine_code") or "TD12",
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
                    if tid and tid not in seen_ids:
                        seen_ids.add(tid)
                        raw_len = len(base64.b64decode(t["base64"])) if "base64" in t else 1024
                        results.append({
                            "filename": t.get("filename", f"M_{str(tid).zfill(4)}.PRG"),
                            "program_number": tid,
                            "program_name": t.get("title", f"Template #{tid}"),
                            "machine_code": t.get("machine_code") or "TD12",
                            "total_steps": t.get("steps", 0),
                            "is_custom": False,
                            "file_size": raw_len
                        })
        except Exception:
            pass

    results.sort(key=lambda x: x["program_number"])
    return results

@router.get("/{program_no}")
def get_program(program_no: int, db: Session = Depends(get_db)):
    """
    Retrieves full Procedure details, including Sub-Programs (Treatments) and flattened steps.
    """
    # 0. Check Custom JSON store first if it has rich sub_programs
    custom = _load_json_file(META_PATH, {})
    if str(program_no) in custom:
        c_prg = custom[str(program_no)]
        if c_prg.get("sub_programs") or c_prg.get("steps"):
            return c_prg

    # 1. Check PostgreSQL
    try:
        p = db.query(ProgramComponent).filter(
            (ProgramComponent.number == str(program_no)) | (ProgramComponent.id == program_no),
            ProgramComponent.level == 1
        ).first()
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
                            fns.append({
                                "function_id": fn.function_number,
                                "name": fn.function_name,
                                "column": fn.resource_number,
                                "params": p_vals
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
                                "params": [float(pv.value) for pv in fn.parameters]
                            } for fn in s.functions
                        ]
                    } for s in p.steps
                ]
            }
    except Exception:
        pass

    # 2. Check Custom JSON store
    custom = _load_json_file(META_PATH, {})
    if str(program_no) in custom:
        return custom[str(program_no)]

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
            for m_dir in sorted(os.listdir(MACHINE_WORKSPACE_BASE)):
                if not m_dir.startswith("MESIN_"):
                    continue
                clean_m = m_dir.replace("MESIN_", "")
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

@router.post("/")
def save_program(p: ProcedureIn, db: Session = Depends(get_db)):
    """
    Saves or updates Procedure into PostgreSQL program_components table
    and synchronizes JSON storage and auto-compiles binary M_xxxx.PRG.
    """
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

    # 1. Update/Insert in PostgreSQL
    try:
        proc = db.query(ProgramComponent).filter(
            ProgramComponent.number == str(p.program_no),
            ProgramComponent.level == 1
        ).first()

        if not proc:
            proc = ProgramComponent(
                level=1,
                type=1,
                number=str(p.program_no),
                name=p.program_name.strip().upper(),
                machine_code=p.machine_code or "TD12"
            )
            db.add(proc)
            db.flush()
        else:
            proc.name = p.program_name.strip().upper()
            proc.machine_code = p.machine_code or "TD12"
            proc.modification_time = datetime.utcnow()

        # Update steps directly if provided
        if p.steps:
            db.query(Step).filter(Step.parent_component_id == proc.id).delete()
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

                    for idx, val in enumerate(fn.params or []):
                        new_p = StepFunctionParameter(
                            step_function_id=new_fn.id,
                            function_parameter_number=idx + 1,
                            value=val
                        )
                        db.add(new_p)

        db.commit()
    except Exception as e:
        db.rollback()

    # 2. Keep local JSON fallback synced
    custom = _load_json_file(META_PATH, {})
    custom[str(p.program_no)] = p.dict()
    _save_json_file(META_PATH, custom)

    # 3. Auto-compile binary M_xxxx.PRG
    try:
        if p.steps:
            compiled_bytes = serialize_prg_binary(p.program_no, p.program_name, [s.dict() for s in p.steps])
            out_file = os.path.join(COMPILED_DIR, f"M_{str(p.program_no).zfill(4)}.PRG")
            with open(out_file, "wb") as f:
                f.write(compiled_bytes)
    except Exception:
        pass

    return {
        "status": "success",
        "program_no": p.program_no,
        "program_name": p.program_name,
        "total_steps": len(p.steps or []),
        "sub_programs_count": len(p.sub_programs or []),
        "table": "program_components (Level 1 Procedure)",
        "download_url": f"/api/programs/download/{p.program_no}",
        "message": f"Procedure OrgaTEX M_{str(p.program_no).zfill(4)}.PRG berhasil disimpan dan dikompilasi!"
    }

def get_compiled_prg_bytes(program_no: int, db: Optional[Session] = None) -> bytes:
    """Retrieves or builds byte-exact SETEX SECOM 777 .PRG binary."""
    file_path = os.path.join(COMPILED_DIR, f"M_{str(program_no).zfill(4)}.PRG")
    if os.path.exists(file_path):
        try:
            with open(file_path, "rb") as f:
                data = f.read()
                if len(data) >= 384 and data[:4] == bytes.fromhex("508fc2f5"):
                    return data
        except Exception:
            pass

    # Try to load program and compile
    try:
        prg_data = get_program(program_no, db)
        steps = prg_data.get("steps", [])
        if steps:
            title = prg_data.get("program_name", f"PRG {program_no}")
            compiled = serialize_prg_binary(program_no, title, steps)
            with open(file_path, "wb") as f:
                f.write(compiled)
            return compiled
    except Exception:
        pass

    # Try reverse-engineered catalog
    if os.path.exists(CATALOG_PATH):
        try:
            with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                cat = json.load(f)
                for t in cat.get("templates", []):
                    if t.get("id") == program_no and "base64" in t:
                        raw = base64.b64decode(t["base64"])
                        with open(file_path, "wb") as f:
                            f.write(raw)
                        return raw
        except Exception:
            pass

    # Fallback to minimal valid PRG
    fallback = build_minimal_prg(program_no, f"PRG {program_no}")
    try:
        with open(file_path, "wb") as f:
            f.write(fallback)
    except Exception:
        pass
    return fallback


@router.post("/compile/{program_no}")
def compile_program_binary(program_no: int, db: Session = Depends(get_db)):
    """
    Compiles Procedure into standard 65-byte SETEX Secom 777CE binary record format.
    Saves to compiled cache and returns hash and size.
    """
    prg = get_program(program_no, db)
    steps = prg.get("steps", [])
    title = prg.get("program_name", f"PRG {program_no}")
    compiled_bytes = serialize_prg_binary(program_no, title, steps)

    out_file = os.path.join(COMPILED_DIR, f"M_{str(program_no).zfill(4)}.PRG")
    with open(out_file, "wb") as f:
        f.write(compiled_bytes)

    sha256 = hashlib.sha256(compiled_bytes).hexdigest()
    steps_count = len(steps)
    actual_size = len(compiled_bytes)

    return {
        "status": "compiled",
        "target_file": f"M_{str(program_no).zfill(4)}.PRG",
        "sha256": sha256,
        "download_url": f"/api/programs/download/{program_no}",
        "header": {
            "program_no": program_no,
            "program_name": title,
            "records": steps_count,
            "sub_programs_count": len(prg.get("sub_programs", [])),
            "binary_bytes": actual_size
        },
        "message": f"Kompilasi sukses! Program M_{str(program_no).zfill(4)}.PRG siap digunakan ({steps_count} langkah, {actual_size} bytes, SHA-256: {sha256[:8]}...)."
    }


@router.get("/download/{program_no}")
def download_program_binary(program_no: int, db: Session = Depends(get_db)):
    """Downloads byte-exact SETEX SECOM 777 M_xxxx.PRG binary file."""
    prg_bytes = get_compiled_prg_bytes(program_no, db)
    filename = f"M_{str(program_no).zfill(4)}.PRG"
    return Response(
        content=prg_bytes,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.post("/upload-prg")
async def upload_prg_file(request: Request, machine_code: Optional[str] = "TD12", db: Session = Depends(get_db)):
    """Uploads and parses a binary SETEX SECOM 777 .PRG file (raw bytes or JSON base64)."""
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
        clean_mach = target_machine.strip().upper().replace("MESIN_", "")
        parsed["machine_code"] = clean_mach
        parsed["filename"] = filename

        custom = _load_json_file(META_PATH, {})
        custom[str(p_no)] = parsed
        _save_json_file(META_PATH, custom)

        # Save compiled binary cache
        out_path = os.path.join(COMPILED_DIR, f"M_{str(p_no).zfill(4)}.PRG")
        with open(out_path, "wb") as f:
            f.write(content)

        # Also save to machine workspace
        m_folder = f"MESIN_{clean_mach}"
        m_save_dir = os.path.join(MACHINE_WORKSPACE_BASE, m_folder, "03_CONTOH_PRG_DARI_HMI")
        os.makedirs(m_save_dir, exist_ok=True)
        save_name = filename if filename.upper().endswith(".PRG") else f"M_{str(p_no).zfill(4)}.PRG"
        with open(os.path.join(m_save_dir, save_name), "wb") as f:
            f.write(content)

        return {
            "status": "success",
            "message": f"Berkas {filename} berhasil diimpor sebagai Program #{p_no} ({len(parsed['steps'])} langkah) untuk Mesin {clean_mach}.",
            "program": parsed
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal mem-parsing berkas .PRG: {str(e)}")


class FetchFromMachineIn(BaseModel):
    ip_address: Optional[str] = None
    ftp_port: Optional[int] = 21
    timeout: Optional[float] = 10.0
    remote_dir: Optional[str] = None
    controller_type: Optional[str] = None

@router.post("/fetch-from-machine/{machine_no}")
def fetch_programs_from_machine(machine_no: str, req: Optional[FetchFromMachineIn] = None, db: Session = Depends(get_db)):
    """
    Downloads all .PRG binary files from the machine's SETEX HMI controller via FTP (Port 21).
    Saves them to WORKSPACE_PROGRAM_MESIN/MESIN_<ID>/03_CONTOH_PRG_DARI_HMI/,
    parses each program, and registers it so it appears in the program list and can be opened in EDX300/SECOM Studio.
    """
    clean_code = machine_no.strip().upper().replace("MESIN_", "")
    
    # 1. Determine machine IP and port
    ip = None
    port = 21
    if req and req.ip_address:
        ip = req.ip_address.strip()
        port = req.ftp_port or 21
    
    if not ip and db:
        try:
            m = db.query(Machine).filter(Machine.machine_no == clean_code).first()
            if m and m.ip_address:
                ip = m.ip_address
                port = m.ftp_port or 21
        except Exception:
            pass

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
        ip == "192.168.1.95" or 
        (req and req.controller_type and "797" in req.controller_type.upper()) or
        "797" in clean_code or
        clean_code in ["DA01", "DA1", "DA-01"] or
        (req and req.remote_dir and "SC797" in req.remote_dir.upper())
    )

    timeout_val = req.timeout if req and req.timeout else 10.0
    remote_path = (
        req.remote_dir 
        if req and req.remote_dir 
        else ("/Flashdisk/SC797CE/Programs" if is_797 else "/Storage/sc777ce/Programs")
    )

    result = fetch_machine_programs_from_hmi(
        machine_no=clean_code,
        ip=ip,
        ftp_port=port,
        timeout=timeout_val,
        remote_dir=remote_path
    )
    return result


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


# =============================================================================
# Machine-Specific Workspace Integration
# =============================================================================

MACHINE_WORKSPACE_BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../WORKSPACE_PROGRAM_MESIN"))

@router.get("/machine-workspace/{machine_no}/config")
def get_machine_workspace_config(machine_no: str):
    """
    Returns specific functions, parameters, and profile for the selected machine
    from WORKSPACE_PROGRAM_MESIN/MESIN_{machine_no}/02_CONFIG_SIAP_PAKAI/.
    """
    clean_no = machine_no.upper().replace("MESIN_", "")
    m_folder = f"MESIN_{clean_no}"
    m_path = os.path.join(MACHINE_WORKSPACE_BASE, m_folder)

    if not os.path.isdir(m_path):
        m_path = os.path.join(MACHINE_WORKSPACE_BASE, "_TEMPLATE_MESIN_BARU")

    config_dir = os.path.join(m_path, "02_CONFIG_SIAP_PAKAI")
    tf_path = os.path.join(config_dir, "typeconf_functions.json")
    cf_path = os.path.join(config_dir, "conftext_aligned.json")
    prof_path = os.path.join(config_dir, "machine_profile.json")

    functions = {}
    if os.path.exists(tf_path):
        try:
            with open(tf_path, "r", encoding="utf-8") as f:
                functions = json.load(f)
        except Exception:
            pass

    profile = {}
    if os.path.exists(prof_path):
        try:
            with open(prof_path, "r", encoding="utf-8") as f:
                profile = json.load(f)
        except Exception:
            pass

    return {
        "machine_no": clean_no,
        "folder": m_folder,
        "profile": profile,
        "functions_count": len(functions.get("functions", {})),
        "parameters_count": len(functions.get("parameters", {})),
        "functions": functions.get("functions", {}),
        "parameters": functions.get("parameters", {})
    }

@router.post("/export-to-machine/{machine_no}/{program_no}")
def export_program_for_machine(machine_no: str, program_no: int, db: Session = Depends(get_db)):
    """
    Compiles dyeing program and outputs M_xxxx.PRG directly into that machine's
    04_HASIL_PROGRAM_CELUP folder ready for USB Storage transfer or FTP.
    """
    clean_no = machine_no.upper().replace("MESIN_", "")
    m_folder = f"MESIN_{clean_no}"
    m_path = os.path.join(MACHINE_WORKSPACE_BASE, m_folder)
    out_dir = os.path.join(m_path, "04_HASIL_PROGRAM_CELUP")
    os.makedirs(out_dir, exist_ok=True)

    prg_bytes = get_compiled_prg_bytes(program_no, db)
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
        ip == "192.168.1.95" or 
        (req.controller_type and "797" in req.controller_type.upper()) or
        "797" in clean_code or
        clean_code in ["DA01", "DA1", "DA-01"] or
        (req.target_dir and "SC797" in req.target_dir.upper())
    )

    prg_bytes = get_compiled_prg_bytes(program_no, db)
    filename = f"M_{str(program_no).zfill(4)}.PRG"

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

    try:
        ftp = ftplib.FTP(timeout=req.timeout)
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
        ftp.quit()

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

