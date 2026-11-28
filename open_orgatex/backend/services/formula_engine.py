"""
OpenOrgaTEX Safe Parameter Formula Engine
Evaluates dynamic step-parameter formulas from batch inputs without using Python eval().

Supports 4 formula types:
  - MATH: Direct mathematical expression using batch numeric variables
  - IF_ELSE: Ordered IF / ELSE IF / ELSE rules with AND/OR multi-conditions
  - RANGE_TABLE: Excel-like numeric range brackets (min..max -> value/expression)
  - LOOKUP_TABLE: Category/text keyword mapping (fabric type, shade, article, etc.)

Supports 2 output modes:
  - SINGLE: Evaluates to a single numeric parameter value
  - MULTI: Evaluates multiple named parameter outputs at once (e.g., Temp + Gradient + Hold)
"""

import ast
import copy
import json
import math
from typing import Any, Dict, List, Optional, Tuple


class FormulaEvaluationError(ValueError):
    """Raised when a formula expression or structure is invalid or unsafe."""


# =============================================================================
# 1. CATALOG OF BATCH INPUT VARIABLES (Single Source of Truth for Backend & UI)
# =============================================================================

FABRIC_TYPE_OPTIONS = [
    "COTTON", "POLYESTER", "TC", "CVC", "RAYON", "SPANDEX", "NYLON", "T/R", "LINEN", "WOOL"
]

COLOR_SHADE_OPTIONS = [
    "PUTIH", "MUDA", "SEDANG", "TUA", "HITAM"
]

DYE_TYPE_OPTIONS = [
    "REACTIVE", "DISPERSE", "DOUBLE", "DIRECT", "ACID", "VAT"
]

REDYE_OPTIONS = [
    {"value": "0", "label": "Normal (0)"},
    {"value": "1", "label": "Redye / Celup Ulang (1)"}
]

BATCH_VARIABLES_CATALOG: List[Dict[str, Any]] = [
    # Numeric / Physical
    {
        "key": "fabric_weight_kg",
        "label": "Berat Kain",
        "type": "number",
        "unit": "kg",
        "group": "Fisik & Kapasitas",
        "sample": 350.0,
        "description": "Berat kain yang dicelup dalam kilogram"
    },
    {
        "key": "liquor_ratio",
        "label": "Liquor Ratio",
        "type": "number",
        "unit": "1:x",
        "group": "Fisik & Kapasitas",
        "sample": 8.0,
        "description": "Perbandingan air terhadap berat kain"
    },
    {
        "key": "total_water_l",
        "label": "Total Air (Otomatis)",
        "type": "number",
        "unit": "L",
        "group": "Fisik & Kapasitas",
        "sample": 2800.0,
        "description": "Otomatis dihitung: Berat Kain × Liquor Ratio"
    },
    {
        "key": "fabric_length",
        "label": "Panjang Kain",
        "type": "number",
        "unit": "m",
        "group": "Fisik & Kapasitas",
        "sample": 200.0,
        "description": "Panjang total kain dalam meter"
    },
    {
        "key": "fabric_gsm",
        "label": "Gramasi Kain (GSM)",
        "type": "number",
        "unit": "g/m²",
        "group": "Fisik & Kapasitas",
        "sample": 180.0,
        "description": "Ketebalan/gramasi kain dalam gram per meter persegi"
    },
    {
        "key": "chamber_count",
        "label": "Jumlah Rope / Chamber",
        "type": "number",
        "unit": "pcs",
        "group": "Fisik & Kapasitas",
        "sample": 2,
        "description": "Jumlah rope atau chamber mesin yang terisi"
    },
    {
        "key": "machine_capacity_kg",
        "label": "Kapasitas Mesin",
        "type": "number",
        "unit": "kg",
        "group": "Fisik & Kapasitas",
        "sample": 350.0,
        "description": "Kapasitas maksimal mesin (otomatis dari Master Mesin)"
    },
    {
        "key": "load_percent",
        "label": "Persen Beban Mesin",
        "type": "number",
        "unit": "%",
        "group": "Fisik & Kapasitas",
        "sample": 100.0,
        "description": "Otomatis dihitung: (Berat Kain ÷ Kapasitas Mesin) × 100"
    },
    # Config Mesin (otomatis dari MACHCONF.CNF / machine_profile.json)
    {
        "key": "machine_min_load_kg",
        "label": "Beban Min Mesin",
        "type": "number",
        "unit": "kg",
        "group": "Config Mesin (MACHCONF)",
        "sample": 150.0,
        "description": "Beban kain minimum mesin dari MACHCONF.CNF"
    },
    {
        "key": "machine_min_fill_l",
        "label": "Air Min Mesin",
        "type": "number",
        "unit": "L",
        "group": "Config Mesin (MACHCONF)",
        "sample": 500.0,
        "description": "Volume pengisian air minimum Main Tank dari MACHCONF.CNF"
    },
    {
        "key": "machine_max_fill_l",
        "label": "Air Maks Mesin",
        "type": "number",
        "unit": "L",
        "group": "Config Mesin (MACHCONF)",
        "sample": 6000.0,
        "description": "Volume pengisian air maksimum Main Tank dari MACHCONF.CNF"
    },
    {
        "key": "machine_max_liquor_ratio",
        "label": "LR Maks Mesin",
        "type": "number",
        "unit": "1:x",
        "group": "Config Mesin (MACHCONF)",
        "sample": 9.0,
        "description": "Batas maksimum Liquor Ratio mesin dari MACHCONF.CNF"
    },
    {
        "key": "machine_max_temp_c",
        "label": "Suhu Maks Mesin",
        "type": "number",
        "unit": "°C",
        "group": "Config Mesin (MACHCONF)",
        "sample": 135.0,
        "description": "Batas suhu maksimum mesin dari MACHCONF.CNF"
    },
    {
        "key": "machine_winch_max_speed",
        "label": "Winch Maks Mesin",
        "type": "number",
        "unit": "m/min",
        "group": "Config Mesin (MACHCONF)",
        "sample": 350.0,
        "description": "Kecepatan winch maksimum mesin dari MACHCONF.CNF"
    },
    {
        "key": "machine_max_pressure_bar",
        "label": "Tekanan Maks Mesin",
        "type": "number",
        "unit": "bar",
        "group": "Config Mesin (MACHCONF)",
        "sample": 3.0,
        "description": "Batas tekanan diferensial maksimum mesin dari MACHCONF.CNF"
    },
    {
        "key": "machine_seam_count",
        "label": "Jumlah Tube / Seam",
        "type": "number",
        "unit": "pcs",
        "group": "Config Mesin (MACHCONF)",
        "sample": 2,
        "description": "Jumlah seam / tube kain mesin dari MACHCONF.CNF"
    },
    {
        "key": "machine_dt1_max_l",
        "label": "Kapasitas DT1",
        "type": "number",
        "unit": "L",
        "group": "Config Mesin (MACHCONF)",
        "sample": 450.0,
        "description": "Kapasitas maksimum Addition Tank 1 (DT1) dari MACHCONF.CNF"
    },
    {
        "key": "machine_dt2_max_l",
        "label": "Kapasitas DT2",
        "type": "number",
        "unit": "L",
        "group": "Config Mesin (MACHCONF)",
        "sample": 450.0,
        "description": "Kapasitas maksimum Addition Tank 2 (DT2) dari MACHCONF.CNF"
    },
    {
        "key": "machine_st1_max_l",
        "label": "Kapasitas Stock Tank",
        "type": "number",
        "unit": "L",
        "group": "Config Mesin (MACHCONF)",
        "sample": 3000.0,
        "description": "Kapasitas maksimum Stock Tank (ST1) dari MACHCONF.CNF"
    },
    {
        "key": "machine_tanks_count",
        "label": "Jumlah Tangki Mesin",
        "type": "number",
        "unit": "pcs",
        "group": "Config Mesin (MACHCONF)",
        "sample": 3,
        "description": "Total tangki tambahan (DT + ST) mesin dari MACHCONF.CNF"
    },
    # Categorical / Text
    {
        "key": "fabric_type",
        "label": "Jenis Kain / Serat",
        "type": "select",
        "unit": "",
        "group": "Kain, Warna & Proses",
        "sample": "COTTON",
        "options": FABRIC_TYPE_OPTIONS,
        "description": "Jenis serat kain utama (Cotton, Polyester, TC, CVC, Rayon, dll.)"
    },
    {
        "key": "color_shade",
        "label": "Kedalaman Warna (Shade)",
        "type": "select",
        "unit": "",
        "group": "Kain, Warna & Proses",
        "sample": "TUA",
        "options": COLOR_SHADE_OPTIONS,
        "description": "Tingkat kepekatan warna (Putih, Muda, Sedang, Tua, Hitam)"
    },
    {
        "key": "dye_type",
        "label": "Jenis Zat Warna",
        "type": "select",
        "unit": "",
        "group": "Kain, Warna & Proses",
        "sample": "REACTIVE",
        "options": DYE_TYPE_OPTIONS,
        "description": "Golongan zat warna yang digunakan (Reactive, Disperse, Double, dll.)"
    },
    {
        "key": "redye",
        "label": "Status Redye (Celup Ulang)",
        "type": "select",
        "unit": "",
        "group": "Kain, Warna & Proses",
        "sample": "0",
        "options": ["0", "1"],
        "option_labels": {"0": "Normal (0)", "1": "Redye / Celup Ulang (1)"},
        "description": "0 = Proses normal, 1 = Celup ulang / perbaikan warna"
    },
    {
        "key": "article",
        "label": "Artikel Kain",
        "type": "text",
        "unit": "",
        "group": "Kain, Warna & Proses",
        "sample": "CM 30S RIB 100% Cotton",
        "description": "Kode atau deskripsi artikel kain"
    },
    {
        "key": "color_name",
        "label": "Nama Warna",
        "type": "text",
        "unit": "",
        "group": "Kain, Warna & Proses",
        "sample": "UNGU TUA",
        "description": "Nama warna pada order produksi"
    },
    {
        "key": "color_code",
        "label": "Kode Warna",
        "type": "text",
        "unit": "",
        "group": "Kain, Warna & Proses",
        "sample": "1650159",
        "description": "Kode referensi warna"
    },
    {
        "key": "customer",
        "label": "Customer",
        "type": "text",
        "unit": "",
        "group": "Kain, Warna & Proses",
        "sample": "PT. SMM JETFLOW",
        "description": "Nama pelanggan / buyer"
    },
]

