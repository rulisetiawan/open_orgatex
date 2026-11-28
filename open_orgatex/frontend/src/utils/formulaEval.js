/**
 * Client-side Safe Formula Evaluator (No eval / No new Function)
 * Mirrors backend `formula_engine.py` for 0ms real-time simulator & batch preview.
 */

export const FABRIC_TYPE_OPTIONS = [
  'COTTON', 'POLYESTER', 'TC', 'CVC', 'RAYON', 'SPANDEX', 'NYLON', 'T/R', 'LINEN', 'WOOL'
];

export const COLOR_SHADE_OPTIONS = [
  'PUTIH', 'MUDA', 'SEDANG', 'TUA', 'HITAM'
];

export const DYE_TYPE_OPTIONS = [
  'REACTIVE', 'DISPERSE', 'DOUBLE', 'DIRECT', 'ACID', 'VAT'
];

export const DEFAULT_BATCH_VARIABLES = [
  { key: 'fabric_weight_kg', label: 'Berat Kain', type: 'number', unit: 'kg', group: 'Fisik & Kapasitas', sample: 350 },
  { key: 'liquor_ratio', label: 'Liquor Ratio', type: 'number', unit: '1:x', group: 'Fisik & Kapasitas', sample: 8 },
  { key: 'total_water_l', label: 'Total Air (Otomatis)', type: 'number', unit: 'L', group: 'Fisik & Kapasitas', sample: 2800 },
  { key: 'fabric_length', label: 'Panjang Kain', type: 'number', unit: 'm', group: 'Fisik & Kapasitas', sample: 200 },
  { key: 'fabric_gsm', label: 'Gramasi Kain (GSM)', type: 'number', unit: 'g/m²', group: 'Fisik & Kapasitas', sample: 180 },
  { key: 'chamber_count', label: 'Jumlah Rope / Chamber', type: 'number', unit: 'pcs', group: 'Fisik & Kapasitas', sample: 2 },
  { key: 'machine_capacity_kg', label: 'Kapasitas Mesin', type: 'number', unit: 'kg', group: 'Config Mesin (MACHCONF)', sample: 350 },
  { key: 'load_percent', label: 'Persen Beban Mesin', type: 'number', unit: '%', group: 'Fisik & Kapasitas', sample: 100 },
  { key: 'machine_min_load_kg', label: 'Beban Min Mesin', type: 'number', unit: 'kg', group: 'Config Mesin (MACHCONF)', sample: 150 },
  { key: 'machine_min_fill_l', label: 'Air Min Mesin', type: 'number', unit: 'L', group: 'Config Mesin (MACHCONF)', sample: 500 },
  { key: 'machine_max_fill_l', label: 'Air Maks Mesin', type: 'number', unit: 'L', group: 'Config Mesin (MACHCONF)', sample: 6000 },
  { key: 'machine_max_liquor_ratio', label: 'LR Maks Mesin', type: 'number', unit: '1:x', group: 'Config Mesin (MACHCONF)', sample: 9 },
  { key: 'machine_max_temp_c', label: 'Suhu Maks Mesin', type: 'number', unit: '°C', group: 'Config Mesin (MACHCONF)', sample: 135 },
  { key: 'machine_winch_max_speed', label: 'Winch Maks Mesin', type: 'number', unit: 'm/min', group: 'Config Mesin (MACHCONF)', sample: 350 },
  { key: 'machine_max_pressure_bar', label: 'Tekanan Maks Mesin', type: 'number', unit: 'bar', group: 'Config Mesin (MACHCONF)', sample: 3 },
  { key: 'machine_seam_count', label: 'Jumlah Tube / Seam', type: 'number', unit: 'pcs', group: 'Config Mesin (MACHCONF)', sample: 2 },
  { key: 'machine_dt1_max_l', label: 'Kapasitas DT1', type: 'number', unit: 'L', group: 'Config Mesin (MACHCONF)', sample: 450 },
  { key: 'machine_dt2_max_l', label: 'Kapasitas DT2', type: 'number', unit: 'L', group: 'Config Mesin (MACHCONF)', sample: 450 },
  { key: 'machine_st1_max_l', label: 'Kapasitas Stock Tank', type: 'number', unit: 'L', group: 'Config Mesin (MACHCONF)', sample: 3000 },
  { key: 'machine_tanks_count', label: 'Jumlah Tangki Mesin', type: 'number', unit: 'pcs', group: 'Config Mesin (MACHCONF)', sample: 3 },
  { key: 'fabric_type', label: 'Jenis Kain / Serat', type: 'select', unit: '', group: 'Kain, Warna & Proses', sample: 'COTTON', options: FABRIC_TYPE_OPTIONS },
  { key: 'color_shade', label: 'Kedalaman Warna (Shade)', type: 'select', unit: '', group: 'Kain, Warna & Proses', sample: 'TUA', options: COLOR_SHADE_OPTIONS },
  { key: 'dye_type', label: 'Jenis Zat Warna', type: 'select', unit: '', group: 'Kain, Warna & Proses', sample: 'REACTIVE', options: DYE_TYPE_OPTIONS },
  { key: 'redye', label: 'Status Redye (Celup Ulang)', type: 'select', unit: '', group: 'Kain, Warna & Proses', sample: '0', options: ['0', '1'], option_labels: { '0': 'Normal (0)', '1': 'Redye / Celup Ulang (1)' } },
  { key: 'article', label: 'Artikel Kain', type: 'text', unit: '', group: 'Kain, Warna & Proses', sample: 'CM 30S RIB 100% Cotton' },
  { key: 'color_name', label: 'Nama Warna', type: 'text', unit: '', group: 'Kain, Warna & Proses', sample: 'UNGU TUA' },
  { key: 'color_code', label: 'Kode Warna', type: 'text', unit: '', group: 'Kain, Warna & Proses', sample: '1650159' },
  { key: 'customer', label: 'Customer', type: 'text', unit: '', group: 'Kain, Warna & Proses', sample: 'PT. SMM JETFLOW' },
];

