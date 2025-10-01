from __future__ import annotations

"""Runtime helper shims for incremental migration.

This module provides a small surface that defers to the top-level `app`
module when available (lazy import) but provides safe fallbacks so services
can be imported and unit-tested without starting the whole monolith.
"""

from typing import Any, Dict, List
import concurrent.futures
import importlib
import logging
import os
import json
import time
import threading
import requests
from typing import Optional
from typing import Tuple
# ...existing code...

logger = logging.getLogger(__name__)


def _lazy_app():
    try:
        return importlib.import_module("app")
    except Exception as e:
        logger.debug("runtime: could not import app: %s", e)
        return None


# Minimal NETWORKS fallback; the canonical NETWORKS lives in the monolith but
# these defaults are safe for unit tests and basic CSV conversion.
NETWORKS: Dict[str, Dict[str, Any]] = {
    "arbitrum": {"chain_id": 42161, "name": "Arbitrum One"},
    "flare": {"chain_id": 14, "name": "Flare"},
    "ethereum": {"chain_id": 1, "name": "Ethereum"},
}


def get_networks():
    app = _lazy_app()
    if app and hasattr(app, "NETWORKS"):
        try:
            return getattr(app, "NETWORKS")
        except Exception:
            pass
    return NETWORKS


EXCHANGE_NAMES: Dict[str, str] = {}


def get_exchange_names():
    app = _lazy_app()
    if app and hasattr(app, "EXCHANGE_NAMES"):
        try:
            return getattr(app, "EXCHANGE_NAMES")
        except Exception:
            pass
    return EXCHANGE_NAMES


METHOD_SIGNATURE_MAPPING: Dict[str, str] = {}


def get_method_signature_mapping():
    app = _lazy_app()
    if app and hasattr(app, "METHOD_SIGNATURE_MAPPING"):
        try:
            return getattr(app, "METHOD_SIGNATURE_MAPPING")
        except Exception:
            pass
    return METHOD_SIGNATURE_MAPPING


def get_eth_price(ts: int) -> float:
    """Get ETH price at timestamp `ts`. Delegates to app when available.

    Returns 0.0 when price can't be determined (safe fallback for tests).
    """
    app = _lazy_app()
    if app and hasattr(app, "get_eth_price"):
        try:
            return float(app.get_eth_price(ts))
        except Exception:
            logger.debug("get_eth_price delegation failed")
    return 0.0


# Simple price cache and CoinGecko helpers
PRICE_CACHE: Dict[str, float] = {}
COINGECKO_BASE = 'https://api.coingecko.com/api/v3'
COINGECKO_PLATFORM_MAP = {
    'arbitrum': 'arbitrum-one',
    'flare': 'flare'
}


def get_token_price_coingecko(contract_address: str, network: str, vs_currency: str = 'usd') -> float:
    """Fetch token price from CoinGecko by contract address (cached)."""
    app = _lazy_app()
    if app and hasattr(app, 'get_token_price_coingecko'):
        try:
            return float(app.get_token_price_coingecko(contract_address, network, vs_currency))
        except Exception:
            logger.debug('Delegation to app.get_token_price_coingecko failed')

    if not contract_address:
        return 0.0
    key = f"price_{contract_address.lower()}_{network}_{vs_currency}"
    if key in PRICE_CACHE:
        return PRICE_CACHE[key]

    platform = COINGECKO_PLATFORM_MAP.get(network, 'ethereum')
    try:
        url = f"{COINGECKO_BASE}/simple/token_price/{platform}"
        params = {'contract_addresses': contract_address, 'vs_currencies': vs_currency}
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        addr_key = contract_address.lower()
        if isinstance(data, dict) and addr_key in data and isinstance(data[addr_key], dict):
            price = float(data[addr_key].get(vs_currency, 0.0) or 0.0)
            PRICE_CACHE[key] = price
            return price
    except Exception:
        pass

    try:
        url2 = f"{COINGECKO_BASE}/coins/{platform}/contract/{contract_address}"
        r2 = requests.get(url2, timeout=10)
        r2.raise_for_status()
        jd = r2.json()
        price = float(jd.get('market_data', {}).get('current_price', {}).get(vs_currency, 0.0) or 0.0)
        PRICE_CACHE[key] = price
        return price
    except Exception:
        PRICE_CACHE[key] = 0.0
        return 0.0


