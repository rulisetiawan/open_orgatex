import os
import sys

log_path = r"C:\Users\ruli_smm\Documents\PR072657.LOG"
if not os.path.exists(log_path):
    print(f"Error: {log_path} does not exist")
    sys.exit(1)

size = os.path.getsize(log_path)
print(f"Found file {log_path}, Size = {size} bytes")

with open(log_path, "rb") as f:
    raw_data = f.read()

print(f"First 64 bytes (hex): {raw_data[:64].hex()}")

# Import existing parser
sys.path.append("services/da-batch-worker")
from reader import SetexFolderReader

points = SetexFolderReader.parse_cyclic_log_bytes(raw_data)
print(f"Total points decoded: {len(points)}")

if points:
    print("\n--- SAMPLE POINT (FIRST) ---")
    for k, v in points[0].items():
        print(f"  {k}: {v}")
    
    print("\n--- SAMPLE POINT (MIDDLE) ---")
    mid = len(points) // 2
    for k, v in points[mid].items():
        print(f"  {k}: {v}")

    print("\n--- SAMPLE POINT (LAST) ---")
    for k, v in points[-1].items():
        print(f"  {k}: {v}")

    # Summary of unique steps and ranges
    steps = sorted(list(set(p.get("step_no", 0) for p in points)))
    temp_pvs = [p.get("temp_pv", 0) for p in points if p.get("temp_pv") is not None]
    temp_sps = [p.get("temp_sp", 0) for p in points if p.get("temp_sp") is not None]
    print(f"\nUnique steps in this batch: {steps}")
    if temp_pvs:
        print(f"Temp PV Range: Min = {min(temp_pvs):.1f} °C, Max = {max(temp_pvs):.1f} °C")
    if temp_sps:
        print(f"Temp SP Range: Min = {min(temp_sps):.1f} °C, Max = {max(temp_sps):.1f} °C")
