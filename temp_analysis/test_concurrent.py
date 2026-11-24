import sys
import os
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("./open_orgatex"))

import time
import socket
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from open_orgatex.backend.database import get_db, init_db
from open_orgatex.backend.models.schema_pg import Machine
from open_orgatex.backend.services.ingestion import LogIngestionService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_concurrency")

def is_controller_online(ip: str, port: int = 21, timeout: float = 0.4) -> bool:
    if not ip or ip in ("127.0.0.1", "0.0.0.0", "localhost"):
        return False
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False

def ingest_one(machine_no: str):
    t0 = time.time()
    for db in get_db():
        m = db.query(Machine).filter(Machine.machine_no == machine_no).first()
        if not m:
            return machine_no, False, 0.0, "Not found"
        try:
            res = LogIngestionService.ingest_machine_on_the_fly(db, m)
            dur = time.time() - t0
            return machine_no, True, dur, f"Batch={res.get('current_batch')}, Step={res.get('current_step')}"
        except Exception as e:
            dur = time.time() - t0
            return machine_no, False, dur, str(e)

def test_concurrent_run():
    init_db()
    t_start = time.time()
    online_m = []
    
    for db in get_db():
        machines = db.query(Machine).filter(Machine.is_active == True, Machine.ip_address.isnot(None)).all()
        for m in machines:
            if is_controller_online(m.ip_address, m.ftp_port or 21, timeout=0.3):
                online_m.append(m.machine_no)
        break

    print(f"Total online machines detected: {len(online_m)}")

    # Run with 6 worker threads in parallel
    max_workers = 6
    completed = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(ingest_one, mno): mno for mno in online_m}
        for fut in as_completed(futures):
            mno, ok, dur, info = fut.result()
            completed += 1
            status_str = "OK" if ok else "FAIL"
            print(f"[{completed}/{len(online_m)}] {mno} ({dur:.2f}s): {status_str} -> {info}")

    total_time = time.time() - t_start
    print(f"\n==========================================")
    print(f"FINISHED ALL {len(online_m)} MACHINES IN {total_time:.2f}s WITH {max_workers} WORKERS!")
    print(f"==========================================")

if __name__ == "__main__":
    test_concurrent_run()
