"""
SECOM 777 / OrgaTEX Binary Codec & Planning Utilities
Strictly Offline & Local: Does not write to shared network folders.
Based on static analysis & reverse-engineering of Setex 777 / OrgaTEX Workplace.
Includes full PRG binary encoder/decoder (65-byte records) and Btrieve QueueTool integration.
"""

import io
import os
import re
import json
import struct
import hashlib
import zipfile
import subprocess
import tempfile
from typing import Dict, List, Optional, Tuple, Any

TEMPLATE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/template_batchref.bin"))
QUEUE_TEMPLATE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/QUEUE.template.BTD"))
QUEUE_TOOL_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/QueueTool.exe"))


def _put_cp1252_text(buffer: bytearray, offset: int, length: int, text_val: str, label: str = "Field"):
    """Encodes ASCII/CP1252 text into fixed-length buffer null-padded."""
    if not isinstance(text_val, str):
        text_val = str(text_val or "")
    cleaned = "".join(c for c in text_val if ord(c) >= 32)
    try:
        raw = cleaned.encode("cp1252")
    except UnicodeEncodeError:
        raw = cleaned.encode("ascii", errors="replace")
    if len(raw) >= length:
        raw = raw[:length - 1]
    buffer[offset:offset + length] = raw.ljust(length, b"\0")


def _get_cp1252_text(b: bytes, offset: int, length: int) -> str:
    """Decodes null-terminated ASCII/CP1252 text from buffer."""
    chunk = b[offset:offset + length]
    return chunk.split(b"\0", 1)[0].decode("cp1252", errors="replace").strip()


def get_template_batchref() -> bytearray:
    """Loads baseline 762-byte BATCHREF template."""
    if os.path.exists(TEMPLATE_PATH):
        try:
            with open(TEMPLATE_PATH, "rb") as f:
                data = f.read()
                if len(data) == 762:
                    return bytearray(data)
        except Exception:
            pass
    return bytearray(762)


