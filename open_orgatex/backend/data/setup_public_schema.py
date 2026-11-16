"""
Create Tables directly in the 'public' schema of pt_smm_jetflow
Ensures that any DB client (DBeaver, pgAdmin, psql, Navicat) opening 'public'
immediately sees all tables.
Also configures TimescaleDB hypertable, 6h chunk interval, and 1-day compression.
"""

import psycopg2

DB_CONFIG = {
    "host": "192.168.100.30",
    "port": 5433,
    "dbname": "pt_smm_jetflow",
    "user": "postgres",
    "password": "sensorSMM!"
}

SQL_PUBLIC_SETUP = """
-- Set search path
SET search_path TO public;

-- Enable Extensions
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS dblink;
CREATE EXTENSION IF NOT EXISTS postgres_fdw;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Alter default search paths for database and user
ALTER DATABASE pt_smm_jetflow SET search_path TO public, orgatex;
ALTER USER postgres SET search_path TO public, orgatex;

-- 1. Master Categories
CREATE TABLE IF NOT EXISTS public.categories (
    category_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    parent_id VARCHAR(50),
    is_system BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 2. Items
CREATE TABLE IF NOT EXISTS public.items (
    item_id VARCHAR(36) PRIMARY KEY,
    code VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    category_id VARCHAR(50),
    unit VARCHAR(20) DEFAULT 'g/l',
    density NUMERIC(8, 4) DEFAULT 1.0,
    stock_qty NUMERIC(12, 3) DEFAULT 0.0,
    is_active BOOLEAN DEFAULT TRUE
);

-- 3. Recipes
CREATE TABLE IF NOT EXISTS public.recipes (
    recipe_id BIGSERIAL PRIMARY KEY,
    recipe_code VARCHAR(100) NOT NULL UNIQUE,
    recipe_name VARCHAR(255) NOT NULL,
    customer_name VARCHAR(255),
    fabric_type VARCHAR(100) DEFAULT 'COTTON',
    standard_liquor_ratio NUMERIC(5, 2) DEFAULT 8.0,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS public.recipe_items (
    id BIGSERIAL PRIMARY KEY,
    recipe_id BIGINT NOT NULL REFERENCES public.recipes(recipe_id) ON DELETE CASCADE,
    chemical_code VARCHAR(100) NOT NULL,
    chemical_name VARCHAR(255) NOT NULL,
    amount NUMERIC(10, 4) NOT NULL,
    unit VARCHAR(20) DEFAULT 'g/l',
    dosing_tank INT DEFAULT 1
);

-- 4. Program Headers & Steps
CREATE TABLE IF NOT EXISTS public.program_headers (
    program_no INT PRIMARY KEY,
    program_name VARCHAR(30) NOT NULL,
    fabric_type VARCHAR(100) DEFAULT 'COTTON',
    estimated_duration_min INT DEFAULT 0,
    max_temperature NUMERIC(5, 2) DEFAULT 95.0,
    compiled_file_path VARCHAR(500),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.program_steps (
    id BIGSERIAL PRIMARY KEY,
    program_no INT NOT NULL REFERENCES public.program_headers(program_no) ON DELETE CASCADE,
    step_no INT NOT NULL,
    label VARCHAR(60),
    CONSTRAINT uq_prg_step_pub UNIQUE (program_no, step_no)
);

CREATE TABLE IF NOT EXISTS public.program_step_functions (
    id BIGSERIAL PRIMARY KEY,
    step_id BIGINT NOT NULL REFERENCES public.program_steps(id) ON DELETE CASCADE,
    column_no INT NOT NULL,
    function_id INT NOT NULL,
    flags INT DEFAULT 0,
    param_1 NUMERIC(10, 2) DEFAULT 0.0,
    param_2 NUMERIC(10, 2) DEFAULT 0.0,
    param_3 NUMERIC(10, 2) DEFAULT 0.0
);

-- 4b. OrgaTEX EDX300 ProgramComponent & StepList (Procedure & Treatment)
CREATE TABLE IF NOT EXISTS public.process_groups (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    level INT DEFAULT 1,
    hidden BOOLEAN DEFAULT FALSE,
    parent_group_id BIGINT REFERENCES public.process_groups(id)
);

CREATE TABLE IF NOT EXISTS public.program_components (
    id BIGSERIAL PRIMARY KEY,
    level INT NOT NULL DEFAULT 1,                -- 1: Procedure (Program Induk), 2: Treatment (Sub-Program)
    type INT NOT NULL DEFAULT 1,                 -- 1: Discontinuous, 2: Continuous
    number VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    comment TEXT,
    hidden BOOLEAN DEFAULT FALSE,
    machine_code VARCHAR(50) DEFAULT 'C012',
    content_type INT DEFAULT 0,
    creation_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    modification_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.program_component_items (
    id BIGSERIAL PRIMARY KEY,
    position INT NOT NULL DEFAULT 1,
    parent_component_id BIGINT NOT NULL REFERENCES public.program_components(id) ON DELETE CASCADE,
    program_component_id BIGINT NOT NULL REFERENCES public.program_components(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS public.program_component_parameters (
    id BIGSERIAL PRIMARY KEY,
    program_component_item_id BIGINT NOT NULL REFERENCES public.program_component_items(id) ON DELETE CASCADE,
    treatment_parameter_number INT NOT NULL,
    parameter_name VARCHAR(100),
    value NUMERIC(12, 4) DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS public.steps (
    id BIGSERIAL PRIMARY KEY,
    position INT NOT NULL DEFAULT 1,
    parent_component_id BIGINT NOT NULL REFERENCES public.program_components(id) ON DELETE CASCADE,
    label VARCHAR(100),
    summary_temp NUMERIC(6, 2),
    summary_time_min NUMERIC(6, 2),
    summary_water_l NUMERIC(10, 2)
);

CREATE TABLE IF NOT EXISTS public.step_functions (
    id BIGSERIAL PRIMARY KEY,
    step_id BIGINT NOT NULL REFERENCES public.steps(id) ON DELETE CASCADE,
    resource_number INT NOT NULL DEFAULT 1,
    function_number INT NOT NULL,
    function_name VARCHAR(100),
    label INT DEFAULT 0,
    label_type INT DEFAULT 0,
    acknowledge INT DEFAULT 0,
    comment VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS public.step_function_parameters (
    id BIGSERIAL PRIMARY KEY,
    step_function_id BIGINT NOT NULL REFERENCES public.step_functions(id) ON DELETE CASCADE,
    function_parameter_number INT NOT NULL DEFAULT 1,
    attribute INT DEFAULT 0,
    value NUMERIC(12, 4) DEFAULT 0.0,
    treatment_parameter_number INT
);

CREATE TABLE IF NOT EXISTS public.program_component_2_groups (
    id BIGSERIAL PRIMARY KEY,
    process_group_id BIGINT NOT NULL REFERENCES public.process_groups(id) ON DELETE CASCADE,
    program_component_id BIGINT NOT NULL REFERENCES public.program_components(id) ON DELETE CASCADE
);

-- 5. Master Machines
CREATE TABLE IF NOT EXISTS public.machines (
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
    status VARCHAR(30) DEFAULT 'ONLINE',
    current_batch VARCHAR(50),
    current_step INT,
    current_temp NUMERIC(5, 2),
    last_ping_time TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 6. Batch Headers
CREATE TABLE IF NOT EXISTS public.batch_headers (
    id BIGSERIAL PRIMARY KEY,
    batch_ref_no VARCHAR(50) NOT NULL UNIQUE,
    machine_no VARCHAR(50) NOT NULL REFERENCES public.machines(machine_no),
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

-- 7. Cyclic Telemetry Table for TimescaleDB (Hypertable)
CREATE TABLE IF NOT EXISTS public.datalog_cyclic_records (
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
    CONSTRAINT pk_cyclic_pub PRIMARY KEY (log_timestamp, machine_no, batch_ref_no)
);

-- 8. Alarms
CREATE TABLE IF NOT EXISTS public.datalog_alarms (
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
    CONSTRAINT uq_alarm_pub UNIQUE (machine_no, batch_ref_no, alarm_timestamp, alarm_code)
);

-- 9. Datalog Calloffs
CREATE TABLE IF NOT EXISTS public.datalog_calloffs (
    id BIGSERIAL PRIMARY KEY,
    batch_ref_no VARCHAR(50) NOT NULL,
    machine_no VARCHAR(50) NOT NULL,
    step_no INT NOT NULL,
    tank_no INT NOT NULL,
    calloff_type VARCHAR(30) NOT NULL,
    calloff_timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Insert Default Machines into public.machines
INSERT INTO public.machines (machine_no, display_name, ip_address, controller_type, os_family, capacity_kg, default_liquor_ratio, share_folder_path, status)
VALUES 
('TD12', 'Thies Eco-Soft 350kg #12', '192.168.1.102', 'SECOM777', 'WindowsCE', 350.0, 8.0, '/app/STATUS', 'ONLINE'),
('TD13', 'Thies Eco-Soft 500kg #13', '192.168.1.103', 'SECOM777', 'WindowsCE', 500.0, 8.0, '/app/STATUS', 'IDLE'),
('M01', 'Fong''s Superwin Jet 1000kg #01', '192.168.1.104', 'SECOM777', 'WindowsCE', 1000.0, 7.0, '/app/STATUS', 'IDLE'),
('1A', 'SETEX 777CE Mesin 1A', '172.16.110.101', 'SECOM777', 'WindowsCE', 350.0, 8.0, '/Storage/SC777CE', 'ONLINE'),
('A002', 'SETEX 777CE Mesin A002', '172.16.110.102', 'SECOM777', 'WindowsCE', 500.0, 8.0, '/Storage/SC777CE', 'ONLINE')
ON CONFLICT (machine_no) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    ip_address = EXCLUDED.ip_address,
    controller_type = EXCLUDED.controller_type;
"""

