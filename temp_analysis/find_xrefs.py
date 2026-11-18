import struct

with open(r'C:\Users\ruli_smm\Flashdisk\SC797CE\SecomCE_BackGround_4d.dll', 'rb') as f:
    data = f.read()

# In 32-bit PE DLL, image base is usually 0x10000000 or similar
# Let's inspect PE header to get ImageBase
pe_offset = struct.unpack_from('<I', data, 0x3c)[0]
image_base = struct.unpack_from('<I', data, pe_offset + 0x34)[0]
print(f"PE offset: {hex(pe_offset)}, ImageBase: {hex(image_base)}")

str_va = image_base + 2002116
print(f"Target string VA: {hex(str_va)}")

# Search for str_va in data
matches = []
for i in range(0, len(data) - 4, 4):
    val = struct.unpack_from('<I', data, i)[0]
    if val == str_va or (2002000 <= val - image_base <= 2002200):
        matches.append((i, val, val - image_base))

print(f"Matches for string address: {len(matches)}")
for m in matches:
    print(f"  Offset in DLL: {hex(m[0])}, Target VA: {hex(m[1])}, Target file offset: {hex(m[2])}")