export const NUMERIC_VAR_KEYS = new Set(
  DEFAULT_BATCH_VARIABLES.filter((v) => v.type === 'number').map((v) => v.key)
);

export const NUMERIC_OPERATORS = [
  { value: '>', label: 'Lebih besar dari (>)' },
  { value: '>=', label: 'Lebih besar / sama (≥)' },
  { value: '<', label: 'Lebih kecil dari (<)' },
  { value: '<=', label: 'Lebih kecil / sama (≤)' },
  { value: '==', label: 'Sama dengan (=)' },
  { value: '!=', label: 'Tidak sama (≠)' },
  { value: 'between', label: 'Antara (Min .. Maks)' },
];

export const TEXT_OPERATORS = [
  { value: 'equals', label: 'Sama dengan (=)' },
  { value: 'not_equals', label: 'Tidak sama (≠)' },
  { value: 'contains', label: 'Mengandung kata' },
  { value: 'not_contains', label: 'Tidak mengandung' },
  { value: 'starts_with', label: 'Diawali dengan' },
  { value: 'in', label: 'Salah satu dari (koma)' },
];

const toNum = (v, def = 0) => {
  if (v === null || v === undefined || v === '') return def;
  const n = Number(v);
  return Number.isFinite(n) ? n : def;
};

export function buildBatchContextClient(raw = {}) {
  const weight = toNum(raw.fabric_weight_kg, 350);
  const lr = toNum(raw.liquor_ratio, 8);
  const totalWater = toNum(raw.total_water_l, +(weight * lr).toFixed(2));
  const cap = toNum(raw.machine_capacity_kg, 350);
  const loadPct = cap > 0 ? +((weight / cap) * 100).toFixed(2) : 100;

  let fabricType = String(raw.fabric_type || '').trim().toUpperCase();
  const article = String(raw.article || '').trim();
  if (!fabricType && article) {
    const up = article.toUpperCase();
    for (const ft of ['POLYESTER', 'COTTON', 'RAYON', 'SPANDEX', 'NYLON', 'CVC', 'TC', 'T/R']) {
      if (up.includes(ft)) {
        fabricType = ft;
        break;
      }
    }
  }

  const redyeRaw = String(raw.redye ?? '0').trim().toLowerCase();
  const redye = ['1', 'true', 'ya', 'yes'].includes(redyeRaw) ? '1' : '0';

  const ctx = {
    fabric_weight_kg: weight,
    liquor_ratio: lr,
    total_water_l: totalWater > 0 ? totalWater : +(weight * lr).toFixed(2),
    fabric_length: toNum(raw.fabric_length, 200),
    fabric_gsm: toNum(raw.fabric_gsm, 180),
    chamber_count: toNum(raw.chamber_count, 1),
    machine_capacity_kg: cap,
    load_percent: loadPct,
    machine_min_load_kg: toNum(raw.machine_min_load_kg, 150),
    machine_min_fill_l: toNum(raw.machine_min_fill_l, 500),
    machine_max_fill_l: toNum(raw.machine_max_fill_l, 6000),
    machine_max_liquor_ratio: toNum(raw.machine_max_liquor_ratio, 9),
    machine_max_temp_c: toNum(raw.machine_max_temp_c, 135),
    machine_winch_max_speed: toNum(raw.machine_winch_max_speed, 350),
    machine_max_pressure_bar: toNum(raw.machine_max_pressure_bar, 3),
    machine_seam_count: toNum(raw.machine_seam_count, 2),
    machine_dt1_max_l: toNum(raw.machine_dt1_max_l, 450),
    machine_dt2_max_l: toNum(raw.machine_dt2_max_l, 450),
    machine_st1_max_l: toNum(raw.machine_st1_max_l, 3000),
    machine_tanks_count: toNum(raw.machine_tanks_count, 3),
    fabric_type: fabricType,
    color_shade: String(raw.color_shade || '').trim().toUpperCase(),
    dye_type: String(raw.dye_type || '').trim().toUpperCase(),
    redye,
    article,
    color_name: String(raw.color_name || '').trim(),
    color_code: String(raw.color_code || '').trim(),
    customer: String(raw.customer || '').trim(),
  };
  for (const [k, v] of Object.entries(raw || {})) {
    if (/^mc_[pts]\d+$/.test(k) && v !== '' && v !== null && v !== undefined) {
      ctx[k] = toNum(v, 0);
    }
  }
  return ctx;
}

