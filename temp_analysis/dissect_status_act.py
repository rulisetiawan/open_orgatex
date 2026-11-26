import io
import re
import struct
import ftplib

def fetch_status(ip, path, out_file):
    ftp = None
    try:
        ftp = ftplib.FTP(timeout=4.0)
        ftp.connect(ip, 21)
        ftp.login("", "")
        ftp.set_pasv(True)
        bio = io.BytesIO()
        ftp.retrbinary(f"RETR {path}", bio.write)
        data = bio.getvalue()
        with open(out_file, "wb") as f:
            f.write(data)
        return data
    except Exception as e:
        print(f"Fetch error {ip} {path}: {e}")
        return None
    finally:
        if ftp:
            try: ftp.quit()
            except Exception: pass
            try: ftp.close()
            except Exception: pass

def dissect(label, data):
    if not data:
        return
    print(f"\n==================== {label} ({len(data)} bytes) ====================")
    # 1. Known Header Fields (0x000..0x200)
    print("--- Known Header Fields ---")
    print(f"  0x0000..0x000B (Header/Magic)   : {data[0:11].hex()}")
    print(f"  0x000B..0x0013 (Machine ID)     : {data[11:19].split(b'\\0')[0].decode('cp1252','ignore')!r}")
    print(f"  0x0014..0x001E (Status Words)   : {[struct.unpack_from('<H', data, o)[0] for o in range(20, 36, 2)]}")
    print(f"  0x0024..0x0030 (Batch No)       : {data[36:48].split(b'\\0')[0].decode('cp1252','ignore')!r}")
    print(f"  0x0034..0x0040 (Program Code)   : {data[52:64].split(b'\\0')[0].decode('cp1252','ignore')!r}")
    print(f"  0x004B..0x0064 (Program Name)   : {data[75:100].split(b'\\0')[0].decode('cp1252','ignore')!r}")
    print(f"  0x015A..0x0166 (Step/Prog Area) : " + ", ".join(f"0x{o:03X}={struct.unpack_from('<H', data, o)[0]}" for o in range(0x158, 0x16A, 2)))

    # 2. All readable ASCII strings with offsets across the whole file
    print("\n--- All Readable Text Strings (offset : text) ---")
    for m in re.finditer(rb"[ -~]{3,}", data):
        s = m.group(0).decode("cp1252", "ignore").strip()
        if len(s) >= 3 and any(c.isalnum() for c in s):
            print(f"  0x{m.start():04X} ({m.start():>5}): {s!r}")

    # 3. Non-zero regions summary (in 256-byte blocks)
    print("\n--- Non-zero Memory Map (per 256-byte block) ---")
    for off in range(0, len(data), 256):
        blk = data[off:off+256]
        nz = sum(1 for b in blk if b != 0)
        if nz > 0:
            # Show first 16 non-zero preview
            print(f"  0x{off:04X}..0x{off+len(blk)-1:04X}: {nz:>3}/{len(blk)} non-zero bytes")

d10b = fetch_status("172.16.110.160", "/Storage/sc777ce/STATUS/STATUS.ACT", "temp_analysis/STATUS_10B.ACT")
d1f  = fetch_status("172.16.120.151", "/Flashdisk/SC797CE/STATUS/STATUS.ACT", "temp_analysis/STATUS_1F.ACT")

dissect("10B (SECOM 777)", d10b)
dissect("1F (SECOM 797CE)", d1f)
