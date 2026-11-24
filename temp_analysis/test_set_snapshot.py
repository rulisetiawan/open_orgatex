import sys
import os

sys.path.insert(0, r"c:\Users\ruli_smm\DA-TEX\open_orgatex\backend")
from services.setex_tcp_client import SetexTcpClient

res = SetexTcpClient.read_all_objects_snapshot("172.16.110.160", 50000, machine_no="10B", timeout=3.0)
set_obj = res.get("objects", {}).get("SET_1009", {})
regs = set_obj.get("registers", [])

print(f"Total SET decoded registers: {len(regs)}")
for r in regs[:16]:
    print(f"  SET {r['address']:2d}: Nama='{r['name']}' | Lokal='{r['name_local']}' | Raw={r['raw']} | Target={r['formatted']}")