// =============================================================================
// SAFE RECURSIVE DESCENT MATH PARSER
// =============================================================================

const MATH_FUNCS = {
  round: (x, n = 0) => {
    const factor = Math.pow(10, Math.round(n));
    return Math.round(x * factor) / factor;
  },
  ceil: (x) => Math.ceil(x),
  floor: (x) => Math.floor(x),
  min: (...args) => Math.min(...args),
  max: (...args) => Math.max(...args),
  abs: (x) => Math.abs(x),
  clamp: (x, lo, hi) => Math.max(lo, Math.min(hi, x)),
};

function tokenize(expr) {
  const tokens = [];
  const s = String(expr).replace(/×/g, '*').replace(/÷/g, '/');
  let i = 0;
  while (i < s.length) {
    const ch = s[i];
    if (/\s/.test(ch)) {
      i++;
      continue;
    }
    if (/[0-9.]/.test(ch)) {
      let numStr = '';
      let dots = 0;
      while (i < s.length && /[0-9.]/.test(s[i])) {
        if (s[i] === '.') dots++;
        numStr += s[i++];
      }
      if (dots > 1 || numStr === '.') throw new Error(`Angka tidak valid: '${numStr}'`);
      tokens.push({ type: 'NUM', value: parseFloat(numStr) });
      continue;
    }
    if (/[a-zA-Z_]/.test(ch)) {
      let id = '';
      while (i < s.length && /[a-zA-Z0-9_]/.test(s[i])) {
        id += s[i++];
      }
      tokens.push({ type: 'ID', value: id });
      continue;
    }
    if ('+-*/%(),'.includes(ch)) {
      tokens.push({ type: 'OP', value: ch });
      i++;
      continue;
    }
    throw new Error(`Karakter tidak dikenal: '${ch}'`);
  }
  return tokens;
}

