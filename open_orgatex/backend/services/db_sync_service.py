"""
OpenOrgaTEX Database Synchronization Service
Bidirectional real-time and periodic synchronization between:
- PostgreSQL (Remote TimescaleDB pt_smm_jetflow @ 192.168.100.30:5433)
- SQLite (Local database open_orgatex/backend/data/orgatex_local.db)

Ensures exact parity whether the system is ONLINE or OFFLINE:
- Master Machines (machines)
- Production Batches (batch_headers)
- Formulas & Recipes (recipes, recipe_items)
- Master Programs & Procedures (program_components, steps, step_functions, step_function_parameters, program_headers)
"""

import os
import json
import socket
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from ..models.schema_pg import (
    Base, Machine, BatchHeader, Recipe, RecipeItem, 
    ProgramHeader, ProgramStep, ProgramStepFunction,
    ProgramComponent, Step, StepFunction, StepFunctionParameter
)

logger = logging.getLogger("orgatex.db_sync")

LOCAL_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/orgatex_local.db"))
PROGRAMS_CUSTOM_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/programs_custom.json"))
DEFAULT_SQLITE_URL = f"sqlite:///{LOCAL_DB_PATH}"

DEFAULT_PG_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+psycopg2://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow"
)
if DEFAULT_PG_URL.startswith("postgresql://"):
    DEFAULT_PG_URL = DEFAULT_PG_URL.replace("postgresql://", "postgresql+psycopg2://", 1)


