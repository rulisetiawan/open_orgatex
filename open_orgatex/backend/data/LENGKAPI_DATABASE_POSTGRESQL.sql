-- =============================================================================
-- SCRIPT LENGKAP STRUKTUR TABEL & DATA ORGATEX UNTUK POSTGRESQL (PUBLIC SCHEMA)
-- Jalankan script ini langsung di DBeaver pada database: pt_smm_jetflow
-- =============================================================================

SET search_path TO public;

-- -----------------------------------------------------------------------------
-- 1. TABEL KONFIGURASI ORGATEX (ALARM, FUNGSI, PARAMETER, RESOURCES)
-- -----------------------------------------------------------------------------

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
    CONSTRAINT uq_cfg_alarm_pub UNIQUE (alarm_no, language, machine_group_no)
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
    function_no INT NOT NULL REFERENCES cfg_functions(function_no) ON DELETE CASCADE,
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

CREATE TABLE IF NOT EXISTS cfg_machine_constants (
    machine_constant_no INT PRIMARY KEY,
    machine_constant_name VARCHAR(100) NOT NULL,
    value VARCHAR(100),
    machine_group_no INT DEFAULT 1
);

CREATE TABLE IF NOT EXISTS cfg_system_constants (
    system_constant_no INT PRIMARY KEY,
    system_constant_name VARCHAR(100) NOT NULL,
    value VARCHAR(100),
    machine_group_no INT DEFAULT 1
);

