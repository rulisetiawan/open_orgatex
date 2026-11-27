"""
OpenOrgaTEX Database Engine (PostgreSQL Only)
Connects strictly to PostgreSQL (pt_smm_jetflow, public schema).
Local SQLite fallback and mirroring have been removed.
"""

import os
import socket
import logging
from urllib.parse import urlparse
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from .models.schema_pg import Base

logger = logging.getLogger("orgatex.database")

default_pg_url = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow"
)

if default_pg_url.startswith("postgresql://"):
    default_pg_url = default_pg_url.replace("postgresql://", "postgresql+psycopg2://", 1)

DATABASE_URL = default_pg_url

engine = None
SessionLocal = None
IS_POSTGRES = True


def ensure_batch_header_columns(target_engine, is_postgres: bool = True):
    """
    Ensures public.batch_headers table has all columns required by the planning interface:
    batch_no, recipe_name, article, color_code, color_name, total_water_l, position
    """
    try:
        with target_engine.connect() as conn:
            needed = [
                ("batch_no", "VARCHAR(100)"),
                ("recipe_name", "VARCHAR(255)"),
                ("article", "VARCHAR(255)"),
                ("color_code", "VARCHAR(100)"),
                ("color_name", "VARCHAR(100)"),
                ("color_rgb", "INT"),
                ("redye", "INT DEFAULT 0"),
                ("procedure_no", "VARCHAR(255)"),
                ("total_water_l", "NUMERIC(12, 2)"),
                ("fabric_length", "NUMERIC(10, 2) DEFAULT 200.0"),
                ("fabric_type", "VARCHAR(50)"),
                ("color_shade", "VARCHAR(30)"),
                ("fabric_gsm", "NUMERIC(8, 2)"),
                ("dye_type", "VARCHAR(50)"),
                ("chamber_count", "INT"),
                ("import_state", "INT DEFAULT 0"),
                ("note1", "TEXT"),
                ("type_of_procedure_no", "INT DEFAULT 1"),
                ("process_type_1", "INT DEFAULT 1"),
                ("process_type_2", "INT DEFAULT 1"),
                ("parameters_json", "TEXT"),
                ("resolved_formula_params_json", "TEXT"),
                ("position", "INT DEFAULT 1")
            ]
            for col_name, col_type in needed:
                conn.execute(text(f"ALTER TABLE public.batch_headers ADD COLUMN IF NOT EXISTS {col_name} {col_type};"))
            try:
                conn.execute(text("ALTER TABLE public.batch_headers ALTER COLUMN fabric_weight_kg TYPE NUMERIC(12, 2);"))
                conn.execute(text("ALTER TABLE public.batch_headers ALTER COLUMN total_water_l TYPE NUMERIC(12, 2);"))
            except Exception:
                pass

            conn.execute(text("UPDATE public.batch_headers SET batch_no = 'LOT-' || batch_ref_no WHERE batch_no IS NULL OR batch_no = '';"))
            conn.execute(text("UPDATE public.batch_headers SET recipe_name = 'Reactive Dyeing Standard' WHERE recipe_name IS NULL OR recipe_name = '';"))
            conn.execute(text("UPDATE public.batch_headers SET total_water_l = fabric_weight_kg * liquor_ratio WHERE total_water_l IS NULL;"))
            conn.commit()
    except Exception as e:
        logger.warning(f"ensure_batch_header_columns notice: {e}")


