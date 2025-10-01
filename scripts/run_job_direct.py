import sys
import os
import time

# Ensure project root is on sys.path so importing app works when running from scripts/
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import app

wallet = '0xb3a2f25d7956f96703c9ed3ce6ea25e4d47295d3'
networks = ['arbitrum']

job_id = app._init_job(wallet, networks)
print('Starting job', job_id)
app.process_job(job_id, wallet, networks)
print('Job status:', app.JOBS[job_id]['status'])
print('db_stored:', app.JOBS[job_id].get('db_stored'))

# Query DB counts
from database import db_config
engine = db_config.initialize_engine()
with engine.connect() as conn:
    try:
        tx_count = conn.execute("SELECT count(*) FROM ethereum_transactions").fetchone()[0]
    except Exception:
        tx_count = 'N/A'
    try:
        tt_count = conn.execute("SELECT count(*) FROM token_transfers").fetchone()[0]
    except Exception:
        tt_count = 'N/A'
    print('ethereum_transactions', tx_count)
    print('token_transfers', tt_count)
