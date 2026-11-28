"""
Parameter Formula CRUD, Machine Group Deployment, Live Testing & Program Preview Route
Provides `/api/formulas` for Formula Studio, Program Studio (`fx` picker), and Batch Planning preview.
"""

import json
import re
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models.schema_pg import (
    ParameterFormula,
    FormulaMachineGroup,
    FormulaMachine,
    Machine,
    StepFunctionParameter,
)
from ..services.formula_engine import (
    BATCH_VARIABLES_CATALOG,
    FORMULA_TEMPLATES,
    FormulaEvaluationError,
    build_batch_context,
    evaluate_formula,
    resolve_program_steps_for_batch,
    validate_formula_definition,
)

router = APIRouter(prefix="/api/formulas", tags=["Parameter Formulas"])


# =============================================================================
# PYDANTIC SCHEMAS
# =============================================================================

class OutputSpecIn(BaseModel):
    key: str
    label: str
    unit: Optional[str] = ""
    decimal_places: Optional[int] = 1
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    default_fallback: Optional[float] = 0.0
    default_param_slot: Optional[int] = None
    target_function_id: Optional[int] = None
    target_function_name: Optional[str] = None


class FormulaUpsertIn(BaseModel):
    code: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=180)
    description: Optional[str] = ""
    formula_type: str = Field("MATH", description="MATH | IF_ELSE | RANGE_TABLE | LOOKUP_TABLE")
    output_mode: str = Field("SINGLE", description="SINGLE | MULTI")
    target_function_id: Optional[int] = None
    target_function_name: Optional[str] = None
    outputs: Optional[List[OutputSpecIn]] = None
    definition: Dict[str, Any]
    unit: Optional[str] = ""
    decimal_places: Optional[int] = 1
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    default_fallback: Optional[float] = 0.0
    apply_all_groups: Optional[bool] = False
    machine_groups: Optional[List[str]] = None
    machine_nos: Optional[List[str]] = None
    is_active: Optional[bool] = True


class AssignGroupsIn(BaseModel):
    machine_groups: List[str] = []
    machine_nos: List[str] = []
    apply_all_groups: bool = False


class BulkAssignGroupsIn(BaseModel):
    formula_ids: List[int]
    machine_groups: List[str] = []
    machine_nos: List[str] = []
    apply_all_groups: bool = False
    mode: str = Field("add", description="'add' (tambahkan ke grup/mesin existing) | 'replace' (ganti seluruh target)")


class FormulaTestIn(BaseModel):
    formula_type: str = "MATH"
    output_mode: str = "SINGLE"
    outputs: Optional[List[Dict[str, Any]]] = None
    definition: Dict[str, Any]
    unit: Optional[str] = ""
    decimal_places: Optional[int] = 1
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    default_fallback: Optional[float] = 0.0
    batch_context: Dict[str, Any] = {}


class ProgramPreviewIn(BaseModel):
    program_no: int
    machine_no: Optional[str] = None
    batch_context: Dict[str, Any] = {}


# =============================================================================
# SERIALIZATION HELPERS
# =============================================================================

def _generate_code(name: str, existing_codes: set) -> str:
    slug = re.sub(r"[^A-Z0-9]+", "-", (name or "FORMULA").upper()).strip("-")[:18]
    base = f"FX-{slug or 'PARAM'}"
    if base not in existing_codes:
        return base
    i = 2
    while f"{base}-{i}" in existing_codes:
        i += 1
    return f"{base}-{i}"