def get_coingecko_simple_price(coin_id: str, vs_currency: str = 'usd') -> float:
    app = _lazy_app()
    if app and hasattr(app, 'get_coingecko_simple_price'):
        try:
            return float(app.get_coingecko_simple_price(coin_id, vs_currency))
        except Exception:
            logger.debug('Delegation to app.get_coingecko_simple_price failed')

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


def fetch_prices_for_tokens(tokens: list, network: str, max_workers: int = 8) -> None:
    """Fetch and attach price_usd, value_usd and price_source into token dicts in-place."""
    app = _lazy_app()
    if app and hasattr(app, 'fetch_prices_for_tokens'):
        try:
            return app.fetch_prices_for_tokens(tokens, network, max_workers=max_workers)
        except Exception:
            logger.debug('Delegation to app.fetch_prices_for_tokens failed')

    def _fetch(contract: str) -> float:
        try:
            return get_token_price_coingecko(contract, network)
        except Exception:
            return 0.0

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

    for t in tokens:
        contract = (t.get('contract') or '').lower()
        price = results.get(contract, 0.0)
        qty = float(t.get('quantity') or 0.0)
        price_source = 'none'
        if price and price != 0.0:
            price_source = 'coingecko'
        if not price or price == 0.0:
            sym = (t.get('symbol') or '').upper()
            name = (t.get('name') or '').lower()
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
            if network == 'flare':
                if 'WFLR' in sym or sym == 'FLR' or 'wrapped flare' in name or 'wrapped-flare' in name:
                    price = get_coingecko_simple_price('flare')
                    price_source = 'heuristic'
                if ('RFLR' in sym) or ('reward flare' in name) or ('rflr' in name):
                    price = get_coingecko_simple_price('flare')
                    price_source = 'heuristic'
                if 'USDT' in sym or 'USDC' in sym or 'TETHER' in name or 'USD COIN' in name:
                    price = 1.0
                    price_source = 'heuristic'
        t['price_usd'] = float(price)
        t['value_usd'] = round(qty * price, 6)
        t['price_source'] = price_source


def fetch_transactions_from_explorer(wallet_address: str, network: str, limit: int = 1000, include_token_transfers: bool = True) -> list:
    """Fetch transactions from explorer APIs or RPCs. Delegates to monolith when available.

    Returns a list of tx dicts. In absence of explorer/RPC access, returns small mock data for tests.
    """
    app = _lazy_app()
    if app and hasattr(app, 'fetch_transactions_from_explorer'):
        try:
            return app.fetch_transactions_from_explorer(wallet_address, network, limit=limit, include_token_transfers=include_token_transfers)
        except Exception:
            logger.debug('Delegation to app.fetch_transactions_from_explorer failed')

    # Conservative local implementation: prefer Etherscan v2 if configured, else try RPC fallbacks, else return mock
    try:
        if network not in NETWORKS:
            return []
        # Try Etherscan v2 if available
        etherscan_base = NETWORKS.get(network, {}).get('etherscan_v2') or NETWORKS.get(network, {}).get('explorer_api')
        chain_id = NETWORKS.get(network, {}).get('chain_id')
        collected = []
        page = 1
        page_size = 200
        if etherscan_base:
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
                        'sort': 'desc'
                    }
                    r = requests.get(etherscan_base, params=params, timeout=15)
                    r.raise_for_status()
                    data = r.json()
                    page_txs = data.get('result', []) or []
                    collected.extend(page_txs)
                    if len(page_txs) < offset:
                        break
                    page += 1
                return collected[:limit]
            except Exception:
                logger.debug('Etherscan v2 fetch failed, falling back to RPC')

        # RPC fallbacks per network
        if network == 'arbitrum':
            rpc_res = fetch_from_arbitrum_rpc(wallet_address, limit)
            if rpc_res:
                return rpc_res
            return generate_mock_arbitrum_transactions(wallet_address, limit)
        elif network == 'flare':
            rpc_res = fetch_from_flare_rpc(wallet_address, limit)
            if rpc_res:
                return rpc_res
            return generate_mock_flare_transactions(wallet_address, limit)
        else:
            return []
    except Exception:
        return []


