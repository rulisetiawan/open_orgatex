"""
SQLAlchemy Models for PostgreSQL TimescaleDB
Matches public & orgatex schema on pt_smm_jetflow
Incorporates official OrgaTEX Program Editor (EDX300) Procedure & Treatment Architecture
"""

from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Numeric, Boolean,
    DateTime, ForeignKey, UniqueConstraint, func
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# =============================================================================
# 1. RDM & RECIPES (CDC800 / RDM LAYER)
# =============================================================================

class Category(Base):
    __tablename__ = 'categories'

    category_id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    parent_id = Column(String(50), ForeignKey('categories.category_id'))
    is_system = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Item(Base):
    __tablename__ = 'items'

    item_id = Column(String(36), primary_key=True)
    code = Column(String(100), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    category_id = Column(String(50), ForeignKey('categories.category_id'), nullable=False)
    unit = Column(String(20), default='g/l')
    density = Column(Numeric(8, 4), default=1.0)
    stock_qty = Column(Numeric(12, 3), default=0.0)
    is_active = Column(Boolean, default=True)

class Recipe(Base):
    __tablename__ = 'recipes'

    recipe_id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    recipe_code = Column(String(100), nullable=False, unique=True)
    recipe_name = Column(String(255), nullable=False)
    customer_name = Column(String(255))
    fabric_type = Column(String(100), default='COTTON')
    standard_liquor_ratio = Column(Numeric(5, 2), default=8.0)
    notes = Column(Text)

    items = relationship("RecipeItem", back_populates="recipe", cascade="all, delete-orphan")

class RecipeItem(Base):
    __tablename__ = 'recipe_items'

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    recipe_id = Column(BigInteger, ForeignKey('recipes.recipe_id'), nullable=False)
    chemical_code = Column(String(100), nullable=False)
    chemical_name = Column(String(255), nullable=False)
    amount = Column(Numeric(10, 4), nullable=False)
    unit = Column(String(20), default='g/l')
    dosing_tank = Column(Integer, default=1)

    recipe = relationship("Recipe", back_populates="items")

# =============================================================================
# 2. MASTER MACHINES (SETEX SECOM 777 CONTROLLERS)
# =============================================================================

class Machine(Base):
    __tablename__ = 'machines'

    machine_no = Column(String(50), primary_key=True)
    display_name = Column(String(150), nullable=False)
    ip_address = Column(String(50), nullable=False)
    tcp_port = Column(Integer, default=50000)
    ftp_port = Column(Integer, default=21)
    controller_type = Column(String(50), default='SECOM777')
    os_family = Column(String(50), default='WindowsCE')
    group_name = Column(String(100), default='Dyeing Section')
    capacity_kg = Column(Numeric(8, 2), default=350.0)
    default_liquor_ratio = Column(Numeric(5, 2), default=8.0)
    tanks_count = Column(Integer, default=2)
    share_folder_path = Column(String(500), default='/app/STATUS')
    polling_interval_sec = Column(Integer, default=5)
    is_active = Column(Boolean, default=True)
    status = Column(String(30), default='ONLINE')
    current_batch = Column(String(50))
    current_step = Column(Integer)
    current_temp = Column(Numeric(5, 2))
    last_ping_time = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# =============================================================================
# 3. ORGATEX EDX300 PROGRAM & SUB-PROGRAM (TREATMENT) ARCHITECTURE
# Exactly matches OrgaTEX ProgramComponent & StepList schema
# =============================================================================

class ProcessGroup(Base):
    """OrgaTEX ProcessGroup (Kelompok Proses Celup: Discontinuous, Continuous, Lab)"""
    __tablename__ = 'process_groups'

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    level = Column(Integer, default=1)
    hidden = Column(Boolean, default=False)
    parent_group_id = Column(BigInteger, ForeignKey('process_groups.id'))

class ProgramComponent(Base):
    """
    OrgaTEX ProgramComponent
    Level 1: Procedure (Program Induk Celup, e.g. 'VINYL ONE BATH')
    Level 2: Treatment (Sub-Program Perlakuan, e.g. 'Scouring 98C', 'Dyeing 60C', 'Soaping')
    """
    __tablename__ = 'program_components'

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    level = Column(Integer, nullable=False, default=1)  # 1 = Procedure (Induk), 2 = Treatment (Sub-Program)
    type = Column(Integer, nullable=False, default=1)   # 1 = Discontinuous (Jet Dyeing), 2 = Continuous
    number = Column(String(100), nullable=False)        # '0001', '0002', 'TR-SCOUR', dll.
    name = Column(String(255), nullable=False)          # Nama Program atau Nama Sub-Program
    comment = Column(Text)                              # Keterangan / Deskripsi proses
    hidden = Column(Boolean, default=False)
    machine_code = Column(String(50), default='C012')
    content_type = Column(Integer, default=0)
    creation_time = Column(DateTime(timezone=True), server_default=func.now())
    modification_time = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relasi untuk Procedure (Level 1) ke Child Treatments (Level 2)
    sub_program_items = relationship(
        "ProgramComponentItem",
        foreign_keys="ProgramComponentItem.parent_component_id",
        back_populates="parent_component",
        cascade="all, delete-orphan",
        order_by="ProgramComponentItem.position"
    )

    # Relasi Steps untuk Treatment (Level 2)
    steps = relationship(
        "Step",
        back_populates="parent_component",
        cascade="all, delete-orphan",
        order_by="Step.position"
    )

class ProgramComponentItem(Base):
    """
    OrgaTEX ProgramComponentItem
    Menghubungkan Program Induk (Procedure) dengan urutan Sub-Program (Treatment).
    """
    __tablename__ = 'program_component_items'

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    position = Column(Integer, nullable=False, default=1)  # Posisi urutan Sub-Program dalam Program Induk
    parent_component_id = Column(BigInteger, ForeignKey('program_components.id'), nullable=False)
    program_component_id = Column(BigInteger, ForeignKey('program_components.id'), nullable=False)

    parent_component = relationship("ProgramComponent", foreign_keys=[parent_component_id], back_populates="sub_program_items")
    treatment = relationship("ProgramComponent", foreign_keys=[program_component_id])
    parameters = relationship("ProgramComponentParameter", back_populates="component_item", cascade="all, delete-orphan")

class ProgramComponentParameter(Base):
    """
    OrgaTEX ProgramComponentParameter
    Nilai parameter dinamis yang dioper saat Sub-Program dipanggil di Program Induk.
    """
    __tablename__ = 'program_component_parameters'

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    program_component_item_id = Column(BigInteger, ForeignKey('program_component_items.id'), nullable=False)
    treatment_parameter_number = Column(Integer, nullable=False)
    parameter_name = Column(String(100))
    value = Column(Numeric(12, 4), default=0.0)

    component_item = relationship("ProgramComponentItem", back_populates="parameters")

class Step(Base):
    """
    OrgaTEX Step (Langkah-langkah dalam Sub-Program Treatment)
    """
    __tablename__ = 'steps'

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    position = Column(Integer, nullable=False, default=1)  # Nomor urut langkah dalam Sub-Program
    parent_component_id = Column(BigInteger, ForeignKey('program_components.id'), nullable=False)
    label = Column(String(100))
    summary_temp = Column(Numeric(6, 2))
    summary_time_min = Column(Numeric(6, 2))
    summary_water_l = Column(Numeric(10, 2))

    parent_component = relationship("ProgramComponent", back_populates="steps")
    functions = relationship("StepFunction", back_populates="step", cascade="all, delete-orphan", order_by="StepFunction.resource_number")

class StepFunction(Base):
    """
    OrgaTEX StepFunction (Fungsi F-Code SETEX Secom 777 di dalam Step)
    """
    __tablename__ = 'step_functions'

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    step_id = Column(BigInteger, ForeignKey('steps.id'), nullable=False)
    resource_number = Column(Integer, nullable=False, default=1)   # Kolom 1..N (1=Main, 2=Pump, 3=Reel)
    function_number = Column(Integer, nullable=False)               # 713 (Fill), 141 (Heat), 121 (Hold), 85/86 (Dose), dll.
    function_name = Column(String(100))
    label = Column(Integer, default=0)
    label_type = Column(Integer, default=0)
    acknowledge = Column(Integer, default=0)
    comment = Column(String(255))

    step = relationship("Step", back_populates="functions")
    parameters = relationship("StepFunctionParameter", back_populates="step_function", cascade="all, delete-orphan", order_by="StepFunctionParameter.function_parameter_number")

class StepFunctionParameter(Base):
    """
    OrgaTEX StepFunctionParameter (Nilai numerik slot parameter fungsi kontroler)
    """
    __tablename__ = 'step_function_parameters'

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    step_function_id = Column(BigInteger, ForeignKey('step_functions.id'), nullable=False)
    function_parameter_number = Column(Integer, nullable=False, default=1)  # Slot 1, 2, dst.
    attribute = Column(Integer, default=0)
    value = Column(Numeric(12, 4), default=0.0)
    treatment_parameter_number = Column(Integer)

    step_function = relationship("StepFunction", back_populates="parameters")

class ProgramComponent2Group(Base):
    """OrgaTEX ProgramComponent2Group"""
    __tablename__ = 'program_component_2_groups'

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    process_group_id = Column(BigInteger, ForeignKey('process_groups.id'), nullable=False)
    program_component_id = Column(BigInteger, ForeignKey('program_components.id'), nullable=False)

# =============================================================================
# 4. LEGACY FLAT TABLES (Untuk kompatibilitas mundur / Secom 777 Flat .PRG)
# =============================================================================

class ProgramHeader(Base):
    __tablename__ = 'program_headers'

    program_no = Column(Integer, primary_key=True)
    program_name = Column(String(30), nullable=False)
    fabric_type = Column(String(100), default='COTTON')
    estimated_duration_min = Column(Integer, default=0)
    compiled_file_path = Column(String(500))

    steps = relationship("ProgramStep", back_populates="program", cascade="all, delete-orphan")

class ProgramStep(Base):
    __tablename__ = 'program_steps'

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    program_no = Column(Integer, ForeignKey('program_headers.program_no'), nullable=False)
    step_no = Column(Integer, nullable=False)
    label = Column(String(60))

    program = relationship("ProgramHeader", back_populates="steps")
    functions = relationship("ProgramStepFunction", back_populates="step", cascade="all, delete-orphan")

class ProgramStepFunction(Base):
    __tablename__ = 'program_step_functions'

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    step_id = Column(BigInteger, ForeignKey('program_steps.id'), nullable=False)
    column_no = Column(Integer, nullable=False)
    function_id = Column(Integer, nullable=False)
    param_1 = Column(Numeric(10, 2), default=0.0)
    param_2 = Column(Numeric(10, 2), default=0.0)

    step = relationship("ProgramStep", back_populates="functions")

# =============================================================================
# 5. BATCH HEADERS & TELEMETRY
# =============================================================================

class BatchHeader(Base):
    __tablename__ = 'batch_headers'

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    batch_ref_no = Column(String(50), unique=True, nullable=False)
    batch_no = Column(String(100), nullable=True)
    machine_no = Column(String(50), ForeignKey('machines.machine_no'), nullable=False)
    program_no = Column(Integer, default=1)
    recipe_id = Column(BigInteger, nullable=True)
    recipe_name = Column(String(255), nullable=True)
    customer = Column(String(150), nullable=True)
    article = Column(String(255), nullable=True)
    color_code = Column(String(100), nullable=True)
    color_name = Column(String(100), nullable=True)
    fabric_weight_kg = Column(Numeric(8, 2), default=350.0)
    liquor_ratio = Column(Numeric(5, 2), default=8.0)
    total_water_l = Column(Numeric(10, 2), nullable=True)
    status = Column(String(30), default='QUEUED')
    position = Column(Integer, default=1)
    planned_start_time = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MachineQueue(Base):
    __tablename__ = 'machine_queues'

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    machine_no = Column(String(50), ForeignKey('machines.machine_no'), nullable=False, index=True)
    batch_ref_no = Column(String(50), nullable=False, index=True)
    batch_no = Column(String(100), nullable=True)
    program_no = Column(Integer, default=1)
    recipe_name = Column(String(255), nullable=True)
    customer = Column(String(150), nullable=True)
    article = Column(String(255), nullable=True)
    color_code = Column(String(100), nullable=True)
    color_name = Column(String(100), nullable=True)
    fabric_weight_kg = Column(Numeric(8, 2), default=350.0)
    liquor_ratio = Column(Numeric(5, 2), default=8.0)
    total_water_l = Column(Numeric(10, 2), nullable=True)
    position = Column(Integer, default=1, nullable=False)
    status = Column(String(30), default='QUEUED')
    dispatched_at = Column(DateTime(timezone=True), nullable=True)
    dispatched_to_ip = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('machine_no', 'batch_ref_no', name='uq_machine_batch_queue'),
    )

