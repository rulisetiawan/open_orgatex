"""
TimescaleDB & PostgreSQL Schema Initializer for pt_smm_jetflow
Executes complete schema with:
- timescaledb, dblink, postgres_fdw extensions
- orgatex schema
- datalog_cyclic_records hypertable chunked per 6 hours
- 1-day compression policy
"""

import psycopg2
from psycopg2 import sql

DB_CONFIG = {
    "host": "192.168.100.30",
    "port": 5433,
    "dbname": "pt_smm_jetflow",
    "user": "postgres",
    "password": "sensorSMM!"
}

SQL_SETUP = """
-- 1. Enable Required Extensions
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS dblink;
CREATE EXTENSION IF NOT EXISTS postgres_fdw;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. Create OrgaTEX Schema
CREATE SCHEMA IF NOT EXISTS orgatex;
SET search_path TO orgatex, public;

-- 3. Machines Master Table
CREATE TABLE IF NOT EXISTS orgatex.machines (
    machine_no VARCHAR(50) PRIMARY KEY,
    display_name VARCHAR(150) NOT NULL,
    ip_address VARCHAR(50) NOT NULL,
    tcp_port INT DEFAULT 50000,
    ftp_port INT DEFAULT 21,
    controller_type VARCHAR(50) DEFAULT 'SECOM777',
    os_family VARCHAR(50) DEFAULT 'WindowsCE',
    group_name VARCHAR(100) DEFAULT 'Dyeing Section',
    capacity_kg NUMERIC(8, 2) DEFAULT 350.0,
    default_liquor_ratio NUMERIC(5, 2) DEFAULT 8.0,
    tanks_count INT DEFAULT 2,
    share_folder_path VARCHAR(500) DEFAULT '/app/STATUS',
    polling_interval_sec INT DEFAULT 5,
    is_active BOOLEAN DEFAULT TRUE,
    status VARCHAR(30) DEFAULT 'UNKNOWN',
    current_batch VARCHAR(50),
    current_step INT,
    current_temp NUMERIC(5, 2),
    last_ping_time TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 4. Batch Headers
CREATE TABLE IF NOT EXISTS orgatex.batch_headers (
    id BIGSERIAL PRIMARY KEY,
    batch_ref_no VARCHAR(50) NOT NULL UNIQUE,
    machine_no VARCHAR(50) NOT NULL REFERENCES orgatex.machines(machine_no),
    program_no INT DEFAULT 1,
    recipe_id BIGINT,
    status VARCHAR(30) NOT NULL DEFAULT 'QUEUED',
    fabric_weight_kg NUMERIC(8, 2) NOT NULL DEFAULT 350.0,
    liquor_ratio NUMERIC(5, 2) NOT NULL DEFAULT 8.0,
    customer VARCHAR(150),
    color_shade VARCHAR(100),
    planned_start_time TIMESTAMPTZ,
    actual_start_time TIMESTAMPTZ,
    actual_finish_time TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 5. Cyclic Telemetry Table for TimescaleDB
CREATE TABLE IF NOT EXISTS orgatex.datalog_cyclic_records (
    log_timestamp TIMESTAMPTZ NOT NULL,
    machine_no VARCHAR(50) NOT NULL,
    batch_ref_no VARCHAR(50) NOT NULL,
    temp_pv NUMERIC(5, 2),
    temp_sp NUMERIC(5, 2),
    temp_pt100_t2 NUMERIC(5, 2),
    pump_speed_percent NUMERIC(5, 2),
    reel_speed_mpm NUMERIC(5, 2),
    vessel_pressure_bar NUMERIC(5, 2),
    step_no INT,
    raw_digital_bits INT,
    CONSTRAINT pk_cyclic_records PRIMARY KEY (log_timestamp, machine_no, batch_ref_no)
);

-- 6. Alarms Table
CREATE TABLE IF NOT EXISTS orgatex.datalog_alarms (
    id BIGSERIAL PRIMARY KEY,
    batch_ref_no VARCHAR(50) NOT NULL,
    machine_no VARCHAR(50) NOT NULL,
    alarm_timestamp TIMESTAMPTZ NOT NULL,
    alarm_code VARCHAR(50) NOT NULL,
    alarm_text VARCHAR(255) NOT NULL,
    step_no INT,
    operator_id INT,
    severity VARCHAR(20) DEFAULT 'WARNING',
    cleared_at TIMESTAMPTZ,
    CONSTRAINT uq_alarm_rec UNIQUE (machine_no, batch_ref_no, alarm_timestamp, alarm_code)
);

-- 7. Calloffs Table
CREATE TABLE IF NOT EXISTS orgatex.datalog_calloffs (
    id BIGSERIAL PRIMARY KEY,
    batch_ref_no VARCHAR(50) NOT NULL,
    machine_no VARCHAR(50) NOT NULL,
    step_no INT NOT NULL,
    tank_no INT NOT NULL,
    calloff_type VARCHAR(30) NOT NULL,
    calloff_timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Seed Default Machines
INSERT INTO orgatex.machines (machine_no, display_name, ip_address, controller_type, os_family, capacity_kg, default_liquor_ratio, share_folder_path, status)
VALUES 
('TD12', 'Thies Eco-Soft 350kg #12', '192.168.1.102', 'SECOM777', 'WindowsCE', 350.0, 8.0, '/app/STATUS', 'ONLINE'),
('TD13', 'Thies Eco-Soft 500kg #13', '192.168.1.103', 'SECOM777', 'WindowsCE', 500.0, 8.0, '/app/STATUS', 'IDLE'),
('M01', 'Fong''s Superwin Jet 1000kg #01', '192.168.1.104', 'SECOM777', 'WindowsCE', 1000.0, 7.0, '/app/STATUS', 'IDLE')
ON CONFLICT (machine_no) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    ip_address = EXCLUDED.ip_address,
    controller_type = EXCLUDED.controller_type;
"""