def fetch_from_arbitrum_rpc(wallet_address: str, limit: int = 1000) -> list:
    """Try to scan recent Arbitrum blocks for transactions involving `wallet_address`.

    This is a best-effort lightweight implementation for tests and fallback; prefer monolith delegation in production.
    """
    try:
        rpc_url = NETWORKS.get('arbitrum', {}).get('rpc_url', 'https://arb1.arbitrum.io/rpc')
        # Get latest block
        blk = requests.post(rpc_url, json={'jsonrpc':'2.0','method':'eth_blockNumber','params':[],'id':1}, timeout=10)
        blk.raise_for_status()
        latest_block = int(blk.json().get('result', '0x0'), 16)
        start_block = max(0, latest_block - 1000)
        transactions = []
        search_blocks = min(500, latest_block - start_block)
        for i in range(search_blocks):
            block_num = latest_block - i
            block_hex = hex(block_num)
            br = requests.post(rpc_url, json={'jsonrpc':'2.0','method':'eth_getBlockByNumber','params':[block_hex, True],'id':1}, timeout=5)
            if br.status_code != 200:
                continue
            bd = br.json().get('result')
            if not bd:
                continue
            for tx in bd.get('transactions', []):
                if (tx.get('from','').lower() == wallet_address.lower() or tx.get('to','').lower() == wallet_address.lower()):
                    formatted_tx = {
                        'hash': tx.get('hash',''),
                        'blockNumber': str(block_num),
                        'timeStamp': str(int(bd.get('timestamp','0x0'), 16)),
                        'from': tx.get('from',''),
                        'to': tx.get('to',''),
                        'value': tx.get('value','0x0'),
                        'gas': tx.get('gas','0x0'),
                        'gasPrice': tx.get('gasPrice','0x0'),
                        'gasUsed': tx.get('gas','0x0'),
                        'input': tx.get('input','0x'),
                        'isError': '0',
                        'txreceipt_status': '1'
                    }
                    transactions.append(formatted_tx)
                    if len(transactions) >= limit:
                        break
            if len(transactions) >= limit:
                break
            if i % 50 == 0:
                time.sleep(0.02)
        return transactions
    except Exception:
        return []


def fetch_from_flare_rpc(wallet_address: str, limit: int = 1000) -> list:
    try:
        rpc_url = NETWORKS.get('flare', {}).get('rpc_url', 'https://flare-api.flare.network/ext/C/rpc')
        br = requests.post(rpc_url, json={'jsonrpc':'2.0','method':'eth_blockNumber','params':[],'id':1}, timeout=10)
        br.raise_for_status()
        latest_block = int(br.json().get('result', '0x0'), 16)
        start_block = max(0, latest_block - 1000)
        transactions = []
        search_blocks = min(500, latest_block - start_block)
        for i in range(search_blocks):
            block_num = latest_block - i
            block_hex = hex(block_num)
            br2 = requests.post(rpc_url, json={'jsonrpc':'2.0','method':'eth_getBlockByNumber','params':[block_hex, True],'id':1}, timeout=5)
            if br2.status_code != 200:
                continue
            bd = br2.json().get('result')
            if not bd:
                continue
            for tx in bd.get('transactions', []):
                if (tx.get('from','').lower() == wallet_address.lower() or tx.get('to','').lower() == wallet_address.lower()):
                    formatted_tx = {
                        'hash': tx.get('hash',''),
                        'blockNumber': str(block_num),
                        'timeStamp': str(int(bd.get('timestamp','0x0'), 16)),
                        'from': tx.get('from',''),
                        'to': tx.get('to',''),
                        'value': tx.get('value','0x0'),
                        'gas': tx.get('gas','0x0'),
                        'gasPrice': tx.get('gasPrice','0x0'),
                        'gasUsed': tx.get('gas','0x0'),
                        'input': tx.get('input','0x'),
                        'isError': '0',
                        'txreceipt_status': '1'
                    }
                    transactions.append(formatted_tx)
                    if len(transactions) >= limit:
                        break
            if len(transactions) >= limit:
                break
            if i % 50 == 0:
                time.sleep(0.02)
        return transactions
    except Exception:
        return []


