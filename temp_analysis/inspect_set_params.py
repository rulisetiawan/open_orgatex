import json

with open(r'c:\Users\ruli_smm\DA-TEX\WORKSPACE_PROGRAM_MESIN\MESIN_10B\02_CONFIG_SIAP_PAKAI\typeconf_functions.json') as f:
    d = json.load(f)

params = d.get('parameters', {})
addresses = [1, 2, 3, 4, 5, 7, 9, 10, 11, 13, 16, 18, 22, 36, 53, 60]

print("=== SET (Object 1009) Parameters in typeconf_functions.json ===")
for addr in addresses:
    p = params.get(str(addr))
    if p:
        scale = p.get('scale', {})
        factor = scale.get('factor', 1.0)
        name = p.get("name", "")
        local = p.get("name_local", "")
        unit = p.get("unit", "")
        print(f"SET {addr:2d} -> Nama: '{name}' | Deskripsi/Lokal: '{local}' | Unit: '{unit}' | Factor: {factor}")
    else:
        print(f"SET {addr:2d} -> NOT FOUND")