NUMERIC_VARIABLE_KEYS = {v["key"] for v in BATCH_VARIABLES_CATALOG if v["type"] == "number"}
ALL_VARIABLE_KEYS = {v["key"] for v in BATCH_VARIABLES_CATALOG}


# =============================================================================
# 2. READY-TO-USE TEXTILE DYEING FORMULA TEMPLATES
# =============================================================================

FORMULA_TEMPLATES: List[Dict[str, Any]] = [
    {
        "code": "FX-AIR-AUTO",
        "name": "Volume Air Otomatis (Berat × LR)",
        "description": "Menghitung volume air pengisian otomatis berdasarkan Berat Kain × Liquor Ratio dengan batas minimum 500 L.",
        "formula_type": "MATH",
        "output_mode": "SINGLE",
        "target_function_id": 713,
        "target_function_name": "Fill Level",
        "unit": "L",
        "decimal_places": 0,
        "min_value": 300,
        "max_value": 10000,
        "default_fallback": 2500,
        "outputs": [
            {"key": "value", "label": "Volume Air", "unit": "L", "decimal_places": 0, "min_value": 300, "max_value": 10000, "default_fallback": 2500, "default_param_slot": 2}
        ],
        "definition": {
            "expression": "max(fabric_weight_kg * liquor_ratio, 500)"
        }
    },
    {
        "code": "FX-SUHU-KAIN",
        "name": "Target Suhu Berdasarkan Jenis Kain",
        "description": "Memetakan Jenis Kain langsung ke suhu celup standar (Polyester 130°C, TC/CVC 115°C, Cotton 60°C, Rayon 50°C).",
        "formula_type": "LOOKUP_TABLE",
        "output_mode": "SINGLE",
        "target_function_id": 141,
        "target_function_name": "Temperature Control",
        "unit": "°C",
        "decimal_places": 1,
        "min_value": 20,
        "max_value": 140,
        "default_fallback": 60,
        "outputs": [
            {"key": "value", "label": "Target Suhu", "unit": "°C", "decimal_places": 1, "min_value": 20, "max_value": 140, "default_fallback": 60, "default_param_slot": 1}
        ],
        "definition": {
            "input_var": "fabric_type",
            "match_mode": "contains",
            "rows": [
                {"match_values": "POLYESTER, PES", "match_mode": "contains", "result_expr": "130", "label": "Polyester HT"},
                {"match_values": "TC, CVC, T/R", "match_mode": "contains", "result_expr": "115", "label": "Campuran TC / CVC"},
                {"match_values": "COTTON, CM", "match_mode": "contains", "result_expr": "60", "label": "Cotton Reaktif"},
                {"match_values": "RAYON, VISCOSE", "match_mode": "contains", "result_expr": "50", "label": "Rayon / Viscose"}
            ],
            "default_expr": "60"
        }
    },
    {
        "code": "FX-HOLD-BERAT",
        "name": "Waktu Hold Berdasarkan Berat Kain",
        "description": "Tabel rentang berat kain (kg) untuk menentukan durasi tahan suhu secara otomatis.",
        "formula_type": "RANGE_TABLE",
        "output_mode": "SINGLE",
        "target_function_id": 141,
        "target_function_name": "Temperature Control",
        "unit": "min",
        "decimal_places": 0,
        "min_value": 5,
        "max_value": 180,
        "default_fallback": 35,
        "outputs": [
            {"key": "value", "label": "Waktu Hold", "unit": "min", "decimal_places": 0, "min_value": 5, "max_value": 180, "default_fallback": 35, "default_param_slot": 3}
        ],
        "definition": {
            "input_var": "fabric_weight_kg",
            "rows": [
                {"min": 0, "max": 100, "result_expr": "25", "label": "Lot Kecil (≤100 kg)"},
                {"min": 100.01, "max": 250, "result_expr": "35", "label": "Lot Sedang (100–250 kg)"},
                {"min": 250.01, "max": 400, "result_expr": "45", "label": "Lot Besar (250–400 kg)"},
                {"min": 400.01, "max": None, "result_expr": "60", "label": "Lot Extra (>400 kg)"}
            ],
            "default_expr": "35"
        }
    },
    {
        "code": "FX-POMPA-ADAPTIF",
        "name": "Kecepatan Pompa Adaptif (IF–ELSE)",
        "description": "Menyesuaikan kecepatan pompa berdasarkan Persen Beban Mesin, Jenis Kain, dan Status Redye.",
        "formula_type": "IF_ELSE",
        "output_mode": "SINGLE",
        "target_function_id": 404,
        "target_function_name": "Dye Liquor Pump",
        "unit": "%",
        "decimal_places": 0,
        "min_value": 30,
        "max_value": 100,
        "default_fallback": 75,
        "outputs": [
            {"key": "value", "label": "Kecepatan Pompa", "unit": "%", "decimal_places": 0, "min_value": 30, "max_value": 100, "default_fallback": 75, "default_param_slot": 2}
        ],
        "definition": {
            "rules": [
                {
                    "label": "Beban tinggi (>85%) untuk kain tebal",
                    "logic": "AND",
                    "conditions": [
                        {"var": "load_percent", "op": ">", "value": 85},
                        {"var": "fabric_gsm", "op": ">=", "value": 200}
                    ],
                    "result_expr": "90"
                },
                {
                    "label": "Kain halus (Rayon / Spandex)",
                    "logic": "OR",
                    "conditions": [
                        {"var": "fabric_type", "op": "contains", "value": "RAYON"},
                        {"var": "fabric_type", "op": "contains", "value": "SPANDEX"}
                    ],
                    "result_expr": "65"
                },
                {
                    "label": "Beban rendah (<50%)",
                    "logic": "AND",
                    "conditions": [
                        {"var": "load_percent", "op": "<", "value": 50}
                    ],
                    "result_expr": "70"
                }
            ],
            "else_expr": "80"
        }
    },
    {
        "code": "FX-PAKET-TEMP",
        "name": "Paket Lengkap Temperature Control (Suhu + Gradient + Hold)",
        "description": "1 Formula mengisi 3 parameter F141 sekaligus (P1 Suhu, P2 Gradient, P3 Hold Time) berdasarkan Jenis Kain.",
        "formula_type": "LOOKUP_TABLE",
        "output_mode": "MULTI",
        "target_function_id": 141,
        "target_function_name": "Temperature Control",
        "unit": "",
        "decimal_places": 1,
        "default_fallback": 60,
        "outputs": [
            {"key": "suhu", "label": "Target Suhu", "unit": "°C", "decimal_places": 1, "min_value": 20, "max_value": 140, "default_fallback": 60, "default_param_slot": 1},
            {"key": "gradient", "label": "Gradient", "unit": "°C/min", "decimal_places": 1, "min_value": 0.5, "max_value": 5.0, "default_fallback": 1.5, "default_param_slot": 2},
            {"key": "hold", "label": "Hold Time", "unit": "min", "decimal_places": 0, "min_value": 5, "max_value": 180, "default_fallback": 45, "default_param_slot": 3}
        ],
        "definition": {
            "input_var": "fabric_type",
            "match_mode": "contains",
            "rows": [
                {
                    "match_values": "POLYESTER, PES",
                    "match_mode": "contains",
                    "label": "Polyester HT 130°C",
                    "outputs": {"suhu": "130", "gradient": "2.0", "hold": "45"}
                },
                {
                    "match_values": "COTTON, CM",
                    "match_mode": "contains",
                    "label": "Cotton Reaktif 60°C",
                    "outputs": {"suhu": "60", "gradient": "1.5", "hold": "round(fabric_weight_kg * 0.08 + 25, 0)"}
                },
                {
                    "match_values": "RAYON, VISCOSE",
                    "match_mode": "contains",
                    "label": "Rayon Soft 50°C",
                    "outputs": {"suhu": "50", "gradient": "1.0", "hold": "30"}
                }
            ],
            "default_outputs": {"suhu": "60", "gradient": "1.5", "hold": "40"}
        }
    }
]


