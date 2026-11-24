import sys
sys.path.insert(0, r"c:\Users\ruli_smm\DA-TEX\services\da-batch-worker")
from reader import SetexFolderReader

HOST = "172.16.110.160"
res = SetexFolderReader.read_status_act(ip=HOST, ftp_port=21)

print("=== STATUS.ACT FROM CONTROLLER 10B ===")
print("Status       :", res.get("status"))
print("Current Batch:", res.get("current_batch"))
print("Step No      :", res.get("step_no"))
print("Program Code :", res.get("program_code"))
print("Program Name :", res.get("program_name"))
print("Prog No      :", res.get("prog_no"))
print("Total Steps  :", res.get("total_steps"))