def init_timescale():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    print("[1/4] Executing Table Schemas...")
    cur.execute(SQL_SETUP)
    print("      Table Schemas created successfully!")

    print("[2/4] Setting up TimescaleDB Hypertable on datalog_cyclic_records (6 hour chunk interval)...")
    try:
        cur.execute("""
            SELECT create_hypertable(
                'orgatex.datalog_cyclic_records',
                'log_timestamp',
                chunk_time_interval => INTERVAL '6 hours',
                if_not_exists => TRUE
            );
        """)
        print("      Hypertable configured with 6-hour chunks!")
    except Exception as e:
        print(f"      Hypertable notice/error: {e}")

    print("[3/4] Setting up TimescaleDB Compression Policy (1 day)...")
    try:
        cur.execute("""
            ALTER TABLE orgatex.datalog_cyclic_records SET (
                timescaledb.compress,
                timescaledb.compress_segmentby = 'machine_no, batch_ref_no',
                timescaledb.compress_orderby = 'log_timestamp DESC'
            );
        """)
        print("      Compression attributes configured!")
    except Exception as e:
        print(f"      Compression setup notice: {e}")

    try:
        cur.execute("""
            SELECT add_compression_policy('orgatex.datalog_cyclic_records', INTERVAL '1 day', if_not_exists => TRUE);
        """)
        print("      Compression policy (1 day) active!")
    except Exception as e:
        print(f"      Compression policy notice: {e}")

    print("[4/4] Verifying Foreign Data Wrapper & dblink status...")
    cur.execute("SELECT extname, extversion FROM pg_extension WHERE extname IN ('timescaledb', 'dblink', 'postgres_fdw');")
    exts = cur.fetchall()
    for ext, ver in exts:
        print(f"      * Extension: {ext} (v{ver}) - ACTIVE")

    cur.close()
    conn.close()
    print("\n[SUCCESS] TimescaleDB setup completed on pt_smm_jetflow!")

if __name__ == "__main__":
    init_timescale()
