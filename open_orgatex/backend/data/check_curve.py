import struct

with open('C:/Users/ruli_smm/DA-TEX/open_orgatex/backend/data/PR066889.LOG', 'rb') as f:
    log_data = f.read()

page_size = 512
num_pages = len(log_data) // page_size
recs_by_seq = {}
for page in range(1, num_pages):
    p = log_data[page * 512:(page + 1) * 512]
    if len(p) < 12: continue
    n = struct.unpack_from('<H', p, 10)[0]
    if not (0 < n < 100): continue
    for slot in range(n):
        a = struct.unpack_from('<H', p, 510 - slot * 2)[0]
        if a == 65535: continue
        start = a & 32767
        end = None
        for j in range(slot + 1, n + 1):
            z = struct.unpack_from('<H', p, 510 - j * 2)[0]
            if z != 65535:
                end = z & 32767
                break
        if end is None or not (12 <= start < end <= 512 - 2 * (n + 1)): continue
        packed = p[start:end]
        if a & 32768: packed = packed[4:]
        pos, out, repeat = 0, bytearray(), False
        while pos + 2 <= len(packed):
            cnt = struct.unpack_from('<H', packed, pos)[0]
            pos += 2
            need = 1 if repeat else cnt
            if pos + need > len(packed): break
            val = packed[pos:pos + need]
            out += val * cnt if repeat else val
            pos += need
            repeat = not repeat
        if len(out) == 154:
            seq = struct.unpack_from('<H', out, 0)[0]
            recs_by_seq[seq] = bytes(out)

e3_recs = [recs_by_seq[s] for s in sorted(recs_by_seq.keys()) if struct.unpack_from('<H', recs_by_seq[s], 2)[0] == 3]

print(f'Total Event 3: {len(e3_recs)}')
for r in e3_recs:
    h, m, s = r[7:10]
    if (h == 10 and m in [15, 30, 45]) or (h == 11 and m in [0, 15]):
        words = [struct.unpack_from('<h', r, i)[0] for i in range(10, 30, 2)]
        print(f'{h}:{m:02d}:{s:02d} -> {words}')
