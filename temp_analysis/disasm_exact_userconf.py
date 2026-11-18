import sys
sys.path.insert(0, r'C:\Users\ruli_smm\DA-TEX\SETEX-LAN 50000\SETEX-LAN 50000\tools_deps')
import capstone

with open(r'C:\Users\ruli_smm\Flashdisk\SC797CE\SecomCE_BackGround_4d.dll', 'rb') as f:
    data = f.read()

# file offset 968932 is around literal pool
# let's disassemble from 968932 - 400 to 968932 + 100
start_off = 968932 - 350
end_off = 968932 + 100

md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
# Let's map file offset to VA:
# RawOff=0x400, VA=0x1000
# va = 0x10000000 + 0x1000 + (off - 0x400)
base_va = 0x10000000 + 0x1000 + (start_off - 0x400)

for insn in md.disasm(data[start_off:end_off], base_va):
    print(f"0x{insn.address:x}:\t{insn.mnemonic}\t{insn.op_str}")
