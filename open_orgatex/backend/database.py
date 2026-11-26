"""
OpenOrgaTEX Database Engine
PostgreSQL with psycopg2 driver & SQLite local fallback
Supports public schema on pt_smm_jetflow and local data/orgatex_local.db
"""

import os
import time
import socket
import logging
from urllib.parse import urlparse
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from .models.schema_pg import Base

logger = logging.getLogger("orgatex.database")

# Environment configuration
OFFLINE_MODE = os.getenv("OFFLINE_MODE", "false").lower() in ("true", "1", "yes")

local_db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "data/orgatex_local.db"))
os.makedirs(os.path.dirname(local_db_path), exist_ok=True)
default_sqlite_url = f"sqlite:///{local_db_path}"

default_pg_url = os.getenv(
    "DATABASE_URL", 
    "postgresql+psycopg2://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow"
)

if default_pg_url.startswith("postgresql://"):
    default_pg_url = default_pg_url.replace("postgresql://", "postgresql+psycopg2://", 1)

DATABASE_URL = default_sqlite_url if OFFLINE_MODE else default_pg_url

engine = None
SessionLocal = None
IS_POSTGRES = False

def ensure_batch_header_columns(target_engine, is_postgres: bool = False):
    """
    Ensures batch_headers table has all columns required by the planning interface:
    batch_no, recipe_name, article, color_code, color_name, total_water_l, position
    """
    try:
        with target_engine.connect() as conn:
            if not is_postgres:
                # SQLite
                cols = [r[1] for r in conn.execute(text("PRAGMA table_info(batch_headers)")).fetchall()]
                needed = [
                    ("batch_no", "VARCHAR(100)"),
                    ("recipe_name", "VARCHAR(255)"),
                    ("article", "VARCHAR(255)"),
                    ("color_code", "VARCHAR(100)"),
                    ("color_name", "VARCHAR(100)"),
                    ("color_rgb", "INTEGER"),
                    ("redye", "INTEGER DEFAULT 0"),
                    ("procedure_no", "VARCHAR(255)"),
                    ("total_water_l", "NUMERIC(12, 2)"),
                    ("fabric_length", "NUMERIC(10, 2) DEFAULT 200.0"),
                    ("import_state", "INTEGER DEFAULT 0"),
                    ("note1", "TEXT"),
                    ("type_of_procedure_no", "INTEGER DEFAULT 1"),
                    ("process_type_1", "INTEGER DEFAULT 1"),
                    ("process_type_2", "INTEGER DEFAULT 1"),
                    ("parameters_json", "TEXT"),
                    ("position", "INTEGER DEFAULT 1")
                ]
                for col_name, col_type in needed:
                    if col_name not in cols:
                        conn.execute(text(f"ALTER TABLE batch_headers ADD COLUMN {col_name} {col_type};"))
                
                # Backfill batch_no if null
                conn.execute(text("UPDATE batch_headers SET batch_no = 'LOT-' || batch_ref_no WHERE batch_no IS NULL OR batch_no = '';"))
                conn.execute(text("UPDATE batch_headers SET recipe_name = 'Reactive Dyeing Standard' WHERE recipe_name IS NULL OR recipe_name = '';"))
                conn.execute(text("UPDATE batch_headers SET total_water_l = fabric_weight_kg * liquor_ratio WHERE total_water_l IS NULL;"))
                conn.commit()
            else:
                # PostgreSQL (public schema)
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
                    ("import_state", "INT DEFAULT 0"),
                    ("note1", "TEXT"),
                    ("type_of_procedure_no", "INT DEFAULT 1"),
                    ("process_type_1", "INT DEFAULT 1"),
                    ("process_type_2", "INT DEFAULT 1"),
                    ("parameters_json", "TEXT"),
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

