import sys
sys.path.insert(0, r'C:\Users\ruli_smm\DA-TEX\SETEX-LAN 50000\SETEX-LAN 50000\tools_deps')
import capstone

with open(r'C:\Users\ruli_smm\Flashdisk\SC797CE\SecomCE_BackGround_4d.dll', 'rb') as f:
    data = f.read()

# Find the string "Check_User_Config"
str_idx = data.find(b'Check_User_Config\x00')
print(f"String at {hex(str_idx)}")

# Find where this string VA is loaded
# ImageBase = 0x10000000
str_va = 0x10000000 + str_idx

md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)

# Search for xrefs to str_va in 4-byte aligned data
for i in range(0, len(data) - 4, 4):
    val = int.from_bytes(data[i:i+4], 'little')
    if val == str_va:
        print(f"Literal pool hit at {hex(i)}: points to Check_User_Config")
        # Disassemble 50 instructions before and 100 after
        start = max(0, i - 200)
        end = min(len(data), i + 400)
        print(f"Disassembly around {hex(start)}..{hex(end)}:")
        for insn in md.disasm(data[start:end], 0x10000000 + start):
            print(f"0x{insn.address:x}:\t{insn.mnemonic}\t{insn.op_str}")
