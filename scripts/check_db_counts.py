import os, sys
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database import db_config
from sqlalchemy import text

engine = db_config.initialize_engine()
print('Database URL:', db_config.database_url)
with engine.connect() as conn:
    try:
        tables = conn.execute(text("SELECT schemaname, tablename FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema') ORDER BY schemaname, tablename")).fetchall()
        print('Tables:')
        for t in tables:
            print(' -', t[0], t[1])
    except Exception as e:
        print('Error listing tables:', repr(e))

    for tbl in ['ethereum_transactions', 'token_transfers', 'wallet_analysis']:
        try:
            c = conn.execute(text(f"SELECT count(*) FROM {tbl}")).fetchone()[0]
            print(f'{tbl}:', c)
        except Exception as e:
            print(f'Error selecting from {tbl}:', repr(e))