# =============================================================================
# 3. SAFE AST MATHEMATICAL EXPRESSION EVALUATOR (NO Python eval!)
# =============================================================================

def _fn_clamp(val: float, lo: float, hi: float) -> float:
    return max(float(lo), min(float(hi), float(val)))


SAFE_MATH_FUNCTIONS = {
    "round": lambda x, n=0: round(float(x), int(n)),
    "ceil": lambda x: float(math.ceil(float(x))),
    "floor": lambda x: float(math.floor(float(x))),
    "min": lambda *args: float(min(args)),
    "max": lambda *args: float(max(args)),
    "abs": lambda x: float(abs(float(x))),
    "clamp": _fn_clamp,
}

SAFE_BIN_OPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: _safe_div(a, b),
    ast.Mod: lambda a, b: _safe_mod(a, b),
}

SAFE_UNARY_OPS = {
    ast.UAdd: lambda a: +a,
    ast.USub: lambda a: -a,
}


def _safe_div(a: float, b: float) -> float:
    if b == 0:
        raise FormulaEvaluationError("Pembagian dengan nol (0) tidak diperbolehkan.")
    return a / b


def _safe_mod(a: float, b: float) -> float:
    if b == 0:
        raise FormulaEvaluationError("Modulo dengan nol (0) tidak diperbolehkan.")
    return a % b