export function safeEvalMathClient(expr, context = {}) {
  if (expr === null || expr === undefined) return 0;
  if (typeof expr === 'number' && Number.isFinite(expr)) return expr;
  const trimmed = String(expr).trim();
  if (!trimmed) return 0;

  const numVars = {};
  for (const [k, v] of Object.entries(context || {})) {
    const n = Number(v);
    if (v !== '' && v !== null && Number.isFinite(n)) numVars[k] = n;
  }
  for (const k of NUMERIC_VAR_KEYS) {
    if (!(k in numVars)) numVars[k] = 0;
  }

  const tokens = tokenize(trimmed);
  let pos = 0;

  const peek = () => tokens[pos];
  const consume = (expected) => {
    const t = tokens[pos];
    if (!t || (expected && t.value !== expected)) {
      throw new Error(`Diharapkan '${expected}', ditemukan '${t ? t.value : 'akhir rumus'}'`);
    }
    pos++;
    return t;
  };

  function parseExpr() {
    let left = parseTerm();
    while (peek() && (peek().value === '+' || peek().value === '-')) {
      const op = consume().value;
      const right = parseTerm();
      left = op === '+' ? left + right : left - right;
    }
    return left;
  }

  function parseTerm() {
    let left = parseUnary();
    while (peek() && (peek().value === '*' || peek().value === '/' || peek().value === '%')) {
      const op = consume().value;
      const right = parseUnary();
      if ((op === '/' || op === '%') && right === 0) {
        throw new Error('Pembagian dengan nol (0) tidak diperbolehkan.');
      }
      if (op === '*') left = left * right;
      else if (op === '/') left = left / right;
      else left = left % right;
    }
    return left;
  }

  function parseUnary() {
    if (peek() && (peek().value === '+' || peek().value === '-')) {
      const op = consume().value;
      const val = parseUnary();
      return op === '-' ? -val : val;
    }
    return parsePrimary();
  }

  function parsePrimary() {
    const t = peek();
    if (!t) throw new Error('Rumus tidak lengkap.');
    if (t.type === 'NUM') {
      consume();
      return t.value;
    }
    if (t.value === '(') {
      consume('(');
      const val = parseExpr();
      consume(')');
      return val;
    }
    if (t.type === 'ID') {
      consume();
      if (peek() && peek().value === '(') {
        const fn = MATH_FUNCS[t.value];
        if (!fn) throw new Error(`Fungsi '${t.value}' tidak dikenal.`);
        consume('(');
        const args = [];
        if (peek() && peek().value !== ')') {
          args.push(parseExpr());
          while (peek() && peek().value === ',') {
            consume(',');
            args.push(parseExpr());
          }
        }
        consume(')');
        if (args.length === 0) throw new Error(`Fungsi '${t.value}()' butuh minimal 1 angka.`);
        return fn(...args);
      }
      if (t.value in numVars) return numVars[t.value];
      if (/^mc_[pts]\d+$/.test(t.value)) return 0;
      throw new Error(`Variabel '${t.value}' tidak dikenal.`);
    }
    throw new Error(`Token tidak terduga: '${t.value}'`);
  }

  const result = parseExpr();
  if (pos < tokens.length) {
    throw new Error(`Sintaks berlebih di '${tokens[pos].value}'`);
  }
  if (!Number.isFinite(result)) {
    throw new Error('Hasil perhitungan tidak valid (NaN/Infinity).');
  }
  return result;
}

