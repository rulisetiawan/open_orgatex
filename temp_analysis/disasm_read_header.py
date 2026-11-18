import sys
sys.path.insert(0, r'C:\Users\ruli_smm\DA-TEX\SETEX-LAN 50000\SETEX-LAN 50000\tools_deps')
import capstone

with open(r'C:\Users\ruli_smm\Flashdisk\SC797CE\SecomCE_BackGround_4d.dll', 'rb') as f:
    data = f.read()

# file offset 0x89860 is near the function
start_off = (0x89860 - 300) & ~1
base_va = 0x10000000 + 0x1000 + (start_off - 0x400)

md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
for insn in md.disasm(data[start_off:start_off+350], base_va):
    print(f"0x{insn.address:x}:\t{insn.mnemonic}\t{insn.op_str}")
