import os
import io
import re
import sys
import json
import time
import socket
import ftplib
import hashlib
import psycopg2

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "temp_analysis"))
sys.path.insert(0, os.path.join(BASE_DIR, "open_orgatex", "backend"))

from download_and_parse_all_machines import decode_typeconf_cat10, machine_to_asset_id
from open_orgatex.backend.services.machine_config_service import sync_machine_ready_config
from open_orgatex.backend.sync_all_machines_iw_mapping import sync_machine

DB_URL = "postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow"
WORKSPACE_DIR = os.path.join(BASE_DIR, "WORKSPACE_PROGRAM_MESIN")

WANTED_CNF = {
    "TYPECONF.CNF",
    "CONFTEXT.CNF",
    "MACHCONF.CNF",
    "FNLEGEND.CNF",
    "TYPECONT.CNF",
    "USERCONF.CNF",
    "TYPEFORM.CNF",
}

def parse_awl_file(awl_path: str) -> dict:
    with open(awl_path, "rb") as f:
        data = f.read()
    sha = hashlib.sha256(data).hexdigest()
    # Extract .pro project name(s)
    pro_matches = sorted(set(s.decode("latin1", "ignore") for s in re.findall(rb"[A-Za-z0-9_.\-]+\.pro", data, re.I)))
    # Extract SETEX/CoDeSys date/version/target strings
    dates = sorted(set(s.decode("latin1", "ignore") for s in re.findall(rb"\b\d{2}[./-]\d{2}[./-]\d{2,4}\b", data)))[:10]
    # Extract readable symbol/module identifiers (end of file or symbol table)
    raw_syms = re.findall(rb"[A-Za-z_][A-Za-z0-9_]{4,40}", data)
    # Filter to meaningful PLC/SETEX symbols (exclude random binary noise)
    plc_keywords = ("PLC", "SECOM", "SETEX", "TEMP", "PUMP", "LEVEL", "VALVE", "DRAIN", "FILL", "HEAT", "COOL", "DOS", "WINCH", "ALARM", "MAIN", "TANK", "STEP", "BATCH", "CP14", "CP16", "CP12", "CAN", "MODBUS", "PID", "FLOW", "PRESS")
    matched_syms = []
    seen = set()
    for s in raw_syms:
        st = s.decode("latin1", "ignore")
        up = st.upper()
        if up not in seen and any(k in up for k in plc_keywords):
            seen.add(up)
            matched_syms.append(st)
            if len(matched_syms) >= 30:
                break

    fname = os.path.basename(awl_path)
    # Infer PLC CPU family from filename (CP14, CP16, CP12, etc.)
    cpu_match = re.search(r"(CP\d+)", fname, re.I)
    cpu_type = cpu_match.group(1).upper() if cpu_match else "UNKNOWN"

    return {
        "filename": fname,
        "cpu_type": cpu_type,
        "size_bytes": len(data),
        "sha256": sha,
        "project_names": pro_matches,
        "primary_project": pro_matches[0] if pro_matches else None,
        "dates_found": dates,
        "plc_symbols_sample": matched_syms[:20],
        "header_hex_16": data[:16].hex(),
    }

