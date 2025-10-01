#!/usr/bin/env python3
import csv, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import prepare_transaction_for_db
import database
from sqlalchemy import text

csv_path = Path(__file__).resolve().parent.parent / '0xb3a2f25d7956f96703c9ed3ce6ea25e4d47295d3_arbitrum_flare_transactions_20251001_065818.csv'

print('Using DB URL:', database.db_config.database_url)

rows = []
with open(csv_path, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for r in reader:
        rows.append(r)

print(f'Total CSV rows: {len(rows)}')

prepared = []
for i, r in enumerate(rows):
    tx = {k: r.get(k) for k in r}
    # parse logs if present
    if 'logs' in r and r['logs']:
        try:
            tx['logs'] = json.loads(r['logs'])
        except Exception:
            tx['logs'] = r['logs']
    db_tx = prepare_transaction_for_db(tx, {}, 'arbitrum', '0xb3a2f25d7956f96703c9ed3ce6ea25e4d47295d3')
    prepared.append(db_tx)

print('Prepared transactions:', len(prepared))

# Store into DB
res = database.db_manager.store_transactions(prepared, None)
print('store_transactions returned', res)

# Print counts and sample token_transfers
engine = database.db_config.initialize_engine()
with engine.connect() as conn:
    tt_count = conn.execute(text('SELECT COUNT(*) FROM token_transfers')).fetchone()[0]
    eth_count = conn.execute(text('SELECT COUNT(*) FROM ethereum_transactions')).fetchone()[0]
    print('ethereum_transactions', eth_count)
    print('token_transfers', tt_count)
    print('\nSample token_transfers (latest 10):')
    rows = conn.execute(text('SELECT id, tx_hash, token_address, value_raw, value_scaled, token_decimals FROM token_transfers ORDER BY id DESC LIMIT 10')).fetchall()
    for r in rows:
        # SQLAlchemy Row objects expose a _mapping for column access
        try:
            print(dict(r._mapping))
        except Exception:
            print(tuple(r))