// =============================================================================
// FORMULA EVALUATOR (ALL 4 TYPES × SINGLE/MULTI)
// =============================================================================

function evalConditionClient(cond, ctx) {
  const varKey = String(cond.var || '').trim();
  const op = String(cond.op || '==').trim().toLowerCase();
  const actual = ctx[varKey];
  const isNum = NUMERIC_VAR_KEYS.has(varKey) || ['>', '>=', '<', '<=', 'between'].includes(op);

  if (isNum) {
    const resolveTarget = (rawT, defVal = 0) => {
      if (rawT === null || rawT === undefined || rawT === '') return defVal;
      const n = Number(rawT);
      if (Number.isFinite(n)) return n;
      try {
        return safeEvalMathClient(String(rawT), ctx);
      } catch {
        return defVal;
      }
    };
    const a = toNum(actual, 0);
    const t = resolveTarget(cond.value, 0);
    if (op === '>') return a > t;
    if (op === '>=') return a >= t;
    if (op === '<') return a < t;
    if (op === '<=') return a <= t;
    if (op === '==' || op === '=' || op === 'equals') return Math.abs(a - t) < 1e-9;
    if (op === '!=' || op === '<>' || op === 'not_equals') return Math.abs(a - t) >= 1e-9;
    if (op === 'between') {
      const t2 = resolveTarget(cond.value2, t);
      const lo = Math.min(t, t2);
      const hi = Math.max(t, t2);
      return a >= lo && a <= hi;
    }
    return false;
  }

  const aStr = String(actual || '').trim().toUpperCase();
  const tStr = String(cond.value || '').trim().toUpperCase();
  if (op === '==' || op === '=' || op === 'equals') return aStr === tStr;
  if (op === '!=' || op === '<>' || op === 'not_equals') return aStr !== tStr;
  if (op === 'contains') {
    if (!tStr) return false;
    return tStr.split(',').map((x) => x.trim()).filter(Boolean).some((tok) => aStr.includes(tok));
  }
  if (op === 'not_contains') {
    if (!tStr) return true;
    return tStr.split(',').map((x) => x.trim()).filter(Boolean).every((tok) => !aStr.includes(tok));
  }
  if (op === 'starts_with') return tStr ? aStr.startsWith(tStr) : false;
  if (op === 'in') {
    return tStr.split(',').map((x) => x.trim()).filter(Boolean).includes(aStr);
  }
  return false;
}

function postprocess(rawVal, dp, minVal, maxVal) {
  let val = Number(rawVal);
  let clamped = false;
  if (minVal !== null && minVal !== undefined && minVal !== '' && val < Number(minVal)) {
    val = Number(minVal);
    clamped = true;
  }
  if (maxVal !== null && maxVal !== undefined && maxVal !== '' && val > Number(maxVal)) {
    val = Number(maxVal);
    clamped = true;
  }
  const places = dp === null || dp === undefined ? 1 : Math.max(0, Math.min(4, Number(dp)));
  const factor = Math.pow(10, places);
  val = Math.round(val * factor) / factor;
  return { val, clamped };
}