def fetch_missing_for_machine(m_no: str, ip: str, is_797_hint: bool):
    folder = f"MESIN_{m_no}"
    raw_dir = os.path.join(WORKSPACE_DIR, folder, "01_CONFIG_DARI_HMI")
    os.makedirs(raw_dir, exist_ok=True)
    existing_upper = {f.upper() for f in os.listdir(raw_dir)}

    # Fast TCP port 21 reachability check
    try:
        with socket.create_connection((ip, 21), timeout=0.6):
            pass
    except Exception:
        return (m_no, ip, "OFFLINE", "", [], False)

    ftp = None
    try:
        ftp = ftplib.FTP(timeout=4.0)
        ftp.connect(ip, 21)
        ftp.login("", "")
        ftp.set_pasv(True)

        dir_candidates = (
            ["/Flashdisk/SC797CE/Config", "/Flashdisk/SC797CE/CONFIG", "/Storage/sc777ce/Config", "/Storage/SC777CE/Config"]
            if is_797_hint else
            ["/Storage/sc777ce/Config", "/Storage/SC777CE/Config", "/Flashdisk/SC797CE/Config", "/Flashdisk/SC797CE/CONFIG"]
        )
        found_dir = None
        for d in dir_candidates:
            try:
                ftp.cwd(d)
                found_dir = d
                break
            except Exception:
                continue

        if not found_dir:
            return (m_no, ip, "NO_CONFIG_DIR", "", [], False)

        is_797_actual = "FLASHDISK" in found_dir.upper() or "797" in found_dir.upper()
        files = ftp.nlst()
        downloaded = []
        for fn in files:
            base = os.path.basename(fn.replace("\\", "/"))
            up = base.upper()
            need_dl = up.endswith(".AWL") or (up in WANTED_CNF and up not in existing_upper)
            if not need_dl:
                continue
            bio = io.BytesIO()
            try:
                ftp.retrbinary(f"RETR {base}", bio.write)
                data = bio.getvalue()
                if data:
                    with open(os.path.join(raw_dir, up), "wb") as f_out:
                        f_out.write(data)
                    downloaded.append(f"{up}({len(data)}B)")
            except Exception as e_dl:
                downloaded.append(f"{up}:ERR({e_dl})")

        return (m_no, ip, "OK", found_dir, downloaded, is_797_actual)
    except Exception as e:
        return (m_no, ip, "FTP_ERROR", str(e).strip(), [], is_797_hint)
    finally:
        if ftp:
            try:
                ftp.quit()
            except Exception:
                pass
            try:
                ftp.close()
            except Exception:
                pass