-- -----------------------------------------------------------------------------
-- 2. TABEL DYELOT & OPERASIONAL CELUP RIIL (Parity: OtxDataBaseLayer)
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dyelots (
    dyelot_id BIGSERIAL PRIMARY KEY,
    dyelot_no VARCHAR(50) NOT NULL UNIQUE,
    batch_no VARCHAR(50) NOT NULL,
    machine_no VARCHAR(50) NOT NULL REFERENCES machines(machine_no),
    recipe_code VARCHAR(100),
    program_no INT,
    customer VARCHAR(150),
    article VARCHAR(150),
    color_code VARCHAR(50),
    color_name VARCHAR(100),
    fabric_weight_kg NUMERIC(10, 2) DEFAULT 350.0,
    liquor_ratio NUMERIC(5, 2) DEFAULT 8.0,
    total_water_l NUMERIC(10, 2) DEFAULT 2800.0,
    status VARCHAR(30) DEFAULT 'QUEUED',
    position INT DEFAULT 1,
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dyelot_recipe (
    id BIGSERIAL PRIMARY KEY,
    dyelot_no VARCHAR(50) NOT NULL REFERENCES dyelots(dyelot_no) ON DELETE CASCADE,
    recipe_name VARCHAR(255) NOT NULL,
    recipe_type VARCHAR(50) DEFAULT 'STANDARD',
    total_chemicals_count INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS dyelot_recipe_pos (
    id BIGSERIAL PRIMARY KEY,
    dyelot_no VARCHAR(50) NOT NULL REFERENCES dyelots(dyelot_no) ON DELETE CASCADE,
    position INT NOT NULL,
    chemical_code VARCHAR(100) NOT NULL,
    chemical_name VARCHAR(255) NOT NULL,
    amount NUMERIC(10, 4) NOT NULL,
    unit VARCHAR(20) DEFAULT 'g/l',
    dosing_tank INT DEFAULT 1
);

CREATE TABLE IF NOT EXISTS dyelot_procedure (
    id BIGSERIAL PRIMARY KEY,
    dyelot_no VARCHAR(50) NOT NULL REFERENCES dyelots(dyelot_no) ON DELETE CASCADE,
    step_no INT NOT NULL,
    function_id INT NOT NULL,
    function_name VARCHAR(100),
    duration_min NUMERIC(6, 2) DEFAULT 0.0,
    target_temp NUMERIC(6, 2) DEFAULT 0.0,
    status VARCHAR(30) DEFAULT 'PENDING'
);

CREATE TABLE IF NOT EXISTS dyelot_parameter (
    id BIGSERIAL PRIMARY KEY,
    dyelot_no VARCHAR(50) NOT NULL REFERENCES dyelots(dyelot_no) ON DELETE CASCADE,
    step_no INT NOT NULL,
    parameter_no INT NOT NULL,
    value NUMERIC(10, 2) DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS treatment_parameter (
    id BIGSERIAL PRIMARY KEY,
    treatment_no INT NOT NULL,
    parameter_no INT NOT NULL,
    parameter_name VARCHAR(100),
    default_value NUMERIC(10, 2) DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS dyelot_adds (
    id BIGSERIAL PRIMARY KEY,
    dyelot_no VARCHAR(50) NOT NULL REFERENCES dyelots(dyelot_no) ON DELETE CASCADE,
    add_no INT NOT NULL DEFAULT 1,
    chemical_code VARCHAR(100) NOT NULL,
    chemical_name VARCHAR(255) NOT NULL,
    amount NUMERIC(10, 4) NOT NULL,
    unit VARCHAR(20) DEFAULT '%',
    reason VARCHAR(255) DEFAULT 'Color Correction / Penambahan Obat',
    requested_by VARCHAR(100),
    approved_by VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dyelot_adds_request (
    id BIGSERIAL PRIMARY KEY,
    dyelot_no VARCHAR(50) NOT NULL REFERENCES dyelots(dyelot_no) ON DELETE CASCADE,
    status VARCHAR(30) DEFAULT 'REQUESTED',
    lab_remark TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dyelot_qc (
    id BIGSERIAL PRIMARY KEY,
    dyelot_no VARCHAR(50) NOT NULL REFERENCES dyelots(dyelot_no) ON DELETE CASCADE,
    delta_e NUMERIC(6, 3),
    delta_l NUMERIC(6, 3),
    delta_a NUMERIC(6, 3),
    delta_b NUMERIC(6, 3),
    qc_result VARCHAR(30) DEFAULT 'PASS',
    checked_by VARCHAR(100),
    checked_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dyelot_qualities (
    id BIGSERIAL PRIMARY KEY,
    quality_code VARCHAR(50) NOT NULL UNIQUE,
    quality_name VARCHAR(150) NOT NULL,
    fabric_type VARCHAR(100),
    weight_gsm NUMERIC(8, 2),
    width_cm NUMERIC(8, 2)
);

CREATE TABLE IF NOT EXISTS employees (
    employee_id VARCHAR(50) PRIMARY KEY,
    full_name VARCHAR(150) NOT NULL,
    role VARCHAR(50) DEFAULT 'OPERATOR',
    shift INT DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS la_dosing_orders (
    order_id BIGSERIAL PRIMARY KEY,
    order_no VARCHAR(50) NOT NULL UNIQUE,
    dyelot_no VARCHAR(50),
    machine_no VARCHAR(50),
    tank_no INT DEFAULT 1,
    status VARCHAR(30) DEFAULT 'PENDING',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_roles (
    role_id VARCHAR(50) PRIMARY KEY,
    role_name VARCHAR(100) NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS users (
    user_id VARCHAR(50) PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(150),
    email VARCHAR(150),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_role_memberships (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role_id VARCHAR(50) NOT NULL REFERENCES user_roles(role_id) ON DELETE CASCADE,
    CONSTRAINT uq_user_role_pub UNIQUE (user_id, role_id)
);

-- -----------------------------------------------------------------------------
-- 3. SEED DATA RIIL (INSERT INTO DARI HASIL REVERSE ENGINEERING)
-- -----------------------------------------------------------------------------

INSERT INTO cfg_alarm_groups (alarm_group_no, alarm_group_name, machine_group_no) VALUES
  (1, 'General Alarms', 1),
  (2, 'Temperature Deviation', 1),
  (3, 'Pressure / Pump Warning', 1),
  (4, 'Dosing Station Alarms', 1)
ON CONFLICT (alarm_group_no) DO UPDATE SET alarm_group_name = EXCLUDED.alarm_group_name;

INSERT INTO cfg_stop_groups (stop_group_no, stop_group_name, machine_group_no) VALUES
  (1, 'Label 1', 1),
  (2, 'Label 2', 1),
  (3, 'Label 3', 1),
  (4, 'Label 4', 1),
  (5, 'Label 5', 1),
  (6, 'Label 6', 1),
  (7, 'Label 7', 1),
  (8, 'Label 8', 1),
  (9, 'Label 9', 1),
  (10, 'Label 10', 1),
  (11, 'Label 11', 1),
  (12, 'Label 12', 1),
  (13, 'Label 13', 1),
  (14, 'Label 14', 1),
  (15, 'Label 15', 1),
  (16, 'Label 16', 1),
  (17, 'Label 17', 1),
  (18, 'Label 18', 1),
  (19, 'Label 19', 1),
  (20, 'Label 20', 1)
ON CONFLICT (stop_group_no) DO NOTHING;

INSERT INTO cfg_alarms (alarm_no, language, machine_group_no, alarm_text, alarm_group_no, alarm_group_name) VALUES
  (1, 'en', 1, 'Set Time Main', 1, 'Process Alarms'),
  (1, 'de', 1, 'Sollzeit', 1, 'Process Alarms'),
  (2, 'en', 1, 'Protect Time Main', 1, 'Process Alarms'),
  (2, 'de', 1, 'Schutzzeit', 1, 'Process Alarms'),
  (3, 'en', 1, 'Temperature', 1, 'Process Alarms'),
  (3, 'de', 1, 'Temperatur', 1, 'Process Alarms'),
  (4, 'en', 1, 'Gradient', 1, 'Process Alarms'),
  (4, 'de', 1, 'Gradient', 1, 'Process Alarms'),
  (5, 'en', 1, 'Hold Time', 1, 'Process Alarms'),
  (5, 'de', 1, 'Haltezeit', 1, 'Process Alarms'),
  (7, 'en', 1, 'Water Type', 1, 'Process Alarms'),
  (7, 'de', 1, 'Wassersorte', 1, 'Process Alarms'),
  (8, 'en', 1, 'Level', 1, 'Process Alarms'),
  (8, 'de', 1, 'Niveau', 1, 'Process Alarms'),
  (13, 'en', 1, 'Rinse Time', 1, 'Process Alarms'),
  (16, 'en', 1, 'Drain', 1, 'Process Alarms'),
  (16, 'de', 1, 'Ablauf', 1, 'Process Alarms'),
  (18, 'en', 1, 'Waiting Time', 1, 'Process Alarms'),
  (18, 'de', 1, 'Nachlaufzeit', 1, 'Process Alarms'),
  (20, 'en', 1, 'Dosing Curve AT1', 1, 'Process Alarms'),
  (20, 'de', 1, 'Dosierkurve AB1', 1, 'Process Alarms'),
  (22, 'en', 1, 'Dosing Time AT1', 1, 'Process Alarms'),
  (22, 'de', 1, 'Dosierzeit AB1', 1, 'Process Alarms'),
  (25, 'en', 1, 'Dosing Curve AT2', 1, 'Process Alarms'),
  (25, 'de', 1, 'Dosierkurve AB2', 1, 'Process Alarms'),
  (27, 'en', 1, 'Dosing Time AT2', 1, 'Process Alarms'),
  (27, 'de', 1, 'Dosierzeit AB2', 1, 'Process Alarms'),
  (36, 'en', 1, 'Alert time', 1, 'Process Alarms'),
  (36, 'de', 1, 'Zeit bis Alarm', 1, 'Process Alarms'),
  (60, 'en', 1, 'Check prep. number', 1, 'Process Alarms'),
  (60, 'de', 1, 'Einzug Nr.  AB1', 1, 'Process Alarms'),
  (81, 'en', 1, 'Set Time Speed', 1, 'Process Alarms'),
  (81, 'de', 1, 'Sollzeit Gesch.', 1, 'Process Alarms'),
  (82, 'en', 1, 'Protect Time Speed', 1, 'Process Alarms'),
  (82, 'de', 1, 'Schutzzeit Geschw.', 1, 'Process Alarms'),
  (83, 'en', 1, 'Speed', 1, 'Process Alarms'),
  (83, 'de', 1, 'Geschwindigkeit', 1, 'Process Alarms'),
  (131, 'en', 1, 'Set time AT1', 1, 'Process Alarms'),
  (131, 'de', 1, 'Sollzeit AB1', 1, 'Process Alarms'),
  (132, 'en', 1, 'Protect time AT1', 1, 'Process Alarms'),
  (132, 'de', 1, 'Schutzzeit AB1', 1, 'Process Alarms'),
  (134, 'en', 1, 'Valve AT1', 1, 'Process Alarms'),
  (134, 'de', 1, 'Füllventil AB1', 1, 'Process Alarms'),
  (135, 'en', 1, 'Level AT1', 1, 'Process Alarms'),
  (136, 'en', 1, 'Temperature AT1', 1, 'Process Alarms'),
  (136, 'de', 1, 'Temperatur AB1', 1, 'Process Alarms'),
  (137, 'en', 1, 'Dissolving time AT1', 1, 'Process Alarms'),
  (137, 'de', 1, 'Lösezeit AB1', 1, 'Process Alarms'),
  (138, 'en', 1, 'Mixer AT1', 1, 'Process Alarms'),
  (138, 'de', 1, 'Mischen AB1', 1, 'Process Alarms'),
  (140, 'en', 1, 'Recipe number AT1', 1, 'Process Alarms'),
  (140, 'de', 1, 'Rezept Nummer AB1', 1, 'Process Alarms'),
  (141, 'en', 1, 'Preparation no', 1, 'Process Alarms'),
  (141, 'de', 1, 'Ansatz Nr. AB1', 1, 'Process Alarms'),
  (143, 'en', 1, 'Tank No AT1', 1, 'Process Alarms'),
  (143, 'de', 1, 'Tank Nr. AB1', 1, 'Process Alarms'),
  (144, 'en', 1, 'Prep. release AT1', 1, 'Process Alarms'),
  (144, 'de', 1, 'Ansatz Freigabe AB1', 1, 'Process Alarms'),
  (145, 'en', 1, 'Station No AT1', 1, 'Process Alarms'),
  (145, 'de', 1, 'Stationsnummer AB1', 1, 'Process Alarms'),
  (151, 'en', 1, 'Set time AT2', 1, 'Process Alarms'),
  (151, 'de', 1, 'Sollzeit AB2', 1, 'Process Alarms'),
  (152, 'en', 1, 'Protect time AT2', 1, 'Process Alarms'),
  (152, 'de', 1, 'Schutzzeit AB2', 1, 'Process Alarms'),
  (154, 'en', 1, 'Valve AT2', 1, 'Process Alarms'),
  (154, 'de', 1, 'Füllventil AB2', 1, 'Process Alarms'),
  (155, 'en', 1, 'Level AT2', 1, 'Process Alarms'),
  (155, 'de', 1, 'Niveau AB2', 1, 'Process Alarms'),
  (156, 'en', 1, 'Temperature AT2', 1, 'Process Alarms'),
  (156, 'de', 1, 'Temperatur AB2', 1, 'Process Alarms'),
  (157, 'en', 1, 'Dissolving time AT2', 1, 'Process Alarms'),
  (157, 'de', 1, 'Lösezeit AB2', 1, 'Process Alarms'),
  (158, 'en', 1, 'Mixer AT2', 1, 'Process Alarms'),
  (158, 'de', 1, 'Mischen AB2', 1, 'Process Alarms'),
  (160, 'en', 1, 'Recipe number AT2', 1, 'Process Alarms'),
  (160, 'de', 1, 'Rezept Nummer AB2', 1, 'Process Alarms'),
  (161, 'en', 1, 'PreparÍ┐ü»Ä~eR', 1, 'Process Alarms'),
  (161, 'de', 1, 'Ansatz Nummer AB2', 1, 'Process Alarms'),
  (163, 'en', 1, 'Tank No AT2', 1, 'Process Alarms'),
  (163, 'de', 1, 'Tank Nr. AB2', 1, 'Process Alarms'),
  (164, 'en', 1, 'Prep. release AT2', 1, 'Process Alarms'),
  (164, 'de', 1, 'Ansatz Freigabe AB2', 1, 'Process Alarms'),
  (165, 'en', 1, 'Station No AT2', 1, 'Process Alarms'),
  (165, 'de', 1, 'Stationsnummer AB2', 1, 'Process Alarms'),
  (271, 'de', 1, 'Zeit bis Alarm AB1', 1, 'Process Alarms'),
  (272, 'de', 1, 'Einzug Nr. AB1', 1, 'Process Alarms'),
  (273, 'en', 1, 'ReleaseNextBatch AT1', 1, 'Process Alarms'),
  (273, 'de', 1, 'Partiefreigabe AB1', 1, 'Process Alarms'),
  (274, 'en', 1, 'required in', 1, 'Process Alarms'),
  (274, 'de', 1, 'Benötigt in', 1, 'Process Alarms'),
  (275, 'en', 1, 'Pump pressure', 1, 'Process Alarms'),
  (275, 'de', 1, 'Pumpendruck', 1, 'Process Alarms'),
  (276, 'en', 1, 'Quantity', 1, 'Process Alarms'),
  (276, 'de', 1, 'Menge', 1, 'Process Alarms'),
  (281, 'de', 1, 'Zeit bis Alarm AB2', 1, 'Process Alarms'),
  (282, 'de', 1, 'Einzug Nr. AB2', 1, 'Process Alarms'),
  (283, 'de', 1, 'Partiefreigabe AB2', 1, 'Process Alarms'),
  (284, 'en', 1, 'required in', 1, 'Process Alarms'),
  (284, 'de', 1, 'Benötigt in', 1, 'Process Alarms'),
  (291, 'en', 1, 'Check prep. number', 1, 'Process Alarms'),
  (291, 'de', 1, 'Einzug Nr.  AB2', 1, 'Process Alarms')
ON CONFLICT (alarm_no, language, machine_group_no) DO UPDATE SET alarm_text = EXCLUDED.alarm_text;

INSERT INTO cfg_functions (function_no, function_name, function_name_local, function_group_no, machine_group_no, parameter_count) VALUES
  (678, 'Fill ST1 Quantity', 'RK Mikt.Doldur', 1, 1, 5),
  (668, 'Filling AT2 Level', 'BK Doldur', 1, 1, 5),
  (401, 'Pump Set Value', 'Pompa Hizi', 1, 1, 1),
  (262, 'Check pH Min-Max', 'pH Kontrol Min-Max', 1, 1, 3),
  (661, 'Dyes/Chemicals AT2', 'Boya/Kimyasal BK', 1, 1, 2),
  (671, 'Dyes/Chemicals ST1', 'Dyes/Chemicals ST1', 1, 1, 2),
  (708, 'Machine -> ST1', 'Makine->ST', 1, 1, 0),
  (709, 'Rinse Nozzle', 'Yikama Hattan Duze', 1, 1, 3),
  (713, 'Fill Level', 'Seviye Doldur', 1, 1, 2),
  (702, 'Circulate AT2 -> App', 'Sirkülasyon BK -> AK', 1, 1, 6),
  (2, 'Program End', 'Program Son', 1, 1, 0),
  (3, 'No Operation', 'Islem Yok', 1, 1, 0),
  (5, 'Addition End', 'Ilave Son', 1, 1, 0),
  (4, 'Addition Start', 'Ilave Basla', 1, 1, 0),
  (21, 'Fill Level', 'Füllen auf Niveau', 1, 1, 2),
  (22, 'Fill Quantity', 'Miktar Doldur', 1, 1, 2),
  (23, 'Fill Blendw. Level', 'Füll Mischw. Niveau', 1, 1, 2),
  (24, 'Fill Blendw. Quant.', 'Füll Mischw. Menge', 1, 1, 2),
  (719, 'Fill Quantity ST', 'RK Mikt.Doldur', 1, 1, 5),
  (716, 'ST -> Machine', 'RK->Makine', 1, 1, 2),
  (126, 'Check', 'Kontrol', 1, 1, 1),
  (123, 'Sample', 'Numune', 1, 1, 1),
  (122, 'Unload', 'Mal Bosalt', 1, 1, 1),
  (65, 'HT-Drain', 'HT-Ablassen', 1, 1, 0),
  (127, 'Check pH', 'pH Kontrol', 1, 1, 2),
  (141, 'Temperature Control', 'Sicaklik Kontrol', 1, 1, 3),
  (145, 'Heating', 'Isitma', 1, 1, 3),
  (144, 'Runtime', 'Sirkulasyon', 1, 1, 1),
  (146, 'Cooling', 'Sogutma', 1, 1, 3),
  (227, 'Dosing AT1', 'Dozaj KK', 1, 1, 6),
  (653, 'Wait AT1', 'Wait AT1', 1, 1, 0),
  (652, 'Start batch +1 AT1', 'Start batch +1 AT1', 1, 1, 1),
  (654, 'Go AT1', 'Go AT1', 1, 1, 0),
  (655, 'Prep. AT1->ST1 ok', 'Prep. AT1->ST1 ok', 1, 1, 1),
  (656, 'Call Prep.AT1', 'Call Prep.AT1', 1, 1, 6),
  (662, 'Start batch +1 AT2', 'Start batch +1 AT2', 1, 1, 1),
  (663, 'Wait AT2', 'Wait AT2', 1, 1, 0),
  (664, 'Go AT2', 'Go AT2', 1, 1, 0),
  (666, 'Call Prep.AT2', 'Call Prep.AT2', 1, 1, 6),
  (672, 'Start batch +1 ST1', 'Start batch +1 ST1', 1, 1, 1),
  (676, 'Call Prep. ST1', 'Call Prep. ST1', 1, 1, 6),
  (533, 'Drain AT2', 'BK Bosalt', 1, 1, 0),
  (37, 'Fill Memo', 'Doldur Hafiza', 1, 1, 1),
  (665, 'Prep. AT2->ST1 ok', 'Prep. AT2->ST1 ok', 1, 1, 1),
  (38, 'Fill Blendw. Memo', 'Füll Mischw. Memo', 1, 1, 1),
  (261, 'Load', 'Yukle', 1, 1, 3),
  (119, 'ST --> MA', 'RK --> AK', 1, 1, 2),
  (411, 'Material Flow', 'Warenlauf', 1, 1, 1),
  (513, 'Drain AT1', 'KK Bosalt', 1, 1, 0),
  (130, 'Check H2O2', 'H2O2 Kontrol', 1, 1, 1),
  (228, 'Dosing AT2', 'Dozaj BK', 1, 1, 6),
  (231, 'Salt Transfer -> MA', 'Salz Transfer -> App', 1, 1, 5),
  (239, 'Inject Time AT1', 'Einziehen Zeit AG1', 1, 1, 6),
  (79, 'Drain/Fill', 'Bosalt Doldur', 1, 1, 3),
  (237, 'Inject AT1', 'Transfer KK', 1, 1, 4),
  (238, 'Inject AT2', 'Transfer BK', 1, 1, 4),
  (240, 'Inject Time AT2', 'Einziehen Zeit AG2', 1, 1, 6),
  (417, 'Material Flow Vario.', 'Kule / Düze', 1, 1, 2),
  (657, 'Mixing AT1', 'KK Mikser', 1, 1, 2),
  (667, 'Mixing AT2', 'BK Mikser', 1, 1, 2),
  (242, 'Rinse Time Mode', 'Yikama Zamanli', 1, 1, 4),
  (243, 'Rinse Quantity Mode', 'Yimama Miktarli', 1, 1, 4),
  (1, 'Program Start', 'Program Start', 1, 1, 0),
  (722, 'Soda AT2 Quantity', 'BK 2Soda Doldur', 1, 1, 1),
  (673, 'Wait ST1', 'Wait ST1', 1, 1, 0),
  (241, 'Rinsing / Cooling', 'Yika / Sogut', 1, 1, 2),
  (747, 'Rinsing / Cooling', 'Yika / Sogut', 1, 1, 2),
  (938, 'Dosing Prpgression 1', 'KK Dozaj', 1, 1, 5),
  (730, 'Calculation', 'Tekrar Hesaplamak', 1, 1, 0),
  (723, 'Sodaash', 'Soda Al', 1, 1, 2),
  (651, 'Dyes/Chemicals AT1', 'Dyes/Chemicals AT1', 1, 1, 2),
  (718, 'Filling AT2 Level', 'BK Doldur', 1, 1, 5),
  (717, 'Filling AT1 Level', 'KK Doldur', 1, 1, 5),
  (720, 'Fill Level ST', 'RK Seviye Doldur', 1, 1, 5),
  (93, 'Inject AT1-->ST', 'KK-->ST Transfer', 1, 1, 0),
  (710, 'Rinse Time Mode', 'Yikama Zamanli', 1, 1, 4),
  (658, 'Filling AT1 Level', 'KK Doldur', 1, 1, 5),
  (712, 'Material Flow', 'Kule Hizi', 1, 1, 2),
  (404, 'Dye Liquor Pump', 'Pompa Hiz', 1, 1, 2),
  (139, 'Stop', 'Bekle', 1, 1, 1),
  (680, 'Transfer AT1 -> ST', 'Transfer KK -> RK', 1, 1, 2),
  (711, 'Rinse Conductivity', 'Yikama Iletkenlikli', 1, 1, 5),
  (244, 'Rinse Time BW Mode', 'Spülen Zeit MW Mode', 1, 1, 4),
  (71, 'Drain Percent', 'AK Bosaltma', 1, 1, 3),
  (61, 'Drain Level', 'Ablassen Niveau', 1, 1, 3),
  (516, 'Prep. AT1 ->MA ok', 'KK Hazirla', 1, 1, 1),
  (551, 'Drain ST', 'RK Bosalt', 1, 1, 0),
  (701, 'Circulate AT1 -> MA', 'Sirkülasyon KK -> AK', 1, 1, 6),
  (681, 'Transfer AT2 -> ST', 'Transfer BK -> RK', 1, 1, 2),
  (679, 'Fill ST1 Level', 'RK Seviye Doldur', 1, 1, 5),
  (28, 'Fill Blendw. Percent', 'Füll Mischw. Prozent', 1, 1, 2),
  (674, 'Go ST1', 'Go ST1', 1, 1, 0),
  (245, 'Rinse Qua. BW Mode', 'Spülen Menge MW Mode', 1, 1, 4),
  (39, 'Memory level !', 'Hafiza Seviye', 1, 1, 0),
  (536, 'Prep. AT2 ->MA ok', 'BK Hazirla', 1, 1, 1),
  (27, 'Fill Level Percent', 'Füllen auf Prozent', 1, 1, 2),
  (721, 'Circulate ST<->AT1', 'Sirkulasyon RK<->KK', 1, 1, 2),
  (554, 'Prep. ST1 ok !', 'ST Hazirla !', 1, 1, 1),
  (714, 'Rinsing ST', 'Yikama Stok Tankdan', 1, 1, 4),
  (803, 'Pressurize off', 'Basinc Bosalt', 1, 1, 0),
  (715, 'Dosing AT2->AT1', 'Dozaj BK->KK', 1, 1, 6),
  (800, 'Machine Clear on', 'Ic Yikama Ac', 1, 1, 1),
  (802, 'Pressurize on', 'Basinc Al', 1, 1, 0),
  (801, 'Machine Clear off', 'Ic Yikama Kapa', 1, 1, 0),
  (939, 'Dosing Prpgression 2', 'BK Dozaj', 1, 1, 5)
ON CONFLICT (function_no) DO NOTHING;

INSERT INTO cfg_resources (resource_no, resource_name, machine_group_no) VALUES
  (1, 'Main Vessel (V1)', 1),
  (2, 'Circulation Pump (P1)', 1),
  (3, 'Fabric Reel / Winch (R1)', 1),
  (4, 'Dosing Tank 1 (DT1)', 1),
  (5, 'Dosing Tank 2 (DT2)', 1)
ON CONFLICT (resource_no) DO NOTHING;

INSERT INTO cfg_system_constants (system_constant_no, system_constant_name, value, machine_group_no) VALUES
  (1, 'SC_MAX_TEMP', '140.0', 1),
  (2, 'SC_DEFAULT_LIQUOR_RATIO', '8.0', 1),
  (3, 'SC_VERSION', '12.4.4.1119', 1)
ON CONFLICT (system_constant_no) DO NOTHING;

INSERT INTO machines (machine_no, display_name, ip_address, status, current_temp, current_step, current_batch, capacity_kg) VALUES
  ('TD12', 'SETEX Controller TD12', '192.168.1.102', 'ONLINE', 98.5, 12, 'PJT026', 350.0),
  ('TD13', 'SETEX Controller TD13', '192.168.1.103', 'ONLINE', 40.0, 1, 'PJT029', 350.0),
  ('TD14', 'SETEX Controller TD14', '192.168.1.104', 'ONLINE', 30.0, 0, NULL, 400.0)
ON CONFLICT (machine_no) DO UPDATE SET status = EXCLUDED.status, current_temp = EXCLUDED.current_temp;

INSERT INTO dyelots (dyelot_no, batch_no, machine_no, recipe_code, program_no, customer, article, color_code, color_name, fabric_weight_kg, liquor_ratio, total_water_l, status, position) VALUES
  ('DYE-062340', 'PJT026', 'TD12', 'REC-VIOLET-30S', 401, 'PT. ARTA PERMAI', 'CM 30S RIB', '1650159', 'UNGU TUA', 325.85, 8.0, 2606.8, 'RUNNING', 1),
  ('DYE-062341', 'PJT027', 'TD12', 'REC-BLEACH-45S', 182, 'PT. SUKSES MAKMUR', 'TC 45S COMBED', 'WHITE-01', 'PUTIH BLEACH', 400.0, 7.5, 3000.0, 'WAITING_LA', 2),
  ('DYE-062342', 'PJT028', 'TD12', 'REC-BLACK-POLY', 502, 'PT. SAMATEX INDAH', 'POLY MICRO 75D', 'BK-9901', 'JET BLACK', 380.0, 8.0, 3040.0, 'QUEUED', 3),
  ('DYE-062343', 'PJT029', 'TD13', 'REC-YELLOW-COT', 401, 'PT. CITRA TEX', 'BABY TERRY 20S', 'YL-4002', 'KUNING LEMON', 300.0, 8.5, 2550.0, 'QUEUED', 1)
ON CONFLICT (dyelot_no) DO NOTHING;

INSERT INTO recipes (recipe_code, recipe_name, customer_name, fabric_type, standard_liquor_ratio) VALUES
  ('REC-VIOLET-30S', 'Reactive Violet 30S Cotton', 'PT. ARTA PERMAI', 'COTTON COMBED 30S', 8.0)
ON CONFLICT (recipe_code) DO NOTHING;

INSERT INTO program_headers (program_no, program_name, fabric_type, estimated_duration_min) VALUES
  (401, 'COTTON_REACTIVE_DYEING', 'COTTON', 180)
ON CONFLICT (program_no) DO NOTHING;

INSERT INTO employees (employee_id, full_name, role, shift, is_active) VALUES
  ('EMP-001', 'Bambang Sutrisno', 'HEAD_DYER', 1, TRUE),
  ('EMP-002', 'Agus Hendra', 'OPERATOR_CELUP', 1, TRUE),
  ('EMP-003', 'Rudi Hartono', 'OPERATOR_CELUP', 2, TRUE)
ON CONFLICT (employee_id) DO NOTHING;

INSERT INTO user_roles (role_id, role_name, description) VALUES
  ('ADMIN', 'System Administrator', 'Akses penuh konfigurasi'),
  ('OPERATOR', 'Machine Operator', 'Operator mesin celup di lapangan'),
  ('THIRD_PARTY', 'ERP Integration API', 'Akses integrasi sistem pihak ketiga')
ON CONFLICT (role_id) DO NOTHING;

INSERT INTO users (user_id, username, password_hash, full_name, is_active) VALUES
  ('USR-001', 'admin', '$2b$12$e/samplehashadmin', 'Administrator OrgaTEX', TRUE),
  ('USR-002', 'erp_integration', '$2b$12$e/samplehasherp', 'SAP ERP Third Party Service', TRUE)
ON CONFLICT (user_id) DO NOTHING;