export function evaluateFormulaClient(formula, rawBatchContext = {}) {
  try {
    const ctx = buildBatchContextClient(rawBatchContext);
    const fType = String(formula.formula_type || 'MATH').toUpperCase();
    const outMode = String(formula.output_mode || 'SINGLE').toUpperCase();
    const def = formula.definition || {};
    const outputsSpec = (Array.isArray(formula.outputs) && formula.outputs.length > 0)
      ? formula.outputs
      : [{
          key: 'value',
          label: formula.name || 'Hasil',
          unit: formula.unit || '',
          decimal_places: formula.decimal_places ?? 1,
          min_value: formula.min_value ?? null,
          max_value: formula.max_value ?? null,
          default_fallback: formula.default_fallback ?? 0,
        }];

    let matchedIdx = null;
    let matchedLabel = '';
    let exprMap = {};

    if (fType === 'MATH') {
      matchedIdx = 0;
      matchedLabel = 'Rumus Matematika';
      exprMap = outMode === 'MULTI'
        ? { ...(def.expressions || {}) }
        : { [outputsSpec[0].key]: def.expression ?? '0' };
    } else if (fType === 'IF_ELSE') {
      const rules = def.rules || [];
      let found = false;
      for (let i = 0; i < rules.length; i++) {
        const rule = rules[i];
        const conds = rule.conditions || [];
        if (conds.length === 0) continue;
        const logic = String(rule.logic || 'AND').toUpperCase();
        const checks = conds.map((c) => evalConditionClient(c, ctx));
        const ok = logic === 'AND' ? checks.every(Boolean) : checks.some(Boolean);
        if (ok) {
          matchedIdx = i;
          matchedLabel = rule.label || `Kondisi #${i + 1}`;
          exprMap = outMode === 'MULTI'
            ? { ...(rule.outputs || {}) }
            : { [outputsSpec[0].key]: rule.result_expr ?? '0' };
          found = true;
          break;
        }
      }
      if (!found) {
        matchedIdx = -1;
        matchedLabel = 'Selain Itu (ELSE / Default)';
        exprMap = outMode === 'MULTI'
          ? { ...(def.else_outputs || {}) }
          : { [outputsSpec[0].key]: def.else_expr ?? '0' };
      }
    } else if (fType === 'RANGE_TABLE') {
      const inputVar = def.input_var || 'fabric_weight_kg';
      const actual = toNum(ctx[inputVar], 0);
      const rows = def.rows || [];
      let found = false;
      for (let i = 0; i < rows.length; i++) {
        const r = rows[i];
        const minOk = (r.min === null || r.min === undefined || r.min === '') ? true : actual >= toNum(r.min);
        const maxOk = (r.max === null || r.max === undefined || r.max === '') ? true : actual <= toNum(r.max);
        if (minOk && maxOk) {
          matchedIdx = i;
          matchedLabel = r.label || `Rentang #${i + 1}`;
          exprMap = outMode === 'MULTI'
            ? { ...(r.outputs || {}) }
            : { [outputsSpec[0].key]: r.result_expr ?? '0' };
          found = true;
          break;
        }
      }
      if (!found) {
        matchedIdx = -1;
        matchedLabel = 'Di luar rentang (Default)';
        exprMap = outMode === 'MULTI'
          ? { ...(def.default_outputs || {}) }
          : { [outputsSpec[0].key]: def.default_expr ?? '0' };
      }
    } else if (fType === 'LOOKUP_TABLE') {
      const inputVar = def.input_var || 'fabric_type';
      const defMode = String(def.match_mode || 'contains').toLowerCase();
      const actualStr = String(ctx[inputVar] || '').trim().toUpperCase();
      const rows = def.rows || [];
      let found = false;
      for (let i = 0; i < rows.length; i++) {
        const r = rows[i];
        const rawVals = String(r.match_values || '').trim().toUpperCase();
        if (!rawVals) continue;
        const tokens = rawVals.split(',').map((x) => x.trim()).filter(Boolean);
        const mode = String(r.match_mode || defMode).toLowerCase();
        const isMatch = mode === 'equals'
          ? tokens.includes(actualStr)
          : tokens.some((tok) => actualStr.includes(tok));
        if (isMatch) {
          matchedIdx = i;
          matchedLabel = r.label || `Cocok '${r.match_values}'`;
          exprMap = outMode === 'MULTI'
            ? { ...(r.outputs || {}) }
            : { [outputsSpec[0].key]: r.result_expr ?? '0' };
          found = true;
          break;
        }
      }
      if (!found) {
        matchedIdx = -1;
        matchedLabel = 'Lainnya (Default)';
        exprMap = outMode === 'MULTI'
          ? { ...(def.default_outputs || {}) }
          : { [outputsSpec[0].key]: def.default_expr ?? '0' };
      }
    }

    const values = {};
    let anyClamped = false;
    for (const spec of outputsSpec) {
      const expr = exprMap[spec.key];
      const rawV = (expr === null || expr === undefined || String(expr).trim() === '')
        ? toNum(spec.default_fallback, toNum(formula.default_fallback, 0))
        : safeEvalMathClient(expr, ctx);
      const { val, clamped } = postprocess(
        rawV,
        spec.decimal_places ?? formula.decimal_places ?? 1,
        spec.min_value ?? (outMode === 'SINGLE' ? formula.min_value : null),
        spec.max_value ?? (outMode === 'SINGLE' ? formula.max_value : null)
      );
      if (clamped) anyClamped = true;
      values[spec.key] = {
        key: spec.key,
        label: spec.label || spec.key,
        unit: spec.unit || (outMode === 'SINGLE' ? (formula.unit || '') : ''),
        raw_value: +rawV.toFixed(4),
        value: val,
        clamped,
        expression: String(expr ?? ''),
      };
    }

    return {
      ok: true,
      output_mode: outMode,
      value: values[outputsSpec[0].key].value,
      values,
      matched_rule_index: matchedIdx,
      matched_label: matchedLabel,
      clamped: anyClamped,
      error: null,
    };
  } catch (err) {
    return {
      ok: false,
      value: 0,
      values: {},
      matched_rule_index: null,
      matched_label: '',
      clamped: false,
      error: err.message || 'Gagal menghitung formula',
    };
  }
}

