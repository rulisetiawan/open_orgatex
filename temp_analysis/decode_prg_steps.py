import struct
import json
import os

with open(r'open_orgatex\backend\data\typeconf_functions.json', 'r', encoding='utf-8') as f:
    cfg = json.load(f)

fn_dict = cfg.get('functions', {})

def get_fn_info(fn_id):
    s = str(fn_id)
    if s in fn_dict:
        return fn_dict[s].get('name', 'UNKNOWN'), fn_dict[s].get('name_local', '')
    return f'FN_{fn_id}', ''

def decode_full_prg(path):
    with open(path, 'rb') as f:
        b = f.read()

    prog_id = struct.unpack_from('<H', b, 8)[0]
    title = b[10:33].split(b'\0', 1)[0].decode('cp1252', errors='replace').strip()
    step_count = struct.unpack_from('<H', b, 33)[0]

    print(f"=== FULL DECODE OF {path} ===")
    print(f"Program ID: {prog_id}, Title: '{title}', Total Steps declared: {step_count}")
    print(f"Total size: {len(b)} bytes -> { (len(b)-384)//65 } records\n")

    current_step = None
    step_records = {}

    for off in range(384, len(b), 65):
        raw = b[off:off+65]
        step = struct.unpack_from('<H', raw, 0)[0]
        slot = raw[2]
        byte3 = raw[3]
        if step not in step_records:
            step_records[step] = []

        if slot == 0:
            comment = raw[3:].split(b'\0', 1)[0].decode('cp1252', errors='replace').strip()
            step_records[step].append({'kind': 'comment', 'text': comment})
        else:
            fn_id = struct.unpack_from('<H', raw, 4)[0]
            ack = raw[6]
            params = []
            for j in range(6):
                meta, val = struct.unpack_from('<Hf', raw, 7 + 6*j)
                params.append((meta, val))
            add_fields = struct.unpack_from('<5HBfHBHH', raw, 43)
            name_en, name_loc = get_fn_info(fn_id)
            step_records[step].append({
                'kind': 'function',
                'slot': slot,
                'fn_id': fn_id,
                'name_en': name_en,
                'name_loc': name_loc,
                'params': params,
                'ack': ack,
                'add_fields': add_fields
            })

    for s in sorted(step_records.keys()):
        recs = step_records[s]
        comments = [r['text'] for r in recs if r['kind'] == 'comment']
        cmt_str = f" // COMMENT: \"{comments[0]}\"" if comments else ""
        print(f"--- STEP {s:2d}{cmt_str} ---")
        for r in recs:
            if r['kind'] == 'comment':
                continue
            p_active = [f"P{i+1}={v:.1f}" for i, (m, v) in enumerate(r['params']) if v != 0.0]
            p_str = ", ".join(p_active) if p_active else "no-param"
            print(f"  Slot {r['slot']}: [{r['fn_id']:3d}] {r['name_en']:<25} ({r['name_loc']}) | {p_str}")

if __name__ == '__main__':
    decode_full_prg(r'temp_analysis\M_0002.PRG')
