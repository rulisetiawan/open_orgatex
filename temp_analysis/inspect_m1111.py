import struct
import os

path = r'C:\Users\ruli_smm\Flashdisk\SC797CE\BATCH\537491\M_1111.PRG'
with open(path, 'rb') as f:
    b = f.read()

print("M_1111.PRG length:", len(b))
print("Header 0..40:", b[:40].hex(' '))
print("Magic:", b[:4].hex())
print("Prog ID:", struct.unpack_from('<H', b, 8)[0])
print("Title:", b[10:33])
print("Step count:", struct.unpack_from('<H', b, 33)[0])
print("Payload len:", len(b) - 384, "Records:", (len(b) - 384) // 65, "Remainder:", (len(b) - 384) % 65)

for idx, off in enumerate(range(384, len(b), 65)):
    rec = b[off:off+65]
    step = struct.unpack_from('<H', rec, 0)[0]
    slot = rec[2]
    fn = struct.unpack_from('<H', rec, 4)[0] if slot > 0 else 0
    text = rec[3:].split(b'\0', 1)[0].decode('cp1252', 'ignore') if slot == 0 else ""
    print(f"Record {idx}: Step={step}, Slot={slot}, Fn={fn}, Text='{text}', raw={rec[:10].hex(' ')}")
