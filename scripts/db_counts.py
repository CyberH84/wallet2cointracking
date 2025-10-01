"""Small helper to print row counts for key tables using the project's database config.

Run with the workspace Python environment (virtualenv):
D:/wallet2cointracking/.venv/Scripts/python.exe scripts/db_counts.py
"""
import sys
import os
import logging
from sqlalchemy import text

# Make sure the project root is on sys.path so top-level modules (like database)
# can be imported when running this script from scripts/.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    import database
except Exception as e:
    print('Failed to import project database module:', e)
    sys.exit(2)

logging.basicConfig(level=logging.INFO)

def main():
    try:
        db = database.db_config
        engine = db.initialize_engine()
        with engine.connect() as conn:
            tables = [
                'ethereum_transactions',
                'token_transfers',
                'wallet_analysis',
            ]
            for t in tables:
                try:
                    r = conn.execute(text(f'SELECT COUNT(*) FROM {t}'))
                    cnt = r.fetchone()[0]
                except Exception as e:
                    cnt = f'ERROR: {e}'
                print(f"{t}: {cnt}")
    except Exception as e:
        print('Database query failed:', e)
        sys.exit(3)

if __name__ == '__main__':
    main()