class DatalogCyclicRecord(Base):
    __tablename__ = 'datalog_cyclic_records'

    log_timestamp = Column(DateTime(timezone=True), primary_key=True)
    machine_no = Column(String(50), primary_key=True)
    batch_ref_no = Column(String(50), primary_key=True)
    temp_pv = Column(Numeric(5, 2))
    temp_sp = Column(Numeric(5, 2))
    temp_pt100_t2 = Column(Numeric(5, 2))
    pump_speed_percent = Column(Numeric(5, 2))
    reel_speed_mpm = Column(Numeric(5, 2))
    vessel_pressure_bar = Column(Numeric(5, 2))
    step_no = Column(Integer)
    raw_digital_bits = Column(Integer)

class DatalogAlarm(Base):
    __tablename__ = 'datalog_alarms'
    __table_args__ = (
        UniqueConstraint('machine_no', 'batch_ref_no', 'alarm_timestamp', 'alarm_code', name='uq_alarm_pub'),
    )

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    batch_ref_no = Column(String(50), nullable=False, index=True)
    machine_no = Column(String(50), nullable=False, index=True)
    alarm_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    alarm_code = Column(String(50), nullable=False)
    alarm_text = Column(String(255), nullable=False)
    step_no = Column(Integer)
    operator_id = Column(Integer)
    severity = Column(String(20), default='WARNING')
    cleared_at = Column(DateTime(timezone=True))

