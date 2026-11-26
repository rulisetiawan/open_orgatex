import io
import os
import re
import sys
import struct
import ftplib

sys.path.insert(0, "services/da-batch-worker")
from reader import SetexFolderReader

def fetch_pr(ip, paths, out_file):
    ftp = None
    try:
        ftp = ftplib.FTP(timeout=4.0)
        ftp.connect(ip, 21)
        ftp.login("", "")
        ftp.set_pasv(True)
        for p in paths:
            try:
                bio = io.BytesIO()
                ftp.retrbinary(f"RETR {p}", bio.write)
                data = bio.getvalue()
                if data:
                    with open(out_file, "wb") as f:
                        f.write(data)
                    return p, data
            except Exception:
                continue
        return None, None
    except Exception as e:
        print(f"FTP err {ip}: {e}")
        return None, None
    finally:
        if ftp:
            try: ftp.quit()
            except Exception: pass
            try: ftp.close()
            except Exception: pass

def inspect_pr(label, path, data):
    if not data:
        print(f"\n=== {label}: NOT FOUND ===")
        return
    print(f"\n==================== {label} ({path}, {len(data)} bytes) ====================")
    page_size = struct.unpack_from("<H", data, 0x08)[0] if len(data) >= 16 else 0
    print(f"  Btrieve Page Size (0x08) : {page_size} bytes | Total Pages: {len(data)//512 if len(data)%512==0 else 'non-512'}")

    # Decompress Btrieve 512-byte pages and check record lengths & event types
    rec_lens = {}
    evt_counts = {}
    if len(data) >= 512 and len(data) % 512 == 0:
        num_pages = len(data) // 512
        for page in range(1, num_pages):
            p = data[page * 512:(page + 1) * 512]
            n = struct.unpack_from("<H", p, 10)[0]
            if not (0 < n < 100):
                continue
            for slot in range(n):
                a = struct.unpack_from("<H", p, 510 - slot * 2)[0]
                if a == 65535: continue
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
                pos, out, repeat = 0, bytearray(), False
                while pos + 2 <= len(packed):
                    cnt = struct.unpack_from("<H", packed, pos)[0]
                    pos += 2
                    need = 1 if repeat else cnt
                    if pos + need > len(packed): break
                    val = packed[pos:pos + need]
                    out += val * cnt if repeat else val
                    pos += need
                    repeat = not repeat
                rec_lens[len(out)] = rec_lens.get(len(out), 0) + 1
                if len(out) >= 4:
                    evt = struct.unpack_from("<H", out, 2)[0]
                    evt_counts[evt] = evt_counts.get(evt, 0) + 1

    print(f"  Decompressed record sizes : {rec_lens}")
    print(f"  Event types (evt IDs)     : {dict(sorted(evt_counts.items()))}")

    # Test our current parser
    pts = SetexFolderReader.parse_cyclic_log_bytes(data)
    print(f"  parse_cyclic_log_bytes()  : {len(pts)} points decoded")
    if pts:
        print(f"    First: {pts[0]}")
        print(f"    Last : {pts[-1]}")

    # Metadata strings in first 4KB / Page 5
    p5 = data[5*512:6*512] if len(data) >= 6*512 else data
    strs = [s.decode("cp1252", "ignore").strip() for s in re.findall(rb"[A-Za-z0-9_.\- ]{4,}", p5) if any(c.isalnum() for c in s.decode("cp1252", "ignore"))]
    print(f"  Page 5 metadata strings   : {strs[:12]}")

p10, d10 = fetch_pr("172.16.110.160", ["/Storage/sc777ce/BATCH/072612/PR072612.LOG", "/Storage/sc777ce/BATCH/PR072612.LOG"], "temp_analysis/PR_10B.LOG")
p1f, d1f = fetch_pr("172.16.120.151", ["/Flashdisk/SC797CE/BATCH/072633/PR072633.LOG", "/Flashdisk/SC797CE/BATCH/PR072633.LOG"], "temp_analysis/PR_1F.LOG")

inspect_pr("10B (SECOM 777) PR072612.LOG", p10, d10)
inspect_pr("1F (SECOM 797CE) PR072633.LOG", p1f, d1f)
