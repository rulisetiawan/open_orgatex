import struct
from pathlib import Path

def decompress_pr(path_str):
    log_data = Path(path_str).read_bytes()
    recs_by_seq = {}
    num_pages = len(log_data) // 512
    for page in range(1, num_pages):
        p = log_data[page * 512:(page + 1) * 512]
        if len(p) < 12:
            continue
        n = struct.unpack_from("<H", p, 10)[0]
        if not (0 < n < 100):
            continue
        for slot in range(n):
            a = struct.unpack_from("<H", p, 510 - slot * 2)[0]
            if a == 65535:
                continue
            start = a & 32767
            end = None
            for j in range(slot + 1, n + 1):
                z = struct.unpack_from("<H", p, 510 - j * 2)[0]
                if z != 65535:
                    end = z & 32767
                    break
            if end is None or not (12 <= start < end <= 512 - 2 * (n + 1)):
                continue
            packed = p[start:end]
            if a & 32768:
                packed = packed[4:]
            pos, out_b, repeat = 0, bytearray(), False
            while pos + 2 <= len(packed):
                cnt = struct.unpack_from("<H", packed, pos)[0]
                pos += 2
                need = 1 if repeat else cnt
                if pos + need > len(packed):
                    break
                val = packed[pos:pos + need]
                out_b += val * cnt if repeat else val
                pos += need
                repeat = not repeat
            if len(out_b) == 154:
                seq = struct.unpack_from("<H", out_b, 0)[0]
                recs_by_seq[seq] = bytes(out_b)
    return recs_by_seq

for fname in ["temp_analysis/PR_10B.LOG", "temp_analysis/PR_1F.LOG", "temp_analysis/PR_1A.LOG"]:
    p = Path(fname)
    if not p.exists():
        continue
    recs = decompress_pr(fname)
    print(f"\n================ {p.name} ({len(recs)} records) ================")
    curr_step = 0
    by_step = {}
    for seq in sorted(recs.keys()):
        raw = recs[seq]
        evt = struct.unpack_from("<H", raw, 2)[0]
        y, mo, d, h, mi, s = raw[4:10]
        dt = f"{h:02d}:{mi:02d}:{s:02d}"
        if evt == 261:
            curr_step = struct.unpack_from("<H", raw, 22)[0]
        elif evt == 3:
            w10 = struct.unpack_from("<h", raw, 10)[0]
            w12 = struct.unpack_from("<h", raw, 12)[0]
            w14 = struct.unpack_from("<h", raw, 14)[0]
            w16 = struct.unpack_from("<h", raw, 16)[0]
            w18 = struct.unpack_from("<h", raw, 18)[0]
            w20 = struct.unpack_from("<h", raw, 20)[0]
            by_step.setdefault(curr_step, []).append((dt, w10, w12, w14, w16, w18, w20))
    for st in sorted(by_step.keys())[:15]:
        arr = by_step[st]
        u_w16 = sorted(set(r[4] for r in arr))
        u_w10 = (min(r[1] for r in arr), max(r[1] for r in arr))
        u_w12 = (min(r[2] for r in arr), max(r[2] for r in arr))
        u_w14 = (min(r[3] for r in arr), max(r[3] for r in arr))
        print(f"Step {st:2d} (n={len(arr):3d}): w10(sp_ramp?)={u_w10} ({u_w10[0]*1.5/100:.1f}..{u_w10[1]*1.5/100:.1f}C) | w12(pv?)={u_w12} ({u_w12[0]*1.5/100:.1f}..{u_w12[1]*1.5/100:.1f}C) | w14={u_w14} | w16_uniq={u_w16[:8]}")
        if len(u_w16) > 1:
            prev = None
            for r in arr:
                if r[4] != prev:
                    print(f"   -> {r[0]}: w10={r[1]} ({r[1]*1.5/100:.1f}C) w12={r[2]} ({r[2]*1.5/100:.1f}C) w14={r[3]} w16={r[4]} w18={r[5]} w20={r[6]}")
                    prev = r[4]
