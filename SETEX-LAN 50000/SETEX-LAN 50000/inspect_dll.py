"""Read-only PE inspection for local SETEX protocol research."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'tools_deps'))
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_32

path = sys.argv[1]
pe = pefile.PE(path)
base = pe.OPTIONAL_HEADER.ImageBase
symbols = sorted((s.address, s.name.decode(errors='replace'))
                 for s in getattr(pe, 'DIRECTORY_ENTRY_EXPORT', type('X', (), {'symbols': []})).symbols if s.name)
print(path, 'machine', hex(pe.FILE_HEADER.Machine), 'base', hex(base))
needle = sys.argv[2] if len(sys.argv) > 2 else 'TranslateMessage'
if needle.startswith('0x'):
    rva = int(needle, 16)
    for ins in Cs(CS_ARCH_X86, CS_MODE_32).disasm(pe.get_data(rva, int(sys.argv[3], 0) if len(sys.argv)>3 else 800), base+rva):
        print(f'{ins.address:08x}: {ins.mnemonic:8} {ins.op_str}')
    sys.exit(0)
for i, (rva, name) in enumerate(symbols):
    if needle.lower() not in name.lower():
        continue
    end = symbols[i+1][0] if i+1 < len(symbols) else rva+800
    print('\n', hex(base+rva), name)
    for ins in Cs(CS_ARCH_X86, CS_MODE_32).disasm(pe.get_data(rva, min(end-rva, 2000)), base+rva):
        print(f'{ins.address:08x}: {ins.mnemonic:8} {ins.op_str}')
