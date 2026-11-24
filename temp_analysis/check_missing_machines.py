import json

with open('temp_analysis/scan_results.json') as f:
    data = json.load(f)

missing = [
    'MESIN_10E', 'MESIN_11E', 'MESIN_12C', 'MESIN_12E', 'MESIN_13E',
    'MESIN_15C', 'MESIN_15D', 'MESIN_1E', 'MESIN_1F', 'MESIN_2E',
    'MESIN_2F', 'MESIN_3C', 'MESIN_3E', 'MESIN_3F', 'MESIN_4E',
    'MESIN_4F', 'MESIN_5E', 'MESIN_5F', 'MESIN_6E', 'MESIN_6F',
    'MESIN_7E', 'MESIN_8E', 'MESIN_9E'
]

print("Status of the 23 machines in scan_results.json:")
for m in missing:
    found = next((d for d in data if d.get('folder') == m), None)
    if found:
        print(f"  {m:<12} -> IP: {found.get('ip'):<15} Status: {found.get('status')}")
    else:
        print(f"  {m:<12} -> NOT IN SCAN RESULTS")
