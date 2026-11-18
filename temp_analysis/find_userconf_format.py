with open(r'C:\Users\ruli_smm\Flashdisk\SC797CE\SecomCE_BackGround_4d.dll', 'rb') as f:
    data = f.read()

# Let's search for '%s\\USERCONF' or 'USERCONF.CNF' or '%03d' or '%d'
import re
for m in re.finditer(rb'USERCONF', data):
    start = max(0, m.start() - 100)
    end = min(len(data), m.end() + 100)
    print(f"Match at {m.start()}:")
    print("  RAW:", data[start:end])
