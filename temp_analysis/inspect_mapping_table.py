import psycopg2

conn = psycopg2.connect("postgresql://postgres:sensorSMM!@192.168.100.30:5433/pt_smm_jetflow")
cur = conn.cursor()

cur.execute("""
    SELECT column_name, data_type, is_nullable 
    FROM information_schema.columns 
    WHERE table_name = 'cfg_machine_iw_tag_mapping'
    ORDER BY ordinal_position;
""")
cols = cur.fetchall()
print("Columns in cfg_machine_iw_tag_mapping:")
for c in cols:
    print(f"  {c[0]} ({c[1]}, nullable={c[2]})")

cur.execute("""
    SELECT conname, contype, pg_get_constraintdef(c.oid)
    FROM pg_constraint c
    JOIN pg_class t ON c.conrelid = t.oid
    WHERE t.relname = 'cfg_machine_iw_tag_mapping';
""")
constrs = cur.fetchall()
print("\nConstraints:")
for c in constrs:
    print(f"  {c[0]} ({c[1]}): {c[2]}")

conn.close()