def create_batchref_binary(
    reference_no: Any,
    machine_no: Optional[str] = None,
    batch_no: Optional[str] = None,
    program_no: Optional[int] = None,
    recipe_no: str = "",
    customer: str = "",
    article: str = "",
    color_code: str = "",
    color_name: str = "",
    fabric_weight: float = 350.0,
    program_title: str = "",
    batch_config: int = 2,
    custom_texts: Optional[Dict[int, str]] = None,
    custom_params: Optional[List[float]] = None
) -> bytes:
    """
    Constructs exact 762-byte BATCHREF.REF structure.
    Accepts either individual parameters or a single dictionary (target_batch).

    Offset map according to OrgaTEX T_BATCH_HEADER_ELEMENT:
      0: pstat_key (0 = CREATED)
      1..7: batch_ref_no (6 digits + null)
      8..25: 3x timestamps (reset to 0)
      26..27: program_no uint16
      28..447: 20 text slots @ 21 bytes
      448..527: 20 parameter float32 (P1: fabric weight)
      528..607: 20 consumption float32 (reset to 0)
      608..687: 20 times int32 (preserved)
      688..747: 20 events uint16 & 10 alarm counters uint16 (reset to 0)
      748..752: machine_no (5 bytes)
      753..754: host_batch uint16 = 1
      755..756: host_config_no uint16 = batch_config
      757..758: position uint16 = 0
      759..761: program_list: uint16 program_no + uint8 program_type (0)
    """
    if isinstance(reference_no, dict):
        d = reference_no
        reference_no = str(d.get("reference_no", "000000"))
        machine_no = str(d.get("machine_no", machine_no or "TD12"))
        batch_no = str(d.get("batch_no", batch_no or f"LOT-{reference_no}"))
        program_no = int(d.get("program_no", program_no or 1))
        recipe_no = str(d.get("recipe_name", d.get("recipe_no", recipe_no or "")))
        customer = str(d.get("customer", customer or ""))
        article = str(d.get("article", article or ""))
        color_code = str(d.get("color_code", color_code or ""))
        color_name = str(d.get("color_name", color_name or ""))
        fabric_weight = float(d.get("fabric_weight_kg", d.get("fabric_weight", fabric_weight or 350.0)))
        program_title = str(d.get("program_title", program_title or f"Program {program_no}"))

    if machine_no is None:
        machine_no = "TD12"
    if batch_no is None:
        batch_no = f"LOT-{reference_no}"
    if program_no is None:
        program_no = 1
    buf = get_template_batchref()
    buf[0] = 0  # Status CREATED
    buf[8:26] = bytes(18)    # Reset timestamps
    buf[528:608] = bytes(80) # Reset consumption
    buf[688:748] = bytes(60) # Reset events & alarms

    # Reference & Machine
    clean_ref = re.sub(r"\D", "", reference_no).zfill(6)[:6]
    _put_cp1252_text(buf, 1, 7, clean_ref, "Reference")
    _put_cp1252_text(buf, 748, 5, machine_no[:4].upper(), "Machine")

    # Program No
    struct.pack_into("<H", buf, 26, int(program_no))

    # 20 Text slots (@ 21 bytes each, starting at 28)
    _put_cp1252_text(buf, 28, 21, batch_no, "Batch No")                # Slot 1
    _put_cp1252_text(buf, 28 + 21 * 2, 21, customer, "Customer")      # Slot 3
    _put_cp1252_text(buf, 28 + 21 * 3, 21, article, "Article")        # Slot 4
    _put_cp1252_text(buf, 28 + 21 * 4, 21, color_code, "Color Code")  # Slot 5
    _put_cp1252_text(buf, 28 + 21 * 5, 21, color_name, "Color Desc")  # Slot 6
    _put_cp1252_text(buf, 28 + 21 * 6, 21, recipe_no, "Recipe No")    # Slot 7
    _put_cp1252_text(buf, 28 + 21 * 19, 21, program_title or f"PRG {program_no}", "Prog Title") # Slot 20

    if custom_texts:
        for slot_idx, txt in custom_texts.items():
            if 1 <= slot_idx <= 20:
                _put_cp1252_text(buf, 28 + 21 * (slot_idx - 1), 21, txt, f"Text Slot {slot_idx}")

    # Batch Parameters: Slot 1 is Fabric Weight (float32 at offset 448)
    try:
        struct.pack_into("<f", buf, 448, float(fabric_weight))
    except Exception:
        struct.pack_into("<f", buf, 448, 350.0)

    if custom_params:
        for p_idx, val in enumerate(custom_params[:20]):
            try:
                struct.pack_into("<f", buf, 448 + p_idx * 4, float(val))
            except Exception:
                pass

    # Config & Position
    struct.pack_into("<HHHHB", buf, 753, 1, int(batch_config), 0, int(program_no), 0)

    return bytes(buf)


