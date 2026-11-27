"""
OpenOrgaTEX Database Utility Service (PostgreSQL Only)
All local SQLite mirroring and bidirectional SQLite sync functions have been removed.
All database operations run directly against PostgreSQL (pt_smm_jetflow).
"""

import os
import socket
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse

from ..models.schema_pg import (
    ProgramComponent,
    ProgramComponentItem,
    ProgramComponent2Group,
)

logger = logging.getLogger("orgatex.db_sync")

DEFAULT_PG_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow",
)
if DEFAULT_PG_URL.startswith("postgresql://"):
    DEFAULT_PG_URL = DEFAULT_PG_URL.replace("postgresql://", "postgresql+psycopg2://", 1)


class DBSyncService:
    """PostgreSQL-only utility helpers (local SQLite sync/mirror removed)."""

    @classmethod
    def is_pg_reachable(cls, timeout: float = 1.0) -> bool:
        cur_url = os.getenv("DATABASE_URL", DEFAULT_PG_URL)
        if cur_url.startswith("sqlite"):
            return False
        try:
            parsed = urlparse(cur_url)
            host = parsed.hostname or "192.168.100.30"
            port = parsed.port or 5433
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except Exception:
            return False

    @staticmethod
    def _norm_machine(machine_code: Optional[str]) -> str:
        clean = str(machine_code or "TD12").strip().upper()
        if clean.startswith("MESIN_"):
            clean = clean[6:]
        return clean or "TD12"

    @staticmethod
    def _norm_prog_no(number: Any) -> str:
        s = str(number or "").strip()
        if s.isdigit():
            return str(int(s))
        return s.upper()

    @classmethod
    def deduplicate_program_components(cls, session) -> int:
        """
        Removes duplicate ProgramComponent rows within the SAME machine
        (same level, normalized machine_code, normalized number) in PostgreSQL.
        Different machines are allowed to share the same program number.
        """
        rows = session.query(ProgramComponent).order_by(ProgramComponent.id.asc()).all()
        groups: Dict[tuple, List[ProgramComponent]] = {}
        for row in rows:
            m_norm = cls._norm_machine(row.machine_code)
            n_norm = cls._norm_prog_no(row.number)
            key = (row.level, m_norm, n_norm)
            groups.setdefault(key, []).append(row)

        removed = 0
        for (lvl, m_norm, n_norm), items in groups.items():
            items_sorted = sorted(
                items,
                key=lambda c: (len(c.steps or []), str(c.modification_time or ""), c.id),
                reverse=True,
            )
            keeper = items_sorted[0]
            if keeper.machine_code != m_norm:
                keeper.machine_code = m_norm
            if keeper.number != n_norm:
                keeper.number = n_norm

            for dup in items_sorted[1:]:
                session.query(ProgramComponentItem).filter(
                    ProgramComponentItem.parent_component_id == dup.id
                ).update({"parent_component_id": keeper.id}, synchronize_session=False)
                session.query(ProgramComponentItem).filter(
                    ProgramComponentItem.program_component_id == dup.id
                ).update({"program_component_id": keeper.id}, synchronize_session=False)
                session.query(ProgramComponent2Group).filter(
                    ProgramComponent2Group.program_component_id == dup.id
                ).update({"program_component_id": keeper.id}, synchronize_session=False)
                session.delete(dup)
                removed += 1

        if removed > 0 or any(
            r.machine_code != cls._norm_machine(r.machine_code)
            or r.number != cls._norm_prog_no(r.number)
            for r in rows
        ):
            session.commit()
        return removed

    @classmethod
    def sync_all(cls) -> Dict[str, Any]:
        """Local SQLite sync is disabled; all operations write directly to PostgreSQL."""
        pg_online = cls.is_pg_reachable()
        return {
            "status": "postgres_only" if pg_online else "postgres_unreachable",
            "pg_online": pg_online,
            "sqlite_enabled": False,
            "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "message": (
                "Mode PostgreSQL-only aktif (database lokal SQLite sudah dihapus/dinonaktifkan)."
                if pg_online
                else "PostgreSQL tidak terjangkau. Database lokal SQLite sudah dinonaktifkan."
            ),
        }

    @classmethod
    def get_sync_status(cls) -> Dict[str, Any]:
        """Returns PostgreSQL-only connectivity status."""
        pg_online = cls.is_pg_reachable()
        return {
            "mode": "POSTGRES_ONLY",
            "pg_online": pg_online,
            "sqlite_enabled": False,
            "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
