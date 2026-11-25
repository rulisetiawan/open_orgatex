import sys
sys.path.append('services/da-batch-worker')
import worker

res = worker.load_program_from_db('10B', 0, 'PROGRAM 30 MCT F', '')
print("Found:", bool(res))
if res:
    print("program_no:", res["program_no"], "| program_name:", res["program_name"])
    print("total scada_steps:", len(res["scada_steps"]))
    print("Sample Step 4:", res["scada_steps"][3])
