"""
Unit tests for OpenOrgaTEX Safe Parameter Formula Engine (`formula_engine.py`).
Covers all 4 formula types (MATH, IF_ELSE, RANGE_TABLE, LOOKUP_TABLE),
SINGLE & MULTI output modes, AST safety/security, clamping, and step resolution.
"""

import pytest
from open_orgatex.backend.services.formula_engine import (
    FormulaEvaluationError,
    FORMULA_TEMPLATES,
    build_batch_context,
    evaluate_formula,
    resolve_program_steps_for_batch,
    safe_eval_math,
    validate_formula_definition,
)


def test_math_formula_single_and_clamping():
    ctx = build_batch_context({"fabric_weight_kg": 350, "liquor_ratio": 8})
    formula = {
        "formula_type": "MATH",
        "output_mode": "SINGLE",
        "definition": {"expression": "fabric_weight_kg * liquor_ratio + 200"},
        "decimal_places": 0,
        "min_value": 500,
        "max_value": 2900,
    }
    res = evaluate_formula(formula, ctx)
    assert res["value"] == 2900.0
    assert res["clamped"] is True


def test_math_safe_functions():
    ctx = build_batch_context({"fabric_weight_kg": 123.4, "liquor_ratio": 7.5})
    assert safe_eval_math("round(fabric_weight_kg * liquor_ratio, 0)", ctx) == 926.0
    assert safe_eval_math("max(fabric_weight_kg * 2, 500)", ctx) == 500.0
    assert safe_eval_math("clamp(fabric_weight_kg, 50, 100)", ctx) == 100.0


def test_math_security_blocks_unsafe_expressions():
    ctx = build_batch_context({"fabric_weight_kg": 100})
    with pytest.raises(FormulaEvaluationError):
        safe_eval_math("__import__('os').system('echo pwn')", ctx)
    with pytest.raises(FormulaEvaluationError):
        safe_eval_math("fabric_weight_kg / 0", ctx)
    with pytest.raises(FormulaEvaluationError):
        safe_eval_math("unknown_var + 10", ctx)


def test_if_else_and_or_conditions():
    formula = {
        "formula_type": "IF_ELSE",
        "output_mode": "SINGLE",
        "decimal_places": 0,
        "definition": {
            "rules": [
                {
                    "label": "Cotton Tua",
                    "logic": "AND",
                    "conditions": [
                        {"var": "fabric_type", "op": "equals", "value": "COTTON"},
                        {"var": "color_shade", "op": "equals", "value": "TUA"},
                    ],
                    "result_expr": "round(fabric_weight_kg * 0.1 + 30, 0)",
                },
                {
                    "label": "Redye atau Beban Tinggi",
                    "logic": "OR",
                    "conditions": [
                        {"var": "redye", "op": "equals", "value": "1"},
                        {"var": "load_percent", "op": ">", "value": 90},
                    ],
                    "result_expr": "40",
                },
            ],
            "else_expr": "25",
        },
    }

    ctx1 = build_batch_context({"fabric_type": "COTTON", "color_shade": "TUA", "fabric_weight_kg": 300})
    r1 = evaluate_formula(formula, ctx1)
    assert r1["value"] == 60.0
    assert r1["matched_rule_index"] == 0

    ctx2 = build_batch_context({"fabric_type": "POLYESTER", "redye": 1, "fabric_weight_kg": 100}, machine_capacity_kg=350)
    r2 = evaluate_formula(formula, ctx2)
    assert r2["value"] == 40.0
    assert r2["matched_rule_index"] == 1

    ctx3 = build_batch_context({"fabric_type": "RAYON", "redye": 0, "fabric_weight_kg": 100}, machine_capacity_kg=350)
    r3 = evaluate_formula(formula, ctx3)
    assert r3["value"] == 25.0
    assert r3["matched_rule_index"] == -1


def test_range_table_evaluation():
    tmpl = next(t for t in FORMULA_TEMPLATES if t["code"] == "FX-HOLD-BERAT")
    assert evaluate_formula(tmpl, build_batch_context({"fabric_weight_kg": 80}))["value"] == 25.0
    assert evaluate_formula(tmpl, build_batch_context({"fabric_weight_kg": 200}))["value"] == 35.0
    assert evaluate_formula(tmpl, build_batch_context({"fabric_weight_kg": 350}))["value"] == 45.0
    assert evaluate_formula(tmpl, build_batch_context({"fabric_weight_kg": 500}))["value"] == 60.0