def parse_prg_binary(data: bytes) -> Dict[str, Any]:
    """
    Parses a raw SETEX SECOM 777 binary .PRG file.
    Header: 384 bytes.
    Records: 65 bytes each (Line 0 = comment, Line 1 = main function, Line 2..13 = sub-functions).
    """
    if len(data) < 384 or data[:4] != bytes.fromhex("508fc2f5") or (len(data) - 384) % 65 != 0:
        raise ValueError("Berkas bukan format program biner SECOM 777 (.PRG) yang valid")

    program_no = struct.unpack_from("<H", data, 8)[0]
    program_name = _get_cp1252_text(data, 10, 21)
    step_count = struct.unpack_from("<H", data, 33)[0]

    steps_map: Dict[int, Dict[str, Any]] = {}
    for i in range(1, step_count + 1):
        steps_map[i] = {
            "step_no": i,
            "label": f"Langkah {i}",
            "functions": [],
            "summary_temp": None,
            "summary_time_min": 0.0,
            "summary_pump_pct": 85.0,
            "summary_reel_speed": 200.0,
            "summary_water_l": 0.0
        }

    for off in range(384, len(data), 65):
        rec = data[off:off + 65]
        step_idx = struct.unpack_from("<H", rec, 0)[0]
        line = rec[2]

        if step_idx not in steps_map:
            steps_map[step_idx] = {
                "step_no": step_idx,
                "label": f"Langkah {step_idx}",
                "functions": [],
                "summary_temp": None,
                "summary_time_min": 0.0,
                "summary_pump_pct": 85.0,
                "summary_reel_speed": 200.0,
                "summary_water_l": 0.0
            }

        if line == 0:
            # Comment record
            comment_str = _get_cp1252_text(rec, 3, 62)
            if comment_str:
                steps_map[step_idx]["label"] = comment_str
        else:
            func_id = struct.unpack_from("<H", rec, 4)[0]
            ack = rec[6]
            params = [struct.unpack_from("<f", rec, 9 + p * 6)[0] for p in range(6)]

            fn_entry = {
                "function_id": func_id,
                "column": line,
                "flags": ack,
                "params": params
            }
            steps_map[step_idx]["functions"].append(fn_entry)

            # Extract curve / summary indicators
            if func_id == 141 and len(params) >= 3:  # Temperature Control
                steps_map[step_idx]["summary_temp"] = params[0]
                steps_map[step_idx]["summary_time_min"] = params[2]
            elif func_id == 713 and len(params) >= 2:  # Water Fill
                steps_map[step_idx]["summary_water_l"] = params[1]
            elif func_id == 404 and len(params) >= 2:  # Pump
                steps_map[step_idx]["summary_pump_pct"] = params[1]

    ordered_steps = [steps_map[k] for k in sorted(steps_map.keys())]

    return {
        "program_no": program_no,
        "program_name": program_name or f"M_{program_no:04d}",
        "total_steps": len(ordered_steps),
        "file_size": len(data),
        "steps": ordered_steps
    }


def serialize_prg_binary(program_id: int, title: str, steps: List[Dict[str, Any]]) -> bytes:
    """
    Serializes structured program and steps into byte-exact SETEX SECOM 777 .PRG format.
    Ensures Program Start (F1) at step 1 and Program End (F2) at last step.
    """
    if not steps:
        raise ValueError("Program harus memiliki minimal satu langkah.")

    p_id = int(program_id)
    if p_id < 1 or p_id > 9999:
        raise ValueError(f"Nomor program SETEX harus antara 1 sampai 9999 (format M_xxxx.PRG). Diterima: {program_id}")

    header = bytearray(384)
    # Magic bytes: 50 8f c2 f5
    header[0:4] = bytes.fromhex("508fc2f5")
    struct.pack_into("<H", header, 8, p_id)
    _put_cp1252_text(header, 10, 21, title[:20], "Title")
    struct.pack_into("<H", header, 33, len(steps))

    records = bytearray()
    for s_idx, step in enumerate(steps, start=1):
        label = step.get("label", "").strip()
        if label:
            rec_comment = bytearray(65)
            struct.pack_into("<H", rec_comment, 0, s_idx)
            rec_comment[2] = 0  # Line 0 = Comment
            _put_cp1252_text(rec_comment, 3, 62, label[:61], "Comment")
            records.extend(rec_comment)

        funcs = step.get("functions", [])
        if not funcs:
            # Default placeholder function
            funcs = [{"function_id": 1 if s_idx == 1 else (2 if s_idx == len(steps) else 121), "column": 1, "params": []}]

        has_col1 = any(f.get("column", 1) == 1 for f in funcs)
        if not has_col1:
            funcs[0]["column"] = 1

        for fn in funcs:
            col = fn.get("column", 1)
            func_id = int(fn.get("function_id", 1))
            ack = int(fn.get("flags", 0))
            raw_params = fn.get("params", [])

            rec = bytearray(65)
            struct.pack_into("<H", rec, 0, s_idx)
            rec[2] = col
            struct.pack_into("<H", rec, 4, func_id)
            rec[6] = ack

            for p_i in range(6):
                val = float(raw_params[p_i]) if p_i < len(raw_params) else 0.0
                struct.pack_into("<f", rec, 9 + p_i * 6, val)

            records.extend(rec)

    return bytes(header + records)


