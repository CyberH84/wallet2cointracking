from __future__ import annotations

"""Explorer and RPC helper fallbacks extracted from the monolith.

These functions try to delegate to the top-level `app` when available but
provide local fallbacks so the logic can be unit-tested without starting the
monolith.
"""
from typing import Any, Dict, List, Optional, Tuple
import importlib
import requests
import concurrent.futures
import os
import json
import time


def _lazy_app():
    try:
        return importlib.import_module('app')
    except Exception:
        return None


def _get_networks():
    app = _lazy_app()
    if app and hasattr(app, 'NETWORKS'):
        try:
            return getattr(app, 'NETWORKS')
        except Exception:
            pass
    return {
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


def _get_etherscan_config() -> Tuple[str, str]:
    app = _lazy_app()
    base = 'https://api.etherscan.io/v2/api'
    key = ''
    if app:
        try:
            base = getattr(app, 'ETHERSCAN_V2_BASE', base)
            key = getattr(app, 'ETHERSCAN_API_KEY', key)
        except Exception:
            pass
    return base, key


def fetch_token_balances(wallet_address: str, network: str, tokens: List[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    """Query on-chain token balances for a list of token dicts.

    Returns a map { contract_lower_with_0x: quantity (float) | None }.
    Tries explorer API tokenbalance, Etherscan v2 multi-chain, then RPC eth_call.
    """
    app = _lazy_app()
    if app and hasattr(app, 'fetch_token_balances'):
        try:
            return app.fetch_token_balances(wallet_address, network, tokens)
        except Exception:
            pass

    NETWORKS = _get_networks()
    if network not in NETWORKS:
        return {}

    explorer_api = NETWORKS[network].get('explorer_api')
    chain_id = NETWORKS[network].get('chain_id')
    rpc_url = NETWORKS[network].get('rpc_url')

    contracts = [ (t.get('contract') or '').lower().replace('0x','') for t in tokens if t.get('contract') ]
    unique_contracts = list(dict.fromkeys(c for c in contracts if c))

    headers = {'Accept': 'application/json'}

    def _to_qty_raw(raw_str: str, decimals: int) -> Optional[float]:
        try:
            raw = int(raw_str or 0)
            if decimals and decimals > 0:
                return raw / (10 ** decimals)
            return float(raw)
        except Exception:
            return None

    ETHERSCAN_V2_BASE, ETHERSCAN_API_KEY = _get_etherscan_config()

    def fetch_one(c_no0x: str):
        key = '0x' + c_no0x
        decimals = 0
        for t in tokens:
            if (t.get('contract') or '').lower().replace('0x','') == c_no0x:
                try:
                    decimals = int(t.get('decimals') or 0)
                except Exception:
                    decimals = 0
                break

        # 1) Explorer API
        if explorer_api:
            try:
                params = {'module': 'account', 'action': 'tokenbalance', 'contractaddress': key, 'address': wallet_address, 'tag': 'latest'}
                r = requests.get(explorer_api, params=params, timeout=10, headers=headers)
                r.raise_for_status()
                d = r.json()
                if isinstance(d, dict) and ('result' in d):
                    qty = _to_qty_raw(d.get('result'), decimals)
                    return (key, qty)
            except Exception:
                pass

        # 2) Etherscan v2
        try:
            params2 = {
                'module': 'account', 'action': 'tokenbalance', 'contractaddress': key, 'address': wallet_address,
                'tag': 'latest', 'chainid': chain_id, 'apikey': ETHERSCAN_API_KEY
            }
            r2 = requests.get(ETHERSCAN_V2_BASE, params=params2, timeout=10, headers=headers)
            r2.raise_for_status()
            d2 = r2.json()
            if isinstance(d2, dict) and ('result' in d2):
                qty = _to_qty_raw(d2.get('result'), decimals)
                return (key, qty)
        except Exception:
            pass

        # 3) RPC eth_call
        if rpc_url:
            try:
                selector = '0x70a08231'
                addr_no0x = wallet_address.lower().replace('0x','').rjust(64, '0')
                data = selector + addr_no0x
                payload = {'jsonrpc': '2.0', 'method': 'eth_call', 'params': [{'to': key, 'data': data}, 'latest'], 'id': 1}
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


def fetch_token_transfers(wallet_address: str, network: str, limit: int = 1000) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    app = _lazy_app()
    if app and hasattr(app, 'fetch_token_transfers'):
        try:
            return app.fetch_token_transfers(wallet_address, network, limit=limit)
        except Exception:
            pass

    NETWORKS = _get_networks()
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

    ETHERSCAN_V2_BASE, ETHERSCAN_API_KEY = _get_etherscan_config()

    try:
        if explorer_api:
            while len(collected) < limit:
                remaining = limit - len(collected)
                offset = min(page_size, remaining)
                params = {
                    'module': 'account', 'action': 'tokentx', 'address': wallet_address,
                    'startblock': 0, 'endblock': 99999999, 'page': page, 'offset': offset, 'sort': 'desc'
                }
                r = requests.get(explorer_api, params=params, timeout=30)
                r.raise_for_status()
                d = r.json()
                if not _is_valid_result(d):
                    break
                items = d.get('result', []) or []
                pages_main += 1
                collected.extend(items)
                if len(items) < offset:
                    break
                page += 1

        if len(collected) == 0:
            chain_id = NETWORKS[network].get('chain_id')
            page = 1
            used_fallback = True
            while len(collected) < limit:
                remaining = limit - len(collected)
                offset = min(page_size, remaining)
                params = {
                    'module': 'account', 'action': 'tokentx', 'chainid': chain_id, 'address': wallet_address,
                    'startblock': 0, 'endblock': 99999999, 'page': page, 'offset': offset, 'sort': 'desc', 'apikey': ETHERSCAN_API_KEY
                }
                r = requests.get(ETHERSCAN_V2_BASE, params=params, timeout=30)
                r.raise_for_status()
                d = r.json()
                if not _is_valid_result(d):
                    break
                items = d.get('result', []) or []
                pages_fallback += 1
                collected.extend(items)
                if len(items) < offset:
                    break
                page += 1

        meta = {'pages_main': pages_main, 'pages_fallback': pages_fallback, 'used_fallback': used_fallback}
        return collected[:limit], meta
    except Exception:
        return [], {'pages_main': pages_main, 'pages_fallback': pages_fallback, 'used_fallback': used_fallback}


def fetch_flare_token_details(wallet_address: str, limit: int = 1000) -> List[Dict]:
    app = _lazy_app()
    if app and hasattr(app, 'fetch_flare_token_details'):
        try:
            return app.fetch_flare_token_details(wallet_address, limit=limit)
        except Exception:
            pass

    NETWORKS = _get_networks()
    explorer_api = NETWORKS.get('flare', {}).get('explorer_api')
    collected: List[Dict] = []
    page = 1
    page_size = 200

    try:
        while len(collected) < limit:
            remaining = limit - len(collected)
            offset = min(page_size, remaining)
            params = {'module': 'account', 'action': 'tokentx', 'address': wallet_address, 'startblock': 0, 'endblock': 99999999, 'page': page, 'offset': offset, 'sort': 'desc'}
            if not explorer_api:
                break
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

        tokens: Dict[str, Dict[str, Any]] = {}
        for t in collected:
            contract = (t.get('contractAddress') or '').lower()
            if not contract:
                continue
            try:
                decimals = int(t.get('tokenDecimal') or 0)
            except Exception:
                decimals = 0
            try:
                raw_value = int(t.get('value') or 0)
            except Exception:
                raw_value = 0

            qty = (raw_value / (10 ** decimals)) if decimals > 0 else float(raw_value)
            info = tokens.setdefault(contract, {'contract': contract, 'name': t.get('tokenName') or '', 'symbol': t.get('tokenSymbol') or '', 'decimals': decimals, 'quantity': 0.0, 'last_block': int(t.get('blockNumber') or 0)})
            if not info.get('name') and t.get('tokenName'):
                info['name'] = t.get('tokenName')
            if not info.get('symbol') and t.get('tokenSymbol'):
                info['symbol'] = t.get('tokenSymbol')
            if info.get('decimals', 0) == 0 and decimals:
                info['decimals'] = decimals

            wallet_lower = wallet_address.lower()
            to_addr = (t.get('to') or '').lower()
            from_addr = (t.get('from') or '').lower()
            direction = 0
            if to_addr == wallet_lower:
                direction = 1
            elif from_addr == wallet_lower:
                direction = -1
            else:
                continue

            info['quantity'] = info.get('quantity', 0.0) + (direction * qty)
            try:
                blk = int(t.get('blockNumber') or 0)
                if blk > info.get('last_block', 0):
                    info['last_block'] = blk
            except Exception:
                pass

        result = sorted(tokens.values(), key=lambda x: x.get('quantity', 0), reverse=True)
        return result
    except Exception:
        return []