# =============================================================================
# 6. ORGATEX EXACT CONFIGURATION TABLES (Parity: OtxDataBaseLayer.Database.Configuration)
# =============================================================================

class CfgAlarm(Base):
    __tablename__ = 'cfg_alarms'
    __table_args__ = (
        UniqueConstraint('alarm_no', 'language', 'machine_group_no', name='uq_cfg_alarm'),
    )

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    alarm_no = Column(Integer, nullable=False, index=True)
    language = Column(String(10), default='en', index=True)
    machine_group_no = Column(Integer, default=1, index=True)
    alarm_text = Column(String(255), nullable=False)
    alarm_group_no = Column(Integer, default=1)
    alarm_group_name = Column(String(100), default='Process Alarms')

class CfgAlarmGroup(Base):
    __tablename__ = 'cfg_alarm_groups'

    alarm_group_no = Column(Integer, primary_key=True)
    alarm_group_name = Column(String(100), nullable=False)
    machine_group_no = Column(Integer, default=1)

class CfgStopGroup(Base):
    __tablename__ = 'cfg_stop_groups'

    stop_group_no = Column(Integer, primary_key=True)
    stop_group_name = Column(String(100), nullable=False)
    machine_group_no = Column(Integer, default=1)

class CfgFunction(Base):
    __tablename__ = 'cfg_functions'

    function_no = Column(Integer, primary_key=True)
    function_name = Column(String(100), nullable=False)
    function_name_local = Column(String(100))
    function_group_no = Column(Integer, default=1)
    machine_group_no = Column(Integer, default=1)
    parameter_count = Column(Integer, default=0)

