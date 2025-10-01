from flask import Flask, render_template, request, jsonify, send_file
import logging
import threading
import uuid
import requests
import json
import csv
import io
from datetime import datetime
# from web3 import Web3  # Removed to avoid installation issues
# import pandas as pd  # Removed to avoid installation issues
from typing import Dict, List, Any, Optional, Tuple
import time
from defi_config import (
    AAVE_V3_CONFIG, OPENOCEAN_CONFIG, SPARKDEX_V3_CONFIG, 
    UNISWAP_V3_CONFIG, SUSHISWAP_CONFIG,
    KINETIC_MARKET_CONFIG, FLARE_STAKING_CONFIG, FLARE_DEFI_PROTOCOLS,
    ARBITRUM_DEFI_PROTOCOLS, ERC20_METHODS,
    DEFI_CATEGORIES, TRANSACTION_TYPES, EXCHANGE_NAMES
)
# Additional pattern imports
from defi_config import CURVE_LP_PATTERNS, ANGLE_PATTERNS, LIQUITY_PATTERNS
import os
from pathlib import Path
import concurrent.futures

# Database integration
try:
    from database import db_manager, get_db_health, test_db_connection, db_config
    DATABASE_ENABLED = True
    app_logger = logging.getLogger(__name__)
    app_logger.info("Database integration enabled")
except ImportError as e:
    DATABASE_ENABLED = False
    app_logger = logging.getLogger(__name__)
    app_logger.warning(f"Database integration disabled: {e}")
    # Create mock functions for compatibility
    class MockDBManager:
        def store_transactions(self, *args, **kwargs):
            return False
        def get_wallet_summary(self, *args, **kwargs):
            return None
    db_manager = MockDBManager()
    def get_db_health():
        return {'status': 'disabled', 'message': 'Database not configured'}
    def test_db_connection():
        return False

app = Flask(__name__)

# Configure logging for detailed terminal output
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
)
app.logger.setLevel(logging.DEBUG)
logging.getLogger('werkzeug').setLevel(logging.DEBUG)

@app.before_request
def log_request_info():
    app.logger.info(
        "Request %s %s | args=%s | json=%s",
        request.method,
        request.path,
        dict(request.args) if request.args else {},
        (request.get_json(silent=True) if request.is_json else None)
    )

@app.after_request
def log_response_info(response):
    app.logger.info(
        "Response %s %s | status=%s | length=%s",
        request.method,
        request.path,
        response.status,
        response.content_length,
    )
    return response

# In-memory job store for async processing (simple demo; replace with Redis/celery for prod)
JOBS_LOCK = threading.Lock()
JOBS: Dict[str, Dict[str, Any]] = {}

def _init_job(wallet_address: str, networks: List[str]) -> str:
    job_id = str(uuid.uuid4())
    with JOBS_LOCK:
        JOBS[job_id] = {
            'wallet': wallet_address,
            'networks': networks,
            'status': 'running',  # running | completed | failed
            'error': None,
            'progress': { n: { 'total': 0, 'processed': 0 } for n in networks },
            'protocol_counts': { n: {} for n in networks },
            'all_transactions': [],
            'csv_bytes': None,
            'started_at': int(time.time()),
            'finished_at': None,
        }
    return job_id

def _update_progress(job_id: str, network: str, total: Optional[int] = None, inc: int = 0):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        net = job['progress'].setdefault(network, { 'total': 0, 'processed': 0 })
        if total is not None:
            net['total'] = total
        if inc:
            net['processed'] = min(net.get('processed', 0) + inc, net.get('total', 0) or 10**9)

