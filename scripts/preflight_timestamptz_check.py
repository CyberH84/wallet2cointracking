"""Preflight check: verify key timestamp columns are timestamptz.

Exit code 0 = OK (all columns are timestamptz).
Exit code 2 = Problem detected (one or more columns not timestamptz).

Run this before applying migrations in production to ensure the UTC assumption holds.
"""
import sys
from database import db_config
from sqlalchemy import text

TABLE_COLUMNS = {
    'ethereum_transactions': ['block_time', 'processed_at'],
    'token_transfers': ['block_time', 'processed_at'],
    'wallet_analysis': ['analysis_date', 'last_activity']
}


def main():
    engine = db_config.initialize_engine()
    problems = []
    with engine.connect() as conn:
        for table, cols in TABLE_COLUMNS.items():
            for col in cols:
                info = conn.execute(text("""
                    SELECT data_type, udt_name
                    FROM information_schema.columns
                    WHERE table_name = :table AND column_name = :col
                """), {'table': table, 'col': col}).fetchone()

                udt = info[1] if info is not None else None
                if udt is None:
                    problems.append(f"{table}.{col}: column not found")
                elif udt.lower() not in ('timestamptz', 'timestamp with time zone') and 'timestamp with time zone' not in (info[0] or '').lower():
                    problems.append(f"{table}.{col}: expected timestamptz but found udt_name={udt}, data_type={info[0]}")

    if problems:
        print("Preflight failed: the following issues were found:")
        for p in problems:
            print(" - ", p)
        return 2

    print("Preflight OK: all checked columns are timestamptz")
    return 0


if __name__ == '__main__':
    sys.exit(main())