def build_minimal_prg(program_id: int, title: str = "OpenOrgaTEX PRG") -> bytes:
    """Builds a valid baseline M_xxxx.PRG (Program Start -> Fill -> Temp -> End)."""
    p_id = max(1, min(int(program_id or 1), 9999))
    steps = [
        {"step_no": 1, "label": "Start Program", "functions": [{"function_id": 1, "column": 1, "params": []}]},
        {"step_no": 2, "label": "Isi Air", "functions": [{"function_id": 713, "column": 1, "params": [1.0, 1800.0]}]},
        {"step_no": 3, "label": "Penaikan Suhu", "functions": [{"function_id": 141, "column": 1, "params": [98.0, 2.5, 30.0]}]},
        {"step_no": 4, "label": "Selesai", "functions": [{"function_id": 2, "column": 1, "params": []}]}
    ]
    return serialize_prg_binary(p_id, title, steps)


def generate_queue_btd(records_759: List[bytes], machine_no: str) -> Optional[bytes]:
    """
    Generates a native 12,288-byte Btrieve QUEUE.BTD database using QueueTool.exe.
    Verifies all 5 indexes (Key 0-4).
    """
    if not os.path.exists(QUEUE_TOOL_PATH) or not os.path.exists(QUEUE_TEMPLATE_PATH):
        return None

    tool_dir = os.path.dirname(QUEUE_TOOL_PATH)
    try:
        # Note: QueueTool requires all paths to be located within tool_dir
        with tempfile.TemporaryDirectory(prefix="btr_q_", dir=tool_dir) as tmpdir:
            payload_bin = os.path.join(tmpdir, "payload.bin")
            out_btd = os.path.join(tmpdir, "output.BTD")

            with open(payload_bin, "wb") as f:
                for rec in records_759:
                    f.write(rec[:759])

            # Run QueueTool with cwd set to tool_dir so it finds BtrieveInterface.dll
            res = subprocess.run(
                [QUEUE_TOOL_PATH, QUEUE_TEMPLATE_PATH, payload_bin, out_btd],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=tool_dir,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )

            if res.returncode == 0 and os.path.exists(out_btd):
                with open(out_btd, "rb") as f:
                    return f.read()
            else:
                print(f"QueueTool error (code {res.returncode}): {res.stderr.strip() or res.stdout.strip()}")
    except Exception as e:
        print(f"Warning: QueueTool.exe failed ({e}); falling back without QUEUE.BTD")

    return None