def _inc_protocol_count(job_id: str, network: str, protocol_key: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        counts = job['protocol_counts'].setdefault(network, {})
        counts[protocol_key] = counts.get(protocol_key, 0) + 1

def _finalize_job(job_id: str, csv_bytes: bytes):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        job['csv_bytes'] = csv_bytes
        job['status'] = 'completed'
        job['finished_at'] = int(time.time())
        
        # Store transactions in database if enabled
        app.logger.info(f"🔍 _finalize_job: DATABASE_ENABLED={DATABASE_ENABLED}, job keys={list(job.keys())}")
        if DATABASE_ENABLED:
            all_transactions = job.get('all_transactions', [])
            wallet_analysis = job.get('wallet_analysis')
            app.logger.info(f"🔍 all_transactions count: {len(all_transactions)}, wallet_analysis: {wallet_analysis is not None}")
            
            if all_transactions:
                try:
                    app.logger.info(f"🗄️ Storing {len(all_transactions)} transactions in database...")
                    success = db_manager.store_transactions(all_transactions, wallet_analysis)
                    if success:
                        app.logger.info("✅ Transactions stored in database successfully")
                        if wallet_analysis:
                            app.logger.info("✅ Wallet analysis stored in database successfully")
                    else:
                        app.logger.warning("⚠️ Failed to store transactions in database")
                    job['db_stored'] = success
                except Exception as e:
                    app.logger.error(f"❌ Database storage error: {e}")
                    import traceback
                    app.logger.error(f"❌ Traceback: {traceback.format_exc()}")
                    job['db_stored'] = False
            else:
                app.logger.warning("⚠️ No transactions to store in database")
                job['db_stored'] = False
        else:
            app.logger.warning("⚠️ Database storage disabled")

def _fail_job(job_id: str, error_message: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        job['status'] = 'failed'
        job['error'] = error_message
        job['finished_at'] = int(time.time())

def prepare_transaction_for_db(tx: Dict, defi_analysis: Dict, network: str, wallet_address: str) -> Dict[str, Any]:
    """Prepare raw transaction data for database storage"""
    try:
        # Get chain ID from network
        chain_id_map = {
            'arbitrum': 42161,
            'flare': 14,
            'ethereum': 1
        }
        chain_id = chain_id_map.get(network, 0)
        
        # Parse basic transaction data
        timestamp = int(tx.get('timeStamp', 0))
        
        # Prepare the transaction data structure that matches the database schema
        db_tx = {
            'chain_id': chain_id,
            'hash': tx.get('hash', ''),
            'blockNumber': int(tx.get('blockNumber', 0)),
            'timeStamp': timestamp,
            'from': tx.get('from', '').lower(),
            'to': tx.get('to', '').lower(),
            'value': tx.get('value', '0'),
            'gasUsed': int(tx.get('gasUsed', 0)),
            'gasPrice': int(tx.get('gasPrice', 0)),
            'txreceipt_status': int(tx.get('isError', '0') == '0'),  # Convert to success status
            'input': tx.get('input', ''),
            'logs': tx.get('logs', []),
            'protocol': defi_analysis.get('protocol', 'unknown'),
            'action_type': defi_analysis.get('action_type', 'transfer'),
            'token_transfers': []
        }
        
        # Handle token transfers - check if this is a token transfer transaction
        if tx.get('contractAddress') or tx.get('tokenAddress'):
            # This is a token transfer transaction
            token_transfer = {
                'log_index': 0,
                'contractAddress': tx.get('contractAddress') or tx.get('tokenAddress', ''),
                'from': tx.get('from', '').lower(),
                'to': tx.get('to', '').lower(),
                'value': tx.get('value', '0'),
                'tokenSymbol': tx.get('tokenSymbol', ''),
                'tokenName': tx.get('tokenName', ''),
                'tokenDecimal': int(tx.get('tokenDecimal', 18)),
                'value_scaled': None,
                'usd_value': None
            }
            
            # Calculate scaled value
            try:
                decimals = int(tx.get('tokenDecimal', 18))
                raw_value = int(token_transfer['value'])
                token_transfer['value_scaled'] = raw_value / (10 ** decimals)
            except (ValueError, TypeError):
                token_transfer['value_scaled'] = 0
                
            db_tx['token_transfers'] = [token_transfer]
        
        # Add any additional logs as token transfers if available
        if isinstance(tx.get('logs'), list):
            for i, log in enumerate(tx.get('logs', [])):
                if isinstance(log, dict) and log.get('topics'):
                    # Check if this is a Transfer event (topic[0] == Transfer signature)
                    if (log.get('topics') and 
                        len(log['topics']) > 0 and 
                        log['topics'][0] == '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'):
                        
                        # Parse Transfer event
                        try:
                            transfer_data = {
                                'log_index': i + 1,
                                'contractAddress': log.get('address', '').lower(),
                                'from': log['topics'][1][-40:] if len(log['topics']) > 1 else '',
                                'to': log['topics'][2][-40:] if len(log['topics']) > 2 else '',
                                'value': str(int(log.get('data', '0x0'), 16)) if log.get('data') else '0',
                                'tokenSymbol': '',
                                'tokenName': '',
                                'tokenDecimal': 18,
                                'value_scaled': None,
                                'usd_value': None
                            }
                            
                            # Add 0x prefix to addresses
                            if transfer_data['from']:
                                transfer_data['from'] = '0x' + transfer_data['from']
                            if transfer_data['to']:
                                transfer_data['to'] = '0x' + transfer_data['to']
                                
                            db_tx['token_transfers'].append(transfer_data)
                        except (ValueError, IndexError, KeyError):
                            # Skip malformed log entries
                            continue
        
        return db_tx
        
    except Exception as e:
        app.logger.error(f"Error preparing transaction for DB: {e}")
        # Return minimal transaction data in case of error
        return {
            'chain_id': chain_id_map.get(network, 0),
            'hash': tx.get('hash', ''),
            'blockNumber': int(tx.get('blockNumber', 0)),
            'timeStamp': int(tx.get('timeStamp', 0)),
            'from': tx.get('from', '').lower(),
            'to': tx.get('to', '').lower(),
            'value': tx.get('value', '0'),
            'gasUsed': int(tx.get('gasUsed', 0)),
            'gasPrice': int(tx.get('gasPrice', 0)),
            'txreceipt_status': 1,
            'input': '',
            'logs': [],
            'protocol': 'unknown',
            'action_type': 'transfer',
            'token_transfers': []
        }

def create_wallet_analysis(wallet_address: str, raw_transactions: List[Dict], networks: List[str]) -> Dict[str, Any]:
    """Create wallet analysis summary"""
    try:
        total_transactions = len(raw_transactions)
        total_gas_used = sum(int(tx.get('gasUsed', 0)) for tx in raw_transactions)
        total_gas_cost = sum(int(tx.get('gasUsed', 0)) * int(tx.get('gasPrice', 0)) for tx in raw_transactions)
        
        # Count unique contracts interacted with
        unique_contracts = set()
        protocols_used = set()
        
        for tx in raw_transactions:
            if tx.get('to'):
                unique_contracts.add(tx['to'].lower())
            if tx.get('protocol') and tx['protocol'] != 'unknown':
                protocols_used.add(tx['protocol'])
        
        # Calculate date range
        timestamps = [int(tx.get('timeStamp', 0)) for tx in raw_transactions if tx.get('timeStamp')]
        first_tx_date = datetime.fromtimestamp(min(timestamps)) if timestamps else datetime.now()
        last_tx_date = datetime.fromtimestamp(max(timestamps)) if timestamps else datetime.now()
        
        return {
            'wallet_address': wallet_address.lower(),
            'networks': ','.join(networks),
            'total_transactions': total_transactions,
            'unique_contracts': len(unique_contracts),
            'total_gas_used': str(total_gas_used),
            'total_gas_cost_wei': str(total_gas_cost),
            'protocols_used': ','.join(sorted(protocols_used)),
            'first_transaction_date': first_tx_date,
            'last_transaction_date': last_tx_date,
            'analysis_date': datetime.now(),
            'defi_score': min(len(protocols_used) * 10, 100)  # Simple DeFi activity score
        }
        
    except Exception as e:
        app.logger.error(f"Error creating wallet analysis: {e}")
        return {
            'wallet_address': wallet_address.lower(),
            'networks': ','.join(networks),
            'total_transactions': 0,
            'unique_contracts': 0,
            'total_gas_used': '0',
            'total_gas_cost_wei': '0',
            'protocols_used': '',
            'first_transaction_date': datetime.now(),
            'last_transaction_date': datetime.now(),
            'analysis_date': datetime.now(),
            'defi_score': 0
        }

def prefetch_token_meta_bulk(contract_addresses: List[str], network: str, max_workers: int = 10) -> None:
    """Prefetch token metadata (name/symbol) for a list of contract addresses in parallel.

    This populates TOKEN_META_CACHE to avoid repeated eth_call per transaction during job processing.
    contract_addresses: list of checksummed or non-checksummed addresses (0x pref allowed)
    """
    addrs_norm = []
    for a in contract_addresses:
        if not a:
            continue
        s = a.lower()
        if not s.startswith('0x'):
            s = '0x' + s
        addrs_norm.append(s)

    def _prefetch(addr: str):
        try:
            # populate cache via get_token_meta, which performs eth_call and caches
            _ = get_token_meta(addr, network)
        except Exception:
            pass

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(max_workers, max(2, len(addrs_norm)))) as ex:
        futures = [ex.submit(_prefetch, a) for a in addrs_norm]
        for f in concurrent.futures.as_completed(futures):
            try:
                _ = f.result()
            except Exception:
                pass


def process_job(job_id: str, wallet_address: str, networks: List[str]):
    try:
        app.logger.info("Job %s started for %s on %s", job_id, wallet_address, networks)
        max_transactions_per_network = 10000  # Increased limit for production
        app.logger.info("Job %s: max %s tx per network", job_id, max_transactions_per_network)

        all_transactions_local: List[Dict[str, Any]] = []  # CSV format
        all_raw_transactions: List[Dict[str, Any]] = []    # Raw transaction data for DB
        all_tx_lock = threading.Lock()

        def process_network(network: str):
            try:
                app.logger.info("Job %s: fetching %s", job_id, network)
                transactions = fetch_transactions_from_explorer(wallet_address, network, limit=max_transactions_per_network)
                txs = transactions or []
                total_for_net = min(len(txs), max_transactions_per_network)
                _update_progress(job_id, network, total=total_for_net)
                app.logger.info("Job %s: %s fetched %s tx (capped %s)", job_id, network, len(txs), total_for_net)

                processed_count = 0
                local_rows: List[Dict[str, Any]] = []           # CSV format data
                local_raw_txs: List[Dict[str, Any]] = []        # Raw transaction data for DB
                # Before iterating transactions, collect a seeded set of token contract addresses
                # from tokentx events in the batch to prefetch their metadata in bulk.
                try:
                    token_contracts = []
                    # some tx entries contain token transfer info inline (tokentx style)
                    for t in txs[:max_transactions_per_network]:
                        c = (t.get('contractAddress') or t.get('tokenAddress') or t.get('contract') or '')
                        if c:
                            token_contracts.append(c)
                    # Deduplicate and prefetch
                    if token_contracts:
                        token_contracts = list(dict.fromkeys([c.lower().replace('0x','') for c in token_contracts if c]))
                        prefetch_token_meta_bulk([('0x' + c) for c in token_contracts], network)
                except Exception:
                    pass

                for tx in txs[:max_transactions_per_network]:
                    try:
                        defi_analysis = analyze_defi_interaction(tx, network)
                        # Defensive: ensure we always have a dict result
                        if not isinstance(defi_analysis, dict):
                            app.logger.debug("Job %s: analyze_defi_interaction returned non-dict for tx %s", job_id, tx.get('hash'))
                            defi_analysis = {'protocol': 'unknown', 'is_defi': False}
                    except Exception as exa:
                        app.logger.exception("Job %s: analyze_defi_interaction failed for tx %s: %s", job_id, tx.get('hash'), exa)
                        defi_analysis = {'protocol': 'unknown', 'is_defi': False}

                    # Only track protocol counts for transactions that are actually identified as DeFi
                    if isinstance(defi_analysis, dict) and defi_analysis.get('is_defi', False):
                        protocol_key = defi_analysis.get('protocol') or 'unknown'
                        try:
                            _inc_protocol_count(job_id, network, protocol_key)
                        except Exception:
                            # non-critical
                            pass

                    try:
                        # Convert to CSV format for download
                        local_rows.append(convert_to_required_format(tx, defi_analysis, network, wallet_address))
                        
                        # Prepare raw transaction data for database storage
                        raw_tx_data = prepare_transaction_for_db(tx, defi_analysis, network, wallet_address)
                        local_raw_txs.append(raw_tx_data)
                        
                    except Exception as conv_ex:
                        app.logger.exception("Job %s: convert_to_required_format failed for tx %s: %s", job_id, tx.get('hash'), conv_ex)
                        # Skip this row but continue

                    processed_count += 1
                    _update_progress(job_id, network, inc=1)
                    # Removed sleep for production performance

                with all_tx_lock:
                    all_transactions_local.extend(local_rows)
                    all_raw_transactions.extend(local_raw_txs)
                app.logger.info("Job %s: %s processed %s rows", job_id, network, len(local_rows))
            except Exception as ne:
                app.logger.exception("Job %s: network %s failed: %s", job_id, network, ne)

        threads: List[threading.Thread] = []
        for n in networks:
            t = threading.Thread(target=process_network, args=(n,), daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        output = io.StringIO()
        fieldnames = [
            'Transaction Hash', 'Blockno', 'UnixTimestamp', 'DateTime (UTC)', 'From', 'To',
            'ContractAddress', 'Value_IN(ETH)', 'Value_OUT(ETH)', 'CurrentValue/Eth',
            'TxnFee(ETH)', 'TxnFee(USD)', 'Historical $Price/Eth', 'Status', 'ErrCode',
            'Method', 'ChainId', 'Chain', 'Value(ETH)', 'Platform', 'FunctionName', 'TokenId',
            'dAppPlatform', 'ToTokenName', 'FromContractName', 'FromTokenName', 
            'ContractName', 'ContractTokenName'
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_transactions_local)
        csv_content = output.getvalue()
        output.close()

        csv_io = io.BytesIO()
        csv_io.write(csv_content.encode('utf-8'))
        
        # Store raw transactions and wallet analysis in job for database storage
        with JOBS_LOCK:
            job = JOBS.get(job_id)
            if job:
                job['all_transactions'] = all_raw_transactions
                # Create wallet analysis
                try:
                    wallet_analysis = create_wallet_analysis(wallet_address, networks[0] if networks else 'arbitrum', all_raw_transactions)
                    job['wallet_analysis'] = wallet_analysis
                    app.logger.info(f"Generated wallet analysis for {wallet_address}")
                except Exception as e:
                    app.logger.error(f"Failed to create wallet analysis: {e}")
                    job['wallet_analysis'] = None
        
        _finalize_job(job_id, csv_io.getvalue())
        app.logger.info("Job %s completed, %s rows, %s raw transactions", job_id, len(all_transactions_local), len(all_raw_transactions))
    except Exception as e:
        app.logger.exception("Job %s failed: %s", job_id, e)
        _fail_job(job_id, str(e))

@app.route('/start_job', methods=['POST'])
def start_job():
    try:
        data = request.get_json()
        wallet_address = data.get('wallet_address', '').strip()
        networks = data.get('networks', ['arbitrum'])

        if not wallet_address or not wallet_address.startswith('0x') or len(wallet_address) != 42:
            return jsonify({'error': 'Invalid wallet address format'}), 400
        for network in networks:
            if network not in NETWORKS:
                return jsonify({'error': f'Invalid network: {network}'}), 400

        job_id = _init_job(wallet_address, networks)
        t = threading.Thread(target=process_job, args=(job_id, wallet_address, networks), daemon=True)
        t.start()
        return jsonify({'job_id': job_id}), 200
    except Exception as e:
        app.logger.exception("Failed to start job: %s", e)
        return jsonify({'error': 'Failed to start job'}), 500

@app.route('/job_status/<job_id>', methods=['GET'])
def job_status(job_id: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        # do not include csv bytes
        resp = {
            'status': job['status'],
            'wallet': job['wallet'],
            'networks': job['networks'],
            'progress': job['progress'],
            'protocol_counts': job['protocol_counts'],
            'error': job['error'],
            'started_at': job['started_at'],
            'finished_at': job['finished_at'],
        }
        return jsonify(resp)

@app.route('/debug_status', methods=['GET'])
def debug_status():
    """Debug endpoint to check Flask app status"""
    return jsonify({
        'DATABASE_ENABLED': DATABASE_ENABLED,
        'db_manager_available': db_manager is not None,
        'jobs_count': len(JOBS)
    })

@app.route('/debug_job/<job_id>', methods=['GET'])
def debug_job(job_id: str):
    """Debug endpoint to check job data"""
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        return jsonify({
            'job_keys': list(job.keys()),
            'has_all_transactions': 'all_transactions' in job,
            'all_transactions_count': len(job.get('all_transactions', [])),
            'has_wallet_analysis': 'wallet_analysis' in job,
            'has_csv_bytes': 'csv_bytes' in job,
            'database_enabled': DATABASE_ENABLED,
            'status': job.get('status'),
            'db_stored': job.get('db_stored', 'not_set')
        })

@app.route('/download/<job_id>', methods=['GET'])
def download(job_id: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        if job['status'] != 'completed' or not job.get('csv_bytes'):
            return jsonify({'error': 'Job not completed'}), 400
        csv_io = io.BytesIO(job['csv_bytes'])
        csv_io.seek(0)
        networks_suffix = "_".join(job['networks'])
        filename = f"{job['wallet']}_{networks_suffix}_transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        return send_file(csv_io, as_attachment=True, download_name=filename, mimetype='text/csv')

@app.route('/health')
def health():
    """Health check for external APIs and RPC endpoints."""
    results = {
        'status': 'ok',
        'timestamp': int(time.time()),
        'checks': {
            'arbitrum': {
                'explorer': {'ok': False, 'latency_ms': None, 'error': None},
                'rpc': {'ok': False, 'latency_ms': None, 'error': None},
            },
            'flare': {
                'explorer': {'ok': False, 'latency_ms': None, 'error': None},
                'rpc': {'ok': False, 'latency_ms': None, 'error': None},
            }
        }
    }

    # Arbitrum explorer (Etherscan v2)
    try:
        start = time.time()
        response = requests.get(
            ETHERSCAN_V2_BASE,
            params={'module': 'proxy', 'action': 'eth_blockNumber', 'chainid': NETWORKS['arbitrum']['chain_id'], 'apikey': ETHERSCAN_API_KEY},
            timeout=5
        )
        response.raise_for_status()
        data = response.json()
        ok = (data.get('status') in ('1', None)) and ('result' in data)
        results['checks']['arbitrum']['explorer']['ok'] = bool(ok)
        results['checks']['arbitrum']['explorer']['latency_ms'] = int((time.time() - start) * 1000)
    except Exception as e:
        results['checks']['arbitrum']['explorer']['error'] = str(e)

    # Arbitrum RPC
    try:
        start = time.time()
        r = requests.post('https://arb1.arbitrum.io/rpc', json={
            'jsonrpc': '2.0', 'method': 'eth_blockNumber', 'params': [], 'id': 1
        }, timeout=5)
        r.raise_for_status()
        jd = r.json()
        ok = 'result' in jd
        results['checks']['arbitrum']['rpc']['ok'] = bool(ok)
        results['checks']['arbitrum']['rpc']['latency_ms'] = int((time.time() - start) * 1000)
    except Exception as e:
        results['checks']['arbitrum']['rpc']['error'] = str(e)

    # Flare explorer (Etherscan v2)
    try:
        start = time.time()
        resp = requests.get(
            ETHERSCAN_V2_BASE,
            params={'module': 'proxy', 'action': 'eth_blockNumber', 'chainid': NETWORKS['flare']['chain_id'], 'apikey': ETHERSCAN_API_KEY},
            timeout=5
        )
        resp.raise_for_status()
        _ = resp.json()
        results['checks']['flare']['explorer']['ok'] = True
        results['checks']['flare']['explorer']['latency_ms'] = int((time.time() - start) * 1000)
    except Exception as e:
        results['checks']['flare']['explorer']['error'] = str(e)

    # Flare RPC
    try:
        start = time.time()
        r = requests.post('https://flare-api.flare.network/ext/C/rpc', json={
            'jsonrpc': '2.0', 'method': 'eth_blockNumber', 'params': [], 'id': 1
        }, timeout=5)
        r.raise_for_status()
        jd = r.json()
        ok = 'result' in jd
        results['checks']['flare']['rpc']['ok'] = bool(ok)
        results['checks']['flare']['rpc']['latency_ms'] = int((time.time() - start) * 1000)
    except Exception as e:
        results['checks']['flare']['rpc']['error'] = str(e)

    # Database health check
    if DATABASE_ENABLED:
        try:
            start = time.time()
            db_health = get_db_health()
            db_ok = db_health.get('status') == 'healthy'
            results['checks']['database'] = {
                'ok': db_ok,
                'latency_ms': int((time.time() - start) * 1000),
                'version': db_health.get('database_version', 'Unknown'),
                'connection_pool_size': db_health.get('connection_pool_size', 0)
            }
            if not db_ok:
                results['checks']['database']['error'] = db_health.get('error', 'Unknown error')
        except Exception as e:
            results['checks']['database'] = {
                'ok': False,
                'latency_ms': None,
                'error': str(e)
            }
    else:
        results['checks']['database'] = {
            'ok': False,
            'latency_ms': None,
            'error': 'Database integration disabled'
        }

    # Overall status
    any_fail = False
    for net in results['checks'].values():
        for part in net.values():
            # Handle both dict and boolean values
            if isinstance(part, dict):
                if not part.get('ok', False):
                    any_fail = True
                    break
            elif isinstance(part, bool):
                if not part:
                    any_fail = True
                    break
        if any_fail:
            break
    results['status'] = 'ok' if not any_fail else 'degraded'
    return jsonify(results), 200 if results['status'] == 'ok' else 503


@app.route('/contract_creator/<network>/<address>')
def contract_creator(network: str, address: str):
    """Return the contract creator address and creation tx for a contract address on a network.

    Strategy:
    - Use Etherscan v2 `txlist` for the chainid to fetch transactions involving the contract address and find the earliest tx where `contractAddress` equals the queried address (creation tx).
    - If not found, return best-effort message.
    """
    try:
        net = (network or '').lower()
        addr = (address or '').strip()
        if net not in NETWORKS:
            return jsonify({'error': 'Unknown network'}), 400
        if not addr.startswith('0x'):
            addr = '0x' + addr
        # Query Etherscan v2 txlist with chainid param
        chainid = NETWORKS[net]['chain_id']
        params = {
            'module': 'account',
            'action': 'txlist',
            'chainid': chainid,
            'address': addr,
            'startblock': 0,
            'endblock': 99999999,
            'page': 1,
            'offset': 1000,
            'sort': 'asc',
            'apikey': ETHERSCAN_API_KEY
        }
        r = requests.get(ETHERSCAN_V2_BASE, params=params, timeout=20)
        r.raise_for_status()
        jd = r.json()
        txs = jd.get('result') or []
        # Find earliest tx where contractAddress equals the target (creation tx)
        creator = None
        creation_tx = None
        for tx in txs:
            # Etherscan txlist entries may include 'contractAddress' for internal contract creations
            caddr = tx.get('contractAddress') or tx.get('to')
            if caddr and caddr.lower() == addr.lower():
                # The sender is the creator
                creator = tx.get('from')
                creation_tx = tx.get('hash')
                break

        if creator:
            return jsonify({'creator': creator, 'creation_tx': creation_tx}), 200
        else:
            # Fallback: try explorer contract API (if available) to get creation info
            explorer_api = NETWORKS[net].get('explorer_api')
            if explorer_api:
                try:
                    # Some explorers expose contract creation endpoints; we try a best-effort call
                    url = f"{explorer_api.replace('/api','')}/address/{addr}"
                    resp = requests.get(url, timeout=10)
                    if resp.status_code == 200:
                        return jsonify({'info': 'no creator found in txlist, explorer address page fetched', 'explorer_html_snippet': resp.text[:200]}), 200
                except Exception:
                    pass

        return jsonify({'error': 'creator not found via txlist'}), 404
    except Exception as e:
        app.logger.exception('contract_creator failed: %s', e)
        return jsonify({'error': 'failed to lookup contract creator', 'detail': str(e)}), 500

# API Configuration
ETHERSCAN_API_KEY = "5GNG5ZQRP3TEF7EJ7RTMW96N68JJQZFD9D"
ETHERSCAN_V2_BASE = "https://api.etherscan.io/v2/api"

# Network configurations
NETWORKS = {
    'flare': {
        'name': 'Flare',
        'rpc_url': 'https://flare-api.flare.network/ext/bc/C/rpc',
        'explorer_api': 'https://flare-explorer.flare.network/api',
        'chain_id': 14
    },
    'arbitrum': {
        'name': 'Arbitrum',
        'rpc_url': 'https://arb1.arbitrum.io/rpc',
        'explorer_api': 'https://api.arbiscan.io/api',
        'chain_id': 42161
    }
}

# Token price cache
PRICE_CACHE = {}
# Simple in-memory token metadata cache to avoid repeated RPC calls
TOKEN_META_CACHE: Dict[str, Dict[str, Any]] = {}
# Disk-backed cache file for token metadata
TOKEN_META_CACHE_DIR = os.path.join(app.root_path, 'data')
Path(TOKEN_META_CACHE_DIR).mkdir(parents=True, exist_ok=True)
TOKEN_META_CACHE_FILE = os.path.join(TOKEN_META_CACHE_DIR, 'token_meta_cache.json')
# TTL (seconds) for token metadata entries (24 hours default)
# TTL for token metadata entries: configurable via environment variable (seconds)
try:
    TOKEN_META_CACHE_TTL = int(os.environ.get('TOKEN_META_CACHE_TTL_SECONDS', str(7 * 24 * 60 * 60)))
except Exception:
    TOKEN_META_CACHE_TTL = 7 * 24 * 60 * 60

# Debounce / batch settings for disk saves (seconds). Configure via TOKEN_META_CACHE_SAVE_DEBOUNCE.
try:
    SAVE_DEBOUNCE_SECONDS = int(os.environ.get('TOKEN_META_CACHE_SAVE_DEBOUNCE', '30'))
except Exception:
    SAVE_DEBOUNCE_SECONDS = 30

# Internal saver state
_SAVE_TIMER_LOCK = threading.Lock()
_SAVE_TIMER: Optional[threading.Timer] = None

# Simple in-memory address info cache to avoid repeated explorer calls
ADDRESS_INFO_CACHE: Dict[str, Dict[str, Any]] = {}
# Disk-backed cache for address info
ADDRESS_INFO_CACHE_FILE = os.path.join(TOKEN_META_CACHE_DIR, 'address_info_cache.json')
# TTL for address info entries; configurable via env var ADDRESS_INFO_CACHE_TTL_SECONDS
try:
    ADDRESS_INFO_CACHE_TTL = int(os.environ.get('ADDRESS_INFO_CACHE_TTL_SECONDS', str(7 * 24 * 60 * 60)))
except Exception:
    ADDRESS_INFO_CACHE_TTL = 7 * 24 * 60 * 60

# Debounce timer state for address info saves
_ADDRESS_SAVE_TIMER_LOCK = threading.Lock()
_ADDRESS_SAVE_TIMER: Optional[threading.Timer] = None


def load_address_info_cache() -> None:
    try:
        if not os.path.exists(ADDRESS_INFO_CACHE_FILE):
            return
        with open(ADDRESS_INFO_CACHE_FILE, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
            now = int(time.time())
            loaded = 0
            for k, v in (data or {}).items():
                try:
                    ts = int(v.get('_ts', 0))
                    if now - ts <= ADDRESS_INFO_CACHE_TTL:
                        ADDRESS_INFO_CACHE[k] = v
                        loaded += 1
                except Exception:
                    continue
            app.logger.info('Loaded %s address info entries from disk cache', loaded)
    except Exception as e:
        app.logger.debug('Failed loading address info cache: %s', e)


def save_address_info_cache() -> None:
    try:
        tmp = ADDRESS_INFO_CACHE_FILE + '.tmp'
        now = int(time.time())
        to_save = {}
        for k, v in ADDRESS_INFO_CACHE.items():
            try:
                ts = int(v.get('_ts', 0))
                if now - ts <= ADDRESS_INFO_CACHE_TTL:
                    to_save[k] = v
            except Exception:
                continue

        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump(to_save, fh)
        os.replace(tmp, ADDRESS_INFO_CACHE_FILE)
    except Exception as e:
        app.logger.debug('Failed saving address info cache: %s', e)


def _address_debounced_save_worker():
    try:
        save_address_info_cache()
    finally:
        global _ADDRESS_SAVE_TIMER
        with _ADDRESS_SAVE_TIMER_LOCK:
            _ADDRESS_SAVE_TIMER = None


def schedule_save_address_info_cache(delay: Optional[int] = None) -> None:
    global _ADDRESS_SAVE_TIMER
    d = delay if (delay is not None) else SAVE_DEBOUNCE_SECONDS
    with _ADDRESS_SAVE_TIMER_LOCK:
        try:
            if _ADDRESS_SAVE_TIMER is not None:
                try:
                    _ADDRESS_SAVE_TIMER.cancel()
                except Exception:
                    pass
            t = threading.Timer(d, _address_debounced_save_worker)
            t.daemon = True
            _ADDRESS_SAVE_TIMER = t
            t.start()
        except Exception as e:
            app.logger.debug('Failed scheduling address info cache save: %s', e)
# Token icon cache directory under static
TOKEN_ICON_CACHE_DIR = os.path.join(app.root_path, 'static', 'token_icons')
Path(TOKEN_ICON_CACHE_DIR).mkdir(parents=True, exist_ok=True)

# Network logos directory
NETWORK_LOGO_DIR = os.path.join(app.root_path, 'static', 'network_logos')
Path(NETWORK_LOGO_DIR).mkdir(parents=True, exist_ok=True)


def _download_network_logos(timeout: int = 6):
    """Best-effort download of official network logos into static/network_logos.

    Sources tried (in order): TrustWallet assets repo info/logo.(png|svg).
    If only a PNG is available, we create a small SVG wrapper that references the PNG
    so the frontend can always request `/static/network_logos/<network>.svg` safely.
    This function swallows all exceptions and is safe to call at import time.
    """
    base = 'https://raw.githubusercontent.com/trustwallet/assets/master/blockchains'
    for net in NETWORKS.keys():
        try:
            # Try svg first
            svg_url = f"{base}/{net}/info/logo.svg"
            png_url = f"{base}/{net}/info/logo.png"
            target_svg = os.path.join(NETWORK_LOGO_DIR, f"{net}.svg")
            target_png = os.path.join(NETWORK_LOGO_DIR, f"{net}.png")

            # Skip if svg already present
            if os.path.exists(target_svg) or os.path.exists(target_png):
                continue

            # Try SVG
            try:
                r = requests.get(svg_url, timeout=timeout)
                if r.status_code == 200 and r.content:
                    with open(target_svg, 'wb') as fh:
                        fh.write(r.content)
                    continue
            except Exception:
                pass

            # Try PNG
            try:
                r2 = requests.get(png_url, timeout=timeout)
                if r2.status_code == 200 and r2.content:
                    with open(target_png, 'wb') as fh:
                        fh.write(r2.content)
                    # write a tiny SVG wrapper referencing the local png path so frontend can use .svg
                    wrapper = f"<svg xmlns='http://www.w3.org/2000/svg' width='64' height='64'>\n  <image href='/static/network_logos/{net}.png' width='64' height='64'/>\n</svg>"
                    with open(target_svg, 'w', encoding='utf-8') as fh:
                        fh.write(wrapper)
                    continue
            except Exception:
                pass

        except Exception:
            # swallow all errors — this is non-critical
            continue


# Attempt download in background thread to avoid blocking startup/tests
try:
    import threading as _thr
    _t = _thr.Thread(target=_download_network_logos, kwargs={'timeout': 6}, daemon=True)
    _t.start()
except Exception:
    # If threading or requests not available, skip silently
    pass


# Prefetch token logos for a seeded set of popular tokens per network
PREFETCH_TOKEN_ADDRESSES = {
    # Addresses are stored as lowercase without the 0x prefix
    'arbitrum': [
        # Aave-like wrapped tokens seen in examples
        '078f358208685046a11c85e8ad32895ded33a249',  # aArbWBTC (example)
        'e50fa9b3c56ffb159cb0fca61f5c9d750e8128c8',  # aArbWETH
        # Common Arbitrum token contracts (canonical L2 wrappers)
        '82af49447d8a07e3bd95bd0d56f35241523fbab1',  # WETH (Arbitrum)
        'ff970a61a04b1ca14834a43f5de4533ebddb5cc8',  # USDC (Arbitrum)
        'fd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9',  # USDT (Arbitrum)
        '2f2a2543b76a4166549f7aaab5ea24bede65b3fa',  # WBTC (Arbitrum)
        '912ce59144191c1204e64559fe8253a0e49e6548',  # ARB token (governance)
    ],
    'flare': [
        # Tokens observed in earlier Flare summaries
        '1d80c49bbbcd1c0911346656b529df9e5c2f783d',  # Wrapped Flare (WFLR)
        '5c2400019017ae61f811d517d088df732642dbd0',  # Lending WETH / kWETH
        '76809abd690b77488ffb5277e0a8300a7e77b779',  # Lending USDT0 / kUSDT0
        '26d460c3cf931fb2014fa436a49e3af08619810e',  # Reward Flare (rFLR)
        'deebabe05bda7e8c1740873abf715f16164c29b8',  # Lending USDC.E (kUSDC.E)
        '9aa42de5ec6f3b3bbf252bf8ac81acb338d888b7',  # GANJA (example)
        # Common stablecoins (may not exist as exact contracts on Flare, kept as optional seeds)
        '0000000000000000000000000000000000000000',  # placeholder (ignored)
    ]
}


def _download_token_logos(timeout: int = 6):
    """Best-effort download of token logos into static/token_icons/<network>/.

    Uses TrustWallet assets raw URLs. For each seeded contract address we try to
    download logo.png and save it under TOKEN_ICON_CACHE_DIR/<network>/<contract>.png.
    We also write a tiny SVG wrapper referencing the PNG so the asset can be requested
    as .svg by the frontend if desired.
    """
    base = 'https://raw.githubusercontent.com/trustwallet/assets/master/blockchains'
    for net, addrs in PREFETCH_TOKEN_ADDRESSES.items():
        try:
            net_dir = os.path.join(TOKEN_ICON_CACHE_DIR, net)
            Path(net_dir).mkdir(parents=True, exist_ok=True)
            for a in addrs:
                try:
                    addr = a.lower().replace('0x', '')
                    png_url = f"{base}/{net}/assets/0x{addr}/logo.png"
                    target_png = os.path.join(net_dir, f"{addr}.png")
                    target_svg = os.path.join(net_dir, f"{addr}.svg")
                    if os.path.exists(target_png) or os.path.exists(target_svg):
                        continue
                    r = requests.get(png_url, timeout=timeout)
                    if r.status_code == 200 and r.content:
                        with open(target_png, 'wb') as fh:
                            fh.write(r.content)
                        # Create a small SVG wrapper referencing the local png file
                        wrapper = f"<svg xmlns='http://www.w3.org/2000/svg' width='64' height='64'>\n  <image href='/static/token_icons/{net}/{addr}.png' width='64' height='64'/>\n</svg>"
                        with open(target_svg, 'w', encoding='utf-8') as fh:
                            fh.write(wrapper)
                except Exception:
                    # ignore per-token errors
                    continue
        except Exception:
            # ignore per-network failures
            continue


try:
    import threading as _thr2
    _t2 = _thr2.Thread(target=_download_token_logos, kwargs={'timeout': 6}, daemon=True)
    _t2.start()
except Exception:
    pass


def load_token_meta_cache() -> None:
    """Load token metadata cache from disk into TOKEN_META_CACHE.

    File format: { key: { 'meta': { 'name':..., 'symbol':... }, '_ts': epoch_seconds }, ... }
    Expired entries are ignored on load.
    """
    try:
        if not os.path.exists(TOKEN_META_CACHE_FILE):
            return
        with open(TOKEN_META_CACHE_FILE, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
            now = int(time.time())
            loaded = 0
            for k, v in (data or {}).items():
                try:
                    ts = int(v.get('_ts', 0))
                    if now - ts <= TOKEN_META_CACHE_TTL:
                        TOKEN_META_CACHE[k] = v
                        loaded += 1
                except Exception:
                    continue
            app.logger.info('Loaded %s token meta entries from disk cache', loaded)
    except Exception as e:
        app.logger.debug('Failed loading token meta cache: %s', e)


def save_token_meta_cache() -> None:
    """Atomically persist TOKEN_META_CACHE to disk.

    This writes the entire cache; entries should be small. Errors are logged and swallowed.
    """
    try:
        tmp = TOKEN_META_CACHE_FILE + '.tmp'
        # Only persist non-expired entries
        now = int(time.time())
        to_save = {}
        for k, v in TOKEN_META_CACHE.items():
            try:
                ts = int(v.get('_ts', 0))
                if now - ts <= TOKEN_META_CACHE_TTL:
                    to_save[k] = v
            except Exception:
                continue

        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump(to_save, fh)
        os.replace(tmp, TOKEN_META_CACHE_FILE)
    except Exception as e:
        app.logger.debug('Failed saving token meta cache: %s', e)


def _debounced_save_worker():
    """Worker invoked by the Timer to perform the actual save."""
    try:
        save_token_meta_cache()
    finally:
        # Clear the timer reference so future schedules can recreate it
        global _SAVE_TIMER
        with _SAVE_TIMER_LOCK:
            _SAVE_TIMER = None


def schedule_save_token_meta_cache(delay: Optional[int] = None) -> None:
    """Schedule a debounced save. Subsequent calls within the debounce window reset the timer.

    delay: seconds to wait before saving; defaults to SAVE_DEBOUNCE_SECONDS.
    """
    global _SAVE_TIMER
    d = delay if (delay is not None) else SAVE_DEBOUNCE_SECONDS
    with _SAVE_TIMER_LOCK:
        try:
            # Cancel existing timer
            if _SAVE_TIMER is not None:
                try:
                    _SAVE_TIMER.cancel()
                except Exception:
                    pass
            # Set new timer
            t = threading.Timer(d, _debounced_save_worker)
            t.daemon = True
            _SAVE_TIMER = t
            t.start()
        except Exception as e:
            app.logger.debug('Failed scheduling token meta cache save: %s', e)


# Load cache at startup (best-effort)
try:
    load_token_meta_cache()
except Exception:
    pass

def get_eth_price(timestamp: int) -> float:
    """Get ETH price at a specific timestamp"""
    cache_key = f"eth_{timestamp}"
    if cache_key in PRICE_CACHE:
        return PRICE_CACHE[cache_key]
    # Use a default price to avoid API delays
    # In production, you would implement proper price fetching
    default_price = 4196.88  # Current ETH price as fallback
    PRICE_CACHE[cache_key] = default_price
    return default_price

def get_token_price(token_address: str, timestamp: int, network: str) -> float:
    """Get token price at a specific timestamp"""
    cache_key = f"{token_address}_{timestamp}_{network}"
    if cache_key in PRICE_CACHE:
        return PRICE_CACHE[cache_key]

    # For now, return a placeholder price
    # In a real implementation, you would query a price API like CoinGecko
    price = 1.0  # Placeholder
    PRICE_CACHE[cache_key] = price
    return price



    


COINGECKO_BASE = 'https://api.coingecko.com/api/v3'
# Mapping from our network keys to CoinGecko platform ids used in their API
COINGECKO_PLATFORM_MAP = {
    'arbitrum': 'arbitrum-one',
    'flare': 'flare'  # CoinGecko may not support Flare contract lookups; we'll try and gracefully fall back
}


def get_token_price_coingecko(contract_address: str, network: str, vs_currency: str = 'usd') -> float:
    """Fetch token price (in USD) from CoinGecko using contract address when possible.

    Returns 0.0 on failure. Results are cached in PRICE_CACHE.
    """
    if not contract_address:
        return 0.0
    key = f"price_{contract_address.lower()}_{network}_{vs_currency}"
    if key in PRICE_CACHE:
        return PRICE_CACHE[key]

    platform = COINGECKO_PLATFORM_MAP.get(network, 'ethereum')

    try:
        # Preferred simple token price endpoint (fast)
        url = f"{COINGECKO_BASE}/simple/token_price/{platform}"
        params = {
            'contract_addresses': contract_address,
            'vs_currencies': vs_currency
        }
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        # data is expected to be { "<address>": { "usd": 1.23 } }
        addr_key = contract_address.lower()
        if isinstance(data, dict) and addr_key in data and isinstance(data[addr_key], dict):
            price = float(data[addr_key].get(vs_currency, 0.0) or 0.0)
            PRICE_CACHE[key] = price
            return price
    except Exception:
        # ignore and try fallback
        pass

    try:
        # Fallback: try coin lookup by contract
        url2 = f"{COINGECKO_BASE}/coins/{platform}/contract/{contract_address}"
        resp2 = requests.get(url2, timeout=10)
        resp2.raise_for_status()
        jd = resp2.json()
        price = float(jd.get('market_data', {}).get('current_price', {}).get(vs_currency, 0.0) or 0.0)
        PRICE_CACHE[key] = price
        return price
    except Exception:
        PRICE_CACHE[key] = 0.0
        return 0.0


def get_address_info(address: str, network: str) -> Dict[str, Any]:
    """Return best-effort info about an address: dApp platform name (if contract) and token name.

    Result: { 'platform': str | '', 'token_name': str | '' }
    Uses explorer API 'getsourcecode' (Etherscan-style) when available; falls back to on-chain token metadata.
    Caches results in ADDRESS_INFO_CACHE keyed by '<network>:<address>'.
    """
    if not address:
        return {'platform': '', 'token_name': ''}
    if not address.startswith('0x'):
        address = '0x' + address
    key = f"{network}:{address.lower()}"
    if key in ADDRESS_INFO_CACHE:
        cached_entry = ADDRESS_INFO_CACHE[key]
        # Return just the info part, not the entire cache entry with timestamp
        if isinstance(cached_entry, dict) and 'info' in cached_entry:
            return cached_entry['info']
        else:
            # Fallback for old cache format
            return cached_entry

    info = {'platform': '', 'token_name': ''}
    try:
        explorer_api = NETWORKS[network].get('explorer_api')
        if explorer_api:
            # Try Etherscan-style getsourcecode
            params = {
                'module': 'contract',
                'action': 'getsourcecode',
                'address': address,
                'apikey': ETHERSCAN_API_KEY
            }
            try:
                r = requests.get(explorer_api, params=params, timeout=8)
                r.raise_for_status()
                jd = r.json()
                if isinstance(jd, dict) and isinstance(jd.get('result'), list) and len(jd['result']) > 0:
                    res0 = jd['result'][0]
                    # Etherscan's result includes ContractName and CompilerVersion and ABI, etc.
                    contract_name = res0.get('ContractName') or res0.get('contractName') or ''
                    if contract_name:
                        info['platform'] = contract_name
                    # If ABI or tokenName present
                    token_name = res0.get('TokenName') or res0.get('tokenName') or ''
                    if token_name:
                        info['token_name'] = token_name
            except Exception:
                pass

        # If no platform found yet and the address looks like a token contract, try get_token_meta
        if not info['token_name'] or not info['platform']:
            try:
                meta = get_token_meta(address, network)
                name = meta.get('name') or ''
                sym = meta.get('symbol') or ''
                if name and not info['token_name']:
                    info['token_name'] = name
                # If no platform but token symbol/name suggests known dapp, leave platform empty for now
            except Exception:
                pass
    except Exception:
        pass

    try:
        ADDRESS_INFO_CACHE[key] = { 'info': info, '_ts': int(time.time()) }
        # schedule save
        try:
            schedule_save_address_info_cache()
        except Exception:
            try:
                save_address_info_cache()
            except Exception:
                pass
        return info
    except Exception:
        ADDRESS_INFO_CACHE[key] = info
        return info


# Load address info cache at startup
try:
    load_address_info_cache()
except Exception:
    pass


def get_coingecko_simple_price(coin_id: str, vs_currency: str = 'usd') -> float:
    """Query CoinGecko simple price for a known coin id (e.g., 'ethereum', 'bitcoin')."""
    if not coin_id:
        return 0.0
    key = f"coingecko_{coin_id}_{vs_currency}"
    if key in PRICE_CACHE:
        return PRICE_CACHE[key]
    try:
        url = f"{COINGECKO_BASE}/simple/price"
        params = {'ids': coin_id, 'vs_currencies': vs_currency}
        r = requests.get(url, params=params, timeout=8)
        r.raise_for_status()
        jd = r.json()
        price = float(jd.get(coin_id, {}).get(vs_currency, 0.0) or 0.0)
        PRICE_CACHE[key] = price
        return price
    except Exception:
        PRICE_CACHE[key] = 0.0
        return 0.0


def fetch_prices_for_tokens(tokens: List[Dict[str, Any]], network: str, max_workers: int = 8) -> None:
    """Fetch prices concurrently for a list of tokens and update each token dict with price_usd and value_usd.

    This updates the tokens in-place. Tokens are expected to have a 'contract' and 'quantity' keys.
    """
    def _fetch(t):
        contract = t.get('contract') or ''
        try:
            price = get_token_price_coingecko(contract, network)
        except Exception:
            price = 0.0
        return (contract, float(price))

    # Build list of unique contracts to avoid duplicate fetches
    unique_contracts = { (t.get('contract') or '').lower(): t for t in tokens }
    contracts = list(unique_contracts.keys())

    results: Dict[str, float] = {}
    if not contracts:
        return

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        future_map = { ex.submit(get_token_price_coingecko, c, network): c for c in contracts }
        for fut in concurrent.futures.as_completed(future_map):
            c = future_map[fut]
            try:
                price = float(fut.result() or 0.0)
            except Exception:
                price = 0.0
            results[c.lower()] = price

    # Update each token in-place
    for t in tokens:
        contract = (t.get('contract') or '').lower()
        price = results.get(contract, 0.0)
        qty = float(t.get('quantity') or 0.0)
        # Track price source: default to coingecko if contract lookup returned a price
        price_source = 'none'
        if price and price != 0.0:
            price_source = 'coingecko'
        # If no price from contract-based lookup, try heuristics (WETH->ethereum, WBTC->bitcoin, ETH)
        if not price or price == 0.0:
            sym = (t.get('symbol') or '').upper()
            name = (t.get('name') or '').lower()
            # General heuristics
            if 'WETH' in sym or sym == 'ETH' or 'wrapped ether' in name:
                price = get_coingecko_simple_price('ethereum')
                price_source = 'heuristic'
            elif 'WBTC' in sym or 'WRAPPED BITCOIN' in name or sym == 'BTC':
                price = get_coingecko_simple_price('bitcoin')
                price_source = 'heuristic'
            elif sym == 'USDT' or 'tether' in name:
                price = 1.0
                price_source = 'heuristic'
            elif sym == 'USDC' or 'usd coin' in name or 'usdc.e' in name.lower():
                price = 1.0
                price_source = 'heuristic'
            # Flare-specific heuristics
            if network == 'flare':
                # Wrapped Flare / Flare native tokens
                if 'WFLR' in sym or sym == 'FLR' or 'wrapped flare' in name or 'wrapped-flare' in name:
                    # CoinGecko coin id for Flare is 'flare'
                    price = get_coingecko_simple_price('flare')
                    price_source = 'heuristic'
                # reward FLR or rFLR may also map to native FLR
                if ('RFLR' in sym) or ('reward flare' in name) or ('rflr' in name):
                    price = get_coingecko_simple_price('flare')
                    price_source = 'heuristic'
                # common lending wrappers that track USD
                if 'USDT' in sym or 'USDC' in sym or 'TETHER' in name or 'USD COIN' in name:
                    price = 1.0
                    price_source = 'heuristic'
        t['price_usd'] = float(price)
        t['value_usd'] = round(qty * price, 6)
        t['price_source'] = price_source


@app.route('/token_icon/<network>/<contract_address>')
def token_icon(network: str, contract_address: str):
    """Serve a cached token icon. If not cached, try downloading from TrustWallet raw assets and cache locally."""
    try:
        if not contract_address:
            return ('', 404)
        net = (network or '').lower()
        addr = contract_address.lower().replace('0x', '')
        # file path
        net_dir = os.path.join(TOKEN_ICON_CACHE_DIR, net)
        Path(net_dir).mkdir(parents=True, exist_ok=True)
        filename = f"{addr}.png"
        filepath = os.path.join(net_dir, filename)
        if os.path.exists(filepath):
            return send_file(filepath, mimetype='image/png')

        # Try to download from TrustWallet assets repo
        # Construct trustwallet path (best-effort)
        # Use lowercase address without 0x
        trust_key = addr.upper()
        # TrustWallet uses checksummed addresses; try common patterns
        # We'll attempt the raw github URL used previously
        chain_key = net if net in ('arbitrum', 'flare') else net
        trust_url = f"https://raw.githubusercontent.com/trustwallet/assets/master/blockchains/{chain_key}/assets/0x{trust_key}/logo.png"
        r = requests.get(trust_url, timeout=10)
        if r.status_code == 200 and r.content:
            with open(filepath, 'wb') as fh:
                fh.write(r.content)
            return send_file(filepath, mimetype='image/png')

        # If download failed, return 404 and let frontend hide or fallback
        return ('', 404)
    except Exception:
        return ('', 404)


def fetch_transactions_from_explorer(wallet_address: str, network: str, limit: int = 1000, include_token_transfers: bool = True) -> List[Dict]:
    """Fetch transactions from network explorer API"""
    network_config = NETWORKS[network]
    
    if network in ('arbitrum', 'flare'):
        # Use Etherscan v2 multi-chain endpoint with pagination
        print(f"Fetching real {network.title()} transactions via Etherscan v2 for: {wallet_address}")
        chain_id = NETWORKS[network]['chain_id']
        url = ETHERSCAN_V2_BASE

        collected: List[Dict] = []
        page = 1
        # Use a sane page size to avoid giant responses while allowing progress
        page_size = 200

        try:
            while len(collected) < limit:
                remaining = limit - len(collected)
                offset = min(page_size, remaining)
                params = {
                    'module': 'account',
                    'action': 'txlist',
                    'chainid': chain_id,
                    'address': wallet_address,
                    'startblock': 0,
                    'endblock': 99999999,
                    'page': page,
                    'offset': offset,
                    'sort': 'desc',
                    'apikey': ETHERSCAN_API_KEY
                }
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                status_ok = (data.get('status') == '1') or ('result' in data and isinstance(data['result'], list))
                if not status_ok:
                    print(f"Etherscan v2 API Error (page {page}): {data.get('message', 'Unknown error')}")
                    break
                page_txs = data.get('result', []) or []
                print(f"Page {page} fetched {len(page_txs)} {network} txs (accum {len(collected)})")
                collected.extend(page_txs)
                if len(page_txs) < offset:
                    # No more pages
                    break
                page += 1

            # For Flare, prefer native Flare Explorer API for txlist and tokentx
            if network == 'flare':
                explorer_url = NETWORKS['flare']['explorer_api']
                # txlist
                page_f = 1
                while len(collected) < limit:
                    remaining = limit - len(collected)
                    offset_f = min(page_size, remaining)
                    p = {
                        'module': 'account',
                        'action': 'txlist',
                        'address': wallet_address,
                        'startblock': 0,
                        'endblock': 99999999,
                        'page': page_f,
                        'offset': offset_f,
                        'sort': 'desc'
                    }
                    r = requests.get(explorer_url, params=p, timeout=30)
                    r.raise_for_status()
                    d = r.json()
                    if not ((d.get('status') == '1') and isinstance(d.get('result'), list)):
                        break
                    items = d.get('result', [])
                    print(f"Flare Explorer txlist page {page_f} -> {len(items)}")
                    collected.extend(items)
                    if len(items) < offset_f:
                        break
                    page_f += 1

                # tokentx
                if include_token_transfers and len(collected) < limit:
                    transfers: List[Dict] = []
                    page_t = 1
                    while len(collected) + len(transfers) < limit:
                        remaining2 = limit - (len(collected) + len(transfers))
                        offset_t = min(page_size, remaining2)
                        tp = {
                            'module': 'account',
                            'action': 'tokentx',
                            'address': wallet_address,
                            'startblock': 0,
                            'endblock': 99999999,
                            'page': page_t,
                            'offset': offset_t,
                            'sort': 'desc'
                        }
                        tr = requests.get(explorer_url, params=tp, timeout=30)
                        tr.raise_for_status()
                        td = tr.json()
                        if not ((td.get('status') == '1') and isinstance(td.get('result'), list)):
                            break
                        titems = td.get('result', [])
                        print(f"Flare Explorer tokentx page {page_t} -> {len(titems)}")
                        for t in titems:
                            t.setdefault('gas', '0x0')
                            t.setdefault('gasPrice', '0x0')
                            t.setdefault('gasUsed', '0x0')
                            t.setdefault('to', t.get('to', ''))
                            t.setdefault('value', t.get('value', '0'))
                        transfers.extend(titems)
                        if len(titems) < offset_t:
                            break
                        page_t += 1

                    collected.extend(transfers)

            print(f"Collected {len(collected)} {network} records via Etherscan v2 (limit {limit})")
            return collected[:limit]
        except Exception as e:
            print(f"Error fetching {network.title()} transactions via Etherscan v2: {e}")

        # Fallbacks per network if Etherscan v2 fails
        if network == 'arbitrum':
            print("Etherscan v2 failed, trying Arbitrum RPC fallback...")
            rpc_result = fetch_from_arbitrum_rpc(wallet_address, limit)
            if rpc_result:
                return rpc_result
            print("Arbitrum RPC also failed, returning mock data for testing...")
            return generate_mock_arbitrum_transactions(wallet_address, limit)
        elif network == 'flare':
            print("Etherscan v2 failed, trying Flare RPC fallback...")
            rpc_result = fetch_from_flare_rpc(wallet_address, limit)
            if rpc_result:
                return rpc_result
            print("Flare RPC also failed, returning mock data for testing...")
            return generate_mock_flare_transactions(wallet_address, limit)
    else:
        print(f"Unsupported network: {network}")
        return []

def fetch_from_arbitrum_rpc(wallet_address: str, limit: int = 1000) -> List[Dict]:
    """Try to fetch transactions using direct RPC call to Arbitrum network"""
    try:
        # Use the official Arbitrum RPC endpoint
        rpc_url = "https://arb1.arbitrum.io/rpc"
        
        # Get the latest block number
        block_response = requests.post(rpc_url, json={
            "jsonrpc": "2.0",
            "method": "eth_blockNumber",
            "params": [],
            "id": 1
        }, timeout=10)
        
        if block_response.status_code == 200:
            block_data = block_response.json()
            latest_block = int(block_data.get('result', '0x0'), 16)
            start_block = max(0, latest_block - 1000)  # Look back 1k blocks
            
            print(f"Arbitrum RPC: Latest block {latest_block}, searching from block {start_block}")
            
            # Search through recent blocks for transactions
            transactions = []
            search_blocks = min(500, latest_block - start_block)  # Search more blocks for better coverage
            
            for i in range(search_blocks):
                block_num = latest_block - i
                block_hex = hex(block_num)
                
                # Get block details
                block_response = requests.post(rpc_url, json={
                    "jsonrpc": "2.0",
                    "method": "eth_getBlockByNumber",
                    "params": [block_hex, True],  # True to include full transaction details
                    "id": 1
                }, timeout=5)
                
                if block_response.status_code == 200:
                    block_data = block_response.json()
                    if 'result' in block_data and block_data['result']:
                        block_info = block_data['result']
                        block_txs = block_info.get('transactions', [])
                        
                        # Filter transactions for our wallet
                        for tx in block_txs:
                            if (tx.get('from', '').lower() == wallet_address.lower() or 
                                tx.get('to', '').lower() == wallet_address.lower()):
                                
                                # Convert to the format expected by our analyzer
                                formatted_tx = {
                                    'hash': tx.get('hash', ''),
                                    'blockNumber': str(block_num),
                                    'timeStamp': str(int(block_info.get('timestamp', '0x0'), 16)),
                                    'from': tx.get('from', ''),
                                    'to': tx.get('to', ''),
                                    'value': tx.get('value', '0x0'),
                                    'gas': tx.get('gas', '0x0'),
                                    'gasPrice': tx.get('gasPrice', '0x0'),
                                    'gasUsed': tx.get('gas', '0x0'),  # Approximate
                                    'input': tx.get('input', '0x'),
                                    'isError': '0',  # Assume success for now
                                    'txreceipt_status': '1'
                                }
                                transactions.append(formatted_tx)
                                
                                if len(transactions) >= limit:
                                    break
                        
                        if len(transactions) >= limit:
                            break
                
                # Reduced delay for production performance
                if i % 50 == 0:
                    time.sleep(0.02)
            
            print(f"Arbitrum RPC: Found {len(transactions)} transactions")
            return transactions
            
    except Exception as e:
        print(f"Arbitrum RPC call failed: {e}")
        return []

def fetch_from_flare_rpc(wallet_address: str, limit: int = 1000) -> List[Dict]:
    """Try to fetch transactions using direct RPC call to Flare network"""
    try:
        # Use the official Flare RPC endpoint from documentation
        rpc_url = "https://flare-api.flare.network/ext/C/rpc"
        
        # Get the latest block number
        block_response = requests.post(rpc_url, json={
            "jsonrpc": "2.0",
            "method": "eth_blockNumber",
            "params": [],
            "id": 1
        }, timeout=10)
        
        if block_response.status_code == 200:
            block_data = block_response.json()
            latest_block = int(block_data.get('result', '0x0'), 16)
            start_block = max(0, latest_block - 1000)  # Look back 1k blocks for faster processing
            
            print(f"Flare RPC: Latest block {latest_block}, searching from block {start_block}")
            
            # Search through recent blocks for transactions
            transactions = []
            search_blocks = min(500, latest_block - start_block)  # Search more blocks for better coverage
            
            for i in range(search_blocks):
                block_num = latest_block - i
                block_hex = hex(block_num)
                
                # Get block details
                block_response = requests.post(rpc_url, json={
                    "jsonrpc": "2.0",
                    "method": "eth_getBlockByNumber",
                    "params": [block_hex, True],  # True to include full transaction details
                    "id": 1
                }, timeout=5)
                
                if block_response.status_code == 200:
                    block_data = block_response.json()
                    if 'result' in block_data and block_data['result']:
                        block_info = block_data['result']
                        block_txs = block_info.get('transactions', [])
                        
                        # Filter transactions for our wallet
                        for tx in block_txs:
                            if (tx.get('from', '').lower() == wallet_address.lower() or 
                                tx.get('to', '').lower() == wallet_address.lower()):
                                
                                # Convert to the format expected by our analyzer
                                formatted_tx = {
                                    'hash': tx.get('hash', ''),
                                    'blockNumber': str(block_num),
                                    'timeStamp': str(int(block_info.get('timestamp', '0x0'), 16)),
                                    'from': tx.get('from', ''),
                                    'to': tx.get('to', ''),
                                    'value': tx.get('value', '0x0'),
                                    'gas': tx.get('gas', '0x0'),
                                    'gasPrice': tx.get('gasPrice', '0x0'),
                                    'gasUsed': tx.get('gas', '0x0'),  # Approximate
                                    'input': tx.get('input', '0x'),
                                    'isError': '0',  # Assume success for now
                                    'txreceipt_status': '1'
                                }
                                transactions.append(formatted_tx)
                                
                                if len(transactions) >= limit:
                                    break
                        
                        if len(transactions) >= limit:
                            break
                
                # Reduced delay for production performance
                if i % 50 == 0:
                    time.sleep(0.02)
            
            print(f"Flare RPC: Found {len(transactions)} transactions")
            return transactions
            
    except Exception as e:
        print(f"Flare RPC call failed: {e}")
        return []

def generate_mock_arbitrum_transactions(wallet_address: str, limit: int = 100) -> List[Dict]:
    """Generate mock Arbitrum transactions for testing when APIs are down"""
    import random
    import time
    
    mock_transactions = []
    current_time = int(time.time())
    
    for i in range(min(limit, 20)):  # Generate up to 20 mock transactions
        tx = {
            'hash': f"0x{'b' * 64}",
            'blockNumber': str(2000000 + i),
            'timeStamp': str(current_time - (i * 3600)),  # 1 hour apart
            'from': wallet_address,
            'to': '0x9876543210987654321098765432109876543210',
            'value': str(random.randint(1000000000000000000, 10000000000000000000)),  # 1-10 ETH in wei
            'gas': '21000',
            'gasPrice': '1000000000',  # Lower gas price for Arbitrum
            'gasUsed': '21000',
            'input': '0x',
            'isError': '0',
            'txreceipt_status': '1'
        }
        mock_transactions.append(tx)
    
    print(f"Generated {len(mock_transactions)} mock Arbitrum transactions")
    return mock_transactions

def generate_mock_flare_transactions(wallet_address: str, limit: int = 100) -> List[Dict]:
    """Generate mock Flare transactions for testing when APIs are down"""
    import random
    import time
    
    mock_transactions = []
    current_time = int(time.time())
    
    for i in range(min(limit, 20)):  # Generate up to 20 mock transactions
        tx = {
            'hash': f"0x{'a' * 64}",
            'blockNumber': str(1000000 + i),
            'timeStamp': str(current_time - (i * 3600)),  # 1 hour apart
            'from': wallet_address,
            'to': '0x1234567890123456789012345678901234567890',
            'value': str(random.randint(1000000000000000000, 10000000000000000000)),  # 1-10 ETH in wei
            'gas': '21000',
            'gasPrice': '20000000000',
            'gasUsed': '21000',
            'input': '0x',
            'isError': '0',
            'txreceipt_status': '1'
        }
        mock_transactions.append(tx)
    
    print(f"Generated {len(mock_transactions)} mock Flare transactions")
    return mock_transactions

def fetch_from_songbird_explorer(wallet_address: str, limit: int = 1000) -> List[Dict]:
    """Fallback to Songbird Explorer for Flare transactions"""
    print(f"Trying Songbird Explorer for: {wallet_address}")
    
    # Songbird Explorer API (Flare uses Songbird infrastructure)
    songbird_api_url = "https://songbird-explorer.flare.network/api"
    
    try:
        params = {
            'module': 'account',
            'action': 'txlist',
            'address': wallet_address,
            'startblock': 0,
            'endblock': 99999999,
            'page': 1,
            'offset': limit,
            'sort': 'desc'
        }
        
        response = requests.get(songbird_api_url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if data.get('status') == '1':
            transactions = data.get('result', [])
            print(f"Found {len(transactions)} transactions from Songbird Explorer")
            return transactions
        else:
            print(f"Songbird Explorer API Error: {data.get('message', 'Unknown error')}")
            return []
            
    except Exception as e:
        print(f"Error fetching from Songbird Explorer: {e}")
        return []


def fetch_flare_token_details(wallet_address: str, limit: int = 1000) -> List[Dict]:
    """Fetch token transfer history from the Flare explorer and aggregate token balances.

    This uses the Flare explorer `tokentx` action (Etherscan-style API) to collect token
    transfer events involving the given wallet, then sums values per token contract
    (respecting decimals reported in the events). This is a lightweight way to derive
    token holdings when a dedicated token balance endpoint isn't available or to
    cross-check balances.

    Returns a list of token dicts: { contract, name, symbol, decimals, quantity, last_block }
    """
    explorer_api = NETWORKS['flare']['explorer_api']
    collected: List[Dict] = []
    page = 1
    page_size = 200

    try:
        while len(collected) < limit:
            remaining = limit - len(collected)
            offset = min(page_size, remaining)
            params = {
                'module': 'account',
                'action': 'tokentx',
                'address': wallet_address,
                'startblock': 0,
                'endblock': 99999999,
                'page': page,
                'offset': offset,
                'sort': 'desc'
            }
            r = requests.get(explorer_api, params=params, timeout=30)
            r.raise_for_status()
            d = r.json()
            if not ((d.get('status') == '1') and isinstance(d.get('result'), list)):
                break
            items = d.get('result', [])
            collected.extend(items)
            if len(items) < offset:
                break
            page += 1

        # Aggregate by contract address
        tokens: Dict[str, Dict[str, Any]] = {}
        for t in collected:
            contract = (t.get('contractAddress') or '').lower()
            if not contract:
                continue
            # tokenDecimal sometimes is string; be defensive
            try:
                decimals = int(t.get('tokenDecimal') or 0)
            except Exception:
                decimals = 0
            try:
                raw_value = int(t.get('value') or 0)
            except Exception:
                raw_value = 0

            qty = (raw_value / (10 ** decimals)) if decimals > 0 else float(raw_value)

            info = tokens.setdefault(contract, {
                'contract': contract,
                'name': t.get('tokenName') or '',
                'symbol': t.get('tokenSymbol') or '',
                'decimals': decimals,
                'quantity': 0.0,
                'last_block': int(t.get('blockNumber') or 0)
            })
            # prefer reported decimals/name/symbol if discovered later
            if not info.get('name') and t.get('tokenName'):
                info['name'] = t.get('tokenName')
            if not info.get('symbol') and t.get('tokenSymbol'):
                info['symbol'] = t.get('tokenSymbol')
            if info.get('decimals', 0) == 0 and decimals:
                info['decimals'] = decimals

            # Determine direction: incoming (+) when to == wallet, outgoing (-) when from == wallet
            wallet_lower = wallet_address.lower()
            to_addr = (t.get('to') or '').lower()
            from_addr = (t.get('from') or '').lower()
            direction = 0
            if to_addr == wallet_lower:
                direction = 1
            elif from_addr == wallet_lower:
                direction = -1
            else:
                # If neither matches, skip this transfer for net balance
                continue

            info['quantity'] = info.get('quantity', 0.0) + (direction * qty)
            try:
                blk = int(t.get('blockNumber') or 0)
                if blk > info.get('last_block', 0):
                    info['last_block'] = blk
            except Exception:
                pass

        # Return as a list sorted by quantity desc
        result = sorted(tokens.values(), key=lambda x: x.get('quantity', 0), reverse=True)
        return result

    except Exception as e:
        print(f"Error fetching/aggregating Flare token details: {e}")
        return []


def fetch_token_balances(wallet_address: str, network: str, tokens: List[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    """Query on-chain token balances for a list of token dicts.

    Returns a map { contract_lower: quantity (float) | None } where None indicates no balance discovered or error.
    Attempts (in order):
      - Explorer API 'tokenbalance' if available
      - Etherscan v2 multi-chain 'tokenbalance'
      - RPC eth_call using ERC20 balanceOf selector as fallback
    """
    result: Dict[str, Optional[float]] = {}
    if network not in NETWORKS:
        return result

    explorer_api = NETWORKS[network].get('explorer_api')
    chain_id = NETWORKS[network].get('chain_id')
    rpc_url = NETWORKS[network].get('rpc_url')

    # Prepare unique contracts (no 0x) but we'll return keys with 0x prefix to match token dicts
    contracts = [ (t.get('contract') or '').lower().replace('0x','') for t in tokens if t.get('contract') ]
    unique_contracts = list(dict.fromkeys(c for c in contracts if c))

    headers = { 'Accept': 'application/json' }

    def _to_qty_raw(raw_str: str, decimals: int) -> Optional[float]:
        try:
            raw = int(raw_str or 0)
            if decimals and decimals > 0:
                return raw / (10 ** decimals)
            return float(raw)
        except Exception:
            return None

    def fetch_one(c_no0x: str) -> Tuple[str, Optional[float]]:
        key = '0x' + c_no0x
        # find decimals for this token
        decimals = 0
        for t in tokens:
            if (t.get('contract') or '').lower().replace('0x','') == c_no0x:
                try:
                    decimals = int(t.get('decimals') or 0)
                except Exception:
                    decimals = 0
                break

        # 1) Try explorer API tokenbalance if available
        if explorer_api:
            try:
                params = {
                    'module': 'account',
                    'action': 'tokenbalance',
                    'contractaddress': key,
                    'address': wallet_address,
                    'tag': 'latest'
                }
                r = requests.get(explorer_api, params=params, timeout=10, headers=headers)
                r.raise_for_status()
                d = r.json()
                if isinstance(d, dict) and ('result' in d):
                    qty = _to_qty_raw(d.get('result'), decimals)
                    return (key, qty)
            except Exception:
                pass

        # 2) Try Etherscan v2 multi-chain tokenbalance
        try:
            params2 = {
                'module': 'account',
                'action': 'tokenbalance',
                'contractaddress': key,
                'address': wallet_address,
                'tag': 'latest',
                'chainid': chain_id,
                'apikey': ETHERSCAN_API_KEY
            }
            r2 = requests.get(ETHERSCAN_V2_BASE, params=params2, timeout=10, headers=headers)
            r2.raise_for_status()
            d2 = r2.json()
            if isinstance(d2, dict) and ('result' in d2):
                qty = _to_qty_raw(d2.get('result'), decimals)
                return (key, qty)
        except Exception:
            pass

        # 3) RPC eth_call fallback for ERC20 balanceOf(address)
        if rpc_url:
            try:
                selector = '0x70a08231'
                addr_no0x = wallet_address.lower().replace('0x','').rjust(64, '0')
                data = selector + addr_no0x
                payload = {
                    'jsonrpc': '2.0', 'method': 'eth_call',
                    'params': [{ 'to': key, 'data': data }, 'latest'], 'id': 1
                }
                r3 = requests.post(rpc_url, json=payload, timeout=10, headers=headers)
                r3.raise_for_status()
                jd = r3.json()
                res = jd.get('result')
                if isinstance(res, str) and res.startswith('0x'):
                    raw = int(res, 16)
                    if decimals and decimals > 0:
                        return (key, raw / (10 ** decimals))
                    return (key, float(raw))
            except Exception:
                pass

        return (key, None)

    # Run fetches in parallel
    results: Dict[str, Optional[float]] = {}
    if not unique_contracts:
        return results

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(16, max(2, len(unique_contracts)))) as ex:
        future_map = { ex.submit(fetch_one, c): c for c in unique_contracts }
        for fut in concurrent.futures.as_completed(future_map):
            try:
                key, qty = fut.result()
            except Exception:
                key = '0x' + future_map[fut]
                qty = None
            results[key] = qty

    return results


@app.route('/flare_tokens/<wallet_address>', methods=['GET'])
def api_flare_tokens(wallet_address: str):
    """Simple API endpoint to return aggregated Flare token holdings for a wallet."""
    try:
        if not wallet_address or not wallet_address.startswith('0x') or len(wallet_address) != 42:
            return jsonify({'error': 'Invalid wallet address format'}), 400
        tokens = fetch_flare_token_details(wallet_address, limit=1000)
        return jsonify({'wallet': wallet_address, 'tokens': tokens, 'count': len(tokens)}), 200
    except Exception as e:
        app.logger.exception("Failed to fetch flare tokens: %s", e)
        return jsonify({'error': str(e)}), 500


def fetch_token_transfers(wallet_address: str, network: str, limit: int = 1000) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Fetch token transfer events for a wallet on a given network (Etherscan-style tokentx)."""
    if network not in NETWORKS:
        raise ValueError(f"Unknown network: {network}")
    explorer_api = NETWORKS[network].get('explorer_api')

    collected: List[Dict] = []
    page = 1
    page_size = 200
    pages_main = 0
    pages_fallback = 0
    used_fallback = False

    def _is_valid_result(d):
        return isinstance(d, dict) and isinstance(d.get('result'), list) and (d.get('status') == '1' or d.get('result') is not None)

    try:
        # Primary attempt: use configured network explorer API (e.g., Arbiscan)
        if explorer_api:
            while len(collected) < limit:
                remaining = limit - len(collected)
                offset = min(page_size, remaining)
                params = {
                    'module': 'account',
                    'action': 'tokentx',
                    'address': wallet_address,
                    'startblock': 0,
                    'endblock': 99999999,
                    'page': page,
                    'offset': offset,
                    'sort': 'desc'
                }
                r = requests.get(explorer_api, params=params, timeout=30)
                r.raise_for_status()
                d = r.json()

                # If the explorer explicitly returns NOTOK or non-list results, break and try fallback
                if not _is_valid_result(d):
                    app.logger.debug("Explorer API (%s) returned non-list or NOTOK: %s", explorer_api, d.get('message') if isinstance(d, dict) else str(d))
                    break

                items = d.get('result', []) or []
                pages_main += 1
                collected.extend(items)
                if len(items) < offset:
                    break
                page += 1

        # If primary didn't return anything, fallback to Etherscan v2 multi-chain endpoint
        if len(collected) == 0:
            app.logger.debug("Falling back to Etherscan v2 for tokentx on network %s", network)
            # Etherscan v2 multi-chain endpoint uses 'chainid' param
            chain_id = NETWORKS[network].get('chain_id')
            page = 1
            used_fallback = True
            while len(collected) < limit:
                remaining = limit - len(collected)
                offset = min(page_size, remaining)
                params = {
                    'module': 'account',
                    'action': 'tokentx',
                    'chainid': chain_id,
                    'address': wallet_address,
                    'startblock': 0,
                    'endblock': 99999999,
                    'page': page,
                    'offset': offset,
                    'sort': 'desc',
                    'apikey': ETHERSCAN_API_KEY
                }
                r = requests.get(ETHERSCAN_V2_BASE, params=params, timeout=30)
                r.raise_for_status()
                d = r.json()

                if not _is_valid_result(d):
                    app.logger.debug("Etherscan v2 tokentx returned non-list or error: %s", d.get('message') if isinstance(d, dict) else str(d))
                    break

                items = d.get('result', []) or []
                pages_fallback += 1
                collected.extend(items)
                if len(items) < offset:
                    break
                page += 1

        meta = {
            'pages_main': pages_main,
            'pages_fallback': pages_fallback,
            'used_fallback': used_fallback
        }
        return collected[:limit], meta
    except Exception as e:
        app.logger.exception("Error fetching token transfers for %s on %s: %s", wallet_address, network, e)
        return [], {'pages_main': pages_main, 'pages_fallback': pages_fallback, 'used_fallback': used_fallback}


def get_network_summary(wallet_address: str, network: str) -> Dict[str, Any]:
    """Return a small summary for the wallet on the given network: transaction count and token summary."""
    if network not in NETWORKS:
        raise ValueError(f"Unknown network: {network}")

    # Get transactions (uses existing fetcher)
    txs = fetch_transactions_from_explorer(wallet_address, network, limit=2000)
    # We'll compute transaction_count as the number of unique transaction hashes
    # across both normal txlist results and token transfer events so token transfers
    # are included in the displayed count (matches explorers that count both).
    tx_hashes = set()
    if txs:
        for tx in txs:
            h = (tx.get('hash') or tx.get('transactionHash') or tx.get('txHash') or '')
            if h:
                tx_hashes.add(str(h).lower())

    # Get token transfers and aggregate unique token contracts
    transfers, transfers_meta = fetch_token_transfers(wallet_address, network, limit=2000)
    if transfers:
        for t in transfers:
            h = (t.get('hash') or t.get('transactionHash') or t.get('txHash') or '')
            if h:
                tx_hashes.add(str(h).lower())

    # Prefer the txlist length (len(txs)) when txlist results are available, as
    # explorers commonly report txlist counts; fall back to unique hash count only
    # when txlist didn't return results.
    if txs:
        try:
            tx_count = len(txs)
        except Exception:
            tx_count = len(tx_hashes)
    else:
        tx_count = len(tx_hashes)
    if not isinstance(transfers_meta, dict):
        transfers_meta = {'pages_main': 0, 'pages_fallback': 0, 'used_fallback': False}
    tokens_map: Dict[str, Dict[str, Any]] = {}
    for t in transfers:
        contract = (t.get('contractAddress') or t.get('tokenAddress') or '').lower()
        if not contract:
            continue
        info = tokens_map.setdefault(contract, {
            'contract': contract,
            'symbol': t.get('tokenSymbol') or t.get('symbol') or '',
            'name': t.get('tokenName') or '',
            'decimals': 0,
            'quantity': 0.0
        })
        try:
            decimals = int(t.get('tokenDecimal') or 0)
        except Exception:
            decimals = 0
        # store discovered decimals on the token info for later on-chain balance decoding
        if decimals and not info.get('decimals'):
            info['decimals'] = decimals
        try:
            raw = int(t.get('value') or 0)
        except Exception:
            raw = 0
        qty = (raw / (10 ** decimals)) if decimals else float(raw)
        # Determine sign based on from/to
        wallet_lower = wallet_address.lower()
        to_addr = (t.get('to') or '').lower()
        from_addr = (t.get('from') or '').lower()
        if to_addr == wallet_lower:
            sign = 1
        elif from_addr == wallet_lower:
            sign = -1
        else:
            sign = 0
        info['quantity'] += sign * qty

    tokens = [v for v in tokens_map.values() if abs(v.get('quantity', 0)) > 1e-12]

    # Prefetch token metadata in bulk (name/symbol) to reduce per-transaction RPC calls
    try:
        contracts_for_prefetch = [ (t.get('contract') or '').lower() for t in tokens if t.get('contract') ]
        if contracts_for_prefetch:
            prefetch_token_meta_bulk(contracts_for_prefetch, network)
    except Exception:
        pass

    # Try to query on-chain balances for the discovered token contracts and prefer them
    try:
        balances = fetch_token_balances(wallet_address, network, tokens)
        # If a balance is available (not None), prefer it over tokentx-derived quantity
        for t in tokens:
            key = (t.get('contract') or '').lower()
            if key in balances and balances[key] is not None:
                try:
                    t['quantity'] = float(balances[key])
                except Exception:
                    pass
    except Exception:
        # If balance fetching fails, proceed with tokentx-derived quantities
        pass

    # Enrich tokens with USD prices concurrently and compute totals
    fetch_prices_for_tokens(tokens, network)
    network_total_usd = sum(float(t.get('value_usd') or 0.0) for t in tokens)

    return {
        'network': network,
        'wallet': wallet_address,
        'transaction_count': tx_count,
        'txlist_count': len(txs) if txs else 0,
        'tokentx_unique_count': len(tx_hashes),
        'token_count': len(tokens),
        'tokens': tokens,
        'network_total_usd': round(network_total_usd, 6),
        'tokentx_pages': {
            'main': int(transfers_meta.get('pages_main', 0)),
            'fallback': int(transfers_meta.get('pages_fallback', 0))
        },
        'tokentx_used_fallback': bool(transfers_meta.get('used_fallback', False))
    }


@app.route('/network_summary/<network>/<wallet_address>', methods=['GET'])
def api_network_summary(network: str, wallet_address: str):
    try:
        if not wallet_address or not wallet_address.startswith('0x') or len(wallet_address) != 42:
            return jsonify({'error': 'Invalid wallet address format'}), 400
        summary = get_network_summary(wallet_address, network)
        return jsonify(summary), 200
    except Exception as e:
        app.logger.exception("Failed to get network summary: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/assets_status', methods=['GET'])
def assets_status():
    """Return a JSON report of downloaded network logos and token icon files.

    Response shape:
      {
        'network_logos': { '<network>': [ { 'filename', 'size_bytes', 'mtime' }, ... ] },
        'token_icons': { '<network>': [ { 'filename', 'size_bytes', 'mtime' }, ... ] }
      }
    """
    try:
        resp = {'network_logos': {}, 'token_icons': {}}

        # Network logos
        try:
            if os.path.exists(NETWORK_LOGO_DIR):
                for fname in os.listdir(NETWORK_LOGO_DIR):
                    fpath = os.path.join(NETWORK_LOGO_DIR, fname)
                    if os.path.isfile(fpath):
                        st = os.stat(fpath)
                        net = os.path.splitext(fname)[0]
                        resp['network_logos'].setdefault(net, []).append({
                            'filename': fname,
                            'size_bytes': st.st_size,
                            'mtime': int(st.st_mtime)
                        })
        except Exception:
            # ignore listing errors
            pass

        # Token icons per network
        try:
            if os.path.exists(TOKEN_ICON_CACHE_DIR):
                for net in os.listdir(TOKEN_ICON_CACHE_DIR):
                    net_dir = os.path.join(TOKEN_ICON_CACHE_DIR, net)
                    if not os.path.isdir(net_dir):
                        continue
                    files = []
                    for fname in os.listdir(net_dir):
                        fpath = os.path.join(net_dir, fname)
                        if os.path.isfile(fpath):
                            st = os.stat(fpath)
                            files.append({
                                'filename': fname,
                                'size_bytes': st.st_size,
                                'mtime': int(st.st_mtime)
                            })
                    resp['token_icons'][net] = files
        except Exception:
            pass

        return jsonify(resp), 200
    except Exception as e:
        app.logger.exception('assets_status failed: %s', e)
        return jsonify({'error': 'failed to list assets'}), 500

def analyze_defi_interaction(tx: Dict, network: str) -> Dict:
    """Analyze a transaction for DeFi interactions with comprehensive protocol detection"""
    result = {
        'is_defi': False,
        'protocol': None,
        'action': None,
        'type': None,
        'group': None,
        'exchange': None
    }
    
    to_address = tx.get('to', '').lower()
    input_data = tx.get('input', '')
    
    # Early return for simple transactions - avoid false positives
    if not input_data or input_data == '0x':
        # Simple ETH transfer, definitely not DeFi
        return result
    
    # Check for basic ERC20 operations (not DeFi protocols)
    method_signature = input_data[:10] if len(input_data) >= 10 else ''
    if method_signature in ['0xa9059cbb', '0x095ea7b3', '0x23b872dd']:  # transfer, approve, transferFrom
        # Basic token operations, not DeFi
        return result


def is_contract(address: str, network: str) -> bool:
    """Return True if address has code on the given network."""
    try:
        addr = address if address.startswith('0x') else '0x' + address
        r = requests.post(NETWORKS[network]['rpc_url'], json={'jsonrpc': '2.0', 'method': 'eth_getCode', 'params': [addr, 'latest'], 'id': 1}, timeout=8)
        r.raise_for_status()
        jd = r.json()
        code = jd.get('result', '') or ''
        return bool(code and code != '0x')
    except Exception:
        return False


def get_token_meta(addr: str, network: str) -> Dict[str, str]:
    """Try to read ERC-20 name() and symbol() via eth_call. Cache results."""
    # Normalize key
    if not addr:
        return {'name': '', 'symbol': ''}
    if not addr.startswith('0x'):
        addr = '0x' + addr
    key = f"{network}:{addr.lower()}"

    # Try to load from in-memory cache (and respect TTL)
    existing = TOKEN_META_CACHE.get(key)
    now = int(time.time())
    if existing:
        try:
            ts = int(existing.get('_ts', 0))
            if now - ts <= TOKEN_META_CACHE_TTL:
                return existing.get('meta', {'name': '', 'symbol': ''})
            else:
                # expired -> drop
                TOKEN_META_CACHE.pop(key, None)
        except Exception:
            TOKEN_META_CACHE.pop(key, None)

    meta = {'name': '', 'symbol': ''}
    try:
        if not addr.startswith('0x'):
            addr = '0x' + addr
        rpc = NETWORKS[network]['rpc_url']

        def _call_and_decode(selector_hex: str, expect_type: str = 'string') -> str:
            try:
                r = requests.post(rpc, json={'jsonrpc': '2.0', 'method': 'eth_call', 'params': [{'to': addr, 'data': selector_hex}, 'latest'], 'id': 1}, timeout=6)
                r.raise_for_status()
                res = r.json().get('result', '') or ''
                if not res or res == '0x':
                    return ''
                # Try ABI decode for dynamic types
                try:
                    val = abi_decode([expect_type], res)
                    if isinstance(val, list):
                        val = val[0] if val else ''
                    if val:
                        return str(val)
                except Exception:
                    pass
                # Fallback: if the return looks like bytes32, decode directly
                hexdata = res[2:]
                if len(hexdata) >= 64:
                    first32 = hexdata[:64]
                    try:
                        b = bytes.fromhex(first32)
                        s = b.rstrip(b'\x00').decode('utf-8', errors='ignore')
                        return s
                    except Exception:
                        return ''
                return ''
            except Exception:
                return ''

        # name()
        n = _call_and_decode('0x06fdde03', 'string')
        if n:
            meta['name'] = n
        # symbol()
        s = _call_and_decode('0x95d89b41', 'string')
        if s:
            meta['symbol'] = s
    except Exception:
        pass
    # Store in cache with timestamp and attempt to persist
    try:
        TOKEN_META_CACHE[key] = {'meta': meta, '_ts': int(time.time())}
        # Schedule a debounced save to batch disk writes
        try:
            schedule_save_token_meta_cache()
        except Exception:
            # Fallback to immediate save if scheduling fails
            try:
                save_token_meta_cache()
            except Exception:
                pass
    except Exception:
        pass
    return meta


def abi_decode(types: List[str], data_hex: str) -> List[Any]:
    """Decode ABI-encoded return data using eth_abi when available.

    Falls back to a minimal decoder for string/bytes32 if eth_abi isn't installed.
    """
    if not data_hex or data_hex == '0x':
        return []

    # Try to use eth_abi for robust decoding. Prefer decode_single for single-element returns
    try:
        from eth_abi import decode_abi, decode_single
        # Strip 0x
        hx = data_hex[2:] if data_hex.startswith('0x') else data_hex
        b = bytes.fromhex(hx)
        try:
            if len(types) == 1:
                val = decode_single(types[0], b)
                # Post-process common types for nicer output
                if isinstance(val, (bytes, bytearray)):
                    # Try decode as utf-8 string if reasonable, else return hex
                    try:
                        s = val.rstrip(b'\x00').decode('utf-8', errors='ignore')
                        return [s]
                    except Exception:
                        return ["0x" + val.hex()]
                else:
                    return [val]
            else:
                decoded = decode_abi(types, b)
                out = []
                for idx, v in enumerate(decoded):
                    t = types[idx] if idx < len(types) else ''
                    if isinstance(v, (bytes, bytearray)):
                        try:
                            s = v.rstrip(b'\x00').decode('utf-8', errors='ignore')
                            out.append(s)
                        except Exception:
                            out.append("0x" + v.hex())
                    else:
                        out.append(v)
                return out
        except Exception:
            # Try a second pass: some return values contain a leading 32-byte offset
            try:
                if len(b) >= 32:
                    offset = int.from_bytes(b[0:32], 'big')
                    if offset > 0 and len(b) > offset:
                        decoded = decode_abi(types, b[offset:])
                        return list(decoded)
            except Exception:
                pass
    except Exception:
        # eth_abi not available or decode failed; fall back to minimal logic below
        pass

    # Fallback minimal logic (previous implementation) for string and bytes32
    try:
        hx = data_hex[2:]
        b = bytes.fromhex(hx)
        if len(types) == 1 and types[0] == 'string':
            if len(b) >= 64:
                length = int.from_bytes(b[32:64], 'big')
                start = 64
                end = start + length
                if end <= len(b):
                    s = b[start:end].decode('utf-8', errors='ignore')
                    return [s]
            try:
                s = b.decode('utf-8', errors='ignore').rstrip('\x00')
                return [s]
            except Exception:
                return ['']
        elif len(types) == 1 and types[0].startswith('bytes'):
            b32 = bytes.fromhex(hx[:64])
            return [b32]
    except Exception:
        return []

    return []

    # Prefer functionName when available (Etherscan provides this in many tx lists)
    fn_name_raw = tx.get('functionName') or ''
    fn_name = ''
    if isinstance(fn_name_raw, str) and fn_name_raw:
        # functionName can include parameters like swapExactTokensForTokens(uint256,uint256,...) — strip args
        fn_name = fn_name_raw.split('(')[0].strip()

    # If there's no input data and no functionName, return unknown
    if (not input_data or len(input_data) < 10) and not fn_name:
        return result

    method_signature = input_data[:10] if input_data and len(input_data) >= 10 else ''
    
    # Network-specific protocol detection
    if network == 'flare':
        # Check Flare-specific protocols first
        for protocol_name, protocol_info in FLARE_DEFI_PROTOCOLS.items():
            if any(to_address == addr.lower() for addr in protocol_info['addresses'] if addr != '0x0000000000000000000000000000000000000000'):
                result['is_defi'] = True
                result['protocol'] = protocol_name
                result['exchange'] = protocol_info['name']
                # Assign appropriate group based on protocol
                if protocol_name in ['sparkdex_v3', 'openocean', 'flare_swap', 'flare_dex']:
                    result['group'] = 'DEX Trading'
                elif protocol_name in ['aave_v3', 'kinetic_market', 'flare_lending']:
                    result['group'] = 'Lending'
                elif protocol_name in ['flare_network']:
                    result['group'] = 'Stacking (passiv)'
                else:
                    result['group'] = 'Other'
                
                # Analyze method calls
                # Prefer functionName when present
                if fn_name:
                    result['action'] = fn_name
                    # Best-effort mapping: try direct map, fall back to generic
                    result['type'] = TRANSACTION_TYPES.get(fn_name, 'Trade')
                    return result

                for action, method in protocol_info['methods'].items():
                    if method_signature == method:
                        result['action'] = action
                        result['type'] = TRANSACTION_TYPES.get(action, 'Trade')
                        break
                
                if not result['action']:
                    result['action'] = 'interaction'
                    result['type'] = 'Trade'
                
                return result
        
        # Check Flare native staking
        flare_config = FLARE_STAKING_CONFIG
        if (to_address == flare_config['wflr_contract'].lower() or 
            to_address == flare_config['ftso_manager'].lower()):
            result['is_defi'] = True
            result['protocol'] = 'flare_staking'
            result['exchange'] = EXCHANGE_NAMES['flare_staking']
            result['group'] = 'Stacking (passiv)'

            # Prefer functionName when present
            if fn_name:
                result['action'] = fn_name
                result['type'] = TRANSACTION_TYPES.get(fn_name, 'Staking')
                return result

            for action, method in flare_config['methods'].items():
                if method_signature == method:
                    result['action'] = action
                    result['type'] = TRANSACTION_TYPES.get(action, 'Staking')
                    break
            
            if not result['action']:
                result['action'] = 'stake'
                result['type'] = 'Staking'
            
            return result
    
    elif network == 'arbitrum':
        # Check Arbitrum-specific protocols
        # Prioritize SparkDEX V3 before Uniswap V3 for clearer Platform labeling
        protocols_to_check = [
            ('aave_v3', AAVE_V3_CONFIG, 'Lending'),
            ('openocean', OPENOCEAN_CONFIG, 'DEX Trading'),
            ('sparkdex_v3', SPARKDEX_V3_CONFIG, 'DEX Trading'),
            ('uniswap_v3', UNISWAP_V3_CONFIG, 'DEX Trading'),
            ('sushiswap', SUSHISWAP_CONFIG, 'DEX Trading'),
            ('kinetic_market', KINETIC_MARKET_CONFIG, 'Lending'),
        ]
        
        for protocol_name, protocol_config, default_group in protocols_to_check:
            if network in protocol_config:
                config = protocol_config[network]
                
                # Check if transaction is to any of the protocol addresses
                addresses_to_check = []
                if 'pool_addresses' in config:
                    addresses_to_check.extend(config['pool_addresses'])
                elif 'router_addresses' in config:
                    addresses_to_check.extend(config['router_addresses'])
                elif 'pool_address' in config:
                    addresses_to_check.append(config['pool_address'])
                elif 'router_address' in config:
                    addresses_to_check.append(config['router_address'])
                elif 'lending_pool' in config:
                    addresses_to_check.append(config['lending_pool'])
                
                # Check if the transaction is to any protocol address
                if any(to_address == addr.lower() for addr in addresses_to_check if addr != '0x0000000000000000000000000000000000000000'):
                    result['is_defi'] = True
                    result['protocol'] = protocol_name
                    result['exchange'] = EXCHANGE_NAMES.get(protocol_name, protocol_name.title())
                    result['group'] = default_group
                    
                    # Analyze the method call
                    # Prefer functionName when present
                    if fn_name:
                        result['action'] = fn_name
                        result['type'] = TRANSACTION_TYPES.get(fn_name, 'Trade')
                        # Best-effort group mapping remains
                        if protocol_name in ['uniswap_v3', 'sparkdex_v3']:
                            result['group'] = 'DEX Liquidity Mining'
                        elif protocol_name in ['aave_v3', 'kinetic_market']:
                            result['group'] = 'Lending'
                        elif protocol_name in ['openocean', 'sushiswap']:
                            result['group'] = 'DEX Trading'
                        return result

                    if 'methods' in config:
                        for action, method in config['methods'].items():
                            if method_signature == method:
                                result['action'] = action
                                result['type'] = TRANSACTION_TYPES.get(action, 'Trade')

                                # Special handling for different protocol types
                                if protocol_name in ['uniswap_v3', 'sparkdex_v3'] and action in ['mint', 'burn', 'collect']:
                                    result['group'] = 'DEX Liquidity Mining'
                                elif protocol_name in ['aave_v3', 'kinetic_market']:
                                    result['group'] = 'Lending'
                                elif protocol_name in ['openocean', 'sushiswap']:
                                    result['group'] = 'DEX Trading'

                                break
                    
                    # If no specific method match, use generic DeFi classification
                    if not result['action']:
                        result['action'] = 'interaction'
                        result['type'] = 'Trade'
                    
                    return result

        # Method-only fallback for protocols with placeholder addresses (e.g., Kinetic Market)
        # This enables Platform labeling when we can confidently infer via method signatures
        if 'arbitrum' in KINETIC_MARKET_CONFIG:
            km_conf = KINETIC_MARKET_CONFIG['arbitrum']
            if km_conf.get('lending_pool', '0x').lower().endswith('000000000'):
                input_data = tx.get('input', '')
                if input_data and len(input_data) >= 10:
                    method_signature = input_data[:10]
                    for action, method in km_conf.get('methods', {}).items():
                        if method_signature == method:
                            result['is_defi'] = True
                            result['protocol'] = 'kinetic_market'
                            result['exchange'] = EXCHANGE_NAMES.get('kinetic_market', 'Kinetic Market')
                            result['group'] = 'Lending'
                            result['action'] = action
                            result['type'] = TRANSACTION_TYPES.get(action, 'Trade')
                            return result

        # General method-signature fallback: map common swap/mint/burn signatures to a best-effort protocol
        method_fallback_map = {
            # V2-style swaps and router methods -> OpenOcean as aggregator
            '0x38ed1739': 'openocean',  # swapExactTokensForTokens
            '0x7ff36ab5': 'openocean',  # swapExactETHForTokens / swapExactTokensForETH (ETH swaps)
            '0x18cbafe5': 'openocean',  # swapExactTokensForETH
            '0x12aa3caf': 'openocean',  # swap (generic)
            # Uniswap V3 / SparkDEX V3 methods
            '0x414bf389': 'sparkdex_v3',  # exactInputSingle
            '0xc04b8d59': 'sparkdex_v3',  # exactInput
            '0xdb3e2198': 'sparkdex_v3',  # exactOutputSingle
            '0xf28c0498': 'sparkdex_v3',  # exactOutput
            '0x88316456': 'sparkdex_v3',  # mint
            '0xa34123a7': 'sparkdex_v3',  # burn
            '0xfc6f7865': 'sparkdex_v3',  # collect
            '0x128acb08': 'sparkdex_v3',  # swap
            # Aave V3 lending methods
            '0x617ba037': 'aave_v3',  # supply
            '0x693ec85e': 'aave_v3',  # withdraw
            '0xa415bcad': 'aave_v3',  # borrow
            '0x573ade81': 'aave_v3',  # repay
            '0x80e670ae': 'aave_v3',  # liquidationCall
            '0xab9c4b5d': 'aave_v3',  # flashLoan
            # Kinetic Market methods
            '0x47e7ef24': 'kinetic_market',  # deposit
            # Flare Network staking methods
            '0x5c19a95c': 'flare_network',  # delegate/undelegate
            '0x3d18b912': 'flare_network',  # claimRewards
            '0xd0e30db0': 'flare_network',  # wrap
            '0x2e1a7d4d': 'flare_network',  # unwrap
        }
        if input_data and len(input_data) >= 10:
            method_signature = input_data[:10]
            mapped_protocol = method_fallback_map.get(method_signature)
            if mapped_protocol:
                # Only apply if we haven't already classified the tx
                if not result['is_defi']:
                    result['is_defi'] = True
                    result['protocol'] = mapped_protocol
                    result['exchange'] = EXCHANGE_NAMES.get(mapped_protocol, mapped_protocol.title())
                    # Determine group based on mapping
                    if mapped_protocol in ['sparkdex_v3', 'openocean', 'sushiswap', 'uniswap_v3']:
                        result['group'] = 'DEX Trading'
                    elif mapped_protocol in ['aave_v3', 'compound', 'kinetic_market']:
                        result['group'] = 'Lending'
                    elif mapped_protocol in ['flare_network']:
                        result['group'] = 'Stacking (passiv)'
                    else:
                        result['group'] = 'Other'
                    # Set action/type where possible
                    # Map signature back to a generic action name from TRANSACTION_TYPES if available
                    action_name = None
                    # Try to find an action key in known configs
                    network_key = 'arbitrum' if network == 'arbitrum' else 'flare'
                    for proto_conf in (
                        AAVE_V3_CONFIG.get(network_key, {}).get('methods', {}), 
                        SPARKDEX_V3_CONFIG.get(network_key, {}).get('methods', {}), 
                        OPENOCEAN_CONFIG.get(network_key, {}).get('methods', {}),
                        KINETIC_MARKET_CONFIG.get(network_key, {}).get('methods', {}),
                        FLARE_STAKING_CONFIG.get('methods', {})
                    ):
                        for act, sig in proto_conf.items():
                            if sig == method_signature:
                                action_name = act
                                break
                        if action_name:
                            break
                    result['action'] = action_name or 'interaction'
                    result['type'] = TRANSACTION_TYPES.get(result['action'], 'Trade')
                    return result
        
        # Check additional Arbitrum protocols
        for protocol_name, protocol_info in ARBITRUM_DEFI_PROTOCOLS.items():
            if any(to_address == addr.lower() for addr in protocol_info['addresses']):
                result['is_defi'] = True
                result['protocol'] = protocol_name
                result['exchange'] = protocol_info['name']
                # Assign appropriate group based on protocol
                if protocol_name in ['sparkdex_v3', 'openocean', 'curve', 'balancer', 'sushiswap']:
                    result['group'] = 'DEX Trading'
                elif protocol_name in ['aave_v3', 'kinetic_market', 'compound']:
                    result['group'] = 'Lending'
                else:
                    result['group'] = 'Other'
                
                # Analyze method calls
                for action, method in protocol_info['methods'].items():
                    if method_signature == method:
                        result['action'] = action
                        result['type'] = TRANSACTION_TYPES.get(action, 'Trade')
                        break
                
                if not result['action']:
                    result['action'] = 'interaction'
                    result['type'] = 'Trade'
                
                return result

        # Token-based heuristics: if 'to' is a token contract, inspect token symbol/name for clues
        try:
            if to_address and to_address != '' and is_contract(to_address, 'arbitrum'):
                meta = get_token_meta(to_address, 'arbitrum')
                sym = (meta.get('symbol') or '').upper()
                name = (meta.get('name') or '').lower()
                # Pattern-based detection: Curve LP, Angle, Liquity
                try:
                    # Curve LP detection
                    curve_sym_matches = any(p.upper() in sym for p in CURVE_LP_PATTERNS.get('symbols', []))
                    curve_name_matches = any(p in name for p in CURVE_LP_PATTERNS.get('names', []))
                    if curve_sym_matches or curve_name_matches:
                        result['is_defi'] = True
                        result['protocol'] = 'curve'
                        result['exchange'] = EXCHANGE_NAMES.get('curve', 'Curve Finance')
                        result['group'] = 'DEX Liquidity Mining'
                        result['action'] = 'add_liquidity'
                        result['type'] = TRANSACTION_TYPES.get('add_liquidity', 'Deposit')
                        return result

                    # Angle detection
                    angle_sym_matches = any(p.upper() in sym for p in ANGLE_PATTERNS.get('symbols', []))
                    angle_name_matches = any(p in name for p in ANGLE_PATTERNS.get('names', []))
                    if angle_sym_matches or angle_name_matches:
                        result['is_defi'] = True
                        result['protocol'] = 'angle'
                        result['exchange'] = 'Angle'
                        result['group'] = 'Stablecoin'
                        result['action'] = 'interaction'
                        result['type'] = TRANSACTION_TYPES.get('interaction', 'Trade')
                        return result

                    # Liquity detection
                    liquity_sym_matches = any(p.upper() in sym for p in LIQUITY_PATTERNS.get('symbols', []))
                    liquity_name_matches = any(p in name for p in LIQUITY_PATTERNS.get('names', []))
                    if liquity_sym_matches or liquity_name_matches:
                        result['is_defi'] = True
                        result['protocol'] = 'liquity'
                        result['exchange'] = 'Liquity'
                        result['group'] = 'Lending'
                        result['action'] = 'borrow'
                        result['type'] = TRANSACTION_TYPES.get('borrow', 'Borrowing')
                        return result
                except Exception:
                    # Pattern detection is non-critical; ignore failures
                    pass
                # Aave aTokens often start with 'a' or include 'aToken' or 'aave' in symbol/name
                if sym.startswith('A') and ('aave' in name or 'atoken' in name or sym.startswith('A') and len(sym) > 1 and sym[1:].isupper()):
                    result['is_defi'] = True
                    result['protocol'] = 'aave_v3'
                    result['exchange'] = EXCHANGE_NAMES.get('aave_v3', 'Aave V3')
                    result['group'] = 'Lending'
                    result['action'] = 'interaction'
                    result['type'] = 'Deposit'
                    return result
                # GMX/angle/others: look for token names
                if 'gmx' in sym.lower() or 'gmx' in name:
                    result['is_defi'] = True
                    result['protocol'] = 'gmx'
                    result['exchange'] = 'GMX'
                    result['group'] = 'DEX Trading'
                    result['action'] = 'interaction'
                    result['type'] = 'Trade'
                    return result
        except Exception:
            pass
    
    # Enhanced generic DeFi detection for both networks
    if not result['is_defi']:
        # Check for complex transactions that are likely DeFi
        if (fn_name or (len(input_data) > 10 and method_signature not in ERC20_METHODS.values())):
            # Additional heuristics for DeFi detection - be more conservative
            value = int(tx.get('value', 0))
            gas_used = int(tx.get('gasUsed', 0))
            gas_price = int(tx.get('gasPrice', 0))
            
            # Only mark as unknown DeFi if there are strong indicators:
            # 1. Complex input data (not just ERC20 methods)
            # 2. High gas usage AND complex function call
            # 3. Exclude simple transfers and approvals
            has_complex_input = len(input_data) > 10 and method_signature not in ERC20_METHODS.values()
            has_function_name = fn_name and fn_name not in ['transfer', 'approve', 'transferFrom']
            has_very_high_gas = gas_used > 200000  # Raise threshold to be more conservative
            
            if has_complex_input and (has_function_name or has_very_high_gas):
                result['is_defi'] = True
                result['protocol'] = 'unknown'
                # Prefer functionName as the action if available
                result['action'] = fn_name or 'interaction'
                result['type'] = 'Trade'
                result['group'] = 'Other'
                # Prefer a clearer label for LP-related methods on V3 routers
                if method_signature in ['0x88316456','0xa34123a7','0xfc6f7865']:
                    result['exchange'] = EXCHANGE_NAMES.get('sparkdex_v3', 'SparkDEX V3')
                else:
                    result['exchange'] = 'Unknown DeFi'
    
    return result

def convert_to_required_format(tx: Dict, defi_analysis: Dict, network: str, wallet_address: str) -> Dict:
    """Convert transaction to the required CSV format"""
    timestamp = int(tx.get('timeStamp', 0))
    date_utc = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    
    # Get transaction details
    tx_hash = tx.get('hash', '')
    block_number = tx.get('blockNumber', '')
    from_address = tx.get('from', '')
    to_address = tx.get('to', '')
    contract_address = to_address  # For most transactions, 'to' is the contract
    
    # Get transaction value
    value_wei = int(tx.get('value', 0))
    value_eth = value_wei / 1e18
    
    # Get gas fee
    gas_used = int(tx.get('gasUsed', 0))
    gas_price = int(tx.get('gasPrice', 0))
    gas_fee_wei = gas_used * gas_price
    gas_fee_eth = gas_fee_wei / 1e18
    
    # Determine value in/out
    if from_address.lower() == wallet_address.lower():
        # Outgoing transaction
        value_in_eth = 0
        value_out_eth = value_eth
    else:
        # Incoming transaction
        value_in_eth = value_eth
        value_out_eth = 0
    
    # Get ETH prices
    current_eth_price = get_eth_price(int(time.time()))  # Current price
    historical_eth_price = get_eth_price(timestamp)  # Historical price at transaction time
    
    # Calculate USD values
    txn_fee_usd = gas_fee_eth * current_eth_price
    value_usd = value_eth * current_eth_price
    
    # Determine status
    is_error = tx.get('isError', '0')
    status = 'true' if is_error == '0' else 'false'
    err_code = '' if is_error == '0' else 'Error'
    
    # Determine method from input data
    input_data = tx.get('input', '')
    method = 'Transfer'  # Default
    if input_data and len(input_data) >= 10:
        method_signature = input_data[:10]
        # Map common method signatures to readable names
        method_mapping = {
            '0xa9059cbb': 'Transfer',
            '0x095ea7b3': 'Approve',
            '0x23b872dd': 'TransferFrom',
            '0x617ba037': 'Supply',
            '0x693ec85e': 'Withdraw',
            '0xa415bcad': 'Borrow',
            '0x573ade81': 'Repay',
            '0x12aa3caf': 'Swap',
            '0x7ff36ab5': 'SwapETH',
            '0x414bf389': 'ExactInputSingle',
            '0x88316456': 'Mint',
            '0xa34123a7': 'Burn',
            '0xfc6f7865': 'Collect',
            '0xd0e30db0': 'Deposit',
            '0x2e1a7d4d': 'Withdraw',
            '0x5c19a95c': 'Delegate',
            '0x3d18b912': 'ClaimRewards',
        }
        method = method_mapping.get(method_signature, 'Unknown')
    
    # Determine chain info
    chain_id = NETWORKS[network]['chain_id']
    chain_name = NETWORKS[network]['name']
    # Prefer Etherscan's functionName when available
    fn_name = ''
    fn_raw = tx.get('functionName') or ''
    if isinstance(fn_raw, str) and fn_raw:
        fn_name = fn_raw.split('(')[0].strip()

    # Token ID (for ERC721/ERC1155 transfers) if available
    token_id = tx.get('tokenID') or tx.get('tokenId') or tx.get('token_id') or tx.get('tokenIDHex') or ''
    
    # Create the required format
    # Derive a friendly Platform label: prefer explicit exchange from analysis,
    # fall back to protocol->EXCHANGE_NAMES mapping or the protocol key itself.
    protocol_key = (defi_analysis.get('protocol') if isinstance(defi_analysis, dict) else None) or ''
    platform_label = ''
    if isinstance(defi_analysis, dict) and defi_analysis.get('exchange'):
        platform_label = str(defi_analysis.get('exchange'))
    elif protocol_key:
        platform_label = EXCHANGE_NAMES.get(protocol_key, protocol_key.title())

    row = {
        'Transaction Hash': tx_hash,
        'Blockno': block_number,
        'UnixTimestamp': str(timestamp),
        'DateTime (UTC)': date_utc,
        'From': from_address,
        'To': to_address,
        'ContractAddress': contract_address,
        'Value_IN(ETH)': str(value_in_eth),
        'Value_OUT(ETH)': str(value_out_eth),
        'CurrentValue/Eth': str(current_eth_price),
        'TxnFee(ETH)': str(gas_fee_eth),
        'TxnFee(USD)': str(txn_fee_usd),
        'Historical $Price/Eth': str(historical_eth_price),
        'Status': status,
        'ErrCode': err_code,
        'Method': method,
        'ChainId': str(chain_id),
        'Chain': chain_name,
        'Value(ETH)': str(value_eth),
    'Platform': platform_label,
        'FunctionName': fn_name,
        'TokenId': str(token_id)
    }

    # Best-effort: fetch dApp platform and token name for the 'to' address (or contract)
    try:
        addr_info = get_address_info(to_address, network)
        row['dAppPlatform'] = addr_info.get('platform') or ''
        # If the 'to' is a token transfer, prefer token name; otherwise, attempt to extract
        row['ToTokenName'] = addr_info.get('token_name') or ''
    except Exception:
        row['dAppPlatform'] = ''
        row['ToTokenName'] = ''

    # Add contract and token information for 'from' address
    try:
        from_addr_info = get_address_info(from_address, network)
        row['FromContractName'] = from_addr_info.get('platform') or ''
        row['FromTokenName'] = from_addr_info.get('token_name') or ''
    except Exception:
        row['FromContractName'] = ''
        row['FromTokenName'] = ''

    # Add contract and token information for contract address (if different from to/from)
    try:
        if contract_address and contract_address != to_address and contract_address != from_address:
            contract_addr_info = get_address_info(contract_address, network)
            row['ContractName'] = contract_addr_info.get('platform') or ''
            row['ContractTokenName'] = contract_addr_info.get('token_name') or ''
        else:
            # If contract address is same as to/from, use existing info to avoid duplicate lookups
            if contract_address == to_address:
                row['ContractName'] = row['dAppPlatform']
                row['ContractTokenName'] = row['ToTokenName']
            elif contract_address == from_address:
                row['ContractName'] = row['FromContractName']
                row['ContractTokenName'] = row['FromTokenName']
            else:
                row['ContractName'] = ''
                row['ContractTokenName'] = ''
    except Exception:
        row['ContractName'] = ''
        row['ContractTokenName'] = ''
    
    return row

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/get_transactions', methods=['POST'])
def get_transactions():
    """API endpoint to fetch and analyze transactions from multiple networks"""
    try:
        data = request.get_json()
        wallet_address = data.get('wallet_address', '').strip()
        networks = data.get('networks', ['arbitrum'])  # Default to arbitrum if not specified
        
        if not wallet_address:
            return jsonify({'error': 'Wallet address is required'}), 400
        
        if not networks or len(networks) == 0:
            return jsonify({'error': 'At least one network must be selected'}), 400
        
        # Validate wallet address format
        if not wallet_address.startswith('0x') or len(wallet_address) != 42:
            return jsonify({'error': 'Invalid wallet address format'}), 400
        
        # Validate networks
        for network in networks:
            if network not in NETWORKS:
                return jsonify({'error': f'Invalid network: {network}'}), 400
        
        print(f"Fetching transactions for {wallet_address} on networks: {networks}")
        
        # Fetch transactions from all selected networks
        all_transactions = []
        total_defi_count = 0
        max_transactions_per_network = 5000  # Production limit - much higher for real usage
        
        for network in networks:
            print(f"Processing {network} network...")
            transactions = fetch_transactions_from_explorer(wallet_address, network, limit=max_transactions_per_network)
            
            if transactions:
                print(f"Found {len(transactions)} transactions on {network}")
                
                # Analyze transactions for this network (limit to prevent timeouts)
                processed_count = 0
                for tx in transactions:
                    if processed_count >= max_transactions_per_network:
                        print(f"Processed maximum {max_transactions_per_network} transactions for {network}")
                        break
                    
                    print(f"Processing transaction {processed_count + 1}/{min(len(transactions), max_transactions_per_network)} for {network}")
                    defi_analysis = analyze_defi_interaction(tx, network)
                    if defi_analysis['is_defi']:
                        total_defi_count += 1
                    
                    transaction_row = convert_to_required_format(tx, defi_analysis, network, wallet_address)
                    all_transactions.append(transaction_row)
                    processed_count += 1
                    
                    # Progress logging (no delays for production performance)
                    if processed_count % 100 == 0:
                        print(f"Processed {processed_count} transactions for {network}")
            else:
                print(f"No transactions found on {network}")
        
        if not all_transactions:
            # If no transactions found on any network
            return jsonify({
                'error': f'No transactions found for wallet {wallet_address} on any selected network ({", ".join(networks)}). This could mean:\n'
                         f'1. The wallet has no transaction history on these networks\n'
                         f'2. API rate limits or connectivity issues\n'
                         f'3. The wallet address is invalid\n\n'
                         f'Try with a different wallet address or check the network selection.'
            }), 404
        
        print(f"Found {total_defi_count} DeFi transactions out of {len(all_transactions)} total across all networks")
        
        # Generate CSV
        print("Generating CSV file...")
        output = io.StringIO()
        fieldnames = [
            'Transaction Hash', 'Blockno', 'UnixTimestamp', 'DateTime (UTC)', 'From', 'To',
            'ContractAddress', 'Value_IN(ETH)', 'Value_OUT(ETH)', 'CurrentValue/Eth',
            'TxnFee(ETH)', 'TxnFee(USD)', 'Historical $Price/Eth', 'Status', 'ErrCode',
            'Method', 'ChainId', 'Chain', 'Value(ETH)', 'Platform', 'FunctionName', 'TokenId',
            'dAppPlatform', 'ToTokenName', 'FromContractName', 'FromTokenName', 
            'ContractName', 'ContractTokenName'
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_transactions)
        print("CSV generation completed")
        
        csv_content = output.getvalue()
        output.close()
        
        # Create file response
        csv_io = io.BytesIO()
        csv_io.write(csv_content.encode('utf-8'))
        csv_io.seek(0)
        
        # Create filename with network info
        network_suffix = "_".join(networks) if len(networks) > 1 else networks[0]
        filename = f"{wallet_address}_{network_suffix}_transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return send_file(
            csv_io,
            as_attachment=True,
            download_name=filename,
            mimetype='text/csv'
        )
        
    except Exception as e:
        print(f"Error processing request: {e}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/db/health')
def database_health():
    """Dedicated database health check endpoint"""
    if not DATABASE_ENABLED:
        return jsonify({
            'status': 'disabled',
            'message': 'Database integration not available'
        }), 503
    
    health = get_db_health()
    status_code = 200 if health.get('status') == 'healthy' else 503
    return jsonify(health), status_code

@app.route('/db/init', methods=['POST'])
def initialize_database():
    """Initialize database with ETL schemas"""
    if not DATABASE_ENABLED:
        return jsonify({
            'error': 'Database integration not available'
        }), 503
    
    try:
        success = db_manager.initialize_database()
        if success:
            # Also run ETL initialization
            etl_success = db_manager.run_etl_initialization()
            return jsonify({
                'status': 'success',
                'message': 'Database initialized successfully',
                'etl_initialized': etl_success
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Database initialization failed'
            }), 500
    except Exception as e:
        app.logger.error(f"Database initialization error: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/db/wallet/<wallet_address>/<int:chain_id>')
def get_wallet_db_summary(wallet_address: str, chain_id: int):
    """Get wallet summary from database"""
    if not DATABASE_ENABLED:
        return jsonify({
            'error': 'Database integration not available'
        }), 503
    
    try:
        summary = db_manager.get_wallet_summary(wallet_address, chain_id)
        if summary:
            return jsonify(summary)
        else:
            return jsonify({
                'message': 'No data found for this wallet',
                'wallet_address': wallet_address,
                'chain_id': chain_id
            }), 404
    except Exception as e:
        app.logger.error(f"Error getting wallet summary: {e}")
        return jsonify({
            'error': str(e)
        }), 500

if __name__ == '__main__':
    # Test database connection on startup if enabled
    if DATABASE_ENABLED:
        app.logger.info("Testing database connection...")
        if test_db_connection():
            app.logger.info("✅ Database connection successful!")
        else:
            app.logger.warning("⚠️  Database connection failed. Running without database.")
    
    # Production mode - no debug, no auto-reload for better performance
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)
