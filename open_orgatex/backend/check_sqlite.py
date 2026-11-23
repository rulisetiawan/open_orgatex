import sqlite3

for dbpath in ['open_orgatex/backend/data/orgatex_local.db', 'open_orgatex/backend/open_orgatex.db']:
    try:
        conn = sqlite3.connect(dbpath)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cur.fetchall()]
        print(dbpath, 'tables count:', len(tables))
        if 'cfg_machine_iw_tag_mapping' in tables:
            cur.execute('SELECT COUNT(*) FROM cfg_machine_iw_tag_mapping;')
            cnt = cur.fetchone()[0]
            print(f'  cfg_machine_iw_tag_mapping count: {cnt}')
            cur.execute('SELECT * FROM cfg_machine_iw_tag_mapping LIMIT 10;')
            for row in cur.fetchall():
                print('   ', row)
    except Exception as e:
        print(dbpath, 'error:', e)
