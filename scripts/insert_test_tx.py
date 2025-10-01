import sys, time
sys.path.append(r'D:/wallet2cointracking')
import database
print('DB URL:', database.db_config.database_url)
# create a synthetic transaction
now = int(time.time())
tx = {
    'chain_id': 14,
    'hash': '0x' + '9'*64,
    'blockNumber': 999999,
    'timeStamp': now,
    'from': '0x' + '1'*40,
    'to': '0x' + '2'*40,
    'value': '1000000000000000000',
    'gasUsed': 21000,
    'gasPrice': 1000000000,
    'txreceipt_status': 1,
    'input': '0x',
    'logs': [],
    'protocol': 'unknown',
    'action_type': 'transfer',
    'token_transfers': []
}
print('Calling store_transactions...')
res = database.db_manager.store_transactions([tx], None)
print('store_transactions returned', res)

# print counts
from sqlalchemy import text
engine = database.db_config.initialize_engine()
with engine.connect() as conn:
    for tbl in ['ethereum_transactions','token_transfers','wallet_analysis']:
        try:
            r = conn.execute(text(f"SELECT count(*) FROM {tbl}"))
            print(tbl, r.fetchone()[0])
        except Exception as e:
            print('Error counting', tbl, e)
