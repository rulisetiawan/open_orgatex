import psycopg2
import json

conn = psycopg2.connect('postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow')
cur = conn.cursor()

cur.execute("""
    SELECT register_index, iw_number, tag_name, tag_role, field_name 
    FROM cfg_machine_iw_tag_mapping 
    WHERE machine_id = '10B' 
    ORDER BY register_index;
""")
db_rows = cur.fetchall()
print(f"Total rows in cfg_machine_iw_tag_mapping for 10B: {len(db_rows)}")

with open(r'c:\Users\ruli_smm\DA-TEX\WORKSPACE_PROGRAM_MESIN\MESIN_10B\02_CONFIG_SIAP_PAKAI\typeconf_iw_map.json') as f:
    typeconf = json.load(f)
print(f"Total keys in typeconf_iw_map.json: {len(typeconf)}")

# Compare tag_names
mismatches = []
exact_matches = []
for r in db_rows:
    reg_idx = str(r[0])
    db_tag = r[2]
    if reg_idx in typeconf:
        tc_tag = typeconf[reg_idx].get('tag_name')
        if db_tag != tc_tag:
            mismatches.append((reg_idx, db_tag, tc_tag))
        else:
            exact_matches.append((reg_idx, db_tag))
    else:
        mismatches.append((reg_idx, db_tag, 'NOT_IN_TYPECONF'))

print(f"Exact matching tags: {len(exact_matches)}")
print(f"Mismatched tag_name between DB and TYPECONF: {len(mismatches)}")
print("\nSample Mismatches:")
for m in mismatches[:20]:
    print(f"  Reg {m[0]}: DB={m[1]}  <--->  TYPECONF={m[2]}")

# Also check live telemetry keys
cur.execute("SELECT telemetry_json FROM live_iw_telemetry WHERE machine_id = '10B'")
row = cur.fetchone()
if row and row[0]:
    tjson = row[0]
    print(f"\nTotal tags in live telemetry_json: {len(tjson)}")
    # Check how many db_tags are present in live telemetry
    found_db = sum(1 for r in db_rows if r[2] in tjson)
    print(f"db_tags found in live telemetry_json: {found_db} / {len(db_rows)}")

conn.close()
