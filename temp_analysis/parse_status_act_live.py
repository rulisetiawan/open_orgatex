import io
import ftplib
import sys
sys.path.insert(0, r"c:\Users\ruli_smm\DA-TEX\services\da-batch-worker")
from reader import BatchReader

HOST = "172.16.110.160"

ftp = ftplib.FTP(timeout=3.0)
ftp.connect(HOST, 21)
ftp.login()

bio = io.BytesIO()
ftp.retrbinary("RETR /Storage/SC777CE/Status/STATUS.ACT", bio.write)
bio.seek(0)
raw = bio.read()
ftp.quit()

status = BatchReader.parse_status_act(raw)
print("=== PARSED STATUS.ACT LIVE FROM CONTROLLER 10B ===")
print("Batch No :", status.batch_no)
print("Step No  :", status.step_no)
print("Prog No  :", status.program_no)
print("Status   :", status.status)
print("Raw State:", status.raw_state)

# Also check PR<batch>.LOG
batch_clean = status.batch_no.strip()
print(f"\nChecking PR{batch_clean}.LOG on controller...")
ftp = ftplib.FTP(timeout=3.0)
ftp.connect(HOST, 21)
ftp.login()

pr_bio = io.BytesIO()
try:
    ftp.retrbinary(f"RETR /Storage/SC777CE/Logs/PR{batch_clean}.LOG", pr_bio.write)
    pr_bio.seek(0)
    pr_raw = pr_bio.read()
    print(f"PR{batch_clean}.LOG exists, size={len(pr_raw)} bytes")
    curve_pts = BatchReader.parse_curve_log(pr_raw)
    print(f"Curve points: {len(curve_pts)}")
    if curve_pts:
        print("Last curve point:", curve_pts[-1])
except Exception as e:
    print(f"Could not read PR{batch_clean}.LOG: {e}")

ftp.quit()
