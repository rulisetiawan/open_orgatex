import struct
import json
import os
import math
from collections import Counter

def text(b):
    return b.split(b'\0', 1)[0].decode('cp1252', errors='replace').strip()

def analyze_batchref(path):
    with open(path, 'rb') as f:
        b = f.read()

    print(f"==================================================")
    print(f"FILE: {path} ({len(b)} bytes)")
    print(f"==================================================")
    
    pstat_key = b[0]
    ref_no = text(b[1:8])
    timestamps = [struct.unpack_from('<I', b, 8 + i*4)[0] for i in range(3)]
    prog_no = struct.unpack_from('<H', b, 26)[0]
    mach = text(b[748:753])
    host_batch = struct.unpack_from('<H', b, 753)[0]
    host_config_no = struct.unpack_from('<H', b, 755)[0]
    position = struct.unpack_from('<H', b, 757)[0]
    
    prog_list = []
    if len(b) >= 762:
        for n, t in struct.iter_unpack('<HB', b[759:762]):
            prog_list.append({'prog_no': n, 'type': t})
            
    print(f"Status (pstat_key): {pstat_key}")
    print(f"Batch Ref No: '{ref_no}'")
    print(f"Timestamps: {timestamps}")
    print(f"Program No in header: {prog_no}")
    print(f"Machine No: '{mach}'")
    print(f"Host Batch: {host_batch}")
    print(f"Host Config No: {host_config_no}")
    print(f"Position: {position}")
    print(f"Program List: {prog_list}")
    
    print("\n--- 20 TEXT SLOTS (21 bytes each, total 420 bytes) ---")
    for i in range(20):
        t = text(b[28 + i*21 : 49 + i*21])
        raw_hex = b[28 + i*21 : 49 + i*21].hex()
        if t or any(x != 0 for x in b[28 + i*21 : 49 + i*21]):
            print(f"  Slot {i+1:2d} (offset {28 + i*21:3d}): '{t}' | Hex: {raw_hex}")
            
    print("\n--- 20 PARAMETERS (float32, offset 448..527) ---")
    params = struct.unpack_from('<20f', b, 448)
    for i, p in enumerate(params):
        if p != 0.0:
            print(f"  Param {i+1:2d} (offset {448 + i*4:3d}): {p}")
            
    print("\n--- 20 CONSUMPTION (float32, offset 528..607) ---")
    consump = struct.unpack_from('<20f', b, 528)
    for i, c in enumerate(consump):
        if c != 0.0:
            print(f"  Consump {i+1:2d}: {c}")

    print("\n--- 20 TIMES (int32, offset 608..687) ---")
    times = struct.unpack_from('<20i', b, 608)
    for i, tm in enumerate(times):
        if tm != 0:
            print(f"  Time {i+1:2d}: {tm}")

    print("\n--- EVENTS & ALARMS (offset 688..747) ---")
    events = struct.unpack_from('<20H', b, 688)
    alarms = struct.unpack_from('<10H', b, 728)
    non_zero_ev = [(i+1, v) for i, v in enumerate(events) if v != 0]
    non_zero_al = [(i+1, v) for i, v in enumerate(alarms) if v != 0]
    print(f"  Non-zero Events: {non_zero_ev}")
    print(f"  Non-zero Alarms: {non_zero_al}")
    print()

def analyze_prg(path):
    with open(path, 'rb') as f:
        b = f.read()

    print(f"==================================================")
    print(f"PRG FILE: {path} ({len(b)} bytes)")
    print(f"==================================================")
    
    magic = b[:4].hex()
    prog_id = struct.unpack_from('<H', b, 8)[0]
    title = text(b[10:33])
    step_count = struct.unpack_from('<H', b, 33)[0]
    header_raw = b[:384]
    
    print(f"Magic: {magic} (Expected 508fc2f5: {magic == '508fc2f5'})")
    print(f"Program ID: {prog_id}")
    print(f"Title: '{title}'")
    print(f"Step Count in header: {step_count}")
    
    rem = len(b) - 384
    num_records = rem // 65
    print(f"Payload bytes: {rem}, Record count: {num_records} (Remainder: {rem % 65})")
    
    records = []
    for idx, off in enumerate(range(384, len(b), 65)):
        raw = b[off:off+65]
        step = struct.unpack_from('<H', raw, 0)[0]
        slot = raw[2]
        byte3 = raw[3]
        if slot == 0:
            # Comment record
            comment_text = raw[3:].split(b'\0', 1)[0].decode('cp1252', errors='replace').strip()
            records.append({'step': step, 'slot': slot, 'kind': 'comment', 'text': comment_text})
        else:
            fn_id = struct.unpack_from('<H', raw, 4)[0]
            flag_byte6 = raw[6]
            params = []
            for j in range(6):
                meta, val = struct.unpack_from('<Hf', raw, 7 + 6*j)
                params.append((meta, val))
            add_fields = struct.unpack_from('<5HBfHBHH', raw, 43)
            records.append({
                'step': step,
                'slot': slot,
                'kind': 'function',
                'fn_id': fn_id,
                'byte3': byte3,
                'flag6': flag_byte6,
                'params': params,
                'add_fields': add_fields
            })
            
    print(f"Parsed {len(records)} records.")
    for r in records[:30]:
        if r['kind'] == 'comment':
            print(f"  Step {r['step']:2d} [COMMENT]: \"{r['text']}\"")
        else:
            p_str = ", ".join(f"P{i+1}={v:.2f}" for i, (m, v) in enumerate(r['params']) if v != 0.0)
            print(f"  Step {r['step']:2d} [Slot {r['slot']}] Fn {r['fn_id']:4d}: {p_str if p_str else 'no-param'} (flags: b3={r['byte3']}, f6={r['flag6']})")
    if len(records) > 30:
        print(f"  ... and {len(records) - 30} more records ...")
    print()

if __name__ == '__main__':
    analyze_batchref(r'temp_analysis\000006\BATCHREF.REF')
    analyze_prg(r'temp_analysis\000006\CALCPARA.PRG')
    analyze_prg(r'temp_analysis\000006\M_0998.PRG')
    analyze_prg(r'temp_analysis\M_0002.PRG')