def ensure_essential_machines(target_engine, is_postgres: bool = True):
    """
    Ensures public.machines table has orgatex_id column and essential machines DA01 and M_95 exist
    so Foreign Key references in batch_headers always succeed.
    """
    try:
        with target_engine.connect() as conn:
            conn.execute(text("ALTER TABLE public.machines ADD COLUMN IF NOT EXISTS orgatex_id VARCHAR(50);"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_public_machines_orgatex_id ON public.machines (orgatex_id);"))
            conn.execute(text("""
                INSERT INTO public.machines (
                    machine_no, display_name, ip_address, tcp_port, ftp_port,
                    controller_type, os_family, group_name, capacity_kg, default_liquor_ratio,
                    tanks_count, share_folder_path, status, is_active
                ) VALUES (
                    'DA01', 'SETEX 797CE Mesin DA01', '192.168.1.95', 50100, 21,
                    'SETEX 797CE (Windows CE)', 'WindowsCE', 'Dyeing Sample / DA', 350.0, 8.0,
                    2, '/Flashdisk/SC797CE', 'ONLINE', TRUE
                ) ON CONFLICT (machine_no) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    ip_address = EXCLUDED.ip_address,
                    controller_type = EXCLUDED.controller_type,
                    share_folder_path = EXCLUDED.share_folder_path;
            """))
            conn.execute(text("""
                INSERT INTO public.machines (
                    machine_no, display_name, ip_address, tcp_port, ftp_port,
                    controller_type, os_family, group_name, capacity_kg, default_liquor_ratio,
                    tanks_count, share_folder_path, status, is_active
                ) VALUES (
                    'M_95', 'SETEX 797CE Mesin DA01 (M_95)', '192.168.1.95', 50100, 21,
                    'SETEX 797CE (Windows CE)', 'WindowsCE', 'Dyeing Sample / DA', 350.0, 8.0,
                    2, '/Flashdisk/SC797CE', 'ONLINE', TRUE
                ) ON CONFLICT (machine_no) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    ip_address = EXCLUDED.ip_address,
                    controller_type = EXCLUDED.controller_type,
                    share_folder_path = EXCLUDED.share_folder_path;
            """))
            conn.commit()
    except Exception as e:
        logger.warning(f"ensure_essential_machines notice: {e}")


def ensure_queue_tables(target_engine, is_postgres: bool = True):
    """
    Ensures public.machine_queues table exists in PostgreSQL
    and synchronizes it from active batch_headers so the queue is always saved in PostgreSQL.
    """
    try:
        with target_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS public.machine_queues (
                    id BIGSERIAL PRIMARY KEY,
                    machine_no VARCHAR(50) NOT NULL,
                    batch_ref_no VARCHAR(50) NOT NULL,
                    batch_no VARCHAR(100),
                    program_no INT DEFAULT 1,
                    recipe_name VARCHAR(255),
                    customer VARCHAR(150),
                    article VARCHAR(255),
                    color_code VARCHAR(100),
                    color_name VARCHAR(100),
                    fabric_weight_kg NUMERIC(8, 2) DEFAULT 350.0,
                    liquor_ratio NUMERIC(5, 2) DEFAULT 8.0,
                    total_water_l NUMERIC(10, 2),
                    position INT NOT NULL DEFAULT 1,
                    status VARCHAR(30) DEFAULT 'QUEUED',
                    dispatched_at TIMESTAMPTZ,
                    dispatched_to_ip VARCHAR(50),
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    CONSTRAINT uq_machine_batch_queue UNIQUE (machine_no, batch_ref_no)
                );
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_mq_mach ON public.machine_queues(machine_no);"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_mq_ref ON public.machine_queues(batch_ref_no);"))

            count = conn.execute(text("SELECT COUNT(*) FROM public.machine_queues")).scalar() or 0
            if count == 0:
                conn.execute(text("""
                    INSERT INTO public.machine_queues (
                        machine_no, batch_ref_no, batch_no, program_no, recipe_name,
                        customer, article, color_code, color_name, fabric_weight_kg,
                        liquor_ratio, total_water_l, position, status
                    )
                    SELECT
                        machine_no, batch_ref_no, batch_no, program_no, recipe_name,
                        customer, article, color_code, color_name, fabric_weight_kg,
                        liquor_ratio, total_water_l, position, status
                    FROM public.batch_headers
                    ON CONFLICT (machine_no, batch_ref_no) DO NOTHING;
                """))
            conn.commit()
    except Exception as e:
        logger.warning(f"ensure_queue_tables notice: {e}")


