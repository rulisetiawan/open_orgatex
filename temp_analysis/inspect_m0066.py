import os
import struct

path = r"c:\Users\ruli_smm\DA-TEX\open_orgatex\backend\data\compiled_prg\M_0066.PRG"
if not os.path.exists(path):
    print("File not found")
else:
    with open(path, "rb") as f:
        data = f.read()
    print("M_0066.PRG size:", len(data))
    # SETEX PRG header is usually text or binary
    print("Header bytes (first 100):", data[:100])
    # Search for ascii strings in PRG
    import re
    strings = re.findall(b'[\x20-\x7E]{4,}', data)
    print("Found strings:", [s.decode('latin1') for s in strings[:15]])