class DBSyncService:
    _sqlite_engine = None
    _pg_engine = None
    _last_sync_time: Optional[str] = None
    _last_sync_stats: Dict[str, Any] = {}

    @classmethod
    def get_sqlite_engine(cls):
        if cls._sqlite_engine is None:
            os.makedirs(os.path.dirname(LOCAL_DB_PATH), exist_ok=True)
            cls._sqlite_engine = create_engine(
                DEFAULT_SQLITE_URL, 
                connect_args={"check_same_thread": False}, 
                poolclass=NullPool
            )
            Base.metadata.create_all(bind=cls._sqlite_engine)
        return cls._sqlite_engine

    @classmethod
    def is_pg_reachable(cls, timeout: float = 0.5) -> bool:
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

    @classmethod
    def get_pg_engine(cls):
        if not cls.is_pg_reachable():
            return None
        if cls._pg_engine is None:
            cur_url = os.getenv("DATABASE_URL", DEFAULT_PG_URL)
            if cur_url.startswith("postgresql://"):
                cur_url = cur_url.replace("postgresql://", "postgresql+psycopg2://", 1)
            try:
                cls._pg_engine = create_engine(
                    cur_url,
                    pool_pre_ping=True,
                    pool_size=10,
                    max_overflow=20,
                    pool_recycle=300,
                    connect_args={"connect_timeout": 2}
                )
                with cls._pg_engine.connect() as conn:
                    conn.execute(text("CREATE SCHEMA IF NOT EXISTS orgatex;"))
                    conn.execute(text("SET search_path TO public, orgatex;"))
                    conn.commit()
                Base.metadata.create_all(bind=cls._pg_engine)
            except Exception as e:
                logger.warning(f"Failed to create PG engine: {e}")
                cls._pg_engine = None
        return cls._pg_engine

    @classmethod
    def sync_machines(cls, pg_session, sqlite_session) -> Dict[str, int]:
        """Bidirectional sync of machines table."""
        stats = {"pulled_to_sqlite": 0, "pushed_to_pg": 0}
        
        pg_machines = {m.machine_no: m for m in pg_session.query(Machine).all()}
        sqlite_machines = {m.machine_no: m for m in sqlite_session.query(Machine).all()}

        # 1. Pull PG machines into SQLite
        for m_no, pg_m in pg_machines.items():
            if m_no not in sqlite_machines:
                new_m = Machine(
                    machine_no=pg_m.machine_no,
                    display_name=pg_m.display_name,
                    ip_address=pg_m.ip_address,
                    tcp_port=pg_m.tcp_port,
                    ftp_port=pg_m.ftp_port,
                    controller_type=pg_m.controller_type,
                    os_family=pg_m.os_family,
                    group_name=pg_m.group_name,
                    capacity_kg=pg_m.capacity_kg,
                    default_liquor_ratio=pg_m.default_liquor_ratio,
                    tanks_count=pg_m.tanks_count or 2,
                    share_folder_path=pg_m.share_folder_path,
                    status=pg_m.status or "ONLINE",
                    is_active=pg_m.is_active if pg_m.is_active is not None else True
                )
                sqlite_session.add(new_m)
                stats["pulled_to_sqlite"] += 1
            else:
                sq_m = sqlite_machines[m_no]
                sq_m.display_name = pg_m.display_name
                sq_m.ip_address = pg_m.ip_address
                sq_m.tcp_port = pg_m.tcp_port
                sq_m.ftp_port = pg_m.ftp_port
                sq_m.controller_type = pg_m.controller_type
                sq_m.share_folder_path = pg_m.share_folder_path
                sq_m.status = pg_m.status
                sq_m.is_active = pg_m.is_active

        # 2. Push SQLite-only machines into PG
        for m_no, sq_m in sqlite_machines.items():
            if m_no not in pg_machines:
                new_pg_m = Machine(
                    machine_no=sq_m.machine_no,
                    display_name=sq_m.display_name,
                    ip_address=sq_m.ip_address,
                    tcp_port=sq_m.tcp_port,
                    ftp_port=sq_m.ftp_port,
                    controller_type=sq_m.controller_type,
                    os_family=sq_m.os_family,
                    group_name=sq_m.group_name,
                    capacity_kg=sq_m.capacity_kg,
                    default_liquor_ratio=sq_m.default_liquor_ratio,
                    tanks_count=sq_m.tanks_count or 2,
                    share_folder_path=sq_m.share_folder_path,
                    status=sq_m.status or "ONLINE",
                    is_active=sq_m.is_active if sq_m.is_active is not None else True
                )
                pg_session.add(new_pg_m)
                stats["pushed_to_pg"] += 1

        sqlite_session.commit()
        pg_session.commit()
        return stats

    @classmethod
    def sync_batch_headers(cls, pg_session, sqlite_session) -> Dict[str, int]:
        """Bidirectional sync of batch_headers table based on batch_ref_no."""
        stats = {"pulled_to_sqlite": 0, "pushed_to_pg": 0, "status_updated": 0}

        pg_batches = {b.batch_ref_no: b for b in pg_session.query(BatchHeader).all() if b.batch_ref_no}
        sq_batches = {b.batch_ref_no: b for b in sqlite_session.query(BatchHeader).all() if b.batch_ref_no}

        # 1. Pull PG batches to SQLite
        for ref_no, pg_b in pg_batches.items():
            if ref_no not in sq_batches:
                new_sq = BatchHeader(
                    batch_ref_no=pg_b.batch_ref_no,
                    batch_no=pg_b.batch_no or f"LOT-{ref_no}",
                    machine_no=pg_b.machine_no,
                    program_no=pg_b.program_no or 1,
                    recipe_id=pg_b.recipe_id,
                    recipe_name=pg_b.recipe_name or "Reactive Dyeing Standard",
                    customer=pg_b.customer or "-",
                    article=pg_b.article or "-",
                    color_code=pg_b.color_code or "-",
                    color_name=pg_b.color_name or "-",
                    color_rgb=pg_b.color_rgb,
                    redye=pg_b.redye or 0,
                    procedure_no=pg_b.procedure_no,
                    fabric_weight_kg=pg_b.fabric_weight_kg or 350.0,
                    liquor_ratio=pg_b.liquor_ratio or 8.0,
                    total_water_l=pg_b.total_water_l or (float(pg_b.fabric_weight_kg or 350.0) * float(pg_b.liquor_ratio or 8.0)),
                    fabric_length=pg_b.fabric_length if pg_b.fabric_length is not None else 200.0,
                    import_state=pg_b.import_state or 0,
                    note1=pg_b.note1,
                    type_of_procedure_no=pg_b.type_of_procedure_no if pg_b.type_of_procedure_no is not None else 1,
                    process_type_1=pg_b.process_type_1 if pg_b.process_type_1 is not None else 1,
                    process_type_2=pg_b.process_type_2 if pg_b.process_type_2 is not None else 1,
                    parameters_json=pg_b.parameters_json,
                    status=pg_b.status or "QUEUED",
                    position=pg_b.position or 1,
                    planned_start_time=pg_b.planned_start_time,
                    created_at=pg_b.created_at
                )
                sqlite_session.add(new_sq)
                stats["pulled_to_sqlite"] += 1
            else:
                sq_b = sq_batches[ref_no]
                if sq_b.status != pg_b.status or sq_b.position != pg_b.position:
                    if pg_b.status in ("RUNNING", "COMPLETED", "WAITING_LA"):
                        sq_b.status = pg_b.status
                    elif sq_b.status in ("RUNNING", "COMPLETED", "WAITING_LA"):
                        pg_b.status = sq_b.status
                    sq_b.position = pg_b.position or sq_b.position
                    stats["status_updated"] += 1

        # 2. Push SQLite offline-created batches to PG
        for ref_no, sq_b in sq_batches.items():
            if ref_no not in pg_batches:
                m_in_pg = pg_session.query(Machine).filter(Machine.machine_no == sq_b.machine_no).first()
                if not m_in_pg:
                    sq_m = sqlite_session.query(Machine).filter(Machine.machine_no == sq_b.machine_no).first()
                    if sq_m:
                        pg_session.add(Machine(
                            machine_no=sq_m.machine_no,
                            display_name=sq_m.display_name,
                            ip_address=sq_m.ip_address,
                            tcp_port=sq_m.tcp_port,
                            ftp_port=sq_m.ftp_port,
                            controller_type=sq_m.controller_type,
                            os_family=sq_m.os_family,
                            group_name=sq_m.group_name,
                            capacity_kg=sq_m.capacity_kg,
                            default_liquor_ratio=sq_m.default_liquor_ratio,
                            share_folder_path=sq_m.share_folder_path,
                            status=sq_m.status or "ONLINE",
                            is_active=True
                        ))
                        pg_session.commit()

                new_pg = BatchHeader(
                    batch_ref_no=sq_b.batch_ref_no,
                    batch_no=sq_b.batch_no or f"LOT-{ref_no}",
                    machine_no=sq_b.machine_no,
                    program_no=sq_b.program_no or 1,
                    recipe_id=sq_b.recipe_id,
                    recipe_name=sq_b.recipe_name or "Reactive Dyeing Standard",
                    customer=sq_b.customer or "-",
                    article=sq_b.article or "-",
                    color_code=sq_b.color_code or "-",
                    color_name=sq_b.color_name or "-",
                    color_rgb=sq_b.color_rgb,
                    redye=sq_b.redye or 0,
                    procedure_no=sq_b.procedure_no,
                    fabric_weight_kg=sq_b.fabric_weight_kg or 350.0,
                    liquor_ratio=sq_b.liquor_ratio or 8.0,
                    total_water_l=sq_b.total_water_l or (float(sq_b.fabric_weight_kg or 350.0) * float(sq_b.liquor_ratio or 8.0)),
                    fabric_length=sq_b.fabric_length if sq_b.fabric_length is not None else 200.0,
                    import_state=sq_b.import_state or 0,
                    note1=sq_b.note1,
                    type_of_procedure_no=sq_b.type_of_procedure_no if sq_b.type_of_procedure_no is not None else 1,
                    process_type_1=sq_b.process_type_1 if sq_b.process_type_1 is not None else 1,
                    process_type_2=sq_b.process_type_2 if sq_b.process_type_2 is not None else 1,
                    parameters_json=sq_b.parameters_json,
                    status=sq_b.status or "QUEUED",
                    position=sq_b.position or 1,
                    planned_start_time=sq_b.planned_start_time,
                    created_at=sq_b.created_at
                )
                pg_session.add(new_pg)
                stats["pushed_to_pg"] += 1

        sqlite_session.commit()
        pg_session.commit()
        return stats

    @classmethod
    def sync_recipes(cls, pg_session, sqlite_session) -> Dict[str, int]:
        """Bidirectional sync of recipes & recipe_items."""
        stats = {"recipes_synced": 0}
        pg_recipes = {r.recipe_code: r for r in pg_session.query(Recipe).all()}
        sq_recipes = {r.recipe_code: r for r in sqlite_session.query(Recipe).all()}

        # 1. Pull PG to SQLite
        for code, pg_r in pg_recipes.items():
            if code not in sq_recipes:
                new_sq_r = Recipe(
                    recipe_code=pg_r.recipe_code,
                    recipe_name=pg_r.recipe_name,
                    customer_name=pg_r.customer_name,
                    fabric_type=pg_r.fabric_type,
                    standard_liquor_ratio=pg_r.standard_liquor_ratio,
                    notes=pg_r.notes
                )
                sqlite_session.add(new_sq_r)
                sqlite_session.flush()
                for item in pg_r.items:
                    sqlite_session.add(RecipeItem(
                        recipe_id=new_sq_r.recipe_id,
                        chemical_code=item.chemical_code,
                        chemical_name=item.chemical_name,
                        amount=item.amount,
                        unit=item.unit,
                        dosing_tank=item.dosing_tank
                    ))
                stats["recipes_synced"] += 1

        # 2. Push SQLite to PG
        for code, sq_r in sq_recipes.items():
            if code not in pg_recipes:
                new_pg_r = Recipe(
                    recipe_code=sq_r.recipe_code,
                    recipe_name=sq_r.recipe_name,
                    customer_name=sq_r.customer_name,
                    fabric_type=sq_r.fabric_type,
                    standard_liquor_ratio=sq_r.standard_liquor_ratio,
                    notes=sq_r.notes
                )
                pg_session.add(new_pg_r)
                pg_session.flush()
                for item in sq_r.items:
                    pg_session.add(RecipeItem(
                        recipe_id=new_pg_r.recipe_id,
                        chemical_code=item.chemical_code,
                        chemical_name=item.chemical_name,
                        amount=item.amount,
                        unit=item.unit,
                        dosing_tank=item.dosing_tank
                    ))
                stats["recipes_synced"] += 1

        sqlite_session.commit()
        pg_session.commit()
        return stats

    @classmethod
    def seed_programs_from_custom_json(cls, session) -> int:
        """Populates missing programs from programs_custom.json into the given session."""
        if not os.path.exists(PROGRAMS_CUSTOM_PATH):
            return 0
        try:
            with open(PROGRAMS_CUSTOM_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            existing_numbers = {
                str(c.number).strip().upper() 
                for c in session.query(ProgramComponent).filter(ProgramComponent.level == 1).all()
                if c.number
            }

            seeded = 0
            for p_key, prg in data.items():
                pno = str(prg.get("program_no") or p_key).strip().upper()
                if pno in existing_numbers:
                    continue

                pname = str(prg.get("program_name") or f"PROGRAM #{pno}").strip().upper()
                mcode = str(prg.get("machine_code") or "TD12")
                proc = ProgramComponent(
                    level=1,
                    type=1,
                    number=pno,
                    name=pname,
                    machine_code=mcode
                )
                session.add(proc)
                session.flush()

                for st in prg.get("steps", []):
                    new_s = Step(
                        position=st.get("step_no", 1),
                        parent_component_id=proc.id,
                        label=st.get("label", ""),
                        summary_temp=st.get("summary_temp"),
                        summary_time_min=st.get("summary_time_min"),
                        summary_water_l=st.get("summary_water_l")
                    )
                    session.add(new_s)
                    session.flush()

                    for fn in st.get("functions", []):
                        new_fn = StepFunction(
                            step_id=new_s.id,
                            resource_number=fn.get("column", 1),
                            function_number=fn.get("function_id", 0),
                            function_name=fn.get("name", "")
                        )
                        session.add(new_fn)
                        session.flush()

                        for idx, val in enumerate(fn.get("params") or []):
                            session.add(StepFunctionParameter(
                                step_function_id=new_fn.id,
                                function_parameter_number=idx + 1,
                                value=val
                            ))

                existing_numbers.add(pno)
                seeded += 1

            session.commit()
            return seeded
        except Exception as e:
            session.rollback()
            logger.warning(f"seed_programs_from_custom_json notice: {e}")
            return 0

    @classmethod
    def sync_programs(cls, pg_session, sqlite_session) -> Dict[str, int]:
        """
        Bidirectional synchronization of OrgaTEX EDX300 programs:
        ProgramComponent (Procedures & Treatments), Step, StepFunction, StepFunctionParameter,
        as well as legacy ProgramHeader and ProgramStep.
        """
        stats = {"pulled_to_sqlite": 0, "pushed_to_pg": 0, "steps_synced": 0}

        # Seed any missing programs from programs_custom.json first
        cls.seed_programs_from_custom_json(sqlite_session)
        cls.seed_programs_from_custom_json(pg_session)

        # 1. Sync ProgramComponent (Level 1: Procedures & Level 2: Treatments)
        pg_comps = {
            (c.level, str(c.number).strip().upper()): c 
            for c in pg_session.query(ProgramComponent).all() if c.number
        }
        sq_comps = {
            (c.level, str(c.number).strip().upper()): c 
            for c in sqlite_session.query(ProgramComponent).all() if c.number
        }

        # 1A. Pull from PG to SQLite
        for key, pg_c in pg_comps.items():
            if key not in sq_comps:
                new_sq_c = ProgramComponent(
                    level=pg_c.level,
                    type=pg_c.type or 1,
                    number=pg_c.number,
                    name=pg_c.name,
                    comment=pg_c.comment,
                    machine_code=pg_c.machine_code or "TD12",
                    content_type=pg_c.content_type or 0
                )
                sqlite_session.add(new_sq_c)
                sqlite_session.flush()

                for pg_s in pg_c.steps:
                    new_sq_s = Step(
                        position=pg_s.position,
                        parent_component_id=new_sq_c.id,
                        label=pg_s.label,
                        summary_temp=pg_s.summary_temp,
                        summary_time_min=pg_s.summary_time_min,
                        summary_water_l=pg_s.summary_water_l
                    )
                    sqlite_session.add(new_sq_s)
                    sqlite_session.flush()
                    stats["steps_synced"] += 1

                    for pg_fn in pg_s.functions:
                        new_sq_fn = StepFunction(
                            step_id=new_sq_s.id,
                            resource_number=pg_fn.resource_number or 1,
                            function_number=pg_fn.function_number,
                            function_name=pg_fn.function_name,
                            label=pg_fn.label or 0,
                            comment=pg_fn.comment
                        )
                        sqlite_session.add(new_sq_fn)
                        sqlite_session.flush()

                        for pg_p in pg_fn.parameters:
                            sqlite_session.add(StepFunctionParameter(
                                step_function_id=new_sq_fn.id,
                                function_parameter_number=pg_p.function_parameter_number,
                                value=pg_p.value,
                                attribute=pg_p.attribute or 0
                            ))
                stats["pulled_to_sqlite"] += 1
            else:
                sq_c = sq_comps[key]
                sq_c.name = pg_c.name
                sq_c.machine_code = pg_c.machine_code or sq_c.machine_code
                sq_c.comment = pg_c.comment
                if len(pg_c.steps) > 0 and len(sq_c.steps) == 0:
                    for pg_s in pg_c.steps:
                        new_sq_s = Step(
                            position=pg_s.position,
                            parent_component_id=sq_c.id,
                            label=pg_s.label,
                            summary_temp=pg_s.summary_temp,
                            summary_time_min=pg_s.summary_time_min,
                            summary_water_l=pg_s.summary_water_l
                        )
                        sqlite_session.add(new_sq_s)
                        sqlite_session.flush()
                        stats["steps_synced"] += 1

                        for pg_fn in pg_s.functions:
                            new_sq_fn = StepFunction(
                                step_id=new_sq_s.id,
                                resource_number=pg_fn.resource_number or 1,
                                function_number=pg_fn.function_number,
                                function_name=pg_fn.function_name,
                                label=pg_fn.label or 0,
                                comment=pg_fn.comment
                            )
                            sqlite_session.add(new_sq_fn)
                            sqlite_session.flush()

                            for pg_p in pg_fn.parameters:
                                sqlite_session.add(StepFunctionParameter(
                                    step_function_id=new_sq_fn.id,
                                    function_parameter_number=pg_p.function_parameter_number,
                                    value=pg_p.value,
                                    attribute=pg_p.attribute or 0
                                ))

        # 1B. Push from SQLite to PG
        for key, sq_c in sq_comps.items():
            if key not in pg_comps:
                new_pg_c = ProgramComponent(
                    level=sq_c.level,
                    type=sq_c.type or 1,
                    number=sq_c.number,
                    name=sq_c.name,
                    comment=sq_c.comment,
                    machine_code=sq_c.machine_code or "TD12",
                    content_type=sq_c.content_type or 0
                )
                pg_session.add(new_pg_c)
                pg_session.flush()

                for sq_s in sq_c.steps:
                    new_pg_s = Step(
                        position=sq_s.position,
                        parent_component_id=new_pg_c.id,
                        label=sq_s.label,
                        summary_temp=sq_s.summary_temp,
                        summary_time_min=sq_s.summary_time_min,
                        summary_water_l=sq_s.summary_water_l
                    )
                    pg_session.add(new_pg_s)
                    pg_session.flush()
                    stats["steps_synced"] += 1

                    for sq_fn in sq_s.functions:
                        new_pg_fn = StepFunction(
                            step_id=new_pg_s.id,
                            resource_number=sq_fn.resource_number or 1,
                            function_number=sq_fn.function_number,
                            function_name=sq_fn.function_name,
                            label=sq_fn.label or 0,
                            comment=sq_fn.comment
                        )
                        pg_session.add(new_pg_fn)
                        pg_session.flush()

                        for sq_p in sq_fn.parameters:
                            pg_session.add(StepFunctionParameter(
                                step_function_id=new_pg_fn.id,
                                function_parameter_number=sq_p.function_parameter_number,
                                value=sq_p.value,
                                attribute=sq_p.attribute or 0
                            ))
                stats["pushed_to_pg"] += 1

        # 2. Sync ProgramHeader (Legacy flat tables)
        pg_headers = {h.program_no: h for h in pg_session.query(ProgramHeader).all()}
        sq_headers = {h.program_no: h for h in sqlite_session.query(ProgramHeader).all()}

        for pno, pg_h in pg_headers.items():
            if pno not in sq_headers:
                new_sq_h = ProgramHeader(
                    program_no=pg_h.program_no,
                    program_name=pg_h.program_name,
                    fabric_type=pg_h.fabric_type,
                    estimated_duration_min=pg_h.estimated_duration_min,
                    compiled_file_path=pg_h.compiled_file_path
                )
                sqlite_session.add(new_sq_h)
                sqlite_session.flush()
                for st in pg_h.steps:
                    new_st = ProgramStep(
                        program_no=new_sq_h.program_no,
                        step_no=st.step_no,
                        label=st.label
                    )
                    sqlite_session.add(new_st)
                    sqlite_session.flush()
                    for fn in st.functions:
                        sqlite_session.add(ProgramStepFunction(
                            step_id=new_st.id,
                            column_no=fn.column_no,
                            function_id=fn.function_id,
                            param_1=fn.param_1,
                            param_2=fn.param_2
                        ))

        for pno, sq_h in sq_headers.items():
            if pno not in pg_headers:
                new_pg_h = ProgramHeader(
                    program_no=sq_h.program_no,
                    program_name=sq_h.program_name,
                    fabric_type=sq_h.fabric_type,
                    estimated_duration_min=sq_h.estimated_duration_min,
                    compiled_file_path=sq_h.compiled_file_path
                )
                pg_session.add(new_pg_h)
                pg_session.flush()
                for st in sq_h.steps:
                    new_st = ProgramStep(
                        program_no=new_pg_h.program_no,
                        step_no=st.step_no,
                        label=st.label
                    )
                    pg_session.add(new_st)
                    pg_session.flush()
                    for fn in st.functions:
                        pg_session.add(ProgramStepFunction(
                            step_id=new_st.id,
                            column_no=fn.column_no,
                            function_id=fn.function_id,
                            param_1=fn.param_1,
                            param_2=fn.param_2
                        ))

        sqlite_session.commit()
        pg_session.commit()
        return stats

    @classmethod
    def sync_all(cls) -> Dict[str, Any]:
        """Executes full bidirectional sync between PostgreSQL and SQLite."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. If offline, ensure SQLite has seeded programs from programs_custom.json
        sq_eng = cls.get_sqlite_engine()
        if not cls.is_pg_reachable():
            SqSessionMaker = sessionmaker(bind=sq_eng)
            sq_session = SqSessionMaker()
            seeded = cls.seed_programs_from_custom_json(sq_session)
            sq_session.close()

            msg = f"PostgreSQL (192.168.100.30:5433) offline. Mode offline lokal aktif ({seeded} program lokal di-seed)."
            logger.info(msg)
            cls._last_sync_stats = {
                "status": "OFFLINE",
                "postgres_online": False,
                "synced_at": now_str,
                "programs_seeded": seeded,
                "message": msg
            }
            return cls._last_sync_stats

        pg_eng = cls.get_pg_engine()
        if not pg_eng or not sq_eng:
            return {
                "status": "ERROR",
                "postgres_online": False,
                "synced_at": now_str,
                "message": "Engine database tidak dapat diinisialisasi."
            }

        PgSessionMaker = sessionmaker(bind=pg_eng)
        SqSessionMaker = sessionmaker(bind=sq_eng)

        pg_session = PgSessionMaker()
        sq_session = SqSessionMaker()

        try:
            m_stats = cls.sync_machines(pg_session, sq_session)
            b_stats = cls.sync_batch_headers(pg_session, sq_session)
            r_stats = cls.sync_recipes(pg_session, sq_session)
            p_stats = cls.sync_programs(pg_session, sq_session)

            cls._last_sync_time = now_str
            cls._last_sync_stats = {
                "status": "ONLINE_SYNCED",
                "postgres_online": True,
                "synced_at": now_str,
                "machines": m_stats,
                "batches": b_stats,
                "recipes": r_stats,
                "programs": p_stats,
                "message": (
                    f"Sinkronisasi PostgreSQL & SQLite berhasil pada {now_str}. "
                    f"Program: +{p_stats['pulled_to_sqlite']} pull, +{p_stats['pushed_to_pg']} push. "
                    f"Batches: +{b_stats['pulled_to_sqlite']} pull, +{b_stats['pushed_to_pg']} push. "
                    f"Mesin: +{m_stats['pulled_to_sqlite']} pull, +{m_stats['pushed_to_pg']} push."
                )
            }
            logger.info(cls._last_sync_stats["message"])
            return cls._last_sync_stats

        except Exception as e:
            pg_session.rollback()
            sq_session.rollback()
            logger.error(f"Error during database sync: {e}")
            cls._last_sync_stats = {
                "status": "ERROR",
                "postgres_online": True,
                "synced_at": now_str,
                "error": str(e),
                "message": f"Sinkronisasi gagal: {str(e)}"
            }
            return cls._last_sync_stats

        finally:
            pg_session.close()
            sq_session.close()

    @classmethod
    def mirror_batch_to_sqlite(cls, batch_header_obj_or_dict):
        """Real-time mirror of batch_headers to local SQLite."""
        try:
            sq_eng = cls.get_sqlite_engine()
            SqSession = sessionmaker(bind=sq_eng)
            sq_session = SqSession()

            b = batch_header_obj_or_dict
            if hasattr(b, "__dict__"):
                ref_no = getattr(b, "batch_ref_no", None)
                batch_no = getattr(b, "batch_no", None)
                mach = getattr(b, "machine_no", "DA01")
                prog = getattr(b, "program_no", 1)
                rec_name = getattr(b, "recipe_name", "Reactive Dyeing Standard")
                cust = getattr(b, "customer", "-")
                art = getattr(b, "article", "-")
                c_code = getattr(b, "color_code", "-")
                c_name = getattr(b, "color_name", "-")
                c_rgb = getattr(b, "color_rgb", None)
                redye = getattr(b, "redye", 0) or 0
                proc_no = getattr(b, "procedure_no", None)
                weight = float(getattr(b, "fabric_weight_kg", 350.0) or 350.0)
                lr = float(getattr(b, "liquor_ratio", 8.0) or 8.0)
                water = float(getattr(b, "total_water_l", weight * lr) or (weight * lr))
                f_len = getattr(b, "fabric_length", 200.0)
                imp_state = getattr(b, "import_state", 0) or 0
                note1 = getattr(b, "note1", None)
                type_proc = getattr(b, "type_of_procedure_no", 1)
                proc_t1 = getattr(b, "process_type_1", 1)
                proc_t2 = getattr(b, "process_type_2", 1)
                params_json = getattr(b, "parameters_json", None)
                stat = getattr(b, "status", "QUEUED")
                pos = getattr(b, "position", 1)
            else:
                ref_no = b.get("reference_no") or b.get("batch_ref_no")
                batch_no = b.get("batch_no")
                mach = b.get("machine_no", "DA01")
                prog = b.get("program_no", 1)
                rec_name = b.get("recipe_name", "Reactive Dyeing Standard")
                cust = b.get("customer", "-")
                art = b.get("article", "-")
                c_code = b.get("color_code", "-")
                c_name = b.get("color_name", "-")
                c_rgb = b.get("color_rgb")
                redye = b.get("redye", 0) or 0
                proc_no = b.get("procedure_no")
                weight = float(b.get("fabric_weight_kg", 350.0) or 350.0)
                lr = float(b.get("liquor_ratio", 8.0) or 8.0)
                water = float(b.get("total_water_l", weight * lr) or (weight * lr))
                f_len = b.get("fabric_length", 200.0)
                imp_state = b.get("import_state", 0) or 0
                note1 = b.get("note1")
                type_proc = b.get("type_of_procedure_no", 1)
                proc_t1 = b.get("process_type_1", 1)
                proc_t2 = b.get("process_type_2", 1)
                params_json = b.get("parameters_json")
                stat = b.get("status", "QUEUED")
                pos = b.get("position", 1)

            if not ref_no:
                return

            existing = sq_session.query(BatchHeader).filter(BatchHeader.batch_ref_no == ref_no).first()
            if existing:
                existing.batch_no = batch_no or existing.batch_no
                existing.machine_no = mach
                existing.program_no = prog
                existing.recipe_name = rec_name
                existing.customer = cust
                existing.article = art
                existing.color_code = c_code
                existing.color_name = c_name
                existing.color_rgb = c_rgb
                existing.redye = redye
                existing.procedure_no = proc_no
                existing.fabric_weight_kg = weight
                existing.liquor_ratio = lr
                existing.total_water_l = water
                existing.fabric_length = f_len
                existing.import_state = imp_state
                existing.note1 = note1
                existing.type_of_procedure_no = type_proc
                existing.process_type_1 = proc_t1
                existing.process_type_2 = proc_t2
                existing.parameters_json = params_json
                existing.status = stat
                existing.position = pos
            else:
                new_sq = BatchHeader(
                    batch_ref_no=ref_no,
                    batch_no=batch_no or f"LOT-{ref_no}",
                    machine_no=mach,
                    program_no=prog,
                    recipe_name=rec_name,
                    customer=cust,
                    article=art,
                    color_code=c_code,
                    color_name=c_name,
                    color_rgb=c_rgb,
                    redye=redye,
                    procedure_no=proc_no,
                    fabric_weight_kg=weight,
                    liquor_ratio=lr,
                    total_water_l=water,
                    fabric_length=f_len,
                    import_state=imp_state,
                    note1=note1,
                    type_of_procedure_no=type_proc,
                    process_type_1=proc_t1,
                    process_type_2=proc_t2,
                    parameters_json=params_json,
                    status=stat,
                    position=pos,
                    created_at=datetime.now()
                )
                sq_session.add(new_sq)

            sq_session.commit()
            sq_session.close()
        except Exception as e:
            logger.warning(f"mirror_batch_to_sqlite notice: {e}")

    @classmethod
    def mirror_program_to_sqlite(cls, p):
        """Real-time mirror of a ProgramComponent/Procedure to local SQLite."""
        try:
            sq_eng = cls.get_sqlite_engine()
            SqSession = sessionmaker(bind=sq_eng)
            sq = SqSession()

            p_no = str(getattr(p, "program_no", p.get("program_no") if isinstance(p, dict) else 1))
            p_name = str(getattr(p, "program_name", p.get("program_name", "") if isinstance(p, dict) else "")).strip().upper()
            m_code = str(getattr(p, "machine_code", p.get("machine_code", "TD12") if isinstance(p, dict) else "TD12"))
            steps = getattr(p, "steps", p.get("steps", []) if isinstance(p, dict) else [])

            proc = sq.query(ProgramComponent).filter(
                ProgramComponent.number == p_no,
                ProgramComponent.level == 1
            ).first()

            if not proc:
                proc = ProgramComponent(
                    level=1,
                    type=1,
                    number=p_no,
                    name=p_name,
                    machine_code=m_code
                )
                sq.add(proc)
                sq.flush()
            else:
                proc.name = p_name
                proc.machine_code = m_code
                proc.modification_time = datetime.now()

            if steps:
                sq.query(Step).filter(Step.parent_component_id == proc.id).delete()
                for st in steps:
                    s_dict = st.dict() if hasattr(st, "dict") else dict(st)
                    new_s = Step(
                        position=s_dict.get("step_no", 1),
                        parent_component_id=proc.id,
                        label=s_dict.get("label", ""),
                        summary_temp=s_dict.get("summary_temp"),
                        summary_time_min=s_dict.get("summary_time_min"),
                        summary_water_l=s_dict.get("summary_water_l")
                    )
                    sq.add(new_s)
                    sq.flush()

                    for fn in s_dict.get("functions", []):
                        fn_dict = fn.dict() if hasattr(fn, "dict") else dict(fn)
                        new_fn = StepFunction(
                            step_id=new_s.id,
                            resource_number=fn_dict.get("column", 1),
                            function_number=fn_dict.get("function_id", 0),
                            function_name=fn_dict.get("name", "")
                        )
                        sq.add(new_fn)
                        sq.flush()

                        for idx, val in enumerate(fn_dict.get("params") or []):
                            sq.add(StepFunctionParameter(
                                step_function_id=new_fn.id,
                                function_parameter_number=idx + 1,
                                value=val
                            ))

            sq.commit()
            sq.close()
        except Exception as e:
            logger.warning(f"mirror_program_to_sqlite notice: {e}")

    @classmethod
    def get_sync_status(cls) -> Dict[str, Any]:
        """Returns the current database sync status and health."""
        pg_online = cls.is_pg_reachable()
        return {
            "postgres_online": pg_online,
            "postgres_host": "192.168.100.30:5433",
            "postgres_db": "pt_smm_jetflow",
            "sqlite_db_path": LOCAL_DB_PATH,
            "last_synced_at": cls._last_sync_time or "Belum sinkron otomatis",
            "last_stats": cls._last_sync_stats,
            "mode": "HYBRID_BIDIRECTIONAL_AUTO_SYNC",
            "status": "ONLINE" if pg_online else "OFFLINE_LOCAL_ACTIVE"
        }