def ensure_iw_tables(target_engine, is_postgres: bool = True):
    """
    Memastikan tabel cfg_machine_iw_tag_mapping dan live_iw_telemetry tersedia di PostgreSQL.
    """
    try:
        with target_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS public.cfg_machine_iw_tag_mapping (
                    id SERIAL PRIMARY KEY,
                    machine_id VARCHAR(50) NOT NULL,
                    asset_id VARCHAR(50) NOT NULL,
                    register_index INT NOT NULL,
                    iw_number INT NOT NULL,
                    tag_name VARCHAR(150) NOT NULL,
                    tag_role VARCHAR(20) NOT NULL,
                    field_name VARCHAR(100) NOT NULL,
                    unit VARCHAR(20),
                    data_type VARCHAR(20) DEFAULT 'FLOAT',
                    raw_min DOUBLE PRECISION DEFAULT 0.0,
                    raw_max DOUBLE PRECISION DEFAULT 1000.0,
                    eng_min DOUBLE PRECISION DEFAULT 0.0,
                    eng_max DOUBLE PRECISION DEFAULT 100.0,
                    scale_factor DOUBLE PRECISION DEFAULT 1.0,
                    is_active BOOLEAN DEFAULT TRUE,
                    notes TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    CONSTRAINT uq_machine_register UNIQUE(machine_id, register_index)
                );
                CREATE TABLE IF NOT EXISTS public.live_iw_telemetry (
                    machine_id VARCHAR(50) PRIMARY KEY,
                    asset_id VARCHAR(50) NOT NULL,
                    last_updated TIMESTAMPTZ NOT NULL,
                    connection_status VARCHAR(20) DEFAULT 'ONLINE',
                    batch_no VARCHAR(50),
                    step_no INT,
                    program_no VARCHAR(50),
                    raw_buffer_hex TEXT,
                    telemetry_json JSONB NOT NULL
                );
            """))
            conn.commit()
    except Exception as e:
        logger.warning(f"ensure_iw_tables notice: {e}")


def ensure_formula_tables(target_engine, is_postgres: bool = True):
    """
    Memastikan tabel parameter_formulas, formula_machine_groups, dan kolom
    formula_id / formula_output_key pada step_function_parameters tersedia di PostgreSQL.
    """
    try:
        with target_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS public.parameter_formulas (
                    id BIGSERIAL PRIMARY KEY,
                    code VARCHAR(60) NOT NULL UNIQUE,
                    name VARCHAR(180) NOT NULL,
                    description TEXT,
                    formula_type VARCHAR(30) NOT NULL DEFAULT 'MATH',
                    output_mode VARCHAR(20) NOT NULL DEFAULT 'SINGLE',
                    target_function_id INT,
                    target_function_name VARCHAR(120),
                    outputs_json TEXT,
                    definition_json TEXT NOT NULL,
                    unit VARCHAR(30) DEFAULT '',
                    decimal_places INT DEFAULT 1,
                    min_value NUMERIC(12, 4),
                    max_value NUMERIC(12, 4),
                    default_fallback NUMERIC(12, 4) DEFAULT 0.0,
                    apply_all_groups BOOLEAN DEFAULT FALSE,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS public.formula_machine_groups (
                    id BIGSERIAL PRIMARY KEY,
                    formula_id BIGINT NOT NULL REFERENCES public.parameter_formulas(id) ON DELETE CASCADE,
                    machine_group_name VARCHAR(100) NOT NULL,
                    deployed_at TIMESTAMPTZ DEFAULT NOW(),
                    CONSTRAINT uq_formula_machine_group UNIQUE (formula_id, machine_group_name)
                );
                CREATE INDEX IF NOT EXISTS idx_fmg_formula_id ON public.formula_machine_groups(formula_id);
                CREATE INDEX IF NOT EXISTS idx_fmg_group_name ON public.formula_machine_groups(machine_group_name);
                CREATE TABLE IF NOT EXISTS public.formula_machines (
                    id BIGSERIAL PRIMARY KEY,
                    formula_id BIGINT NOT NULL REFERENCES public.parameter_formulas(id) ON DELETE CASCADE,
                    machine_no VARCHAR(50) NOT NULL,
                    deployed_at TIMESTAMPTZ DEFAULT NOW(),
                    CONSTRAINT uq_formula_machine UNIQUE (formula_id, machine_no)
                );
                CREATE INDEX IF NOT EXISTS idx_fm_formula_id ON public.formula_machines(formula_id);
                CREATE INDEX IF NOT EXISTS idx_fm_machine_no ON public.formula_machines(machine_no);
            """))
            conn.execute(text(
                "ALTER TABLE public.step_function_parameters "
                "ADD COLUMN IF NOT EXISTS formula_id BIGINT REFERENCES public.parameter_formulas(id) ON DELETE SET NULL;"
            ))
            conn.execute(text(
                "ALTER TABLE public.step_function_parameters "
                "ADD COLUMN IF NOT EXISTS formula_output_key VARCHAR(100);"
            ))
            conn.commit()
    except Exception as e:
        logger.warning(f"ensure_formula_tables notice: {e}")