def inspect_btd_refs(btd_bytes: bytes) -> List[str]:
    """
    Inspects a Btrieve QUEUE.BTD binary buffer using QueueTool.exe and returns
    the ordered list of 6-digit reference numbers present in the file.
    """
    if not btd_bytes or len(btd_bytes) < 1024 or not os.path.exists(QUEUE_TOOL_PATH):
        return []

    tool_dir = os.path.dirname(QUEUE_TOOL_PATH)
    try:
        with tempfile.NamedTemporaryFile(suffix=".BTD", dir=tool_dir, delete=False) as tf:
            tf.write(btd_bytes)
            tf_name = tf.name

        try:
            res = subprocess.run(
                [QUEUE_TOOL_PATH, "inspect", tf_name],
                capture_output=True,
                text=True,
                timeout=15,
                cwd=tool_dir,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
            for line in res.stdout.splitlines():
                if line.startswith("key=0 refs="):
                    raw_refs = line.split("key=0 refs=")[1].strip()
                    if raw_refs:
                        return [r.strip() for r in raw_refs.split(",") if r.strip()]
            return []
        finally:
            try:
                os.unlink(tf_name)
            except Exception:
                pass
    except Exception as e:
        print(f"Warning: inspect_btd_refs error: {e}")
        return []


def generate_batch_zip(
    batch_data: dict,
    prg_bytes: Optional[bytes] = None,
    include_queue: bool = True
) -> bytes:
    """
    Packages a planned batch into standard OrgaTEX offline zip bundle:
      OT/BATCH/{ref}/BATCHREF.REF
      OT/BATCH/{ref}/M_{prog:04d}.PRG
      OT/MACHINES/{machine}/BATCHES/QUEUE.BTD (if QueueTool available)
      planning-manifest.json
      BACA_DULU.txt
    """
    ref_no = str(batch_data.get("reference_no", "062340")).zfill(6)
    prog_no = int(batch_data.get("program_no", 1))
    machine = str(batch_data.get("machine_no", "TD12")).upper()
    batch_name = str(batch_data.get("batch_no", f"B_{ref_no}"))

    batchref_bin = create_batchref_binary(
        reference_no=ref_no,
        machine_no=machine,
        batch_no=batch_name,
        program_no=prog_no,
        recipe_no=batch_data.get("recipe_name", ""),
        customer=batch_data.get("customer", ""),
        article=batch_data.get("article", ""),
        color_code=batch_data.get("color_code", ""),
        color_name=batch_data.get("color_name", ""),
        fabric_weight=float(batch_data.get("fabric_weight_kg", 350.0)),
        program_title=batch_data.get("program_title", f"Program {prog_no}")
    )

    if not prg_bytes or len(prg_bytes) < 384:
        prg_bytes = build_minimal_prg(prog_no, batch_data.get("recipe_name", f"PRG {prog_no}"))

    queue_bytes = None
    if include_queue:
        # Create queue record (759 bytes with position = 1 at offset 757)
        q_rec = bytearray(batchref_bin[:759])
        struct.pack_into("<HH", q_rec, 755, 0, 1)  # host_config_no=0, position=1
        queue_bytes = generate_queue_btd([bytes(q_rec)], machine)

    manifest = {
        "format": "OPEN-ORGATEX-OFFLINE-PLANNING",
        "version": 2,
        "mode": "SAFE_LOCAL_PACKAGE",
        "write_protection": "STRICT_READ_ONLY_MODE_ACTIVE (No writes to shared folders)",
        "batch_reference": ref_no,
        "batch_no": batch_name,
        "machine_no": machine,
        "program_no": prog_no,
        "customer": batch_data.get("customer", "-"),
        "article": batch_data.get("article", "-"),
        "color": f"{batch_data.get('color_code', '')} {batch_data.get('color_name', '')}".strip(),
        "fabric_weight_kg": batch_data.get("fabric_weight_kg", 350.0),
        "files": {
            f"OT/BATCH/{ref_no}/BATCHREF.REF": hashlib.sha256(batchref_bin).hexdigest(),
            f"OT/BATCH/{ref_no}/M_{prog_no:04d}.PRG": hashlib.sha256(prg_bytes).hexdigest(),
        }
    }
    if queue_bytes:
        manifest["files"][f"OT/MACHINES/{machine}/BATCHES/QUEUE.BTD"] = hashlib.sha256(queue_bytes).hexdigest()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"OT/BATCH/{ref_no}/BATCHREF.REF", batchref_bin)
        zf.writestr(f"OT/BATCH/{ref_no}/M_{prog_no:04d}.PRG", prg_bytes)
        if queue_bytes:
            zf.writestr(f"OT/MACHINES/{machine}/BATCHES/QUEUE.BTD", queue_bytes)
        zf.writestr("planning-manifest.json", json.dumps(manifest, indent=2))
        zf.writestr("BACA_DULU.txt", (
            "PAKET PERENCANAAN BATCH & RESEP ORGATEX / SETEX 777\r\n"
            "====================================================\r\n\r\n"
            f"Nomor Referensi : {ref_no}\r\n"
            f"Nomor Batch     : {batch_name}\r\n"
            f"Mesin Target    : {machine}\r\n"
            f"Program Mesin   : M_{prog_no:04d}.PRG\r\n"
            f"Queue Antrean   : {'Disertakan (QUEUE.BTD)' if queue_bytes else 'Tidak disertakan'}\r\n\r\n"
            "CATATAN PENGGUNAAN:\r\n"
            "1. Ekstrak isi ZIP ke folder share mesin OrgaTEX (drive F:\\ atau Storage\\sc777ce).\r\n"
            "2. Queue BTD yang disertakan diverifikasi melalui Btrieve BTRCALL resmi.\r\n"
            "3. Sistem beroperasi dalam mode aman offline tanpa memodifikasi file produksi aktif.\r\n"
        ))

    buf.seek(0)
    return buf.getvalue()