def formula_to_dict(f: ParameterFormula, usage_count: Optional[int] = None) -> Dict[str, Any]:
    try:
        definition = json.loads(f.definition_json) if f.definition_json else {}
    except Exception:
        definition = {}
    try:
        outputs = json.loads(f.outputs_json) if f.outputs_json else None
    except Exception:
        outputs = None

    groups = sorted([g.machine_group_name for g in (f.machine_groups or [])])
    machine_nos = sorted([m.machine_no for m in (getattr(f, "machines", None) or [])])
    res = {
        "id": f.id,
        "code": f.code,
        "name": f.name,
        "description": f.description or "",
        "formula_type": f.formula_type or "MATH",
        "output_mode": f.output_mode or "SINGLE",
        "target_function_id": f.target_function_id,
        "target_function_name": f.target_function_name or "",
        "outputs": outputs,
        "definition": definition,
        "unit": f.unit or "",
        "decimal_places": f.decimal_places if f.decimal_places is not None else 1,
        "min_value": float(f.min_value) if f.min_value is not None else None,
        "max_value": float(f.max_value) if f.max_value is not None else None,
        "default_fallback": float(f.default_fallback) if f.default_fallback is not None else 0.0,
        "apply_all_groups": bool(f.apply_all_groups),
        "machine_groups": groups,
        "machine_nos": machine_nos,
        "is_active": bool(f.is_active),
        "created_at": f.created_at.strftime("%Y-%m-%d %H:%M:%S") if f.created_at else None,
        "updated_at": f.updated_at.strftime("%Y-%m-%d %H:%M:%S") if f.updated_at else None,
    }
    if usage_count is not None:
        res["usage_count"] = usage_count
    return res


def load_formula_map(db: Session, formula_ids: Optional[List[int]] = None) -> Dict[int, Dict[str, Any]]:
    q = db.query(ParameterFormula).options(
        selectinload(ParameterFormula.machine_groups),
        selectinload(ParameterFormula.machines),
    )
    if formula_ids:
        q = q.filter(ParameterFormula.id.in_(list(set(int(i) for i in formula_ids))))
    return {f.id: formula_to_dict(f) for f in q.all()}


# =============================================================================
# METADATA & DISCOVERY ENDPOINTS
# =============================================================================

@router.get("/variables")
def get_batch_variables():
    """Mengembalikan katalog variabel batch yang dapat dipakai dalam formula."""
    return {"variables": BATCH_VARIABLES_CATALOG}


@router.get("/templates")
def get_formula_templates():
    """Mengembalikan daftar template formula siap pakai untuk industri celup tekstil."""
    return {"templates": FORMULA_TEMPLATES}


@router.get("/machine-groups")
def get_machine_groups(db: Session = Depends(get_db)):
    """
    Mengembalikan daftar Grup Mesin unik dari tabel machines,
    beserta jumlah mesin, daftar kode mesin, tipe HMI dari TYPECONF.CNF, dan jumlah formula terpasang.
    """
    import os
    import struct
    from ..services.machine_config_service import (
        WORKSPACE_BASE,
        normalize_folder_name,
        _decode_cnf_records,
    )

    def _read_hmi_identity(machine_no: str) -> Dict[str, str]:
        tc_path = os.path.join(WORKSPACE_BASE, normalize_folder_name(machine_no), "01_CONFIG_DARI_HMI", "TYPECONF.CNF")
        if not os.path.exists(tc_path):
            return {"hmi_controller": "", "hmi_type": ""}
        try:
            recs = _decode_cnf_records(tc_path, expected_len=290)
            ctrl = ""
            t_name = ""
            if (97, 0, 1) in recs:
                ctrl = recs[(97, 0, 1)][6:20].split(b"\x00", 1)[0].decode("cp437", errors="replace").strip()
            if (35, 0, 1) in recs:
                raw35 = recs[(35, 0, 1)]
                short_t = raw35[23:34].split(b"\x00", 1)[0].decode("cp437", errors="replace").strip()
                long_t = raw35[35:65].split(b"\x00", 1)[0].decode("cp437", errors="replace").strip()
                t_name = long_t or short_t
            return {"hmi_controller": ctrl, "hmi_type": t_name}
        except Exception:
            return {"hmi_controller": "", "hmi_type": ""}

    machines = db.query(Machine).order_by(Machine.group_name.asc(), Machine.machine_no.asc()).all()
    groups_map: Dict[str, Dict[str, Any]] = {}
    for m in machines:
        g_name = (m.group_name or "Dyeing Section").strip()
        if g_name not in groups_map:
            groups_map[g_name] = {
                "group_name": g_name,
                "machine_count": 0,
                "machines": [],
                "formula_count": 0,
            }
        hmi_id = _read_hmi_identity(m.machine_no)
        groups_map[g_name]["machine_count"] += 1
        groups_map[g_name]["machines"].append({
            "machine_no": m.machine_no,
            "display_name": m.display_name,
            "controller_type": m.controller_type or "",
            "hmi_controller": hmi_id["hmi_controller"],
            "hmi_type": hmi_id["hmi_type"],
            "capacity_kg": float(m.capacity_kg) if m.capacity_kg is not None else 350.0,
        })

    # Hitung formula terpasang per grup
    formulas = db.query(ParameterFormula).options(selectinload(ParameterFormula.machine_groups)).filter(
        ParameterFormula.is_active == True  # noqa: E712
    ).all()
    for f in formulas:
        if f.apply_all_groups:
            for g in groups_map.values():
                g["formula_count"] += 1
        else:
            for mg in (f.machine_groups or []):
                gn = mg.machine_group_name
                if gn not in groups_map:
                    groups_map[gn] = {
                        "group_name": gn,
                        "machine_count": 0,
                        "machines": [],
                        "formula_count": 0,
                    }
                groups_map[gn]["formula_count"] += 1

    sorted_groups = sorted(groups_map.values(), key=lambda x: x["group_name"].lower())
    machine_group_map: Dict[str, Dict[str, Any]] = {}
    for idx, grp in enumerate(sorted_groups, start=1):
        gid = f"GRP-{idx:02d}"
        grp["group_no"] = idx
        grp["group_id"] = gid
        for m in grp["machines"]:
            m["group_id"] = gid
            m["group_name"] = grp["group_name"]
            machine_group_map[m["machine_no"]] = {
                "group_no": idx,
                "group_id": gid,
                "group_name": grp["group_name"],
            }

    return {"groups": sorted_groups, "machine_group_map": machine_group_map}