def generate_mock_arbitrum_transactions(wallet_address: str, limit: int = 100) -> list:
    import random
    import time as _t
    mock_transactions = []
    current_time = int(_t.time())
    for i in range(min(limit, 20)):
        tx = {
            'hash': f"0x{'b'*64}",
            'blockNumber': str(2000000 + i),
            'timeStamp': str(current_time - (i * 3600)),
            'from': wallet_address,
            'to': '0x9876543210987654321098765432109876543210',
            'value': str(random.randint(1000000000000000000, 10000000000000000000)),
            'gas': '21000',
            'gasPrice': '1000000000',
            'gasUsed': '21000',
            'input': '0x',
            'isError': '0',
            'txreceipt_status': '1'
        }
        mock_transactions.append(tx)
    return mock_transactions


def generate_mock_flare_transactions(wallet_address: str, limit: int = 100) -> list:
    import random
    import time as _t
    mock_transactions = []
    current_time = int(_t.time())
    for i in range(min(limit, 20)):
        tx = {
            'hash': f"0x{'a'*64}",
            'blockNumber': str(1000000 + i),
            'timeStamp': str(current_time - (i * 3600)),
            'from': wallet_address,
            'to': '0x1234567890123456789012345678901234567890',
            'value': str(random.randint(1000000000000000000, 10000000000000000000)),
            'gas': '21000',
            'gasPrice': '20000000000',
            'gasUsed': '21000',
            'input': '0x',
            'isError': '0',
            'txreceipt_status': '1'
        }
        mock_transactions.append(tx)
    return mock_transactions


# Token metadata TTL and debounce save settings
_TOKEN_META_TTL = int(os.environ.get('TOKEN_META_CACHE_TTL_SECONDS', str(7 * 24 * 60 * 60)))
_SAVE_DEBOUNCE_SECONDS = int(os.environ.get('TOKEN_META_CACHE_SAVE_DEBOUNCE', '30'))
_SAVE_TIMER_LOCK = threading.Lock()
_SAVE_TIMER: Optional[threading.Timer] = None

# Address info disk cache (mimics monolith behavior)
_ADDRESS_INFO_CACHE: Dict[str, Dict[str, Any]] = {}
_ADDRESS_INFO_CACHE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'address_info_cache.json'))
_ADDRESS_INFO_TTL = int(os.environ.get('ADDRESS_INFO_CACHE_TTL_SECONDS', str(7 * 24 * 60 * 60)))
_ADDRESS_SAVE_TIMER_LOCK = threading.Lock()
_ADDRESS_SAVE_TIMER: Optional[threading.Timer] = None


def get_address_info(addr: str, network: str) -> Dict[str, Any]:
    """Return metadata about an address/contract (platform, token_name).

    Delegates to the monolith if available, otherwise returns empty metadata.
    """
    # Try top-level app first
    app = _lazy_app()
    if app and hasattr(app, "get_address_info"):
        try:
            return app.get_address_info(addr, network) or {}
        except Exception:
            logger.debug("get_address_info delegation failed for %s", addr)

    # Local disk-backed cache fallback
    try:
        if not addr:
            return {"platform": "", "token_name": ""}
        key = f"{network}:{(addr or '').lower()}"
        # Load address cache lazily from disk if not already loaded
        if not _ADDRESS_INFO_CACHE:
            try:
                if os.path.exists(_ADDRESS_INFO_CACHE_PATH):
                    with open(_ADDRESS_INFO_CACHE_PATH, 'r', encoding='utf-8') as fh:
                        data = json.load(fh) or {}
                        now = int(time.time())
                        for k, v in data.items():
                            try:
                                ts = int(v.get('_ts', 0))
                                if now - ts <= _ADDRESS_INFO_TTL:
                                    _ADDRESS_INFO_CACHE[k] = v
                            except Exception:
                                continue
            except Exception:
                logger.debug('Failed to load address info cache')

        entry = _ADDRESS_INFO_CACHE.get(key)
        if isinstance(entry, dict) and 'info' in entry:
            return entry['info']
        if isinstance(entry, dict):
            return entry
    except Exception:
        pass
    # Best-effort empty metadata
    return {"platform": "", "token_name": ""}


