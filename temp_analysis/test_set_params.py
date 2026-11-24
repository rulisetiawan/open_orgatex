import json

with open("program/Analisis/TYPECONF_functions_parameters.json", "r", encoding="utf-8") as f:
    data = json.load(f)

params = data.get("parameters", {})

print(f"Total parameters defined: {len(params)}")
test_ids = [1, 2, 3, 4, 5, 6, 7, 9, 16, 18, 22, 36, 53, 60, 73, 75, 83, 84, 134, 135, 136, 137, 138]
for pid in test_ids:
    p = params.get(str(pid))
    if p:
        scale = p.get("scale", {})
        print(f"SET ID {pid:3d}: {p['name']:28s} | {p['name_local']:25s} | unit: {p['unit']:6s} | factor: {scale.get('factor')}")