# =============================================================================
# CRUD ENDPOINTS
# =============================================================================

@router.get("", include_in_schema=False)
@router.get("/")
def list_formulas(
    machine_group: Optional[str] = None,
    machine_no: Optional[str] = None,
    formula_type: Optional[str] = None,
    output_mode: Optional[str] = None,
    search: Optional[str] = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    """
    Mengambil daftar formula parameter.
    Jika `machine_no` diberikan, otomatis mencari `group_name` mesin tersebut dan
    hanya mengembalikan formula yang dikirim ke grup mesin itu (atau apply_all_groups=True).
    """
    resolved_group = machine_group
    clean_machine_no = None
    if machine_no:
        clean_machine_no = machine_no.strip().upper().replace("MESIN_", "")
        if not resolved_group:
            m_obj = db.query(Machine).filter(Machine.machine_no == clean_machine_no).first()
            if m_obj and m_obj.group_name:
                resolved_group = m_obj.group_name.strip()

    q = db.query(ParameterFormula).options(
        selectinload(ParameterFormula.machine_groups),
        selectinload(ParameterFormula.machines),
    )
    if not include_inactive:
        q = q.filter(ParameterFormula.is_active == True)  # noqa: E712
    if formula_type and formula_type.upper() != "ALL":
        q = q.filter(ParameterFormula.formula_type == formula_type.upper())
    if output_mode and output_mode.upper() != "ALL":
        q = q.filter(ParameterFormula.output_mode == output_mode.upper())

    all_rows = q.order_by(ParameterFormula.updated_at.desc(), ParameterFormula.id.desc()).all()

    # Hitung pemakaian di step_function_parameters
    usage_counts: Dict[int, int] = {}
    try:
        used_rows = db.query(StepFunctionParameter.formula_id).filter(
            StepFunctionParameter.formula_id.isnot(None)
        ).all()
        for (fid,) in used_rows:
            usage_counts[fid] = usage_counts.get(fid, 0) + 1
    except Exception:
        pass

    results = []
    search_low = (search or "").strip().lower()
    for f in all_rows:
        f_groups = [g.machine_group_name for g in (f.machine_groups or [])]
        f_machines = [m.machine_no.strip().upper() for m in (f.machines or [])]
        if clean_machine_no:
            # Cocok jika global, atau grup mesinnya cocok, atau langsung di-assign ke mesin ini
            group_ok = bool(resolved_group and resolved_group in f_groups)
            mach_ok = clean_machine_no in f_machines
            if not f.apply_all_groups and not group_ok and not mach_ok:
                continue
        elif resolved_group and resolved_group != "ALL":
            if not f.apply_all_groups and resolved_group not in f_groups:
                continue
        if search_low:
            hay = f"{f.code} {f.name} {f.description or ''} {f.target_function_name or ''}".lower()
            if search_low not in hay:
                continue
        results.append(formula_to_dict(f, usage_count=usage_counts.get(f.id, 0)))

    return {
        "machine_group": resolved_group,
        "machine_no": clean_machine_no,
        "count": len(results),
        "formulas": results,
    }


@router.get("/{formula_id}")
def get_formula(formula_id: int, db: Session = Depends(get_db)):
    f = (
        db.query(ParameterFormula)
        .options(
            selectinload(ParameterFormula.machine_groups),
            selectinload(ParameterFormula.machines),
        )
        .filter(ParameterFormula.id == formula_id)
        .first()
    )
    if not f:
        raise HTTPException(status_code=404, detail=f"Formula #{formula_id} tidak ditemukan.")
    return formula_to_dict(f)


@router.post("", include_in_schema=False)
@router.post("/")
def create_formula(payload: FormulaUpsertIn, db: Session = Depends(get_db)):
    f_type = (payload.formula_type or "MATH").upper()
    out_mode = (payload.output_mode or "SINGLE").upper()
    outputs_list = [o.dict() for o in payload.outputs] if payload.outputs else None

    try:
        validate_formula_definition(f_type, out_mode, payload.definition, outputs_list)
    except FormulaEvaluationError as exc:
        raise HTTPException(status_code=400, detail=f"Formula tidak valid: {exc}")

    existing_codes = {row[0] for row in db.query(ParameterFormula.code).all()}
    code = (payload.code or "").strip().upper()
    if not code:
        code = _generate_code(payload.name, existing_codes)
    elif code in existing_codes:
        raise HTTPException(status_code=400, detail=f"Kode formula '{code}' sudah digunakan.")

    new_f = ParameterFormula(
        code=code,
        name=payload.name.strip(),
        description=(payload.description or "").strip(),
        formula_type=f_type,
        output_mode=out_mode,
        target_function_id=payload.target_function_id,
        target_function_name=(payload.target_function_name or "").strip() or None,
        outputs_json=json.dumps(outputs_list, ensure_ascii=False) if outputs_list else None,
        definition_json=json.dumps(payload.definition, ensure_ascii=False),
        unit=(payload.unit or "").strip(),
        decimal_places=payload.decimal_places if payload.decimal_places is not None else 1,
        min_value=payload.min_value,
        max_value=payload.max_value,
        default_fallback=payload.default_fallback if payload.default_fallback is not None else 0.0,
        apply_all_groups=bool(payload.apply_all_groups),
        is_active=True if payload.is_active is None else bool(payload.is_active),
    )
    db.add(new_f)
    db.flush()

    if payload.machine_groups:
        seen = set()
        for gn in payload.machine_groups:
            clean_g = str(gn).strip()
            if clean_g and clean_g not in seen:
                seen.add(clean_g)
                db.add(FormulaMachineGroup(formula_id=new_f.id, machine_group_name=clean_g))

    if payload.machine_nos:
        seen_m = set()
        for mn in payload.machine_nos:
            clean_m = str(mn).strip().upper().replace("MESIN_", "")
            if clean_m and clean_m not in seen_m:
                seen_m.add(clean_m)
                db.add(FormulaMachine(formula_id=new_f.id, machine_no=clean_m))

    db.commit()
    db.refresh(new_f)
    return {
        "status": "success",
        "message": f"Formula '{new_f.name}' ({new_f.code}) berhasil disimpan.",
        "formula": formula_to_dict(new_f, usage_count=0),
    }


@router.put("/{formula_id}")
def update_formula(formula_id: int, payload: FormulaUpsertIn, db: Session = Depends(get_db)):
    f = (
        db.query(ParameterFormula)
        .options(selectinload(ParameterFormula.machine_groups))
        .filter(ParameterFormula.id == formula_id)
        .first()
    )
    if not f:
        raise HTTPException(status_code=404, detail=f"Formula #{formula_id} tidak ditemukan.")

    f_type = (payload.formula_type or "MATH").upper()
    out_mode = (payload.output_mode or "SINGLE").upper()
    outputs_list = [o.dict() for o in payload.outputs] if payload.outputs else None

    try:
        validate_formula_definition(f_type, out_mode, payload.definition, outputs_list)
    except FormulaEvaluationError as exc:
        raise HTTPException(status_code=400, detail=f"Formula tidak valid: {exc}")

    if payload.code and payload.code.strip().upper() != f.code:
        new_code = payload.code.strip().upper()
        clash = db.query(ParameterFormula).filter(
            ParameterFormula.code == new_code,
            ParameterFormula.id != formula_id
        ).first()
        if clash:
            raise HTTPException(status_code=400, detail=f"Kode formula '{new_code}' sudah digunakan.")
        f.code = new_code

    f.name = payload.name.strip()
    f.description = (payload.description or "").strip()
    f.formula_type = f_type
    f.output_mode = out_mode
    f.target_function_id = payload.target_function_id
    f.target_function_name = (payload.target_function_name or "").strip() or None
    f.outputs_json = json.dumps(outputs_list, ensure_ascii=False) if outputs_list else None
    f.definition_json = json.dumps(payload.definition, ensure_ascii=False)
    f.unit = (payload.unit or "").strip()
    f.decimal_places = payload.decimal_places if payload.decimal_places is not None else 1
    f.min_value = payload.min_value
    f.max_value = payload.max_value
    f.default_fallback = payload.default_fallback if payload.default_fallback is not None else 0.0
    if payload.apply_all_groups is not None:
        f.apply_all_groups = bool(payload.apply_all_groups)
    if payload.is_active is not None:
        f.is_active = bool(payload.is_active)

    if payload.machine_groups is not None:
        db.query(FormulaMachineGroup).filter(FormulaMachineGroup.formula_id == f.id).delete()
        seen = set()
        for gn in payload.machine_groups:
            clean_g = str(gn).strip()
            if clean_g and clean_g not in seen:
                seen.add(clean_g)
                db.add(FormulaMachineGroup(formula_id=f.id, machine_group_name=clean_g))

    if payload.machine_nos is not None:
        db.query(FormulaMachine).filter(FormulaMachine.formula_id == f.id).delete()
        seen_m = set()
        for mn in payload.machine_nos:
            clean_m = str(mn).strip().upper().replace("MESIN_", "")
            if clean_m and clean_m not in seen_m:
                seen_m.add(clean_m)
                db.add(FormulaMachine(formula_id=f.id, machine_no=clean_m))

    db.commit()
    db.refresh(f)
    return {
        "status": "success",
        "message": f"Formula '{f.name}' berhasil diperbarui.",
        "formula": formula_to_dict(f),
    }


@router.delete("/{formula_id}")
def delete_formula(formula_id: int, db: Session = Depends(get_db)):
    f = db.query(ParameterFormula).filter(ParameterFormula.id == formula_id).first()
    if not f:
        raise HTTPException(status_code=404, detail=f"Formula #{formula_id} tidak ditemukan.")

    name = f.name
    # Detach from step parameters safely before deleting
    db.query(StepFunctionParameter).filter(StepFunctionParameter.formula_id == formula_id).update(
        {"formula_id": None, "formula_output_key": None}, synchronize_session=False
    )
    db.delete(f)
    db.commit()
    return {"status": "success", "message": f"Formula '{name}' berhasil dihapus."}


# =============================================================================
# MACHINE GROUP DEPLOYMENT (KIRIM FORMULA KE GRUP MESIN)
# =============================================================================

@router.post("/{formula_id}/assign-groups")
def assign_formula_to_groups(formula_id: int, payload: AssignGroupsIn, db: Session = Depends(get_db)):
    f = (
        db.query(ParameterFormula)
        .options(
            selectinload(ParameterFormula.machine_groups),
            selectinload(ParameterFormula.machines),
        )
        .filter(ParameterFormula.id == formula_id)
        .first()
    )
    if not f:
        raise HTTPException(status_code=404, detail=f"Formula #{formula_id} tidak ditemukan.")

    f.apply_all_groups = bool(payload.apply_all_groups)
    db.query(FormulaMachineGroup).filter(FormulaMachineGroup.formula_id == f.id).delete()
    db.query(FormulaMachine).filter(FormulaMachine.formula_id == f.id).delete()

    seen_g = set()
    for gn in (payload.machine_groups or []):
        clean_g = str(gn).strip()
        if clean_g and clean_g not in seen_g:
            seen_g.add(clean_g)
            db.add(FormulaMachineGroup(formula_id=f.id, machine_group_name=clean_g))

    seen_m = set()
    for mn in (payload.machine_nos or []):
        clean_m = str(mn).strip().upper().replace("MESIN_", "")
        if clean_m and clean_m not in seen_m:
            seen_m.add(clean_m)
            db.add(FormulaMachine(formula_id=f.id, machine_no=clean_m))

    db.commit()
    db.refresh(f)

    if f.apply_all_groups:
        msg = f"Formula '{f.name}' dikirim ke Semua Grup & Mesin (Global)."
    else:
        parts = []
        if seen_g:
            parts.append(f"{len(seen_g)} Grup Mesin")
        if seen_m:
            parts.append(f"{len(seen_m)} Mesin Spesifik")
        msg = f"Formula '{f.name}' dikirim ke {' + '.join(parts) if parts else '0 target'}."

    return {
        "status": "success",
        "message": msg,
        "formula": formula_to_dict(f),
    }


@router.post("/bulk-assign-groups")
def bulk_assign_formulas_to_groups(payload: BulkAssignGroupsIn, db: Session = Depends(get_db)):
    if not payload.formula_ids:
        raise HTTPException(status_code=400, detail="Pilih minimal 1 formula untuk dikirim.")

    formulas = (
        db.query(ParameterFormula)
        .options(
            selectinload(ParameterFormula.machine_groups),
            selectinload(ParameterFormula.machines),
        )
        .filter(ParameterFormula.id.in_(payload.formula_ids))
        .all()
    )
    if not formulas:
        raise HTTPException(status_code=404, detail="Formula yang dipilih tidak ditemukan.")

    clean_groups = sorted({str(g).strip() for g in (payload.machine_groups or []) if str(g).strip()})
    clean_machines = sorted({
        str(m).strip().upper().replace("MESIN_", "")
        for m in (payload.machine_nos or [])
        if str(m).strip()
    })

    for f in formulas:
        if payload.apply_all_groups:
            f.apply_all_groups = True
        elif payload.mode == "replace":
            f.apply_all_groups = False
            db.query(FormulaMachineGroup).filter(FormulaMachineGroup.formula_id == f.id).delete()
            db.query(FormulaMachine).filter(FormulaMachine.formula_id == f.id).delete()
            for gn in clean_groups:
                db.add(FormulaMachineGroup(formula_id=f.id, machine_group_name=gn))
            for mn in clean_machines:
                db.add(FormulaMachine(formula_id=f.id, machine_no=mn))
        else:
            existing_g = {g.machine_group_name for g in (f.machine_groups or [])}
            for gn in clean_groups:
                if gn not in existing_g:
                    db.add(FormulaMachineGroup(formula_id=f.id, machine_group_name=gn))
            existing_m = {m.machine_no.strip().upper() for m in (f.machines or [])}
            for mn in clean_machines:
                if mn not in existing_m:
                    db.add(FormulaMachine(formula_id=f.id, machine_no=mn))

    db.commit()
    return {
        "status": "success",
        "updated_count": len(formulas),
        "message": f"{len(formulas)} formula berhasil dikirim ke grup / mesin terpilih.",
    }


# =============================================================================
# LIVE TESTING & BATCH PROGRAM PREVIEW
# =============================================================================

@router.post("/test")
def test_formula_live(payload: FormulaTestIn):
    """Uji coba / simulasi formula secara langsung dengan input batch contoh."""
    ctx = build_batch_context(payload.batch_context)
    formula_dict = {
        "formula_type": payload.formula_type,
        "output_mode": payload.output_mode,
        "outputs": payload.outputs,
        "definition": payload.definition,
        "unit": payload.unit,
        "decimal_places": payload.decimal_places,
        "min_value": payload.min_value,
        "max_value": payload.max_value,
        "default_fallback": payload.default_fallback,
    }
    try:
        res = evaluate_formula(formula_dict, ctx)
        return {"ok": True, "context": ctx, "result": res}
    except FormulaEvaluationError as exc:
        return {"ok": False, "context": ctx, "error": str(exc)}


@router.post("/preview-program")
def preview_program_formulas(payload: ProgramPreviewIn, db: Session = Depends(get_db)):
    """
    Menghitung preview seluruh parameter step yang terikat formula `fx`
    pada sebuah program menggunakan input dari modal Tambah Batch Baru.
    """
    from .programs import get_program

    mach_clean = payload.machine_no.strip().upper().replace("MESIN_", "") if payload.machine_no else None
    mach_cap = None
    if mach_clean:
        m_obj = db.query(Machine).filter(Machine.machine_no == mach_clean).first()
        if m_obj and m_obj.capacity_kg is not None:
            mach_cap = float(m_obj.capacity_kg)

    try:
        prg_data = get_program(payload.program_no, machine_code=mach_clean, db=db)
    except HTTPException:
        return {"has_formulas": False, "resolved_items": [], "context": build_batch_context(payload.batch_context, mach_cap, machine_no=mach_clean)}

    steps = prg_data.get("steps") or []
    needed_ids = set()
    for st in steps:
        for fn in st.get("functions") or []:
            for binding in (fn.get("param_formulas") or {}).values():
                if isinstance(binding, dict) and binding.get("formula_id"):
                    needed_ids.add(int(binding["formula_id"]))
                elif isinstance(binding, int):
                    needed_ids.add(binding)

    ctx = build_batch_context(payload.batch_context, machine_capacity_kg=mach_cap, machine_no=mach_clean)
    if not needed_ids:
        return {
            "has_formulas": False,
            "program_no": payload.program_no,
            "program_name": prg_data.get("program_name", ""),
            "resolved_items": [],
            "context": ctx,
        }

    f_map = load_formula_map(db, list(needed_ids))
    _, resolved_items = resolve_program_steps_for_batch(steps, f_map, ctx)

    return {
        "has_formulas": len(resolved_items) > 0,
        "program_no": payload.program_no,
        "program_name": prg_data.get("program_name", ""),
        "resolved_items": resolved_items,
        "context": ctx,
    }


# =============================================================================
# MACHINE CONFIG FORMULA & PARAMETER INSPECTOR (TYPEFORM / MACHCONF / TYPECONF)
# =============================================================================

@router.get("/machine-config/{machine_no}")
def get_machine_formula_config(machine_no: str):
    """
    Membaca file konfigurasi HMI mesin dari WORKSPACE_PROGRAM_MESIN/MESIN_<ID>/01_CONFIG_DARI_HMI/:
      - TYPEFORM.CNF: daftar Global Formula (cat=7) & jumlah mapping Function Formula (cat=36)
      - MACHCONF.CNF: konstanta/parameter mesin (cat=18) & tabel kalibrasi kurva (cat=75)
      - TYPECONF.CNF: definisi controller parameters (cat=17) & ringkasan fungsi/parameter
    """
    import os
    import struct
    import sys
    from ..services.machine_config_service import (
        DA_TEX_ROOT,
        WORKSPACE_BASE,
        normalize_folder_name,
        _decode_cnf_records,
    )

    folder_name = normalize_folder_name(machine_no)
    raw_dir = os.path.join(WORKSPACE_BASE, folder_name, "01_CONFIG_DARI_HMI")
    dec_dir = os.path.join(WORKSPACE_BASE, folder_name, "02_CONFIG_SIAP_PAKAI")

    tf_path = os.path.join(raw_dir, "TYPEFORM.CNF")
    mc_path = os.path.join(raw_dir, "MACHCONF.CNF")
    tc_path = os.path.join(raw_dir, "TYPECONF.CNF")
    tc_json_path = os.path.join(dec_dir, "typeconf_functions.json")

    analisis_dir = os.path.join(DA_TEX_ROOT, "program", "Analisis")
    if analisis_dir not in sys.path:
        sys.path.append(analisis_dir)

    def _decode_txt_safe(b: bytes) -> str:
        return b.split(b"\x00", 1)[0].decode("cp437", errors="replace").strip()

    typeform_formulas: List[Dict[str, Any]] = []
    typeform_function_links_count = 0
    if os.path.exists(tf_path):
        try:
            tf_recs = _decode_cnf_records(tf_path, expected_len=None)
            for (cat, sub, idx), raw in sorted(tf_recs.items()):
                if cat == 7 and len(raw) >= 48:
                    n_local = _decode_txt_safe(raw[6:27])
                    n_en = _decode_txt_safe(raw[27:48]) or n_local
                    typeform_formulas.append({
                        "id": idx,
                        "name": n_en,
                        "name_local": n_local,
                    })
                elif cat == 36:
                    typeform_function_links_count += 1
        except Exception:
            pass

    machconf_constants: List[Dict[str, Any]] = []
    machconf_calibrations: List[Dict[str, Any]] = []
    if os.path.exists(mc_path):
        try:
            mc_recs = _decode_cnf_records(mc_path, expected_len=None)
            for (cat, sub, idx), raw in sorted(mc_recs.items()):
                if cat == 18:
                    vals = []
                    for off in range(6, min(len(raw) - 4, 62), 4):
                        v = struct.unpack_from("<f", raw, off)[0]
                        if v == v and abs(v) < 1e7 and abs(v) > 1e-4:
                            vals.append(round(v, 3))
                    if vals:
                        machconf_constants.append({
                            "group": sub,
                            "index": idx,
                            "values": vals[:8],
                        })
                elif cat == 75:
                    pts = []
                    for off in range(6, min(len(raw) - 8, 94), 8):
                        x, y = struct.unpack_from("<ff", raw, off)
                        if x == x and y == y and 0 < abs(x) < 1e6 and 0 < abs(y) < 1e6:
                            pts.append({"x": round(x, 2), "y": round(y, 2)})
                    if pts:
                        machconf_calibrations.append({
                            "group": sub,
                            "index": idx,
                            "points": pts[:10],
                        })
        except Exception:
            pass

    controller_params: List[Dict[str, Any]] = []
    if os.path.exists(tc_path):
        try:
            tc_recs = _decode_cnf_records(tc_path, expected_len=290)
            for (cat, sub, idx), raw in sorted(tc_recs.items()):
                if cat == 17 and len(raw) >= 48:
                    n_local = _decode_txt_safe(raw[6:27])
                    n_en = _decode_txt_safe(raw[27:48]) or n_local
                    if n_en and n_en.lower() != "not used":
                        controller_params.append({
                            "group": sub,
                            "index": idx,
                            "name": n_en,
                            "name_local": n_local,
                        })
        except Exception:
            pass

    typeconf_fn_count = 0
    typeconf_param_count = 0
    if os.path.exists(tc_json_path):
        try:
            with open(tc_json_path, "r", encoding="utf-8") as f:
                tc_json = json.load(f)
            typeconf_fn_count = len(tc_json.get("functions") or {})
            typeconf_param_count = len(tc_json.get("parameters") or {})
        except Exception:
            pass

    from ..services.formula_engine import load_machine_config_vars, load_machine_config_catalog
    config_vars = load_machine_config_vars(machine_no)
    machconf_catalog = load_machine_config_catalog(machine_no)

    return {
        "machine_no": machine_no.upper(),
        "folder_name": folder_name,
        "config_vars": config_vars,
        "machconf_catalog": machconf_catalog,
        "files": {
            "TYPEFORM.CNF": os.path.exists(tf_path),
            "MACHCONF.CNF": os.path.exists(mc_path),
            "TYPECONF.CNF": os.path.exists(tc_path),
        },
        "typeform": {
            "formulas": typeform_formulas,
            "function_links_count": typeform_function_links_count,
        },
        "machconf": {
            "constants": machconf_constants,
            "calibrations": machconf_calibrations,
        },
        "typeconf": {
            "functions_count": typeconf_fn_count,
            "parameters_count": typeconf_param_count,
            "controller_params": controller_params[:80],
            "controller_params_total": len(controller_params),
        },
    }