class CfgFunctionParameter(Base):
    __tablename__ = 'cfg_function_parameters'

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    function_no = Column(Integer, ForeignKey('cfg_functions.function_no'), nullable=False, index=True)
    parameter_no = Column(Integer, nullable=False)
    parameter_name = Column(String(100))
    default_val = Column(Numeric(10, 2), default=0.0)
    min_val = Column(Numeric(10, 2), default=0.0)
    max_val = Column(Numeric(10, 2), default=0.0)

class CfgResource(Base):
    __tablename__ = 'cfg_resources'

    resource_no = Column(Integer, primary_key=True)
    resource_name = Column(String(100), nullable=False)
    machine_group_no = Column(Integer, default=1)

# =============================================================================
# 7. OPERATOR INTERVENTIONS & SETPOINT AUDIT LOGS
# =============================================================================

class OperatorIntervention(Base):
    __tablename__ = 'operator_interventions'

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    machine_no = Column(String(50), nullable=False, index=True)
    batch_no = Column(String(50), index=True)
    step_no = Column(Integer)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    trigger_source = Column(String(50), default='ALARMS_LOG')  # ALARMS_LOG, STATUS_CHANGE, EVENT_BROKER, MANUAL
    alarm_code = Column(Integer)
    function_id = Column(Integer)  # e.g. 141 (Temperature Control), 71 (Drain), 713 (Fill)
    parameter_name = Column(String(100), nullable=False)  # e.g. "Target Temperature", "Holding Time", "Pump Speed"
    register_address = Column(Integer)  # Address in SET (1009) or param index (P1..P6)
    unit = Column(String(20), default='')  # °C, min, %, L
    value_before = Column(Numeric(10, 2))
    value_after = Column(Numeric(10, 2))
    delta = Column(Numeric(10, 2))
    operator_id = Column(Integer)
    notes = Column(Text)
    raw_details = Column(Text)  # JSON string of detailed snapshot

class BatchConsumption(Base):
    __tablename__ = 'batch_consumptions'

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    batch_ref_no = Column(String(50), nullable=False, index=True)
    machine_no = Column(String(50), nullable=False, index=True)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    water_liters = Column(Numeric(10, 2), default=0.0)
    power_kwh = Column(Numeric(10, 2), default=0.0)
    steam_kg = Column(Numeric(10, 2), default=0.0)
    runtime_minutes = Column(Numeric(10, 2), default=0.0)
    raw_counters = Column(Text, nullable=True)  # JSON dump of Object 1035 counters