# Explorer helpers (delegation to app when available, otherwise use local explorer module)
try:
    from app_new.services import explorer as _explorer_impl
except Exception:
    _explorer_impl = None


def fetch_token_balances(wallet_address: str, network: str, tokens: List[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    app = _lazy_app()
    if app and hasattr(app, 'fetch_token_balances'):
        try:
            return app.fetch_token_balances(wallet_address, network, tokens)
        except Exception:
            logger.debug('Delegation to app.fetch_token_balances failed')
    if _explorer_impl and hasattr(_explorer_impl, 'fetch_token_balances'):
        try:
            return _explorer_impl.fetch_token_balances(wallet_address, network, tokens)
        except Exception:
            logger.debug('Local explorer.fetch_token_balances failed')
    return {}


def fetch_token_transfers(wallet_address: str, network: str, limit: int = 1000):
    app = _lazy_app()
    if app and hasattr(app, 'fetch_token_transfers'):
        try:
            return app.fetch_token_transfers(wallet_address, network, limit=limit)
        except Exception:
            logger.debug('Delegation to app.fetch_token_transfers failed')
    if _explorer_impl and hasattr(_explorer_impl, 'fetch_token_transfers'):
        try:
            return _explorer_impl.fetch_token_transfers(wallet_address, network, limit=limit)
        except Exception:
            logger.debug('Local explorer.fetch_token_transfers failed')
    return [], {'pages_main': 0, 'pages_fallback': 0, 'used_fallback': False}


def fetch_flare_token_details(wallet_address: str, limit: int = 1000):
    app = _lazy_app()
    if app and hasattr(app, 'fetch_flare_token_details'):
        try:
            return app.fetch_flare_token_details(wallet_address, limit=limit)
        except Exception:
            logger.debug('Delegation to app.fetch_flare_token_details failed')
    if _explorer_impl and hasattr(_explorer_impl, 'fetch_flare_token_details'):
        try:
            return _explorer_impl.fetch_flare_token_details(wallet_address, limit=limit)
        except Exception:
            logger.debug('Local explorer.fetch_flare_token_details failed')
    return []


def get_token_meta(addr: str, network: str) -> Dict[str, str]:
    """Return token metadata (name, symbol) by delegating to app when available.

    Safe fallback returns empty strings.
    """
    # Delegate to app if present
    app = _lazy_app()
    if app and hasattr(app, "get_token_meta"):
        try:
            return app.get_token_meta(addr, network) or {"name": "", "symbol": ""}
        except Exception:
            logger.debug("get_token_meta delegation failed for %s", addr)

    # Local on-chain lookup fallback using eth_call
    if not addr:
        return {"name": "", "symbol": ""}
    if not addr.startswith('0x'):
        addr = '0x' + addr

    try:
        rpc = NETWORKS.get(network, {}).get('rpc_url')
        if not rpc:
            return {"name": "", "symbol": ""}

        def _call_and_decode(selector_hex: str) -> str:
            try:
                payload = {'jsonrpc': '2.0', 'method': 'eth_call', 'params': [{'to': addr, 'data': selector_hex}, 'latest'], 'id': 1}
                r = requests.post(rpc, json=payload, timeout=6)
                r.raise_for_status()
                res = r.json().get('result', '') or ''
                if not res or res == '0x':
                    return ''
                try:
                    val = abi_decode(['string'], res)
                    if isinstance(val, list):
                        return str(val[0]) if val else ''
                except Exception:
                    pass
                # Fallback bytes32 decode
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

        name = _call_and_decode('0x06fdde03')
        symbol = _call_and_decode('0x95d89b41')
        meta = {"name": name or "", "symbol": symbol or ""}
        return meta
    except Exception:
        return {"name": "", "symbol": ""}


# Token meta disk-backed cache and helpers
_TOKEN_META_CACHE: Dict[str, Dict[str, Any]] = {}
_TOKEN_META_CACHE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'token_meta_cache.json'))


