#!/usr/bin/env python3
import csv, json, sys
from pprint import pprint
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import prepare_transaction_for_db

csv_path = Path(__file__).resolve().parent.parent / '0xb3a2f25d7956f96703c9ed3ce6ea25e4d47295d3_arbitrum_flare_transactions_20251001_065818.csv'

with open(csv_path, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

print(f"Total CSV rows: {len(rows)}")
for i, r in enumerate(rows[:10]):
    print('\nRow', i, 'keys sample:', list(r.keys())[:20])
    for k in ('hash','contractAddress','tokenAddress','logs','tokenSymbol','tokenDecimal','from','to','value'):
        if k in r:
            print(f" {k}: {r[k][:120]}")
    logs = None
    if 'logs' in r and r['logs']:
        try:
            logs = json.loads(r['logs'])
        except Exception:
            logs = r['logs']
    tx = {k: r.get(k) for k in r}
    if logs is not None:
        tx['logs'] = logs
    db_tx = prepare_transaction_for_db(tx, {}, 'arbitrum', '0xb3a2f25d7956f96703c9ed3ce6ea25e4d47295d3')
    print('Prepared token_transfers count:', len(db_tx.get('token_transfers', [])))
    pprint(db_tx)