def ensure_program_uniqueness(target_engine, is_postgres: bool = True):
    """
    Ensures no duplicate program_components exist within the same machine
    (level, machine_code, number), while allowing the same program number
    across different machines, and adds a unique index to prevent future duplicates.
    """
    try:
        from .services.db_sync_service import DBSyncService
        SessionTmp = sessionmaker(bind=target_engine)
        sess = SessionTmp()
        try:
            DBSyncService.deduplicate_program_components(sess)
        finally:
            sess.close()

        with target_engine.connect() as conn:
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_program_components_lvl_mach_num "
                "ON public.program_components (level, UPPER(TRIM(COALESCE(machine_code, 'TD12'))), TRIM(number));"
            ))
            conn.commit()
    except Exception as e:
        logger.warning(f"ensure_program_uniqueness notice: {e}")


def is_pg_reachable(url: str, timeout: float = 1.0) -> bool:
    try:
        parsed = urlparse(url)
        host = parsed.hostname or "192.168.100.30"
        port = parsed.port or 5433
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def init_db(retries=1, delay=1):
    global engine, SessionLocal, IS_POSTGRES

    cur_url = os.getenv("DATABASE_URL", DATABASE_URL)
    if cur_url.startswith("sqlite"):
        raise RuntimeError(
            "Database lokal SQLite sudah dinonaktifkan. Gunakan URL PostgreSQL pada DATABASE_URL."
        )

    if cur_url.startswith("postgresql://"):
        cur_url = cur_url.replace("postgresql://", "postgresql+psycopg2://", 1)

    logger.info(f"Connecting to PostgreSQL pt_smm_jetflow: {cur_url}")
    temp_engine = create_engine(
        cur_url,
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=40,
        pool_recycle=300,
        pool_timeout=10,
        connect_args={"connect_timeout": 3}
    )
    with temp_engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS orgatex;"))
        conn.execute(text("SET search_path TO public, orgatex;"))
        conn.commit()

    engine = temp_engine
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    IS_POSTGRES = True
    logger.info("Successfully connected to PostgreSQL pt_smm_jetflow (Schema: public)!")

    Base.metadata.create_all(bind=engine)
    ensure_batch_header_columns(engine, is_postgres=True)
    ensure_essential_machines(engine, is_postgres=True)
    ensure_queue_tables(engine, is_postgres=True)
    ensure_iw_tables(engine, is_postgres=True)
    ensure_formula_tables(engine, is_postgres=True)
    ensure_program_uniqueness(engine, is_postgres=True)


def get_db():
    global SessionLocal
    if SessionLocal is None:
        init_db()
    if SessionLocal is None:
        raise RuntimeError("PostgreSQL database session could not be initialized")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
