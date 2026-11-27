import io
import os
import re
import sys
import struct
import ftplib

sys.path.insert(0, "services/da-batch-worker")
from reader import SetexFolderReader

IP = "172.16.110.101"

ftp = None
status_bytes = None
pr_bytes = None
pr_path = ""
batch_no = ""
try:
    ftp = ftplib.FTP(timeout=5.0)
    ftp.connect(IP, 21)
    ftp.login("", "")
    ftp.set_pasv(True)

    # 1. Read STATUS.ACT
    for sp in ("/Storage/sc777ce/STATUS/STATUS.ACT", "/Storage/SC777CE/STATUS/STATUS.ACT"):
        try:
            bio = io.BytesIO()
            ftp.retrbinary(f"RETR {sp}", bio.write)
            if bio.getvalue():
                status_bytes = bio.getvalue()
                break
        except Exception:
            continue

    if status_bytes:
        st = SetexFolderReader.read_status_act(raw_bytes=status_bytes)
        batch_no = st.get("current_batch") or ""
        print(f"STATUS.ACT 1A -> batch={batch_no}, step={st.get('current_step')}, prog_code={st.get('program_code')}, prog_name={st.get('program_name')}")

    # 2. Read PR<batch>.LOG for active batch
    cands = []
    if batch_no:
        cands.append(f"/Storage/sc777ce/BATCH/{batch_no}/PR{batch_no}.LOG")
        cands.append(f"/Storage/sc777ce/BATCH/PR{batch_no}.LOG")
    for p in cands:
        try:
            bio = io.BytesIO()
            ftp.retrbinary(f"RETR {p}", bio.write)
            if bio.getvalue():
                pr_bytes = bio.getvalue()
                pr_path = p
                break
        except Exception:
            continue

    # Fallback: if active batch PR not found, list /Storage/sc777ce/BATCH and pick latest folder with PR*.LOG
    if not pr_bytes:
        items = ftp.nlst("/Storage/sc777ce/BATCH")
        b_dirs = sorted([os.path.basename(x.replace("\\", "/")) for x in items if re.match(r"^\d{6}$", os.path.basename(x.replace("\\", "/")))], reverse=True)
        print("Batch dirs on 1A:", b_dirs[:8])
        for bd in b_dirs[:3]:
            try:
                p = f"/Storage/sc777ce/BATCH/{bd}/PR{bd}.LOG"
                bio = io.BytesIO()
                ftp.retrbinary(f"RETR {p}", bio.write)
                if bio.getvalue():
                    pr_bytes = bio.getvalue()
                    pr_path = p
                    batch_no = bd
                    break
            except Exception:
                continue
finally:
    if ftp:
        try: ftp.quit()
        except Exception: pass
        try: ftp.close()
        except Exception: pass

if not pr_bytes:
    print("ERROR: Tidak bisa mengambil PR.LOG dari 1A")
    sys.exit(1)

with open("temp_analysis/PR_1A.LOG", "wb") as f:
    f.write(pr_bytes)

print(f"\nDownloaded {pr_path} ({len(pr_bytes)} bytes, {len(pr_bytes)//512} pages)")

meta = SetexFolderReader.parse_pr_log_metadata_and_steps(pr_bytes)
pts = SetexFolderReader.parse_cyclic_log_bytes(pr_bytes)

print("\n=== 1. BATCH INFO ===")
for k, v in meta["batch_info"].items():
    print(f"  {k:<16}: {v}")

print("\n=== 2. BATCH SUMMARY & INTERVENT_ST ===")
print(f"  HMI.INTERVENT_ST: {meta['intervent_active']}")
for k, v in meta["batch_summary"].items():
    print(f"  {k:<16}: {v}")

print(f"\n=== 3. DURASI AKTUAL PER STEP ({len(meta['step_actuals'])} steps) ===")
for s_no, act in sorted(meta["step_actuals"].items()):
    print(f"  Step {s_no:>2}: {act['started_at']} -> {act['ended_at'] or 'RUNNING'} | {act['actual_min']} mnt")

print(f"\n=== 4. OPERATOR TIMELINE ({len(meta['operator_timeline'])} events) ===")
for ev in meta["operator_timeline"]:
    print(f"  {ev['ts']} | {ev['type']:<18} | Step {str(ev.get('step_no','')):<3} | {ev.get('detail','')}")

print(f"\n=== 5. ALARMS ({len(meta['batch_alarms'])} alarms) ===")
for al in meta["batch_alarms"]:
    print(f"  {al['alarm_timestamp']} -> {al['cleared_at'] or 'ACTIVE'} | Step {al['step_no']:<2} | #{al['alarm_code']} {al['alarm_text']}")

print(f"\n=== 6. KURVA SIKLIK ({len(pts)} points) ===")
if pts:
    pvs = [p["temp_pv"] for p in pts]
    sps = [p["temp_sp"] for p in pts if p["temp_sp"] > 0]
    print(f"  Rentang Waktu : {pts[0]['timestamp']} s/d {pts[-1]['timestamp']}")
    print(f"  Suhu PV       : Min {min(pvs)} °C, Max {max(pvs)} °C")
    if sps:
        print(f"  Suhu SP       : Min {min(sps)} °C, Max {max(sps)} °C")
    print("  Sampel 5 titik awal:")
    for p in pts[:5]:
        print("   ", p)
    print("  Sampel 5 titik akhir:")
    for p in pts[-5:]:
        print("   ", p)
