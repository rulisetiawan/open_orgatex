"""
OpenOrgaTEX Database Engine
PostgreSQL with psycopg2 driver & SQLite local fallback
"""

import os
import time
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from .models.schema_pg import Base

logger = logging.getLogger("orgatex.database")

raw_url = os.getenv(
    "DATABASE_URL", 
    "postgresql+psycopg2://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow"
)
if raw_url.startswith("postgresql://"):
    raw_url = raw_url.replace("postgresql://", "postgresql+psycopg2://", 1)

DATABASE_URL = raw_url

engine = None
SessionLocal = None
IS_POSTGRES = False

def init_db(retries=1, delay=1):
    global engine, SessionLocal, IS_POSTGRES
    
    cur_url = os.getenv("DATABASE_URL", DATABASE_URL)
    if cur_url.startswith("postgresql://"):
        cur_url = cur_url.replace("postgresql://", "postgresql+psycopg2://", 1)

    # 0. Direct SQLite if specified in DATABASE_URL
    if cur_url.startswith("sqlite"):
        engine = create_engine(cur_url, connect_args={"check_same_thread": False})
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        IS_POSTGRES = False
        Base.metadata.create_all(bind=engine)
        logger.info(f"Direct SQLite database initialized: {cur_url}")
        return

    # 1. Attempt PostgreSQL connection
    for attempt in range(1, retries + 1):
        try:
            logger.info(f"Connecting to PostgreSQL (Attempt {attempt}/{retries}): {cur_url}")
            temp_engine = create_engine(
                cur_url, 
                pool_pre_ping=True,
                pool_size=5, 
                max_overflow=10,
                connect_args={"connect_timeout": 2}
            )
            with temp_engine.connect() as conn:
                conn.execute(text("CREATE SCHEMA IF NOT EXISTS orgatex;"))
                conn.commit()
            
            engine = temp_engine
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            IS_POSTGRES = True
            logger.info("Successfully connected to PostgreSQL orgatex_db!")
            
            # Create tables in orgatex schema
            Base.metadata.create_all(bind=engine)
            logger.info("Base.metadata.create_all completed in PostgreSQL orgatex schema!")
            return
        except Exception as e:
            logger.warning(f"PostgreSQL connection attempt {attempt} failed: {e}")
            if attempt < retries:
                time.sleep(delay)

    # 2. Resilient Fallback to Local SQLite if PostgreSQL is unreachable
    logger.warning("PostgreSQL unreachable. Activating resilient local SQLite database fallback.")
    local_db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "data/orgatex_local.db"))
    os.makedirs(os.path.dirname(local_db_path), exist_ok=True)
    sqlite_url = f"sqlite:///{local_db_path}"
    
    engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    IS_POSTGRES = False
    Base.metadata.create_all(bind=engine)
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
