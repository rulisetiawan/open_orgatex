import json

with open('WORKSPACE_PROGRAM_MESIN/MESIN_10B/02_CONFIG_SIAP_PAKAI/typeconf_iw_map.json', 'r') as f:
    data = json.load(f)

print('Total:', len(data))
for k in sorted(int(x) for x in data.keys()):
    v = data[str(k)]
    name = v.get('name', '')
    unit = v.get('unit', '')
    factor = v.get('factor', 1.0)
    print(f"IW {k:3d} (idx={v.get('index')}): {name:28s} | unit: {unit:6s} | factor: {factor} | x: {v.get('x1')}..{v.get('x2')}")
