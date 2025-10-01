import sys, time
sys.path.append(r'D:/wallet2cointracking')
import app
import database
import threading
from datetime import datetime

wallet = '0xb3a2f25d7956f96703c9ed3ce6ea25e4d47295d3'
networks = ['arbitrum', 'flare']

# Small synthetic tx generator to keep the job fast and deterministic
now = int(time.time())

def make_tx(i, network):
    return {
        'hash': f"0xdeadbeef{i:02x}{network[:3]}",
        'blockNumber': str(1000000 + i),
        'timeStamp': str(now - i * 60),
        'from': wallet if i % 2 == 0 else '0x' + '1' * 40,
        'to': '0x' + '2' * 40 if i % 2 == 0 else wallet,
        'value': str(10**18),
        'gas': '21000',
        'gasPrice': '1000000000',
        'gasUsed': '21000',
        'input': '0x',
        'isError': '0',
        'txreceipt_status': '1',
        'logs': [],
    }

# Monkeypatch the fetcher so the job will find transactions quickly
def fake_fetch_transactions_from_explorer(wallet_address, network, limit=1000, include_token_transfers=True):
    # return two synthetic transactions per network
    return [make_tx(1, network), make_tx(2, network)]

# Patch in the running app module
app.fetch_transactions_from_explorer = fake_fetch_transactions_from_explorer

print('Initializing job for', wallet)
job_id = app._init_job(wallet, networks)
print('job_id =', job_id)

# Start the processing thread
t = threading.Thread(target=app.process_job, args=(job_id, wallet, networks), daemon=True)
t.start()

# Poll job status with timeout
timeout = 60
start = time.time()
while True:
    job = app.JOBS.get(job_id)
    if not job:
        print('Job not found in JOBS')
        break
    status = job.get('status')
    progress = job.get('progress')
    print(f'status={status} progress={progress}')
    if status in ('completed', 'failed'):
        break
    if time.time() - start > timeout:
        print('Timeout waiting for job to finish')
        break
    time.sleep(1)

print('\n=== JOB DUMP ===')
import json
print(json.dumps(job, default=str, indent=2))

# Print DB counts
engine = database.db_config.initialize_engine()
from sqlalchemy import text
with engine.connect() as conn:
    for tbl in ['ethereum_transactions', 'token_transfers', 'wallet_analysis']:
        try:
            r = conn.execute(text(f"SELECT count(*) FROM {tbl}"))
            print(tbl, r.fetchone()[0])
        except Exception as e:
            print('Error counting', tbl, e)

print('Done')
