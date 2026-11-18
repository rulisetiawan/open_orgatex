with open(r'C:\Users\ruli_smm\Flashdisk\SC797CE\SecomCE_BackGround_4d.dll', 'rb') as f:
    data = f.read()

import re
# Search for byte 108 (0x6c) near calls to error logger or search string "USERCONF"
idx = data.find(b'USERCONF\x00')
print("USERCONF at", hex(idx))
# Let's search for occurrences of 0x1e8000..0x1e9000
for i in range(0, len(data)-4, 4):
    v = int.from_bytes(data[i:i+4], 'little')
    if v == 0x101e8cb0 or v == 0x101e8cc4: # USERCONF
        print(f"Direct match at {hex(i)} -> {hex(v)}")
