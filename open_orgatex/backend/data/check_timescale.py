import psycopg2

conn = psycopg2.connect(
    host='192.168.100.30',
    port=5433,
    dbname='pt_smm_jetflow',
    user='postgres',
    password='sensorSMM!'
)
cur = conn.cursor()

# Hypertable info
cur.execute("""
    SELECT hypertable_schema, hypertable_name, num_chunks, compression_enabled 
    FROM timescaledb_information.hypertables 
    WHERE hypertable_name='datalog_cyclic_records';
""")
print("Hypertable Info:", cur.fetchone())

# Dimensions / Chunk interval
cur.execute("""
    SELECT column_name, time_interval 
    FROM timescaledb_information.dimensions 
    WHERE hypertable_name='datalog_cyclic_records';
""")
print("Dimension & Chunk Interval:", cur.fetchall())

# Compression policy job
cur.execute("""
    SELECT job_id, proc_name, schedule_interval, config 
    FROM timescaledb_information.jobs 
    WHERE proc_name='policy_compression';
""")
print("Compression Policy Jobs:", cur.fetchall())

# Extensions
cur.execute("SELECT extname, extversion FROM pg_extension WHERE extname IN ('timescaledb', 'dblink', 'postgres_fdw');")
print("Installed Extensions:", cur.fetchall())

conn.close()