def _eval_ast_node(node: ast.AST, numeric_vars: Dict[str, float], depth: int = 0) -> float:
    if depth > 40:
        raise FormulaEvaluationError("Rumus terlalu dalam/kompleks.")

    if isinstance(node, ast.Expression):
        return _eval_ast_node(node.body, numeric_vars, depth + 1)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return float(node.value)
        raise FormulaEvaluationError(f"Konstanta tidak valid dalam rumus matematika: {node.value!r}")

    if isinstance(node, ast.Name):
        if node.id in numeric_vars:
            return float(numeric_vars[node.id])
        # Allow dynamic MACHCONF keys (mc_p<id>, mc_t<id>, mc_s<id>) to default to 0.0 during machine-agnostic validation
        if len(node.id) >= 5 and node.id[:4] in ("mc_p", "mc_t", "mc_s") and node.id[4:].isdigit():
            return 0.0
        raise FormulaEvaluationError(f"Variabel tidak dikenal dalam rumus: '{node.id}'")

    if isinstance(node, ast.BinOp):
        op_fn = SAFE_BIN_OPS.get(type(node.op))
        if not op_fn:
            raise FormulaEvaluationError(f"Operator tidak didukung: {type(node.op).__name__}")
        left = _eval_ast_node(node.left, numeric_vars, depth + 1)
        right = _eval_ast_node(node.right, numeric_vars, depth + 1)
        return float(op_fn(left, right))

    if isinstance(node, ast.UnaryOp):
        op_fn = SAFE_UNARY_OPS.get(type(node.op))
        if not op_fn:
            raise FormulaEvaluationError(f"Operator unary tidak didukung: {type(node.op).__name__}")
        return float(op_fn(_eval_ast_node(node.operand, numeric_vars, depth + 1)))

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise FormulaEvaluationError("Pemanggilan fungsi tidak valid.")
        fn_name = node.func.id
        if fn_name not in SAFE_MATH_FUNCTIONS:
            raise FormulaEvaluationError(
                f"Fungsi '{fn_name}' tidak diizinkan. Gunakan: {', '.join(sorted(SAFE_MATH_FUNCTIONS.keys()))}."
            )
        if node.keywords:
            raise FormulaEvaluationError("Argumen keyword tidak didukung pada fungsi matematika.")
        args = [_eval_ast_node(arg, numeric_vars, depth + 1) for arg in node.args]
        if not args:
            raise FormulaEvaluationError(f"Fungsi '{fn_name}' memerlukan minimal 1 argumen.")
        try:
            return float(SAFE_MATH_FUNCTIONS[fn_name](*args))
        except Exception as exc:
            raise FormulaEvaluationError(f"Error menjalankan {fn_name}(): {exc}")

    raise FormulaEvaluationError(f"Sintaks ekspresi tidak diizinkan: {type(node).__name__}")


def safe_eval_math(expr: Any, context: Dict[str, Any]) -> float:
    """Safely evaluates a numeric literal or math expression against batch context."""
    if expr is None:
        return 0.0
    if isinstance(expr, (int, float)) and not isinstance(expr, bool):
        return float(expr)

    text_expr = str(expr).strip()
    if not text_expr:
        return 0.0
    if len(text_expr) > 500:
        raise FormulaEvaluationError("Panjang ekspresi matematika melebihi batas (500 karakter).")

    # Normalize friendly UI symbols (× -> *, ÷ -> /, comma decimal? keep comma for function args!)
    text_expr = text_expr.replace("×", "*").replace("÷", "/")

    # Build numeric variable lookup (also accept numeric strings from context)
    numeric_vars: Dict[str, float] = {}
    for k, v in (context or {}).items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            numeric_vars[k] = float(v)
        elif isinstance(v, str):
            try:
                numeric_vars[k] = float(v)
            except ValueError:
                pass
    # Ensure all standard numeric variables default to 0.0 if missing
    for k in NUMERIC_VARIABLE_KEYS:
        numeric_vars.setdefault(k, 0.0)

    try:
        tree = ast.parse(text_expr, mode="eval")
    except SyntaxError as exc:
        raise FormulaEvaluationError(f"Kesalahan sintaks rumus '{text_expr}': {exc.msg}")

    val = _eval_ast_node(tree, numeric_vars)
    if math.isnan(val) or math.isinf(val):
        raise FormulaEvaluationError("Hasil perhitungan tidak valid (NaN/Infinity).")
    return val


# =============================================================================
# 4. BATCH CONTEXT BUILDER
# =============================================================================

def _to_float(val: Any, default: float = 0.0) -> float:
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _extract_machine_vars_from_profile(prof: Optional[Dict[str, Any]]) -> Dict[str, float]:
    """Maps decoded machine_profile.json fields into formula context `machine_*` numeric variables."""
    if not isinstance(prof, dict):
        return {}
    tanks = prof.get("tanks") if isinstance(prof.get("tanks"), dict) else {}
    dt1 = tanks.get("dt1") if isinstance(tanks.get("dt1"), dict) else {}
    dt2 = tanks.get("dt2") if isinstance(tanks.get("dt2"), dict) else {}
    st1 = tanks.get("stock_tank") if isinstance(tanks.get("stock_tank"), dict) else {}

    raw_map = {
        "machine_capacity_kg": prof.get("capacity_kg"),
        "machine_min_load_kg": prof.get("min_load_kg"),
        "machine_min_fill_l": prof.get("min_fill_l"),
        "machine_max_fill_l": prof.get("max_fill_l"),
        "machine_max_liquor_ratio": prof.get("max_liquor_ratio"),
        "machine_max_temp_c": prof.get("max_temp_c"),
        "machine_winch_max_speed": prof.get("winch_max_speed"),
        "machine_max_pressure_bar": prof.get("max_diff_pressure_bar"),
        "machine_seam_count": prof.get("seam_quantity"),
        "machine_dt1_max_l": dt1.get("max_fill_l"),
        "machine_dt2_max_l": dt2.get("max_fill_l"),
        "machine_st1_max_l": st1.get("max_fill_l"),
        "machine_tanks_count": prof.get("tanks_count"),
    }
    out: Dict[str, float] = {}
    for k, v in raw_map.items():
        if v is not None and v != "":
            try:
                out[k] = float(v)
            except (TypeError, ValueError):
                pass
    return out


