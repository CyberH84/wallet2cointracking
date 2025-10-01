"""Check that key timestamp columns are timestamptz and print sample values.

Usage: run this script with the project's virtualenv python.
"""
from database import db_config
from sqlalchemy import text
import json

TABLE_COLUMNS = {
    'ethereum_transactions': ['block_time', 'processed_at'],
    'token_transfers': ['block_time', 'processed_at'],
    'wallet_analysis': ['analysis_date', 'last_activity']
}


def main():
    engine = db_config.initialize_engine()
    with engine.connect() as conn:
        out = {}
        for table, cols in TABLE_COLUMNS.items():
            out[table] = {}
            for col in cols:
                # Query information_schema for column type
                info = conn.execute(text("""
                    SELECT data_type, udt_name
                    FROM information_schema.columns
                    WHERE table_name = :table AND column_name = :col
                """), {'table': table, 'col': col}).fetchone()

                if info is None:
                    col_info = None
                else:
                    # info is a Row; extract named fields safely
                    try:
                        col_info = { 'data_type': info[0], 'udt_name': info[1] }
                    except Exception:
                        col_info = dict(info._mapping) if hasattr(info, '_mapping') else None
                out[table][col] = {'column_info': col_info, 'samples': []}

                # Fetch a few sample values and render as ISO-8601 UTC strings
                try:
                    rows = conn.execute(text(f"SELECT {col} FROM {table} ORDER BY id DESC LIMIT 5")).fetchall()
                    for r in rows:
                        v = r[0]
                        if v is None:
                            out[table][col]['samples'].append(None)
                        else:
                            # Use Postgres to normalize to UTC string representation
                            s = conn.execute(text(f"SELECT to_char(({col} AT TIME ZONE 'UTC')::timestamp, 'YYYY-MM-DD\"T\"HH24:MI:SS') || 'Z' as iso_utc FROM {table} WHERE {col} IS NOT NULL LIMIT 1")).fetchone()
                            if s is not None:
                                out[table][col]['samples'].append(s[0])
                            else:
                                out[table][col]['samples'].append(str(v))
                except Exception as e:
                    out[table][col]['samples'].append({'error': str(e)})

        print(json.dumps(out, indent=2))


if __name__ == '__main__':
    main()
