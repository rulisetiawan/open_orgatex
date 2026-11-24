"""
Background Controller Periodic Ingestion Service
Periodically polls active machines in factory LAN concurrently:
- Reads STATUS.ACT (Batch, Step, Program, Machine State)
- Reads ALARM.ACT & ALARMS.LOG (Active alarms & operator holds)
- Reads PR<batch>.LOG (Cyclic curve datalog into datalog_cyclic_records)
Uses concurrent ThreadPoolExecutor (max_workers=6) to comfortably process 60-100+ machines
in ~20 seconds without blocking the event loop or overloading controller Windows CE sockets.
"""

import time
import socket
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Tuple

from ..database import get_db
from ..models.schema_pg import Machine
from .ingestion import LogIngestionService

logger = logging.getLogger("orgatex.background_ingest")

# Concurrency tuning: 6 workers can process ~60-80 machines in ~20s
MAX_CONCURRENT_WORKERS = 6
SOCKET_TIMEOUT = 0.35


def is_controller_online(ip: str, port: int = 21, timeout: float = SOCKET_TIMEOUT) -> bool:
    """Fast socket check to prevent waiting on offline controllers."""
    if not ip or ip in ("127.0.0.1", "0.0.0.0", "localhost"):
        return False
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False


def _ingest_machine_worker(machine_no: str) -> Tuple[str, bool, float, str]:
    """Worker function for single machine ingestion with dedicated DB session."""
    t0 = time.time()
    for db in get_db():
        m = db.query(Machine).filter(Machine.machine_no == machine_no).first()
        if not m:
            return machine_no, False, 0.0, "Machine not found in DB"
        try:
            res = LogIngestionService.ingest_machine_on_the_fly(db, m)
            dur = time.time() - t0
            info = f"Batch={res.get('current_batch')}, Step={res.get('current_step')}, NewPts={res.get('new_points_persisted')}"
            return machine_no, True, dur, info
        except Exception as e:
            dur = time.time() - t0
            return machine_no, False, dur, str(e)
    return machine_no, False, 0.0, "DB session unavailable"


class BackgroundIngestionService:
    _is_running = False

    @classmethod
    def run_cycle(cls) -> Dict[str, Any]:
        """
        Executes one full ingestion cycle across all active machines concurrently.
        Designed to be called via asyncio.to_thread every 60 seconds.
        """
        if cls._is_running:
            logger.info("Previous background ingestion cycle still in progress. Skipping overlapping run.")
            return {"status": "skipped", "reason": "in_progress"}

        cls._is_running = True
        t0 = time.time()
        stats = {
            "total_machines": 0,
            "online_machines": 0,
            "ingested_count": 0,
            "errors": 0,
            "elapsed_seconds": 0.0
        }

        try:
            # 1. Fetch active machines and identify online controllers
            online_machine_nos: List[str] = []
            for db in get_db():
                active_machines: List[Machine] = (
                    db.query(Machine)
                    .filter(Machine.is_active == True, Machine.ip_address.isnot(None))
                    .order_by(Machine.machine_no)
                    .all()
                )
                stats["total_machines"] = len(active_machines)

                for m in active_machines:
                    ftp_port = getattr(m, "ftp_port", None) or 21
                    if is_controller_online(m.ip_address, ftp_port, timeout=SOCKET_TIMEOUT):
                        online_machine_nos.append(m.machine_no)

                break  # get_db() generator break

            stats["online_machines"] = len(online_machine_nos)

            # 2. Process all online machines concurrently with bounded worker pool
            if online_machine_nos:
                workers = min(MAX_CONCURRENT_WORKERS, len(online_machine_nos))
                with ThreadPoolExecutor(max_workers=workers) as executor:
                    futures = {executor.submit(_ingest_machine_worker, mno): mno for mno in online_machine_nos}
                    for fut in as_completed(futures):
                        mno, ok, dur, info = fut.result()
                        if ok:
                            stats["ingested_count"] += 1
                            logger.debug(f"[BG Ingest Worker] {mno} ({dur:.2f}s): {info}")
                        else:
                            stats["errors"] += 1
                            logger.warning(f"[BG Ingest Worker Error] {mno} ({dur:.2f}s): {info}")

        except Exception as e:
            logger.error(f"[BG Ingest] Error during concurrent ingestion cycle: {e}")
        finally:
            cls._is_running = False
            stats["elapsed_seconds"] = round(time.time() - t0, 2)
            logger.info(
                f"[BG Ingest Completed] {stats['ingested_count']}/{stats['online_machines']} online machines processed "
                f"({stats['total_machines']} total) in {stats['elapsed_seconds']}s with {MAX_CONCURRENT_WORKERS} workers (Errors: {stats['errors']})"
            )

        return stats
