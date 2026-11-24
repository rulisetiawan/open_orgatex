import os
import shutil
import json
import re

BASE_DIR = r"c:\Users\ruli_smm\DA-TEX"
WORKSPACE_DIR = os.path.join(BASE_DIR, "WORKSPACE_PROGRAM_MESIN")
MASTER_USERCONF = os.path.join(BASE_DIR, "open_orgatex", "backend", "data", "USERCONF.CNF")
TEMPLATE_MAP_PATH = os.path.join(WORKSPACE_DIR, "MESIN_10B", "02_CONFIG_SIAP_PAKAI", "typeconf_iw_map.json")

missing_23 = [
    'MESIN_10E', 'MESIN_11E', 'MESIN_12C', 'MESIN_12E', 'MESIN_13E',
    'MESIN_15C', 'MESIN_15D', 'MESIN_1E', 'MESIN_1F', 'MESIN_2E',
    'MESIN_2F', 'MESIN_3C', 'MESIN_3E', 'MESIN_3F', 'MESIN_4E',
    'MESIN_4F', 'MESIN_5E', 'MESIN_5F', 'MESIN_6E', 'MESIN_6F',
    'MESIN_7E', 'MESIN_8E', 'MESIN_9E'
]

def machine_to_asset_id(folder_name: str) -> str:
    mach = folder_name.replace("MESIN_", "").upper().strip()
    match = re.match(r"^(\d+)([A-Z])$", mach)
    if match:
        num, lane = match.groups()
        return f"JF-L{lane}-{int(num):02d}"
    if mach == "DA01":
        return "JF-LB-01"
    return f"JF-LB-{mach}"

with open(TEMPLATE_MAP_PATH, "r", encoding="utf-8") as f:
    template_map = json.load(f)

print(f"Master template loaded with {len(template_map)} keys.")

processed = []
for folder in missing_23:
    mach_id = folder.replace("MESIN_", "").upper()
    asset_id = machine_to_asset_id(folder)
    folder_path = os.path.join(WORKSPACE_DIR, folder)
    raw_dir = os.path.join(folder_path, "01_CONFIG_DARI_HMI")
    dec_dir = os.path.join(folder_path, "02_CONFIG_SIAP_PAKAI")
    
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(dec_dir, exist_ok=True)

    # 1. Copy USERCONF.CNF
    target_userconf = os.path.join(raw_dir, "USERCONF.CNF")
    if not os.path.exists(target_userconf) and os.path.exists(MASTER_USERCONF):
        shutil.copy2(MASTER_USERCONF, target_userconf)

    # 2. Generate customized typeconf_iw_map.json
    custom_map = {}
    for k_str, meta in template_map.items():
        m_copy = dict(meta)
        old_tag = m_copy.get("tag_name", "")
        # Replace asset_id (e.g. JF-LB-10 -> JF-LE-10)
        # Old asset_id in 10B template is JF-LB-10
        new_tag = re.sub(r"SMM\.[A-Z0-9\-]+\.", f"SMM.{asset_id}.", old_tag)
        m_copy["tag_name"] = new_tag
        custom_map[k_str] = m_copy

    out_map_path = os.path.join(dec_dir, "typeconf_iw_map.json")
    with open(out_map_path, "w", encoding="utf-8") as f:
        json.dump(custom_map, f, indent=2)

    # 3. Update profile.json
    prof_path = os.path.join(dec_dir, "profile.json")
    prof_data = {
        "machine_no": mach_id,
        "asset_id": asset_id,
        "has_typeconf": True,
        "registers_count": len(custom_map),
        "source": "STANDARD_NOVATECH_SETEX_PROFILE",
        "calibration_status": "ready"
    }
    with open(prof_path, "w", encoding="utf-8") as f:
        json.dump(prof_data, f, indent=2)

    processed.append((folder, asset_id, len(custom_map)))

print(f"Successfully generated USERCONF.CNF & typeconf_iw_map.json for {len(processed)} machines:")
for p in processed:
    print(f"  + {p[0]:<12} -> Asset: {p[1]:<10} | Tags: {p[2]}")