def ensure_essential_machines(target_engine, is_postgres: bool = False):
    """
    Ensures machines table has orgatex_id column and essential machines DA01 and M_95 exist
    so Foreign Key references in batch_headers always succeed.
    """
    try:
        with target_engine.connect() as conn:
            prefix = "public." if is_postgres else ""
            if not is_postgres:
                cols = [r[1] for r in conn.execute(text("PRAGMA table_info(machines)")).fetchall()]
                if "orgatex_id" not in cols:
                    conn.execute(text("ALTER TABLE machines ADD COLUMN orgatex_id VARCHAR(50);"))
            else:
                conn.execute(text("ALTER TABLE public.machines ADD COLUMN IF NOT EXISTS orgatex_id VARCHAR(50);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_public_machines_orgatex_id ON public.machines (orgatex_id);"))
            conn.execute(text(f"""
                INSERT INTO {prefix}machines (
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
            """ if is_postgres else f"""
                INSERT OR IGNORE INTO machines (
                    machine_no, display_name, ip_address, tcp_port, ftp_port, 
                    controller_type, os_family, group_name, capacity_kg, default_liquor_ratio, 
                    tanks_count, share_folder_path, status, is_active
                ) VALUES (
                    'DA01', 'SETEX 797CE Mesin DA01', '192.168.1.95', 50100, 21,
                    'SETEX 797CE (Windows CE)', 'WindowsCE', 'Dyeing Sample / DA', 350.0, 8.0,
                    2, '/Flashdisk/SC797CE', 'ONLINE', 1
                );
            """))
            conn.execute(text(f"""
                INSERT INTO {prefix}machines (
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
            """ if is_postgres else f"""
                INSERT OR IGNORE INTO machines (
                    machine_no, display_name, ip_address, tcp_port, ftp_port, 
                    controller_type, os_family, group_name, capacity_kg, default_liquor_ratio, 
                    tanks_count, share_folder_path, status, is_active
                ) VALUES (
                    'M_95', 'SETEX 797CE Mesin DA01 (M_95)', '192.168.1.95', 50100, 21,
                    'SETEX 797CE (Windows CE)', 'WindowsCE', 'Dyeing Sample / DA', 350.0, 8.0,
                    2, '/Flashdisk/SC797CE', 'ONLINE', 1
                );
            """))
            conn.commit()
    except Exception as e:
        logger.warning(f"ensure_essential_machines notice: {e}")

