import sys
import os
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("./open_orgatex"))

import time
import socket
import logging
from open_orgatex.backend.database import get_db, init_db
from open_orgatex.backend.models.schema_pg import Machine
from open_orgatex.backend.services.ingestion import LogIngestionService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_ingest_worker")

def is_controller_online(ip: str, port: int = 21, timeout: float = 0.6) -> bool:
    if not ip or ip in ("127.0.0.1", "0.0.0.0"):
        return False
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False

def run_test_cycle():
    init_db()
    for db in get_db():
        machines = db.query(Machine).filter(Machine.is_active == True, Machine.ip_address.isnot(None)).all()
        print(f"Total active machines with IP: {len(machines)}")
        
        # Test only online machines
        online_machines = []
        for m in machines:
            if is_controller_online(m.ip_address, m.ftp_port or 21, timeout=0.5):
                online_machines.append(m)

        print(f"Online controllers responding to FTP: {len(online_machines)}")
        for om in online_machines:
            print(f"  -> {om.machine_no} at {om.ip_address}")
            t0 = time.time()
            try:
                res = LogIngestionService.ingest_machine_on_the_fly(db, om)
                dur = time.time() - t0
                print(f"     Ingested in {dur:.2f}s: batch={res.get('current_batch')}, step={res.get('current_step')}, points={res.get('new_points_persisted')}")
            except Exception as e:
                print(f"     Error ingesting {om.machine_no}: {e}")
        break

if __name__ == "__main__":
    run_test_cycle()
