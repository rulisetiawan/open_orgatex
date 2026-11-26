-- =============================================================================
-- OpenOrgaTEX PostgreSQL Database Schema
-- Reverse engineered and converted from SETEX OrgaTEX MSSQL & SQLite DDLs
-- (RDMDBStructure.sql, Create_Datalog_Tables.sql, Programs/Create.sql, BatchLog/Create.sql)
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS orgatex;
SET search_path TO orgatex, public;

-- Enable UUID extension if available
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- 1. ROOT DATA MANAGEMENT (RDM) - RESEP, BAHAN KIMIA, KAIN & CUSTOMER
-- =============================================================================

-- Master Kategori Data (RECIPE, DYES, CHEMICAL, AUXILIARY, FABRIC, CUSTOMER)
CREATE TABLE IF NOT EXISTS categories (
    category_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    parent_id VARCHAR(50) REFERENCES categories(category_id),
    is_system BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Master Item Entitas (Resep, Zat Warna, Obat Bantu, Kain)
CREATE TABLE IF NOT EXISTS items (
    item_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    category_id VARCHAR(50) NOT NULL REFERENCES categories(category_id),
    unit VARCHAR(20) DEFAULT 'g/l',         -- 'g/l', '%', 'kg', 'l'
    density NUMERIC(8, 4) DEFAULT 1.0,       -- Berat jenis untuk cairan (g/ml)
    stock_qty NUMERIC(12, 3) DEFAULT 0.0,
    price_per_unit NUMERIC(14, 2) DEFAULT 0.0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Atribut Dinamis EAV (Entity-Attribute-Value) khas OrgaTEX
CREATE TABLE IF NOT EXISTS attributes (
    attribute_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    data_type INT NOT NULL DEFAULT 1,        -- 0=Number, 1=String, 2=List, 3=DateTime, 4=Bool
    display_unit VARCHAR(30)
);

CREATE TABLE IF NOT EXISTS item_attributes (
    id BIGSERIAL PRIMARY KEY,
    item_id UUID NOT NULL REFERENCES items(item_id) ON DELETE CASCADE,
    attribute_id VARCHAR(50) NOT NULL REFERENCES attributes(attribute_id),
    val_string TEXT,
    val_number NUMERIC(14, 4),
    val_date TIMESTAMPTZ,
    CONSTRAINT uq_item_attr UNIQUE (item_id, attribute_id)
);

-- Formula Resep Pencelupan (BOM - Bill of Materials untuk Dosing LA)
CREATE TABLE IF NOT EXISTS recipes (
    recipe_id BIGSERIAL PRIMARY KEY,
    recipe_code VARCHAR(100) NOT NULL UNIQUE,
    recipe_name VARCHAR(255) NOT NULL,
    customer_name VARCHAR(255),
    fabric_type VARCHAR(100) DEFAULT 'COTTON',
    standard_liquor_ratio NUMERIC(5, 2) DEFAULT 8.0,
    ph_target NUMERIC(4, 2),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Detail Komposisi Bahan Kimia Resep (Tangki 1: Aux, Tangki 2: Color)
CREATE TABLE IF NOT EXISTS recipe_items (
    id BIGSERIAL PRIMARY KEY,
    recipe_id BIGINT NOT NULL REFERENCES recipes(recipe_id) ON DELETE CASCADE,
    item_id UUID REFERENCES items(item_id),
    chemical_code VARCHAR(100) NOT NULL,
    chemical_name VARCHAR(255) NOT NULL,
    amount NUMERIC(10, 4) NOT NULL,          -- Nilai takaran
    unit VARCHAR(20) NOT NULL DEFAULT 'g/l', -- '%', 'g/l', 'kg'
    dosing_tank INT NOT NULL DEFAULT 1,      -- 1 = Tangki 1 (Aux/Garam), 2 = Tangki 2 (Zat Warna)
    dosing_curve INT DEFAULT 1,              -- 1=Linear, 2=Progressive, 3=Degressive
    step_calloff INT DEFAULT 1               -- Urutan call-off di mesin
);

-- =============================================================================
-- 2. ORGATEX EDX300 PROGRAM & SUB-PROGRAM (PROCEDURE & TREATMENT) ARCHITECTURE
-- =============================================================================

CREATE TABLE IF NOT EXISTS process_groups (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    level INT DEFAULT 1,
    hidden BOOLEAN DEFAULT FALSE,
    parent_group_id BIGINT REFERENCES process_groups(id)
);

-- ProgramComponent: Level 1 = Procedure (Program Utama), Level 2 = Treatment (Sub-Program)
CREATE TABLE IF NOT EXISTS program_components (
    id BIGSERIAL PRIMARY KEY,
    level INT NOT NULL DEFAULT 1,                -- 1: Procedure (Program Induk), 2: Treatment (Sub-Program)
    type INT NOT NULL DEFAULT 1,                 -- 1: Discontinuous (Jet Dyeing), 2: Continuous
    number VARCHAR(100) NOT NULL,                -- '0001', 'TR-01', dll.
    name VARCHAR(255) NOT NULL,                  -- Nama Prosedur atau Sub-Program
    comment TEXT,                                -- Keterangan perlakuan
    hidden BOOLEAN DEFAULT FALSE,
    machine_code VARCHAR(50) DEFAULT 'C012',
    content_type INT DEFAULT 0,
    creation_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    modification_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ProgramComponentItem: Menghubungkan Procedure Induk dengan urutan Sub-Program
CREATE TABLE IF NOT EXISTS program_component_items (
    id BIGSERIAL PRIMARY KEY,
    position INT NOT NULL DEFAULT 1,             -- Urutan Sub-Program dalam Procedure
    parent_component_id BIGINT NOT NULL REFERENCES program_components(id) ON DELETE CASCADE,
    program_component_id BIGINT NOT NULL REFERENCES program_components(id) ON DELETE CASCADE
);

-- ProgramComponentParameter: Parameter nilai yang dioper ke Sub-Program
CREATE TABLE IF NOT EXISTS program_component_parameters (
    id BIGSERIAL PRIMARY KEY,
    program_component_item_id BIGINT NOT NULL REFERENCES program_component_items(id) ON DELETE CASCADE,
    treatment_parameter_number INT NOT NULL,
    parameter_name VARCHAR(100),
    value NUMERIC(12, 4) DEFAULT 0.0
);

-- Steps: Langkah-langkah fisik dalam Sub-Program (Treatment)
CREATE TABLE IF NOT EXISTS steps (
    id BIGSERIAL PRIMARY KEY,
    position INT NOT NULL DEFAULT 1,             -- Nomor urut langkah dalam Sub-Program
    parent_component_id BIGINT NOT NULL REFERENCES program_components(id) ON DELETE CASCADE,
    label VARCHAR(100),
    summary_temp NUMERIC(6, 2),
    summary_time_min NUMERIC(6, 2),
    summary_water_l NUMERIC(10, 2)
);

-- StepFunction: Fungsi F-Code SETEX Secom 777 dalam Step
CREATE TABLE IF NOT EXISTS step_functions (
    id BIGSERIAL PRIMARY KEY,
    step_id BIGINT NOT NULL REFERENCES steps(id) ON DELETE CASCADE,
    resource_number INT NOT NULL DEFAULT 1,      -- Kolom (1=Main, 2=Pump, 3=Reel)
    function_number INT NOT NULL,                -- 713 (Fill), 141 (Heat), 121 (Hold), 85/86 (Dose), dll.
    function_name VARCHAR(100),
    label INT DEFAULT 0,
    label_type INT DEFAULT 0,
    acknowledge INT DEFAULT 0,
    comment VARCHAR(255)
);

-- StepFunctionParameter: Nilai parameter fungsi kontroler
CREATE TABLE IF NOT EXISTS step_function_parameters (
    id BIGSERIAL PRIMARY KEY,
    step_function_id BIGINT NOT NULL REFERENCES step_functions(id) ON DELETE CASCADE,
    function_parameter_number INT NOT NULL DEFAULT 1,
    attribute INT DEFAULT 0,
    value NUMERIC(12, 4) DEFAULT 0.0,
    treatment_parameter_number INT
);

CREATE TABLE IF NOT EXISTS program_component_2_groups (
    id BIGSERIAL PRIMARY KEY,
    process_group_id BIGINT NOT NULL REFERENCES process_groups(id) ON DELETE CASCADE,
    program_component_id BIGINT NOT NULL REFERENCES program_components(id) ON DELETE CASCADE
);

-- Legacy Flat Tables (Kompatibilitas Mundur & Secom .PRG Exporter)
CREATE TABLE IF NOT EXISTS program_headers (
    program_no INT PRIMARY KEY,
    program_name VARCHAR(30) NOT NULL,
    fabric_type VARCHAR(100) DEFAULT 'COTTON',
    estimated_duration_min INT DEFAULT 0,
    max_temperature NUMERIC(5, 2) DEFAULT 95.0,
    compiled_file_path VARCHAR(500),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS program_steps (
    id BIGSERIAL PRIMARY KEY,
    program_no INT NOT NULL REFERENCES program_headers(program_no) ON DELETE CASCADE,
    step_no INT NOT NULL,
    label VARCHAR(60),
    CONSTRAINT uq_prg_step UNIQUE (program_no, step_no)
);

CREATE TABLE IF NOT EXISTS program_step_functions (
    id BIGSERIAL PRIMARY KEY,
    step_id BIGINT NOT NULL REFERENCES program_steps(id) ON DELETE CASCADE,
    column_no INT NOT NULL,
    function_id INT NOT NULL,
    flags INT DEFAULT 0,
    param_1 NUMERIC(10, 2) DEFAULT 0.0,
    param_2 NUMERIC(10, 2) DEFAULT 0.0,
    param_3 NUMERIC(10, 2) DEFAULT 0.0,
    param_4 NUMERIC(10, 2) DEFAULT 0.0,
    param_5 NUMERIC(10, 2) DEFAULT 0.0,
    param_6 NUMERIC(10, 2) DEFAULT 0.0,
    param_7 NUMERIC(10, 2) DEFAULT 0.0,
    param_8 NUMERIC(10, 2) DEFAULT 0.0,
    param_9 NUMERIC(10, 2) DEFAULT 0.0
);

-- =============================================================================
-- 3. MASTER DATA MESIN & KONFIGURASI HMI (SETEX 777)
-- =============================================================================

CREATE TABLE IF NOT EXISTS machines (
    machine_no VARCHAR(50) PRIMARY KEY,      -- Contoh: '1A', '1B', '12C'
    orgatex_id VARCHAR(50),                  -- ID Mesin di OrgaTEX (Contoh: 'A001', 'B001', 'C012')
    display_name VARCHAR(150) NOT NULL,
    ip_address VARCHAR(50) NOT NULL,
    ftp_port INT DEFAULT 21,
    tcp_port INT DEFAULT 50000,              -- Setex Message Service Port
    controller_type VARCHAR(50) DEFAULT 'SECOM777',
    os_family VARCHAR(50) DEFAULT 'WindowsCE',
    group_name VARCHAR(100) DEFAULT 'Dyeing Section',
    capacity_kg NUMERIC(8, 2) DEFAULT 350.0,
    default_liquor_ratio NUMERIC(5, 2) DEFAULT 8.0,
    tanks_count INT DEFAULT 2,
    share_folder_path VARCHAR(500) DEFAULT '/app/STATUS',
    polling_interval_sec INT DEFAULT 5,
    is_active BOOLEAN DEFAULT TRUE,
    status VARCHAR(30) DEFAULT 'UNKNOWN',    -- 'ONLINE', 'OFFLINE', 'RUNNING', 'IDLE'
    current_batch VARCHAR(50),
    current_step INT,
    current_temp NUMERIC(5, 2),
    last_ping_time TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- 4. PLANNING PRODUKSI & BATCH SCHEDULING (BATCH QUEUE & LOTS)
-- =============================================================================

CREATE TABLE IF NOT EXISTS batch_headers (
    id BIGSERIAL PRIMARY KEY,
    batch_ref_no VARCHAR(50) NOT NULL UNIQUE, -- Nomor Lot/Batch (misal: '061118')
    machine_no VARCHAR(50) NOT NULL REFERENCES machines(machine_no),
    program_no INT NOT NULL REFERENCES program_headers(program_no),
    recipe_id BIGINT REFERENCES recipes(recipe_id),
    status VARCHAR(30) NOT NULL DEFAULT 'QUEUED', -- QUEUED, WAITING_LA, DISPATCHED, RUNNING, COMPLETED
    fabric_weight_kg NUMERIC(8, 2) NOT NULL,
    liquor_ratio NUMERIC(5, 2) NOT NULL DEFAULT 8.0,
    calculated_water_liters NUMERIC(10, 2) GENERATED ALWAYS AS (fabric_weight_kg * liquor_ratio) STORED,
    customer VARCHAR(150),
    color_shade VARCHAR(100),
    planned_start_time TIMESTAMPTZ,
    actual_start_time TIMESTAMPTZ,
    actual_finish_time TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Order Dosing Lab Automation (Color Kitchen / LA .DOS)
CREATE TABLE IF NOT EXISTS la_dosing_orders (
    order_id BIGSERIAL PRIMARY KEY,
    batch_ref_no VARCHAR(50) NOT NULL REFERENCES batch_headers(batch_ref_no) ON DELETE CASCADE,
    machine_no VARCHAR(50) NOT NULL REFERENCES machines(machine_no),
    tank_no INT NOT NULL,                    -- 1 = Tank 1, 2 = Tank 2
    total_gram NUMERIC(12, 2) NOT NULL,
    status VARCHAR(30) DEFAULT 'PENDING',    -- PENDING, SENT_TO_LA, DISPENSED, REJECTED
    dos_file_path VARCHAR(500),
    sent_time TIMESTAMPTZ,
    dispensed_time TIMESTAMPTZ
);

-- =============================================================================
-- 5. DATALOG TELEMETRI & LOG CURVE SECOM 777 (.LOG / .REP / CYCLIC)
-- =============================================================================

-- Cyclic Header Telemetri
CREATE TABLE IF NOT EXISTS datalog_cyclic_records (
    id BIGSERIAL PRIMARY KEY,
    batch_ref_no VARCHAR(50) NOT NULL,
    machine_no VARCHAR(50) NOT NULL,
    log_timestamp TIMESTAMPTZ NOT NULL,
    temp_pv NUMERIC(5, 2),                   -- Suhu Aktual Bejana (PV) °C
    temp_sp NUMERIC(5, 2),                   -- Setpoint Suhu (SP) °C
    temp_pt100_t2 NUMERIC(5, 2),             -- Sensor Tambahan T2
    pump_speed_percent NUMERIC(5, 2),        -- Kecepatan Pompa Sirkulasi (%)
    reel_speed_mpm NUMERIC(5, 2),            -- Kecepatan Haspel (m/min)
    vessel_pressure_bar NUMERIC(5, 2),       -- Tekanan Bejana
    step_no INT,                             -- Sedang di langkah ke berapa
    raw_digital_bits INT,                    -- Bit status katup & pompa
    CONSTRAINT uq_cyclic_rec UNIQUE (machine_no, batch_ref_no, log_timestamp)
);

-- Index khusus untuk query kurva suhu berkecepatan tinggi
CREATE INDEX IF NOT EXISTS idx_cyclic_batch_time 
ON datalog_cyclic_records(batch_ref_no, log_timestamp);

CREATE INDEX IF NOT EXISTS idx_cyclic_machine_time 
ON datalog_cyclic_records(machine_no, log_timestamp);

-- Catatan Alarm & Kejadian Operator (.REP)
CREATE TABLE IF NOT EXISTS datalog_alarms (
    id BIGSERIAL PRIMARY KEY,
    batch_ref_no VARCHAR(50) NOT NULL,
    machine_no VARCHAR(50) NOT NULL,
    alarm_timestamp TIMESTAMPTZ NOT NULL,
    alarm_code VARCHAR(50) NOT NULL,
    alarm_text VARCHAR(255) NOT NULL,
    step_no INT,
    operator_id INT,
    severity VARCHAR(20) DEFAULT 'WARNING',   -- INFO, WARNING, CRITICAL
    cleared_at TIMESTAMPTZ,
    CONSTRAINT uq_alarm_rec UNIQUE (machine_no, batch_ref_no, alarm_timestamp, alarm_code)
);

-- Catatan Handshake Call-Off Lab Automation di HMI (DATALOG_RT_CALLOFF)
CREATE TABLE IF NOT EXISTS datalog_calloffs (
    id BIGSERIAL PRIMARY KEY,
    batch_ref_no VARCHAR(50) NOT NULL,
    machine_no VARCHAR(50) NOT NULL,
    step_no INT NOT NULL,
    tank_no INT NOT NULL,
    calloff_type VARCHAR(30) NOT NULL,       -- SENT, RECEIVED, REJECTED
    calloff_timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- SEED DATA AWAL (DEFAULT CATEGORIES & SETEX ATTRIBUTES)
-- =============================================================================

INSERT INTO categories (category_id, name, description, is_system) VALUES
('RECIPE', 'Resep Pencelupan', 'Formula utama proses celup tekstil', TRUE),
('DYE', 'Zat Warna Tekstil', 'Pewarna reaktif, dispersi, direk, dll', TRUE),
('AUX', 'Zat Pembantu (Auxiliary)', 'Garam, soda, levelling, sequestering', TRUE),
('FABRIC', 'Kain & Benang', 'Konstruksi kain (Cotton, TC, CVC, Poly)', TRUE),
('CUSTOMER', 'Pelanggan / Buyer', 'Data pelanggan pemilik kain', TRUE)
ON CONFLICT (category_id) DO NOTHING;

INSERT INTO machines (machine_no, display_name, ip_address, controller_type, capacity_kg, default_liquor_ratio) VALUES
('TD12', 'Thies Eco-Soft 350kg #12', '192.168.1.102', 'SECOM777', 350.0, 8.0),
('TD13', 'Thies Eco-Soft 500kg #13', '192.168.1.103', 'SECOM777', 500.0, 8.0),
('M01', 'Fong''s Superwin Jet 1000kg #01', '192.168.1.104', 'SECOM777', 1000.0, 7.0),
('1A', 'SETEX 777CE Mesin 1A', '172.16.110.101', 'SECOM777', 350.0, 8.0),
('A002', 'SETEX 777CE Mesin A002', '172.16.110.102', 'SECOM777', 500.0, 8.0)
ON CONFLICT (machine_no) DO NOTHING;


-- =============================================================================
-- 6. USERS, ROLES & ACCESS CONTROL (UserData/Create.sql & NetSqlAzMan.sql)
-- =============================================================================

-- Master Role / Hak Akses Pengguna
CREATE TABLE IF NOT EXISTS user_roles (
    role_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(255),
    is_system_role BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Master Pengguna (User)
CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) NOT NULL UNIQUE,
    full_name VARCHAR(150),
    email VARCHAR(150),
    password_hash VARCHAR(255),              -- Password Hash (BCrypt / Argon2 / SHA256)
    operator_passcode VARCHAR(10),           -- PIN Operator untuk HMI Secom (T_PASSCODE_CE)
    is_system_user BOOLEAN NOT NULL DEFAULT FALSE,
    is_application_user BOOLEAN NOT NULL DEFAULT TRUE,
    is_disabled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Relasi Many-to-Many User dan Role (Role2User)
CREATE TABLE IF NOT EXISTS user_role_memberships (
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES user_roles(role_id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, role_id)
);

-- Relasi Hierarki Antar Role (Role2Role)
CREATE TABLE IF NOT EXISTS role_hierarchies (
    parent_role_id UUID NOT NULL REFERENCES user_roles(role_id) ON DELETE CASCADE,
    child_role_id UUID NOT NULL REFERENCES user_roles(role_id) ON DELETE CASCADE,
    PRIMARY KEY (parent_role_id, child_role_id)
);

-- Penugasan Hak Akses Khusus (UserRightAssignment)
CREATE TABLE IF NOT EXISTS user_permissions (
    permission_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    role_id UUID REFERENCES user_roles(role_id) ON DELETE CASCADE,
    permission_code VARCHAR(100) NOT NULL,    -- Contoh: 'PROGRAM_EDIT', 'RECIPE_DELETE', 'BATCH_START'
    is_denied BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT uq_user_perm UNIQUE (user_id, permission_code),
    CONSTRAINT uq_role_perm UNIQUE (role_id, permission_code)
);

-- =============================================================================
-- SEED DATA DEFAULT USERS & ROLES ORGATEX (UserData/InitialData.sql)
-- =============================================================================

INSERT INTO user_roles (name, description, is_system_role) VALUES
('Supervisor', 'Akses penuh seluruh kontrol mesin & approval resep', TRUE),
('Service', 'Akses teknisi servis PLC, konfigurasi hardware & diagnostik', TRUE),
('Configuration', 'Akses setting sistem & parameter pabrik', TRUE),
('Edit', 'Akses membuat & mengubah resep celup dan program .PRG', TRUE),
('Run', 'Akses operator menjalankan batch di mesin', TRUE),
('Intervent', 'Akses intervensi proses (pause, resume, acknowledge alarm)', TRUE),
('Info', 'Akses hanya baca (monitoring & reporting)', TRUE)
ON CONFLICT (name) DO NOTHING;

INSERT INTO users (username, full_name, password_hash, is_system_user, is_application_user, is_disabled) VALUES
('Supervisor', 'Kepala Bagian Dyehouse', '$2b$12$e80yqV8v8bYpQe.ZqB1iUuK8O7G8W9.oR8F4rL9B8v8bYpQe.ZqB1', TRUE, TRUE, FALSE),
('Service', 'Teknisi SETEX Maintenance', '$2b$12$e80yqV8v8bYpQe.ZqB1iUuK8O7G8W9.oR8F4rL9B8v8bYpQe.ZqB1', TRUE, TRUE, FALSE),
('Configuration', 'Administrator Sistem', '$2b$12$e80yqV8v8bYpQe.ZqB1iUuK8O7G8W9.oR8F4rL9B8v8bYpQe.ZqB1', TRUE, TRUE, FALSE),
('Edit', 'Staff Laboratorium & Resep', '$2b$12$e80yqV8v8bYpQe.ZqB1iUuK8O7G8W9.oR8F4rL9B8v8bYpQe.ZqB1', TRUE, TRUE, FALSE),
('Run', 'Operator Mesin Celup', '$2b$12$e80yqV8v8bYpQe.ZqB1iUuK8O7G8W9.oR8F4rL9B8v8bYpQe.ZqB1', TRUE, TRUE, FALSE)
ON CONFLICT (username) DO NOTHING;

-- =============================================================================
-- ORGATEX EXACT CONFIGURATION TABLES (Parity with OtxDataBaseLayer)
-- =============================================================================

CREATE TABLE IF NOT EXISTS cfg_alarm_groups (
    alarm_group_no INT PRIMARY KEY,
    alarm_group_name VARCHAR(100) NOT NULL,
    machine_group_no INT DEFAULT 1
);

CREATE TABLE IF NOT EXISTS cfg_alarms (
    id BIGSERIAL PRIMARY KEY,
    alarm_no INT NOT NULL,
    language VARCHAR(10) DEFAULT 'en',
    machine_group_no INT DEFAULT 1,
    alarm_text VARCHAR(255) NOT NULL,
    alarm_group_no INT DEFAULT 1,
    alarm_group_name VARCHAR(100) DEFAULT 'Process Alarms',
    CONSTRAINT uq_cfg_alarm UNIQUE (alarm_no, language, machine_group_no)
);

CREATE TABLE IF NOT EXISTS cfg_stop_groups (
    stop_group_no INT PRIMARY KEY,
    stop_group_name VARCHAR(100) NOT NULL,
    machine_group_no INT DEFAULT 1
);

CREATE TABLE IF NOT EXISTS cfg_functions (
    function_no INT PRIMARY KEY,
    function_name VARCHAR(100) NOT NULL,
    function_name_local VARCHAR(100),
    function_group_no INT DEFAULT 1,
    machine_group_no INT DEFAULT 1,
    parameter_count INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cfg_function_parameters (
    id BIGSERIAL PRIMARY KEY,
    function_no INT NOT NULL REFERENCES cfg_functions(function_no),
    parameter_no INT NOT NULL,
    parameter_name VARCHAR(100),
    default_val NUMERIC(10, 2) DEFAULT 0.0,
    min_val NUMERIC(10, 2) DEFAULT 0.0,
    max_val NUMERIC(10, 2) DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS cfg_resources (
    resource_no INT PRIMARY KEY,
    resource_name VARCHAR(100) NOT NULL,
    machine_group_no INT DEFAULT 1
);