def _load_token_meta_cache() -> None:
    global _TOKEN_META_CACHE
    try:
        if os.path.exists(_TOKEN_META_CACHE_PATH):
            with open(_TOKEN_META_CACHE_PATH, 'r', encoding='utf-8') as fh:
                data = json.load(fh) or {}
                now = int(time.time())
                filtered: Dict[str, Dict[str, Any]] = {}
                for k, v in data.items():
                    try:
                        ts = int(v.get('_ts', 0))
                        if now - ts <= _TOKEN_META_TTL:
                            filtered[k] = v
                    except Exception:
                        continue
                _TOKEN_META_CACHE = filtered
    except Exception:
        logger.debug('Failed to load token meta cache')


def _atomic_write(path: str, data: Any) -> None:
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    try:
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(path)
        except Exception:
            pass
        os.replace(tmp, path)


def _save_token_meta_cache() -> None:
    try:
        to_save = {k: v for k, v in _TOKEN_META_CACHE.items()}
        _atomic_write(_TOKEN_META_CACHE_PATH, to_save)
    except Exception:
        logger.debug('Failed to save token meta cache')


def _schedule_save_token_meta_cache() -> None:
    global _SAVE_TIMER
    with _SAVE_TIMER_LOCK:
        if _SAVE_TIMER is not None:
            try:
                _SAVE_TIMER.cancel()
            except Exception:
                pass
        _SAVE_TIMER = threading.Timer(_SAVE_DEBOUNCE_SECONDS, _save_token_meta_cache)
        _SAVE_TIMER.daemon = True
        _SAVE_TIMER.start()


def get_token_meta_cached(addr: str, network: str) -> Dict[str, str]:
    if not addr:
        return {"name": "", "symbol": ""}
    key = f"{network}:{addr.lower()}"
    # lazy load
    if not _TOKEN_META_CACHE:
        _load_token_meta_cache()
    entry = _TOKEN_META_CACHE.get(key)
    if isinstance(entry, dict) and 'name' in entry and 'symbol' in entry:
        return {'name': entry.get('name') or '', 'symbol': entry.get('symbol') or ''}
    meta = get_token_meta(addr, network)
    try:
        _TOKEN_META_CACHE[key] = {**meta, '_ts': int(time.time())}
        _schedule_save_token_meta_cache()
    except Exception:
        pass
    return meta


def get_token_decimals(addr: str, network: str) -> Optional[int]:
    app = _lazy_app()
    if app and hasattr(app, 'get_token_decimals'):
        try:
            return app.get_token_decimals(addr, network)
        except Exception:
            logger.debug('Delegation to app.get_token_decimals failed')
    if not addr:
        return None
    if not addr.startswith('0x'):
        addr = '0x' + addr
    try:
        rpc = NETWORKS.get(network, {}).get('rpc_url')
        if not rpc:
            return None
        payload = {'jsonrpc': '2.0', 'method': 'eth_call', 'params': [{'to': addr, 'data': '0x313ce567'}, 'latest'], 'id': 1}
        r = requests.post(rpc, json=payload, timeout=6)
        r.raise_for_status()
        res = r.json().get('result', '') or ''
        if not res or res == '0x':
            return None
        try:
            val = abi_decode(['uint8'], res)
            if isinstance(val, list) and val:
                return int(val[0])
        except Exception:
            pass
        # Fallback: parse first 32 bytes
        hexdata = res[2:]
        if len(hexdata) >= 64:
            first32 = hexdata[:64]
            try:
                return int(first32, 16)
            except Exception:
                return None
    except Exception:
        return None


