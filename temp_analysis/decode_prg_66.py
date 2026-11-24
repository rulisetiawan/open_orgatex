import sys
sys.path.insert(0, r"c:\Users\ruli_smm\DA-TEX\open_orgatex\backend")
from services.prg_decoder import PrgDecoder

res = PrgDecoder.decode_file(r"c:\Users\ruli_smm\DA-TEX\open_orgatex\backend\data\compiled_prg\M_0066.PRG")
print("Program Title:", res.get("title"))
steps = res.get("steps", [])
print("Total steps:", len(steps))
for s in steps[:15]:
    print(f"  Step {s.get('no'):2d}: {s.get('step'):<22} | SV: {s.get('sv')} | Min: {s.get('min')}")
