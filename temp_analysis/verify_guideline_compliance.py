import json
import re

with open(r'c:\Users\ruli_smm\DA-TEX\WORKSPACE_PROGRAM_MESIN\MESIN_10B\02_CONFIG_SIAP_PAKAI\typeconf_iw_map.json') as f:
    tc = json.load(f)

# Tag Guideline Regex: SMM.{ASSET_ID}.{SECTION}.{QUANTITY}[_{QUALIFIER}]_{ROLE}
# Role must be PV, SV, TOTAL, CNT, ST, FB, STATE, CODE, ALM, CALC, etc.
pattern = re.compile(r'^SMM\.[A-Z0-9\-]+\.[A-Z0-9_]+\.[A-Z0-9_]+_(PV|SV|TOTAL|CNT|ST|FB|STATE|CODE|ALM|CALC|STATUS)$')

valid_count = 0
invalid = []

for k in sorted([int(x) for x in tc.keys()]):
    item = tc[str(k)]
    tag = item.get("tag_name", "")
    if pattern.match(tag):
        valid_count += 1
    else:
        invalid.append((k, tag, item.get("name", "")))

print(f"Total tags in typeconf_iw_map.json: {len(tc)}")
print(f"Tags conforming to guideline: {valid_count} / {len(tc)}")
if invalid:
    print(f"Non-conforming tags ({len(invalid)}):")
    for inv in invalid:
        print(f"  IW {inv[0]}: {inv[1]} (SETEX name: '{inv[2]}')")
else:
    print("ALL tags 100% follow the Tag Guideline!")