def get_token_decimals_cached(addr: str, network: str) -> Optional[int]:
    if not addr:
        return None
    key = f"{network}:{addr.lower()}"
    if not _TOKEN_META_CACHE:
        _load_token_meta_cache()
    entry = _TOKEN_META_CACHE.get(key)
    if isinstance(entry, dict) and 'decimals' in entry:
        try:
            return int(entry.get('decimals'))
        except Exception:
            pass
    dec = get_token_decimals(addr, network)
    try:
        _TOKEN_META_CACHE.setdefault(key, {})
        if dec is not None:
            _TOKEN_META_CACHE[key]['decimals'] = dec
        _TOKEN_META_CACHE[key]['_ts'] = int(time.time())
        _schedule_save_token_meta_cache()
    except Exception:
        pass
    return dec


def is_contract(addr: str, network: str) -> bool:
    """Return True if address is a contract. Delegates to app when available.

    Fallback conservatively returns False.
    """
    app = _lazy_app()
    if app and hasattr(app, "is_contract"):
        try:
            return bool(app.is_contract(addr, network))
        except Exception:
            logger.debug("is_contract delegation failed for %s", addr)

    # Fallback: call eth_getCode on the network RPC
    try:
        if not addr:
            return False
        if not addr.startswith('0x'):
            addr = '0x' + addr
        rpc = NETWORKS.get(network, {}).get('rpc_url')
        if not rpc:
            return False
        payload = {'jsonrpc': '2.0', 'method': 'eth_getCode', 'params': [addr, 'latest'], 'id': 1}
        r = requests.post(rpc, json=payload, timeout=8)
        r.raise_for_status()
        jd = r.json()
        code = jd.get('result', '') or ''
        return bool(code and code != '0x')
    except Exception:
        return False


# Simple in-memory token metadata cache (thread-safe-ish)
_TOKEN_META_CACHE: Dict[str, Dict[str, str]] = {}
_TOKEN_META_CACHE_LOADED = False
_TOKEN_META_CACHE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'token_meta_cache.json'))


# Simple in-memory token decimals cache
_TOKEN_DECIMALS_CACHE: Dict[str, int] = {}


def set_token_decimals(addr: str, network: str, decimals: int) -> None:
    key = f"{network}:{(addr or '').lower()}"
    try:
        _TOKEN_DECIMALS_CACHE[key] = int(decimals)
    except Exception:
        _TOKEN_DECIMALS_CACHE[key] = 18


def get_token_decimals(addr: str, network: str) -> int:
    """Delegate to app.get_token_decimals if available; fallback to 18."""
    app = _lazy_app()
    if app and hasattr(app, 'get_token_decimals'):
        try:
            return int(app.get_token_decimals(addr, network))
        except Exception:
            logger.debug('get_token_decimals delegation failed for %s', addr)
    return 18


def get_token_decimals_cached(addr: str, network: str) -> int:
    key = f"{network}:{(addr or '').lower()}"
    if key in _TOKEN_DECIMALS_CACHE:
        return _TOKEN_DECIMALS_CACHE[key]
    d = get_token_decimals(addr, network)
    _TOKEN_DECIMALS_CACHE[key] = d
    return d


def set_token_meta(addr: str, network: str, meta: Dict[str, str]) -> None:
    key = f"{network}:{(addr or '').lower()}"
    # Ensure disk cache loaded before mutating
    _ensure_token_meta_cache_loaded()
    _TOKEN_META_CACHE[key] = meta or {"name": "", "symbol": ""}
    try:
        _save_token_meta_cache_to_disk()
    except Exception:
        logger.debug("Failed to persist token meta cache to disk")