def ensure_queue_tables(target_engine, is_postgres: bool = False):
    """
    Ensures machine_queues table exists in database (PostgreSQL / SQLite)
    and synchronizes it from active batch_headers so the queue is always saved in database.
    """
    try:
        prefix = "public." if is_postgres else ""
        with target_engine.connect() as conn:
            if not is_postgres:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS machine_queues (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        machine_no VARCHAR(50) NOT NULL,
                        batch_ref_no VARCHAR(50) NOT NULL,
                        batch_no VARCHAR(100),
                        program_no INTEGER DEFAULT 1,
                        recipe_name VARCHAR(255),
                        customer VARCHAR(150),
                        article VARCHAR(255),
                        color_code VARCHAR(100),
                        color_name VARCHAR(100),
                        fabric_weight_kg NUMERIC(8, 2) DEFAULT 350.0,
                        liquor_ratio NUMERIC(5, 2) DEFAULT 8.0,
                        total_water_l NUMERIC(10, 2),
                        position INTEGER NOT NULL DEFAULT 1,
                        status VARCHAR(30) DEFAULT 'QUEUED',
                        dispatched_at TIMESTAMP,
                        dispatched_to_ip VARCHAR(50),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE (machine_no, batch_ref_no)
                    );
                """))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_mq_mach ON machine_queues(machine_no);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_mq_ref ON machine_queues(batch_ref_no);"))
            else:
                conn.execute(text(f"""
                    CREATE TABLE IF NOT EXISTS {prefix}machine_queues (
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
                conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_mq_mach ON {prefix}machine_queues(machine_no);"))
                conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_mq_ref ON {prefix}machine_queues(batch_ref_no);"))

            # Populate machine_queues from batch_headers if empty
            count = conn.execute(text(f"SELECT COUNT(*) FROM {prefix}machine_queues")).scalar() or 0
            if count == 0:
                if not is_postgres:
                    conn.execute(text("""
                        INSERT OR IGNORE INTO machine_queues (
                            machine_no, batch_ref_no, batch_no, program_no, recipe_name,
                            customer, article, color_code, color_name, fabric_weight_kg,
                            liquor_ratio, total_water_l, position, status
                        )
                        SELECT 
                            machine_no, batch_ref_no, batch_no, program_no, recipe_name,
                            customer, article, color_code, color_name, fabric_weight_kg,
                            liquor_ratio, total_water_l, position, status
                        FROM batch_headers
                        ORDER BY machine_no, position, id;
                    """))
                else:
                    conn.execute(text(f"""
                        INSERT INTO {prefix}machine_queues (
                            machine_no, batch_ref_no, batch_no, program_no, recipe_name,
                            customer, article, color_code, color_name, fabric_weight_kg,
                            liquor_ratio, total_water_l, position, status
                        )
                        SELECT 
                            machine_no, batch_ref_no, batch_no, program_no, recipe_name,
                            customer, article, color_code, color_name, fabric_weight_kg,
                            liquor_ratio, total_water_l, position, status
                        FROM {prefix}batch_headers
                        ON CONFLICT (machine_no, batch_ref_no) DO NOTHING;
                    """))
            conn.commit()
    except Exception as e:
        logger.warning(f"ensure_queue_tables notice: {e}")

def ensure_iw_tables(target_engine, is_postgres: bool = False):
    """
    Memastikan tabel cfg_machine_iw_tag_mapping dan live_iw_telemetry tersedia di database.
    """
    try:
        prefix = "public." if is_postgres else ""
        with target_engine.connect() as conn:
            if not is_postgres:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS cfg_machine_iw_tag_mapping (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        machine_id TEXT NOT NULL,
                        asset_id TEXT NOT NULL,
                        register_index INTEGER NOT NULL,
                        iw_number INTEGER NOT NULL,
                        tag_name TEXT NOT NULL,
                        tag_role TEXT NOT NULL,
                        field_name TEXT NOT NULL,
                        unit TEXT,
                        data_type TEXT DEFAULT 'FLOAT',
                        raw_min REAL DEFAULT 0.0,
                        raw_max REAL DEFAULT 1000.0,
                        eng_min REAL DEFAULT 0.0,
                        eng_max REAL DEFAULT 100.0,
                        scale_factor REAL DEFAULT 1.0,
                        is_active INTEGER DEFAULT 1,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(machine_id, register_index)
                    );
                """))
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS live_iw_telemetry (
                        machine_id TEXT PRIMARY KEY,
                        asset_id TEXT NOT NULL,
                        last_updated TIMESTAMP NOT NULL,
                        connection_status TEXT DEFAULT 'ONLINE',
                        batch_no TEXT,
                        step_no INTEGER,
                        program_no TEXT,
                        raw_buffer_hex TEXT,
                        telemetry_json TEXT NOT NULL
                    );
                """))
            else:
                conn.execute(text(f"""
                    CREATE TABLE IF NOT EXISTS {prefix}cfg_machine_iw_tag_mapping (
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
                    CREATE TABLE IF NOT EXISTS {prefix}live_iw_telemetry (
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

def ensure_program_uniqueness(target_engine, is_postgres: bool = False):
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

        prefix = "public." if is_postgres else ""
        with target_engine.connect() as conn:
            conn.execute(text(
                f"CREATE UNIQUE INDEX IF NOT EXISTS ux_program_components_lvl_mach_num "
                f"ON {prefix}program_components (level, UPPER(TRIM(COALESCE(machine_code, 'TD12'))), TRIM(number));"
            ))
            conn.commit()
    except Exception as e:
        logger.warning(f"ensure_program_uniqueness notice: {e}")


def is_pg_reachable(url: str, timeout: float = 0.5) -> bool:
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
    
    # If explicitly SQLite or OFFLINE_MODE
    if OFFLINE_MODE or cur_url.startswith("sqlite"):
        sqlite_target = cur_url if cur_url.startswith("sqlite") else default_sqlite_url
        engine = create_engine(sqlite_target, connect_args={"check_same_thread": False}, poolclass=NullPool)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        IS_POSTGRES = False
        Base.metadata.create_all(bind=engine)
        ensure_batch_header_columns(engine, is_postgres=False)
        ensure_essential_machines(engine, is_postgres=False)
        ensure_queue_tables(engine, is_postgres=False)
        ensure_iw_tables(engine, is_postgres=False)
        ensure_program_uniqueness(engine, is_postgres=False)
        logger.info(f"OpenOrgaTEX Local SQLite database initialized: {sqlite_target}")
        return

    if cur_url.startswith("postgresql://"):
        cur_url = cur_url.replace("postgresql://", "postgresql+psycopg2://", 1)

    # 1. Quick probe to see if PostgreSQL port is open before initializing SQLAlchemy
    if is_pg_reachable(cur_url, timeout=0.6):
        try:
            logger.info(f"Connecting to PostgreSQL pt_smm_jetflow: {cur_url}")
            temp_engine = create_engine(
                cur_url, 
                pool_pre_ping=True,
                pool_size=20, 
                max_overflow=40,
                pool_recycle=300,
                pool_timeout=10,
                connect_args={"connect_timeout": 2}
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
            ensure_program_uniqueness(engine, is_postgres=True)
            return
        except Exception as e:
            logger.warning(f"PostgreSQL connection attempt failed: {e}")

    # 2. Resilient Fallback to Local SQLite if PostgreSQL is unreachable
    logger.info("PostgreSQL unreachable or offline. Activating resilient local SQLite database fallback.")
    sqlite_url = f"sqlite:///{local_db_path}"
    
    engine = create_engine(sqlite_url, connect_args={"check_same_thread": False}, poolclass=NullPool)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    IS_POSTGRES = False
    Base.metadata.create_all(bind=engine)
    ensure_batch_header_columns(engine, is_postgres=False)
    ensure_essential_machines(engine, is_postgres=False)
    ensure_queue_tables(engine, is_postgres=False)
    ensure_iw_tables(engine, is_postgres=False)
    ensure_program_uniqueness(engine, is_postgres=False)
    logger.info(f"SQLite local fallback database initialized at: {local_db_path}")

def get_db():
    global SessionLocal
    if SessionLocal is None:
        init_db()
    if SessionLocal is None:
        raise RuntimeError("Database session could not be initialized")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