def load_machine_config_vars(machine_no: Optional[str]) -> Dict[str, float]:
    """
    Loads formula `machine_*` summary variables AND all dynamic `MACHCONF.CNF` parameters
    (`mc_p<id>` Cat 20, `mc_t<id>` Cat 19, `mc_s<id>` Cat 31) from
    WORKSPACE_PROGRAM_MESIN/MESIN_<ID>/02_CONFIG_SIAP_PAKAI/.
    """
    if not machine_no:
        return {}
    try:
        import os
        from .machine_config_service import WORKSPACE_BASE, normalize_folder_name
        dec_dir = os.path.join(
            WORKSPACE_BASE,
            normalize_folder_name(str(machine_no)),
            "02_CONFIG_SIAP_PAKAI",
        )
        out: Dict[str, float] = {}
        prof_path = os.path.join(dec_dir, "machine_profile.json")
        if os.path.isfile(prof_path):
            with open(prof_path, "r", encoding="utf-8") as f:
                out.update(_extract_machine_vars_from_profile(json.load(f)))

        mc_path = os.path.join(dec_dir, "machconf_info.json")
        if os.path.isfile(mc_path):
            with open(mc_path, "r", encoding="utf-8") as f:
                mc_info = json.load(f)
            for section, prefix in (
                ("machine_parameters", "mc_p"),
                ("machine_timers", "mc_t"),
                ("system_parameters", "mc_s"),
            ):
                entries = mc_info.get(section) or {}
                if isinstance(entries, dict):
                    for pid_str, meta in entries.items():
                        if isinstance(meta, dict) and meta.get("value") is not None:
                            try:
                                out[f"{prefix}{pid_str}"] = float(meta["value"])
                            except (TypeError, ValueError):
                                pass
        return out
    except Exception:
        return {}


def load_machine_config_catalog(machine_no: Optional[str]) -> List[Dict[str, Any]]:
    """
    Returns full selectable catalog of MACHCONF.CNF parameters (Cat 20, Cat 19, Cat 31)
    for a machine, with exact labels and live values.
    """
    if not machine_no:
        return []
    try:
        import os
        from .machine_config_service import WORKSPACE_BASE, normalize_folder_name
        mc_path = os.path.join(
            WORKSPACE_BASE,
            normalize_folder_name(str(machine_no)),
            "02_CONFIG_SIAP_PAKAI",
            "machconf_info.json",
        )
        if not os.path.isfile(mc_path):
            return []
        with open(mc_path, "r", encoding="utf-8") as f:
            mc_info = json.load(f)

        items: List[Dict[str, Any]] = []
        section_specs = (
            ("machine_parameters", "mc_p", "Machine Parameters (Cat 20)"),
            ("machine_timers", "mc_t", "Timers & Valves (Cat 19)"),
            ("system_parameters", "mc_s", "System Parameters (Cat 31)"),
        )
        for section, prefix, group_label in section_specs:
            entries = mc_info.get(section) or {}
            if not isinstance(entries, dict):
                continue
            for pid_str in sorted(entries.keys(), key=lambda x: int(x) if str(x).isdigit() else 9999):
                meta = entries[pid_str]
                if not isinstance(meta, dict):
                    continue
                name = str(meta.get("name") or "").strip()
                if not name or name.lower() in ("reserved", "not used"):
                    continue
                val = meta.get("value")
                items.append({
                    "key": f"{prefix}{pid_str}",
                    "id": meta.get("id", pid_str),
                    "label": name,
                    "value": val,
                    "group": group_label,
                })
        return items
    except Exception:
        return []