def generate_multi_batch_zip(
    batches: List[dict],
    prg_map: Optional[Dict[int, bytes]] = None
) -> bytes:
    """
    Packages multiple planned batches into one unified OrgaTEX offline bundle,
    grouping queue records per machine with correct sequential positions (1..N).
    """
    if not batches:
        raise ValueError("Daftar batch tidak boleh kosong.")

    files: Dict[str, bytes] = {}
    machine_queues: Dict[str, List[bytearray]] = {}
    manifest_entries = []

    prg_map = prg_map or {}

    for b in batches:
        ref_no = str(b.get("reference_no", "062340")).zfill(6)
        prog_no = int(b.get("program_no", 1))
        machine = str(b.get("machine_no", "TD12")).upper()
        batch_name = str(b.get("batch_no", f"B_{ref_no}"))

        batchref_bin = create_batchref_binary(
            reference_no=ref_no,
            machine_no=machine,
            batch_no=batch_name,
            program_no=prog_no,
            recipe_no=b.get("recipe_name", ""),
            customer=b.get("customer", ""),
            article=b.get("article", ""),
            color_code=b.get("color_code", ""),
            color_name=b.get("color_name", ""),
            fabric_weight=float(b.get("fabric_weight_kg", 350.0)),
            program_title=b.get("program_title", f"Program {prog_no}")
        )

        prg_bytes = prg_map.get(prog_no)
        if not prg_bytes or len(prg_bytes) < 384:
            prg_bytes = build_minimal_prg(prog_no, b.get("recipe_name", f"PRG {prog_no}"))

        folder = f"OT/BATCH/{ref_no}"
        files[f"{folder}/BATCHREF.REF"] = batchref_bin
        files[f"{folder}/M_{prog_no:04d}.PRG"] = prg_bytes

        # Group for queue
        pos = len(machine_queues.setdefault(machine, [])) + 1
        q_rec = bytearray(batchref_bin[:759])
        struct.pack_into("<HH", q_rec, 755, 0, pos)  # host_config_no=0, position=pos
        machine_queues[machine].append(q_rec)

        manifest_entries.append({
            "reference": ref_no,
            "batch_no": batch_name,
            "machine": machine,
            "position": pos,
            "program_no": prog_no
        })

    # Generate QUEUE.BTD for each machine
    for machine, q_records in machine_queues.items():
        q_bytes = generate_queue_btd([bytes(r) for r in q_records], machine)
        if q_bytes:
            files[f"OT/MACHINES/{machine}/BATCHES/QUEUE.BTD"] = q_bytes

    manifest = {
        "format": "OPEN-ORGATEX-MULTI-BATCH-PLANNING",
        "version": 2,
        "total_batches": len(batches),
        "machines": list(machine_queues.keys()),
        "entries": manifest_entries,
        "files": {k: hashlib.sha256(v).hexdigest() for k, v in files.items()}
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p, d in files.items():
            zf.writestr(p, d)
        zf.writestr("planning-manifest.json", json.dumps(manifest, indent=2))
        zf.writestr("BACA_DULU.txt", (
            "PAKET MULTI-BATCH PLANNING ORGATEX / SETEX 777\r\n"
            "==============================================\r\n"
            f"Jumlah Batch : {len(batches)}\r\n"
            f"Mesin        : {', '.join(machine_queues.keys())}\r\n"
            "Semua antrean QUEUE.BTD dan folder batch telah digenerate secara otomatis.\r\n"
        ))

    buf.seek(0)
    return buf.getvalue()