def main():
    conn = psycopg2.connect(DB_URL, connect_timeout=5)
    cur = conn.cursor()
    cur.execute("""
        SELECT machine_no, ip_address, controller_type
        FROM machines
        WHERE ip_address IS NOT NULL AND TRIM(ip_address) != ''
          AND ip_address NOT IN ('127.0.0.1', 'localhost', '0.0.0.0', '192.168.1.95')
        ORDER BY machine_no
    """)
    db_machines = cur.fetchall()

    # Phase 1: Identify machines missing ANY .AWL file OR missing TYPECONF.CNF
    need_fetch = []
    for m_no, ip, ctype in db_machines:
        raw_dir = os.path.join(WORKSPACE_DIR, f"MESIN_{m_no}", "01_CONFIG_DARI_HMI")
        files_up = {f.upper() for f in os.listdir(raw_dir)} if os.path.isdir(raw_dir) else set()
        has_awl = any(f.endswith(".AWL") for f in files_up)
        has_tc = "TYPECONF.CNF" in files_up
        if not has_awl or not has_tc:
            is_797_hint = ("797" in str(ctype or "").upper()) or ip.startswith("172.16.120.")
            need_fetch.append((m_no, ip.strip(), is_797_hint))

    print(f"=== PHASE 1: Fetching missing .AWL / .CNF for {len(need_fetch)} machines (1 clean session each) ===")
    newly_797 = []
    newly_tc_machines = []

    for m_no, ip, is_797_hint in need_fetch:
        m, ip_s, st, info, dls, is_797_act = fetch_missing_for_machine(m_no, ip, is_797_hint)
        print(f"  {m:<5} | {ip_s:<15} | {st:<13} | {info:<26} | {len(dls)} dl: {', '.join(dls[:6])}")
        if st == "OK":
            if is_797_act:
                newly_797.append((m, ip_s))
            if any(x.startswith("TYPECONF.CNF") for x in dls):
                newly_tc_machines.append((m, ip_s, is_797_act))
        time.sleep(0.3)

    # Update newly discovered 797CE machines in PostgreSQL
    if newly_797:
        m_list = [x[0] for x in newly_797]
        cur.execute("""
            UPDATE machines SET controller_type = 'SETEX SECOM 797CE'
            WHERE machine_no = ANY(%s)
        """, (m_list,))
        conn.commit()
        print(f"\nUpdated {len(m_list)} machines to SETEX SECOM 797CE in PostgreSQL: {m_list}")

    # Re-compile 02_CONFIG_SIAP_PAKAI + sync DB for newly downloaded TYPECONF.CNF
    if newly_tc_machines:
        print(f"\n=== PHASE 2: Compiling TYPECONF.CNF & syncing DB for {len(newly_tc_machines)} machines ===")
        for m_no, ip_s, is_797_act in newly_tc_machines:
            folder = f"MESIN_{m_no}"
            raw_dir = os.path.join(WORKSPACE_DIR, folder, "01_CONFIG_DARI_HMI")
            dec_dir = os.path.join(WORKSPACE_DIR, folder, "02_CONFIG_SIAP_PAKAI")
            tc_path = os.path.join(raw_dir, "TYPECONF.CNF")
            asset_id = machine_to_asset_id(folder)
            try:
                sync_machine_ready_config(m_no, ip_address=ip_s)
                iw_map = decode_typeconf_cat10(tc_path, asset_id)
                out_map_path = os.path.join(dec_dir, "typeconf_iw_map.json")
                if iw_map:
                    with open(out_map_path, "w", encoding="utf-8") as f:
                        json.dump(iw_map, f, indent=2)
                    sync_machine(m_no, out_map_path, conn=conn, sqlite_conn=None)
                print(f"  Compiled & synced {m_no} ({asset_id}): {len(iw_map) if iw_map else 0} IW")
            except Exception as e:
                print(f"  Warn compile {m_no}: {e}")

    # Phase 3: Parse ALL .AWL files across ALL machines in WORKSPACE_PROGRAM_MESIN
    print(f"\n=== PHASE 3: Parsing ALL .AWL files across ALL machines in WORKSPACE_PROGRAM_MESIN ===")
    all_awl_summary = []
    by_cpu = {}
    by_project = {}
    still_missing_awl = []

    for d in sorted(os.listdir(WORKSPACE_DIR)):
        if d.startswith("_"):
            continue
        raw_dir = os.path.join(WORKSPACE_DIR, d, "01_CONFIG_DARI_HMI")
        dec_dir = os.path.join(WORKSPACE_DIR, d, "02_CONFIG_SIAP_PAKAI")
        if not os.path.isdir(raw_dir):
            continue
        os.makedirs(dec_dir, exist_ok=True)
        awl_files = sorted([f for f in os.listdir(raw_dir) if f.upper().endswith(".AWL")])
        if not awl_files:
            still_missing_awl.append(d.replace("MESIN_", ""))
            continue

        parsed_list = []
        for af in awl_files:
            meta = parse_awl_file(os.path.join(raw_dir, af))
            parsed_list.append(meta)
            by_cpu[meta["cpu_type"]] = by_cpu.get(meta["cpu_type"], 0) + 1
            proj = meta["primary_project"] or f"({meta['filename']}, {meta['size_bytes']}B)"
            by_project.setdefault(proj, []).append(d.replace("MESIN_", ""))

        # Save awl_metadata.json
        with open(os.path.join(dec_dir, "awl_metadata.json"), "w", encoding="utf-8") as f:
            json.dump({
                "machine": d.replace("MESIN_", ""),
                "awl_count": len(parsed_list),
                "files": parsed_list,
            }, f, indent=2)

        # Update machine_profile.json
        prof_path = os.path.join(dec_dir, "machine_profile.json")
        prof = {}
        if os.path.isfile(prof_path):
            try:
                with open(prof_path, "r", encoding="utf-8") as f:
                    prof = json.load(f)
            except Exception:
                pass
        prof["has_awl_plc_program"] = True
        prof["awl_files"] = awl_files
        prof["awl_cpu_types"] = sorted(set(p["cpu_type"] for p in parsed_list))
        prof["awl_project_names"] = sorted(set(p["primary_project"] for p in parsed_list if p["primary_project"]))
        prof["awl_sha256"] = parsed_list[0]["sha256"]
        with open(prof_path, "w", encoding="utf-8") as f:
            json.dump(prof, f, indent=2)

        all_awl_summary.append((d.replace("MESIN_", ""), awl_files, [p["primary_project"] for p in parsed_list]))

    print(f"\nTOTAL MACHINES WITH PARSED .AWL: {len(all_awl_summary)}")
    print(f"STILL MISSING .AWL ({len(still_missing_awl)}): {still_missing_awl}")
    print(f"\nBreakdown by CPU / AWL Type: {by_cpu}")
    print("\nBreakdown by PLC Project (.pro):")
    for proj, mlist in sorted(by_project.items(), key=lambda x: -len(x[1])):
        print(f"  {proj:<35} ({len(mlist):>2} mesin): {', '.join(mlist)}")

    conn.close()

if __name__ == "__main__":
    main()