def test_lookup_table_multi_parameter_and_step_resolution():
    tmpl_multi = next(t for t in FORMULA_TEMPLATES if t["code"] == "FX-PAKET-TEMP")
    tmpl_water = next(t for t in FORMULA_TEMPLATES if t["code"] == "FX-AIR-AUTO")

    formula_map = {
        1: {**tmpl_water, "id": 1},
        2: {**tmpl_multi, "id": 2},
    }

    steps = [
        {
            "step_no": 1,
            "label": "Isi Air",
            "functions": [
                {
                    "function_id": 713,
                    "name": "Fill Level",
                    "column": 1,
                    "params": [1.0, 2000.0],
                    "param_formulas": {"1": {"formula_id": 1, "output_key": None}},
                }
            ],
        },
        {
            "step_no": 2,
            "label": "Celup Utama",
            "functions": [
                {
                    "function_id": 141,
                    "name": "Temperature Control",
                    "column": 1,
                    "params": [60.0, 1.5, 30.0],
                    "param_formulas": {
                        "0": {"formula_id": 2, "output_key": "suhu"},
                        "1": {"formula_id": 2, "output_key": "gradient"},
                        "2": {"formula_id": 2, "output_key": "hold"},
                    },
                }
            ],
        },
    ]

    ctx_poly = build_batch_context({"fabric_type": "POLYESTER", "fabric_weight_kg": 300, "liquor_ratio": 7})
    resolved_steps, resolved_items = resolve_program_steps_for_batch(steps, formula_map, ctx_poly)

    assert resolved_steps[0]["functions"][0]["params"][1] == 2100.0
    assert resolved_steps[1]["functions"][0]["params"] == [130.0, 2.0, 45.0]
    assert resolved_steps[1]["summary_temp"] == 130.0
    assert resolved_steps[1]["summary_time_min"] == 45.0
    assert len(resolved_items) == 4


def test_all_templates_validate_cleanly():
    for tmpl in FORMULA_TEMPLATES:
        res = validate_formula_definition(
            tmpl["formula_type"],
            tmpl["output_mode"],
            tmpl["definition"],
            tmpl.get("outputs"),
        )
        assert res["error"] is None


def test_machine_config_variables_in_formula():
    ctx_donpro = build_batch_context(
        {"fabric_weight_kg": 400, "liquor_ratio": 10},
        machine_no="DONPRO",
    )
    assert ctx_donpro["machine_capacity_kg"] == 600.0
    assert ctx_donpro["machine_min_load_kg"] == 150.0
    assert ctx_donpro["machine_max_fill_l"] == 6600.0
    assert ctx_donpro["machine_max_temp_c"] == 135.0
    assert ctx_donpro["machine_dt1_max_l"] == 450.0
    assert ctx_donpro["machine_st1_max_l"] == 3000.0

    # Clamp volume air terhadap batas min/max dari MACHCONF mesin
    f_clamp = {
        "formula_type": "MATH",
        "output_mode": "SINGLE",
        "definition": {"expression": "clamp(fabric_weight_kg * liquor_ratio, machine_min_fill_l, machine_max_fill_l)"},
        "decimal_places": 0,
    }
    res_donpro = evaluate_formula(f_clamp, ctx_donpro)
    assert res_donpro["value"] == 4000.0

    # Untuk mesin kecil (DA01: max_fill_l=250), otomatis terpotong ke 250 L
    ctx_da01 = build_batch_context(
        {"fabric_weight_kg": 25, "liquor_ratio": 15},
        machine_no="DA01",
    )
    assert ctx_da01["machine_capacity_kg"] == 30.0
    assert ctx_da01["machine_max_fill_l"] == 250.0
    res_da01 = evaluate_formula(f_clamp, ctx_da01)
    assert res_da01["value"] == 250.0

    # IF_ELSE membandingkan variabel batch terhadap parameter config mesin & mengembalikan parameter config mesin
    f_if_mc = {
        "formula_type": "IF_ELSE",
        "output_mode": "SINGLE",
        "definition": {
            "rules": [
                {
                    "label": "Melebihi batas air mesin",
                    "logic": "AND",
                    "conditions": [{"var": "total_water_l", "op": ">", "value": "machine_max_fill_l"}],
                    "result_expr": "machine_max_fill_l",
                }
            ],
            "else_expr": "total_water_l",
        },
        "decimal_places": 0,
    }
    assert evaluate_formula(f_if_mc, ctx_da01)["value"] == 250.0
    assert evaluate_formula(f_if_mc, ctx_donpro)["value"] == 4000.0

    # Dynamic MACHCONF.CNF parameters (Cat 20 mc_p*, Cat 19 mc_t*, Cat 31 mc_s*)
    from open_orgatex.backend.services.formula_engine import load_machine_config_catalog
    cat_donpro = load_machine_config_catalog("DONPRO")
    assert len(cat_donpro) >= 150
    assert ctx_donpro["mc_p24"] == 45.0   # level mid, MT
    assert ctx_donpro["mc_t7"] == 15.0    # Heat pre-drain time
    f_dyn = {
        "formula_type": "MATH",
        "output_mode": "SINGLE",
        "definition": {"expression": "mc_p24 + mc_t7"},
        "decimal_places": 0,
    }
    assert evaluate_formula(f_dyn, ctx_donpro)["value"] == 60.0