def setup_public_schema():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    print("[1/3] Creating all tables in 'public' schema...")
    cur.execute(SQL_PUBLIC_SETUP)
    print("      All tables in 'public' schema created!")

    print("[2/3] Configuring TimescaleDB on public.datalog_cyclic_records...")
    try:
        cur.execute("""
            SELECT create_hypertable(
                'public.datalog_cyclic_records',
                'log_timestamp',
                chunk_time_interval => INTERVAL '6 hours',
                if_not_exists => TRUE
            );
        """)
        print("      Hypertable configured on public.datalog_cyclic_records (6-hour chunks)!")
    except Exception as e:
        print(f"      Hypertable notice: {e}")

    try:
        cur.execute("""
            ALTER TABLE public.datalog_cyclic_records SET (
                timescaledb.compress,
                timescaledb.compress_segmentby = 'machine_no, batch_ref_no',
                timescaledb.compress_orderby = 'log_timestamp DESC'
            );
        """)
        cur.execute("""
            SELECT add_compression_policy('public.datalog_cyclic_records', INTERVAL '1 day', if_not_exists => TRUE);
        """)
        print("      Compression policy (1 day) configured on public.datalog_cyclic_records!")
    except Exception as e:
        print(f"      Compression notice: {e}")

    # Copy existing records from orgatex to public if any
    try:
        cur.execute("""
            INSERT INTO public.datalog_cyclic_records 
            SELECT * FROM orgatex.datalog_cyclic_records
            ON CONFLICT DO NOTHING;
        """)
        cur.execute("""
            INSERT INTO public.datalog_alarms 
            SELECT * FROM orgatex.datalog_alarms
            ON CONFLICT DO NOTHING;
        """)
        cur.execute("""
            INSERT INTO public.batch_headers 
            SELECT * FROM orgatex.batch_headers
            ON CONFLICT DO NOTHING;
        """)
        print("      Synchronized existing data into public schema!")
    except Exception as e:
        print(f"      Sync note: {e}")

    print("[3/3] Listing all tables in 'public' schema:")
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name;
    """)
    for row in cur.fetchall():
        print(f"      - public.{row[0]}")

    cur.close()
    conn.close()
    print("\n[SUCCESS] All tables are now visible in the default 'public' schema of pt_smm_jetflow!")

if __name__ == "__main__":
    setup_public_schema()
