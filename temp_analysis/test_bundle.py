import sys
import os
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("./open_orgatex"))

from open_orgatex.backend.services.reader import SetexFolderReader

bundle = SetexFolderReader.fetch_live_controller_bundle(
    ip='172.16.110.160',
    ftp_port=21,
    is_797=False,
    batch_no_hint='072162',
    timeout=5.0
)
print("status_bytes:", len(bundle['status_bytes']) if bundle['status_bytes'] else None)
print("alarm_bytes:", len(bundle['alarm_bytes']) if bundle['alarm_bytes'] else None)
print("alarms_log_bytes:", len(bundle['alarms_log_bytes']) if bundle['alarms_log_bytes'] else None)
print("batch_log_bytes:", len(bundle['batch_log_bytes']) if bundle['batch_log_bytes'] else None)
print("prg_bytes:", len(bundle['prg_bytes']) if bundle['prg_bytes'] else None)

if bundle['status_bytes']:
    st = SetexFolderReader.read_status_act(raw_bytes=bundle['status_bytes'])
    print("Parsed STATUS.ACT:", st)

if bundle['batch_log_bytes']:
    pts = SetexFolderReader.parse_cyclic_log_bytes(bundle['batch_log_bytes'])
    print(f"Parsed cyclic points from PR072162.LOG: {len(pts)}")
    if pts:
        print("Latest point:", pts[-1])
