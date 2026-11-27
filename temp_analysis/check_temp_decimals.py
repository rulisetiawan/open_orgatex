import psycopg2

def query_db(dbname, queries):
    print(f"================ DATABASE: {dbname} ================")
    conn = psycopg2.connect(f"host=192.168.100.30 port=5433 dbname={dbname} user=postgres password=sensorSMM!")
    cur = conn.cursor()
    for title, sql in queries:
        print(f"\n--- {title} ---")
        try:
            cur.execute(sql)
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchall()
            print("COLS:", cols)
            for r in rows:
                print(r)
            if not rows:
                print("(0 rows)")
        except Exception as e:
            print("ERROR:", e)
            conn.rollback()
    conn.close()

jetflow_queries = [
    ("Tables in pt_smm_jetflow", """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' ORDER BY table_name;
    """),
    ("Columns related to temp/decimal/digit/value in pt_smm_jetflow", """
        SELECT table_name, column_name, data_type, numeric_precision, numeric_scale
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND (column_name ILIKE '%temp%' OR column_name ILIKE '%digit%' OR column_name ILIKE '%dec%' OR column_name ILIKE '%scale%' OR column_name ILIKE '%val%' OR column_name ILIKE '%sv%' OR column_name ILIKE '%pv%')
        ORDER BY table_name, ordinal_position;
    """),
    ("cfg_function_parameters for Temp", """
        SELECT * FROM cfg_function_parameters
        WHERE name ILIKE '%temp%' OR unit ILIKE '%C%' OR unit ILIKE '%°%'
        LIMIT 30;
    """),
    ("cfg_machine_iw_tag_mapping for TEMP", """
        SELECT machine_code, iw_index, tag_code, unit, factor, digits_after, x1, x2, y1, y2
        FROM cfg_machine_iw_tag_mapping
        WHERE tag_code ILIKE '%TEMP%'
        ORDER BY machine_code, iw_index
        LIMIT 20;
    """),
    ("step_function_parameters with fractional values (non-integer)", """
        SELECT sfp.id, sfp.step_function_id, sfp.param_def_id, sfp.param_name, sfp.value, sfp.unit
        FROM step_function_parameters sfp
        WHERE sfp.value IS NOT NULL AND sfp.value <> trunc(sfp.value)
        LIMIT 30;
    """),
    ("steps summary_temp with fractional values", """
        SELECT id, program_id, step_number, summary_temp, summary_time, summary_gradient
        FROM steps
        WHERE summary_temp IS NOT NULL AND summary_temp <> trunc(summary_temp)
        LIMIT 20;
    """),
    ("operator_interventions sample", """
        SELECT * FROM operator_interventions ORDER BY id DESC LIMIT 20;
    """),
    ("datalog_cyclic_records sample temp_pv/temp_sv", """
        SELECT * FROM datalog_cyclic_records ORDER BY id DESC LIMIT 10;
    """),
    ("live_iw_telemetry sample", """
        SELECT machine_code, batch_no, prog_no, step_no, iw1_temp_pv, iw10_temp_sv, updated_at
        FROM live_iw_telemetry
        ORDER BY updated_at DESC LIMIT 10;
    """),
]

scada_queries = [
    ("tag_definition for TEMP", """
        SELECT tag_code, display_name, unit, decimals, min_value, max_value, data_type
        FROM tag_definition
        WHERE tag_code ILIKE '%TEMP%'
        ORDER BY tag_code
        LIMIT 30;
    """),
    ("tag_latest for TEMP with decimals", """
        SELECT tag_code, value_number, value_text, quality, source_ts
        FROM tag_latest
        WHERE tag_code ILIKE '%TEMP%'
        ORDER BY source_ts DESC
        LIMIT 20;
    """),
]

query_db("pt_smm_jetflow", jetflow_queries)
query_db("pt_smm_scada", scada_queries)
