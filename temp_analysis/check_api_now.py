import requests
import json

r = requests.get('http://192.168.100.30:8788/api/v1/assets?process=jetflow', timeout=5)
data = r.json()
assets = data.get('assets', [])
m10b = next((a for a in assets if a.get('id') == 'JF-LB-10'), None)

if m10b:
    print("API Data for JF-LB-10:")
    print("  State:", m10b.get("state"))
    print("  Batch:", m10b.get("batch"))
    print("  Values:", {k: v for k, v in m10b.get("values", {}).items() if k != "program"})
    prog = m10b.get("values", {}).get("program", [])
    print(f"  Program steps count: {len(prog)}")
    if prog:
        print("  Sample step 1:", prog[0])
        print(f"  Sample step {m10b.get('values', {}).get('step_no')}:", next((s for s in prog if s.get('step_no') == m10b.get('values', {}).get('step_no')), None))
