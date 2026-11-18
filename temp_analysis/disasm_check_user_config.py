import sys
sys.path.insert(0, r'C:\Users\ruli_smm\DA-TEX\SETEX-LAN 50000\SETEX-LAN 50000\tools_deps')
import capstone

with open(r'C:\Users\ruli_smm\Flashdisk\SC797CE\SecomCE_BackGround_4d.dll', 'rb') as f:
    data = f.read()

# Let's disassemble around 0xd6400 using ARM or Thumb
md_arm = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
md_thumb = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

print("--- THUMB MODE (0xd6400..0xd6600) ---")
for insn in md_thumb.disasm(data[0xd6400:0xd6580], 0x10000000 + 0xd6400):
    print(f"0x{insn.address:x}:\t{insn.mnemonic}\t{insn.op_str}")
