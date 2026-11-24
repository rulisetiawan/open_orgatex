import sys
import os
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("./open_orgatex"))

import time
from open_orgatex.backend.database import get_db, init_db
from open_orgatex.backend.models.schema_pg import Machine
from open_orgatex.backend.services.ingestion import LogIngestionService

def test_ingest():
    init_db()
    for db in get_db():
        m = db.query(Machine).filter(Machine.machine_no == '10B').first()
        if not m:
            print("Machine 10B not found!")
            return
        print(f"Testing ingestion for {m.machine_no} ({m.ip_address})...")
        t0 = time.time()
        res = LogIngestionService.ingest_machine_on_the_fly(db, m)
        dur = time.time() - t0
        print(f"Ingestion finished in {dur:.2f}s!")
        print(f"Status: {res.get('status')}, Temp: {res.get('temp_pv')}, Batch: {res.get('current_batch')}, Step: {res.get('current_step')}")
        print(f"New points persisted: {res.get('new_points_persisted')}, Total points: {res.get('total_points')}")
        break

if __name__ == "__main__":
    test_ingest()