export function getVarLabel(key) {
  const found = DEFAULT_BATCH_VARIABLES.find((v) => v.key === key);
  return found ? found.label : key;
}

export function summarizeFormulaIndonesian(formula) {
  if (!formula) return '';
  const fType = String(formula.formula_type || 'MATH').toUpperCase();
  const outMode = String(formula.output_mode || 'SINGLE').toUpperCase();
  const def = formula.definition || {};
  const unit = formula.unit ? ` ${formula.unit}` : '';

  const fmtOutputs = (obj) => {
    if (!obj) return '0';
    return Object.entries(obj).map(([k, v]) => `${k}=${v}`).join(', ');
  };

  if (fType === 'MATH') {
    if (outMode === 'MULTI') {
      return `Hitung otomatis: ${fmtOutputs(def.expressions)}`;
    }
    return `Hasil = ${def.expression || '0'}${unit}`;
  }
  if (fType === 'IF_ELSE') {
    const rules = def.rules || [];
    const parts = rules.slice(0, 3).map((r, i) => {
      const condText = (r.conditions || [])
        .map((c) => `${getVarLabel(c.var)} ${c.op} ${c.value}${c.op === 'between' ? `..${c.value2}` : ''}`)
        .join(` ${r.logic === 'OR' ? 'ATAU' : 'DAN'} `);
      const resText = outMode === 'MULTI' ? fmtOutputs(r.outputs) : `${r.result_expr}${unit}`;
      return `${i === 0 ? 'JIKA' : 'ELSE IF'} (${condText || '...'}) → ${resText}`;
    });
    const elseText = outMode === 'MULTI' ? fmtOutputs(def.else_outputs) : `${def.else_expr ?? '0'}${unit}`;
    parts.push(`SELAIN ITU → ${elseText}`);
    return parts.join(' ; ');
  }
  if (fType === 'RANGE_TABLE') {
    const vLabel = getVarLabel(def.input_var || 'fabric_weight_kg');
    const count = (def.rows || []).length;
    return `Tabel Rentang ${vLabel} (${count} kelas rentang)`;
  }
  if (fType === 'LOOKUP_TABLE') {
    const vLabel = getVarLabel(def.input_var || 'fabric_type');
    const count = (def.rows || []).length;
    return `Tabel Pemetaan ${vLabel} (${count} kategori)`;
  }
  return '';
}
