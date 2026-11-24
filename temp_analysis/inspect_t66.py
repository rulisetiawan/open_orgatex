import json

with open('open_orgatex/backend/data/prg_catalog_data.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

templates = d.get('templates', [])
t66 = next((t for t in templates if t.get('id') == 66 or '0066' in t.get('filename', '')), None)
if t66:
    print("Found template 66:")
    print("Filename:", t66.get("filename"))
    print("Title   :", t66.get("title"))
    steps = t66.get("steps", [])
    print("Total steps:", len(steps))
    for s in steps[:12]:
        print(f"  Step {s.get('no'):2d}: {s.get('step'):<20} | SV: {s.get('sv')} | Min: {s.get('min')}")
else:
    print("Template 66 not found in catalog")
