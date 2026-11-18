with open(r'C:\Users\ruli_smm\Flashdisk\SC797CE\SecomCE_BGUtils_4d.dll', 'rb') as f:
    data = f.read()

import re
for m in re.finditer(b'DRHSTPRG', data):
    print("Match at", m.start(), ":")
    chunk = data[max(0, m.start()-100) : min(len(data), m.end()+300)]
    s = "".join([chr(c) if 32 <= c <= 126 else " " for c in chunk])
    print(" ", s)