def build_batch_context(
    batch_dict: Dict[str, Any],
    machine_capacity_kg: Optional[float] = None,
    machine_no: Optional[str] = None,
    machine_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Builds a normalized evaluation context from batch inputs and machine config (MACHCONF.CNF)."""
    b = batch_dict or {}
    target_mach = machine_no or b.get("machine_no")
    mc_vars = (
        _extract_machine_vars_from_profile(machine_profile)
        if machine_profile is not None
        else load_machine_config_vars(target_mach)
    )

    def _resolve_machine_var(key: str, fallback: float) -> float:
        if b.get(key) is not None and b.get(key) != "":
            return _to_float(b.get(key), fallback)
        if key in mc_vars:
            return mc_vars[key]
        return fallback

    weight = _to_float(b.get("fabric_weight_kg"), 350.0)
    lr = _to_float(b.get("liquor_ratio"), 8.0)
    total_water = _to_float(b.get("total_water_l"), round(weight * lr, 2))
    if total_water <= 0 and weight > 0 and lr > 0:
        total_water = round(weight * lr, 2)

    if b.get("machine_capacity_kg") is not None and b.get("machine_capacity_kg") != "":
        cap = _to_float(b.get("machine_capacity_kg"), 350.0)
    elif "machine_capacity_kg" in mc_vars:
        cap = mc_vars["machine_capacity_kg"]
    elif machine_capacity_kg is not None:
        cap = _to_float(machine_capacity_kg, 350.0)
    else:
        cap = 350.0

    load_pct = round((weight / cap) * 100.0, 2) if cap > 0 else 100.0

    # Derive fabric_type fallback from article if fabric_type not explicitly set
    raw_fabric_type = str(b.get("fabric_type") or "").strip().upper()
    article_str = str(b.get("article") or "").strip()
    if not raw_fabric_type and article_str:
        art_up = article_str.upper()
        for ft in ("POLYESTER", "COTTON", "RAYON", "SPANDEX", "NYLON", "CVC", "TC", "T/R"):
            if ft in art_up:
                raw_fabric_type = ft
                break

    redye_raw = b.get("redye", 0)
    redye_str = "1" if str(redye_raw).strip().lower() in ("1", "true", "ya", "yes") else "0"

    ctx = {
        "fabric_weight_kg": weight,
        "liquor_ratio": lr,
        "total_water_l": total_water,
        "fabric_length": _to_float(b.get("fabric_length"), 200.0),
        "fabric_gsm": _to_float(b.get("fabric_gsm"), 180.0),
        "chamber_count": _to_float(b.get("chamber_count"), 1.0),
        "machine_capacity_kg": cap,
        "load_percent": load_pct,
        # Machine config summary variables (from MACHCONF.CNF / machine_profile.json)
        "machine_min_load_kg": _resolve_machine_var("machine_min_load_kg", 0.0),
        "machine_min_fill_l": _resolve_machine_var("machine_min_fill_l", 500.0),
        "machine_max_fill_l": _resolve_machine_var("machine_max_fill_l", 6000.0),
        "machine_max_liquor_ratio": _resolve_machine_var("machine_max_liquor_ratio", 9.0),
        "machine_max_temp_c": _resolve_machine_var("machine_max_temp_c", 135.0),
        "machine_winch_max_speed": _resolve_machine_var("machine_winch_max_speed", 350.0),
        "machine_max_pressure_bar": _resolve_machine_var("machine_max_pressure_bar", 3.0),
        "machine_seam_count": _resolve_machine_var("machine_seam_count", 2.0),
        "machine_dt1_max_l": _resolve_machine_var("machine_dt1_max_l", 450.0),
        "machine_dt2_max_l": _resolve_machine_var("machine_dt2_max_l", 450.0),
        "machine_st1_max_l": _resolve_machine_var("machine_st1_max_l", 3000.0),
        "machine_tanks_count": _resolve_machine_var("machine_tanks_count", 2.0),
        # Categorical / Text
        "fabric_type": raw_fabric_type,
        "color_shade": str(b.get("color_shade") or "").strip().upper(),
        "dye_type": str(b.get("dye_type") or "").strip().upper(),
        "redye": redye_str,
        "article": article_str,
        "color_name": str(b.get("color_name") or "").strip(),
        "color_code": str(b.get("color_code") or "").strip(),
        "customer": str(b.get("customer") or "").strip(),
    }
    # Inject all dynamic MACHCONF parameters (mc_p*, mc_t*, mc_s*)
    for k, v in mc_vars.items():
        if k.startswith(("mc_p", "mc_t", "mc_s")) and k not in ctx:
            ctx[k] = v
    for k, v in b.items():
        if isinstance(k, str) and k.startswith(("mc_p", "mc_t", "mc_s")) and v is not None and v != "":
            ctx[k] = _to_float(v, 0.0)
    return ctx


# =============================================================================
# 5. CONDITION & FORMULA EVALUATOR (ALL 4 TYPES × SINGLE/MULTI OUTPUTS)
# =============================================================================

def _eval_condition(cond: Dict[str, Any], context: Dict[str, Any]) -> bool:
    var_key = str(cond.get("var") or "").strip()
    op = str(cond.get("op") or "==").strip().lower()
    target = cond.get("value")
    target2 = cond.get("value2")

    actual = context.get(var_key)
    is_numeric_var = var_key in NUMERIC_VARIABLE_KEYS

    if is_numeric_var or op in (">", ">=", "<", "<=", "between"):
        a_num = _to_float(actual, 0.0)

        def _resolve_num_target(raw_t: Any, default_v: float = 0.0) -> float:
            if raw_t is None or raw_t == "":
                return default_v
            if isinstance(raw_t, (int, float)) and not isinstance(raw_t, bool):
                return float(raw_t)
            s_t = str(raw_t).strip()
            try:
                return float(s_t)
            except ValueError:
                try:
                    return safe_eval_math(s_t, context)
                except Exception:
                    return default_v

        t_num = _resolve_num_target(target, 0.0)
        if op == ">":
            return a_num > t_num
        if op == ">=":
            return a_num >= t_num
        if op == "<":
            return a_num < t_num
        if op == "<=":
            return a_num <= t_num
        if op in ("==", "=", "equals"):
            return abs(a_num - t_num) < 1e-9
        if op in ("!=", "<>", "not_equals"):
            return abs(a_num - t_num) >= 1e-9
        if op == "between":
            t2_num = _resolve_num_target(target2, t_num)
            lo, hi = (t_num, t2_num) if t_num <= t2_num else (t2_num, t_num)
            return lo <= a_num <= hi
        return False

    # Text / Select comparison (case-insensitive)
    a_str = str(actual or "").strip().upper()
    t_str = str(target or "").strip().upper()

    if op in ("==", "=", "equals"):
        return a_str == t_str
    if op in ("!=", "<>", "not_equals"):
        return a_str != t_str
    if op == "contains":
        if not t_str:
            return False
        tokens = [tok.strip() for tok in t_str.split(",") if tok.strip()]
        return any(tok in a_str for tok in tokens)
    if op == "not_contains":
        if not t_str:
            return True
        tokens = [tok.strip() for tok in t_str.split(",") if tok.strip()]
        return all(tok not in a_str for tok in tokens)
    if op == "starts_with":
        return a_str.startswith(t_str) if t_str else False
    if op == "in":
        tokens = [tok.strip() for tok in t_str.split(",") if tok.strip()]
        return a_str in tokens
    return False


def _postprocess_value(
    raw_val: float,
    decimal_places: Optional[int],
    min_val: Optional[float],
    max_val: Optional[float]
) -> Tuple[float, bool]:
    clamped = False
    val = float(raw_val)
    if min_val is not None and val < float(min_val):
        val = float(min_val)
        clamped = True
    if max_val is not None and val > float(max_val):
        val = float(max_val)
        clamped = True
    dp = 1 if decimal_places is None else max(0, min(4, int(decimal_places)))
    val = round(val, dp)
    if dp == 0:
        val = float(int(round(val)))
    return val, clamped


def _normalize_outputs_spec(formula: Dict[str, Any]) -> List[Dict[str, Any]]:
    outputs = formula.get("outputs")
    if isinstance(outputs, str):
        try:
            outputs = json.loads(outputs)
        except Exception:
            outputs = None
    if isinstance(outputs, list) and len(outputs) > 0:
        return outputs
    return [{
        "key": "value",
        "label": formula.get("name") or "Hasil",
        "unit": formula.get("unit") or "",
        "decimal_places": formula.get("decimal_places", 1),
        "min_value": formula.get("min_value"),
        "max_value": formula.get("max_value"),
        "default_fallback": formula.get("default_fallback", 0.0),
        "default_param_slot": 1
    }]


def evaluate_formula(formula: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluates a formula dict against a batch context dict.
    Returns structured result supporting both SINGLE and MULTI output modes.
    """
    f_type = str(formula.get("formula_type") or "MATH").upper()
    out_mode = str(formula.get("output_mode") or "SINGLE").upper()
    outputs_spec = _normalize_outputs_spec(formula)

    definition = formula.get("definition")
    if definition is None and formula.get("definition_json"):
        definition = json.loads(formula["definition_json"])
    if isinstance(definition, str):
        definition = json.loads(definition)
    definition = definition or {}

    matched_idx: Optional[int] = None
    matched_label: str = ""
    expr_map: Dict[str, Any] = {}

    if f_type == "MATH":
        matched_idx = 0
        matched_label = "Rumus Matematika"
        if out_mode == "MULTI":
            expr_map = dict(definition.get("expressions") or {})
        else:
            expr_map = {outputs_spec[0]["key"]: definition.get("expression", "0")}

    elif f_type == "IF_ELSE":
        rules = definition.get("rules") or []
        found = False
        for idx, rule in enumerate(rules):
            conds = rule.get("conditions") or []
            logic = str(rule.get("logic") or "AND").upper()
            if not conds:
                continue
            results = [_eval_condition(c, context) for c in conds]
            passed = all(results) if logic == "AND" else any(results)
            if passed:
                matched_idx = idx
                matched_label = rule.get("label") or f"Kondisi #{idx + 1}"
                if out_mode == "MULTI":
                    expr_map = dict(rule.get("outputs") or {})
                else:
                    expr_map = {outputs_spec[0]["key"]: rule.get("result_expr", "0")}
                found = True
                break
        if not found:
            matched_idx = -1
            matched_label = "Selain Itu (ELSE / Default)"
            if out_mode == "MULTI":
                expr_map = dict(definition.get("else_outputs") or {})
            else:
                expr_map = {outputs_spec[0]["key"]: definition.get("else_expr", "0")}

    elif f_type == "RANGE_TABLE":
        input_var = str(definition.get("input_var") or "fabric_weight_kg").strip()
        actual_num = _to_float(context.get(input_var), 0.0)
        rows = definition.get("rows") or []
        found = False
        for idx, row in enumerate(rows):
            r_min = row.get("min")
            r_max = row.get("max")
            min_ok = True if (r_min is None or r_min == "") else (actual_num >= _to_float(r_min))
            max_ok = True if (r_max is None or r_max == "") else (actual_num <= _to_float(r_max))
            if min_ok and max_ok:
                matched_idx = idx
                matched_label = row.get("label") or f"Rentang #{idx + 1} ({r_min if r_min is not None else '-∞'}..{r_max if r_max is not None else '∞'})"
                if out_mode == "MULTI":
                    expr_map = dict(row.get("outputs") or {})
                else:
                    expr_map = {outputs_spec[0]["key"]: row.get("result_expr", "0")}
                found = True
                break
        if not found:
            matched_idx = -1
            matched_label = "Di luar rentang (Default)"
            if out_mode == "MULTI":
                expr_map = dict(definition.get("default_outputs") or {})
            else:
                expr_map = {outputs_spec[0]["key"]: definition.get("default_expr", "0")}

    elif f_type == "LOOKUP_TABLE":
        input_var = str(definition.get("input_var") or "fabric_type").strip()
        default_mode = str(definition.get("match_mode") or "contains").lower()
        actual_str = str(context.get(input_var) or "").strip().upper()
        rows = definition.get("rows") or []
        found = False
        for idx, row in enumerate(rows):
            raw_vals = str(row.get("match_values") or "").strip().upper()
            if not raw_vals:
                continue
            tokens = [t.strip() for t in raw_vals.split(",") if t.strip()]
            mode = str(row.get("match_mode") or default_mode).lower()
            if mode == "equals":
                is_match = actual_str in tokens
            else:
                is_match = any(tok in actual_str for tok in tokens)
            if is_match:
                matched_idx = idx
                matched_label = row.get("label") or f"Cocok '{row.get('match_values')}'"
                if out_mode == "MULTI":
                    expr_map = dict(row.get("outputs") or {})
                else:
                    expr_map = {outputs_spec[0]["key"]: row.get("result_expr", "0")}
                found = True
                break
        if not found:
            matched_idx = -1
            matched_label = "Lainnya (Default)"
            if out_mode == "MULTI":
                expr_map = dict(definition.get("default_outputs") or {})
            else:
                expr_map = {outputs_spec[0]["key"]: definition.get("default_expr", "0")}
    else:
        raise FormulaEvaluationError(f"Tipe formula tidak dikenal: '{f_type}'")

    # Evaluate every output slot safely
    evaluated_values: Dict[str, Dict[str, Any]] = {}
    any_clamped = False
    for spec in outputs_spec:
        o_key = spec["key"]
        expr = expr_map.get(o_key)
        if expr is None or str(expr).strip() == "":
            raw_v = _to_float(spec.get("default_fallback"), _to_float(formula.get("default_fallback"), 0.0))
        else:
            raw_v = safe_eval_math(expr, context)

        dp = spec.get("decimal_places", formula.get("decimal_places", 1))
        mn = spec.get("min_value", formula.get("min_value") if out_mode == "SINGLE" else None)
        mx = spec.get("max_value", formula.get("max_value") if out_mode == "SINGLE" else None)
        final_v, was_clamped = _postprocess_value(raw_v, dp, mn, mx)
        if was_clamped:
            any_clamped = True

        evaluated_values[o_key] = {
            "key": o_key,
            "label": spec.get("label") or o_key,
            "unit": spec.get("unit") or (formula.get("unit") if out_mode == "SINGLE" else ""),
            "raw_value": round(raw_v, 4),
            "value": final_v,
            "clamped": was_clamped,
            "expression": str(expr if expr is not None else ""),
            "default_param_slot": spec.get("default_param_slot")
        }

    first_key = outputs_spec[0]["key"]
    primary_val = evaluated_values[first_key]["value"]

    return {
        "output_mode": out_mode,
        "value": primary_val,
        "values": evaluated_values,
        "matched_rule_index": matched_idx,
        "matched_label": matched_label,
        "clamped": any_clamped,
        "error": None
    }


def validate_formula_definition(
    formula_type: str,
    output_mode: str,
    definition: Dict[str, Any],
    outputs: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """Validates a formula definition by running a dry-run evaluation against sample batch data."""
    sample_ctx = build_batch_context({v["key"]: v["sample"] for v in BATCH_VARIABLES_CATALOG})
    dummy = {
        "formula_type": formula_type,
        "output_mode": output_mode,
        "definition": definition,
        "outputs": outputs,
        "decimal_places": 1,
        "default_fallback": 0.0,
    }
    # Also validate every branch's expressions so syntax errors in non-matching branches are caught!
    f_type = str(formula_type or "MATH").upper()
    out_mode = str(output_mode or "SINGLE").upper()

    exprs_to_check: List[Any] = []
    if f_type == "MATH":
        if out_mode == "MULTI":
            exprs_to_check.extend((definition.get("expressions") or {}).values())
        else:
            exprs_to_check.append(definition.get("expression", "0"))
    elif f_type == "IF_ELSE":
        for r in (definition.get("rules") or []):
            if out_mode == "MULTI":
                exprs_to_check.extend((r.get("outputs") or {}).values())
            else:
                exprs_to_check.append(r.get("result_expr", "0"))
        if out_mode == "MULTI":
            exprs_to_check.extend((definition.get("else_outputs") or {}).values())
        else:
            exprs_to_check.append(definition.get("else_expr", "0"))
    elif f_type in ("RANGE_TABLE", "LOOKUP_TABLE"):
        for r in (definition.get("rows") or []):
            if out_mode == "MULTI":
                exprs_to_check.extend((r.get("outputs") or {}).values())
            else:
                exprs_to_check.append(r.get("result_expr", "0"))
        if out_mode == "MULTI":
            exprs_to_check.extend((definition.get("default_outputs") or {}).values())
        else:
            exprs_to_check.append(definition.get("default_expr", "0"))
    else:
        raise FormulaEvaluationError(f"Tipe formula tidak valid: '{f_type}'")

    for expr in exprs_to_check:
        if expr is not None and str(expr).strip() != "":
            safe_eval_math(expr, sample_ctx)

    return evaluate_formula(dummy, sample_ctx)


# =============================================================================
# 6. PROGRAM STEP RESOLUTION FOR BATCH COMPILATION
# =============================================================================

def resolve_program_steps_for_batch(
    steps: List[Dict[str, Any]],
    formula_map: Dict[int, Dict[str, Any]],
    context: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Returns (resolved_steps, resolved_items).
    Each StepFunction may contain `param_formulas`:
      { "0": 12, "1": {"formula_id": 15, "output_key": "gradient"} }
    """
    resolved_steps = copy.deepcopy(steps or [])
    resolved_items: List[Dict[str, Any]] = []
    eval_cache: Dict[int, Dict[str, Any]] = {}

    for step in resolved_steps:
        step_no = step.get("step_no")
        step_label = step.get("label") or ""
        for fn in step.get("functions") or []:
            pf_map = fn.get("param_formulas") or {}
            if not pf_map:
                continue
            params = list(fn.get("params") or [])
            for p_idx_str, binding in pf_map.items():
                if binding is None:
                    continue
                try:
                    p_idx = int(p_idx_str)
                except (TypeError, ValueError):
                    continue

                if isinstance(binding, dict):
                    f_id = binding.get("formula_id")
                    out_key = binding.get("output_key")
                else:
                    f_id = binding
                    out_key = None

                if not f_id:
                    continue
                f_id_int = int(f_id)
                formula_dict = formula_map.get(f_id_int)
                if not formula_dict:
                    continue

                if f_id_int not in eval_cache:
                    try:
                        eval_cache[f_id_int] = evaluate_formula(formula_dict, context)
                    except Exception as exc:
                        eval_cache[f_id_int] = {
                            "value": _to_float(formula_dict.get("default_fallback"), 0.0),
                            "values": {},
                            "matched_label": f"Fallback (Error: {exc})",
                            "clamped": False,
                            "error": str(exc)
                        }

                res = eval_cache[f_id_int]
                values_dict = res.get("values") or {}
                if out_key and out_key in values_dict:
                    slot_res = values_dict[out_key]
                    computed_val = slot_res["value"]
                    out_label = slot_res.get("label") or out_key
                    out_unit = slot_res.get("unit") or ""
                    was_clamped = slot_res.get("clamped", False)
                else:
                    computed_val = res.get("value", 0.0)
                    first_slot = next(iter(values_dict.values()), {})
                    out_label = first_slot.get("label") or formula_dict.get("name") or ""
                    out_unit = first_slot.get("unit") or formula_dict.get("unit") or ""
                    was_clamped = res.get("clamped", False)

                while len(params) <= p_idx:
                    params.append(0.0)
                old_val = params[p_idx]
                params[p_idx] = float(computed_val)

                resolved_items.append({
                    "step_no": step_no,
                    "step_label": step_label,
                    "function_id": fn.get("function_id"),
                    "function_name": fn.get("name") or f"F{fn.get('function_id')}",
                    "column": fn.get("column", 1),
                    "param_index": p_idx,
                    "param_slot": p_idx + 1,
                    "formula_id": f_id_int,
                    "formula_code": formula_dict.get("code", ""),
                    "formula_name": formula_dict.get("name", ""),
                    "output_key": out_key,
                    "output_label": out_label,
                    "unit": out_unit,
                    "fallback_value": old_val,
                    "computed_value": float(computed_val),
                    "matched_label": res.get("matched_label", ""),
                    "clamped": was_clamped,
                    "error": res.get("error")
                })

            fn["params"] = params

            # Keep step summary synced for main function (column 1)
            if fn.get("column", 1) == 1:
                fid = fn.get("function_id")
                if fid == 141:
                    if len(params) > 0:
                        step["summary_temp"] = params[0]
                    if len(params) > 2:
                        step["summary_time_min"] = params[2]
                elif fid == 713 and len(params) > 1:
                    step["summary_water_l"] = params[1]

    return resolved_steps, resolved_items