def get_token_meta_cached(addr: str, network: str) -> Dict[str, str]:
    """Try cache first, otherwise delegate to app via get_token_meta and cache result."""
    key = f"{network}:{(addr or '').lower()}"
    # Load disk cache lazily
    _ensure_token_meta_cache_loaded()
    if key in _TOKEN_META_CACHE:
        return _TOKEN_META_CACHE[key]

    meta = get_token_meta(addr, network)
    if meta and isinstance(meta, dict):
        _TOKEN_META_CACHE[key] = meta
        try:
            _save_token_meta_cache_to_disk()
        except Exception:
            logger.debug("Failed to persist token meta cache to disk after fetch")
        return meta
    return {"name": "", "symbol": ""}


def _ensure_token_meta_cache_loaded() -> None:
    global _TOKEN_META_CACHE_LOADED
    if _TOKEN_META_CACHE_LOADED:
        return
    try:
        if os.path.exists(_TOKEN_META_CACHE_PATH):
            with open(_TOKEN_META_CACHE_PATH, 'r', encoding='utf-8') as fh:
                data = json.load(fh) or {}
                # Expecting dict[str, dict]
                if isinstance(data, dict):
                    for k, v in data.items():
                        if isinstance(v, dict):
                            _TOKEN_META_CACHE[k] = v
    except Exception:
        logger.debug('Failed to load token meta cache from disk: %s', _TOKEN_META_CACHE_PATH)
    _TOKEN_META_CACHE_LOADED = True


def _save_token_meta_cache_to_disk() -> None:
    # Ensure parent dir exists
    try:
        d = os.path.dirname(_TOKEN_META_CACHE_PATH)
        os.makedirs(d, exist_ok=True)
        tmp_path = _TOKEN_META_CACHE_PATH + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as fh:
            json.dump(_TOKEN_META_CACHE, fh, ensure_ascii=False, indent=2)
        os.replace(tmp_path, _TOKEN_META_CACHE_PATH)
    except Exception:
        logger.debug('Failed to write token meta cache to disk: %s', _TOKEN_META_CACHE_PATH)


def _abi_decode_types(types: List[str], data_hex: str) -> List[Any]:
    """Internal robust ABI decoder: types + data_hex -> list of decoded values."""
    if not data_hex or data_hex == '0x':
        return []

    try:
        from eth_abi import decode_abi, decode_single
        hx = data_hex[2:] if data_hex.startswith('0x') else data_hex
        b = bytes.fromhex(hx)
        try:
            if len(types) == 1:
                val = decode_single(types[0], b)
                if isinstance(val, (bytes, bytearray)):
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
            try:
                if len(b) >= 32:
                    offset = int.from_bytes(b[0:32], 'big')
                    if offset > 0 and len(b) > offset:
                        decoded = decode_abi(types, b[offset:])
                        return list(decoded)
            except Exception:
                pass
    except Exception:
        pass

    # Fallback minimal logic
    try:
        hx = data_hex[2:] if data_hex.startswith('0x') else data_hex
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


def abi_decode(*args):
    """Dispatcher: supports two forms:

    - abi_decode(data_str) -> legacy minimal dict { method_signature, params }
    - abi_decode(types_list, data_hex) -> robust list of decoded values
    """
    # Legacy one-arg form: minimal param extraction
    if len(args) == 1 and isinstance(args[0], str):
        data = args[0]
        out: Dict[str, Any] = {"method_signature": "", "params": []}
        if not data or not isinstance(data, str):
            return out
        data_hex = data[2:] if data.startswith('0x') else data
        if len(data_hex) < 8:
            return out
        out["method_signature"] = "0x" + data_hex[:8]
        params_hex = []
        rest = data_hex[8:]
        for i in range(0, len(rest), 64):
            word = rest[i:i+64]
            if word:
                params_hex.append("0x" + word)
        out["params"] = params_hex
        return out

    # Two-arg form: types + data_hex
    if len(args) >= 2 and isinstance(args[0], (list, tuple)) and isinstance(args[1], str):
        types = list(args[0])
        data_hex = args[1]
        return _abi_decode_types(types, data_hex)

    # Unknown usage
    raise TypeError('abi_decode expects either (data_str) or (types_list, data_hex)')
