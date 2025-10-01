from __future__ import annotations

"""DeFi service helpers (clean, single module).

Exports:
- prepare_transaction_for_db
- create_wallet_analysis
- prefetch_token_meta_bulk
- analyze_defi_interaction
- convert_to_required_format

This file is intentionally self-contained and uses lazy delegation to the
top-level app module only when runtime helpers (token metadata, price,
address info) are required. Keep signatures stable for an incremental
migration from the monolith.
"""

from datetime import datetime
from typing import Dict, List, Any, Optional, TypedDict
import concurrent.futures
import importlib
import logging

from app_new.services import runtime

logger = logging.getLogger(__name__)


def _lazy_app():
    try:
        return importlib.import_module('app')
    except Exception as e:
        logger.debug('Could not import top-level app for delegated helpers: %s', e)
        return None


def prepare_transaction_for_db(tx: Dict[str, Any], defi_analysis: Dict[str, Any], network: str, wallet_address: str) -> Dict[str, Any]:
    """Normalize a raw transaction for DB storage.

    Returns a dict with token_transfers extracted from logs and inline fields.
    The shape matches the original helper so it can be swapped in-place.
    """
    try:
        chain_id_map = {'arbitrum': 42161, 'flare': 14, 'ethereum': 1}
        chain_id = chain_id_map.get(network, 0)

        timestamp = int(tx.get('timeStamp', 0) or 0)
        db_tx: Dict[str, Any] = {
            'chain_id': chain_id,
            'hash': tx.get('hash', ''),
            'blockNumber': int(tx.get('blockNumber', 0) or 0),
            'timeStamp': timestamp,
            'from': (tx.get('from') or '').lower(),
            'to': (tx.get('to') or '').lower(),
            'value': tx.get('value', '0'),
            'gasUsed': int(tx.get('gasUsed', 0) or 0),
            'gasPrice': int(tx.get('gasPrice', 0) or 0),
            'txreceipt_status': int((tx.get('isError', '0') or '0') == '0'),
            'input': tx.get('input', ''),
            'logs': tx.get('logs', []),
            'protocol': defi_analysis.get('protocol', 'unknown') if isinstance(defi_analysis, dict) else 'unknown',
            'action_type': defi_analysis.get('action_type', 'transfer') if isinstance(defi_analysis, dict) else 'transfer',
            'token_transfers': [],
        }

        # Inline token transfer fields
        if tx.get('contractAddress') or tx.get('tokenAddress'):
            token_transfer: Dict[str, Any] = {
                'log_index': 0,
                'contractAddress': tx.get('contractAddress') or tx.get('tokenAddress', ''),
                'from': (tx.get('from') or '').lower(),
                'to': (tx.get('to') or '').lower(),
                'value': tx.get('value', '0'),
                'tokenSymbol': tx.get('tokenSymbol', ''),
                'tokenName': tx.get('tokenName', ''),
                'tokenDecimal': int(tx.get('tokenDecimal', 18) or 18),
                'value_scaled': None,
                'usd_value': None,
            }
            try:
                # Prefer an explicitly provided tokenDecimal in the tx; otherwise
                # fall back to the runtime cached decimals (which delegates to
                # the monolith when available).
                if 'tokenDecimal' in tx and (tx.get('tokenDecimal') not in (None, '')):
                    decimals = int(tx.get('tokenDecimal', 18) or 18)
                else:
                    decimals = runtime.get_token_decimals_cached(token_transfer['contractAddress'], network)
                raw_value = int(token_transfer['value'] or 0)
                token_transfer['tokenDecimal'] = int(decimals)
                token_transfer['value_scaled'] = raw_value / (10 ** int(decimals))
            except (ValueError, TypeError):
                token_transfer['value_scaled'] = 0
            db_tx['token_transfers'] = [token_transfer]

        # Parse logs for ERC20 Transfer events
        logs = tx.get('logs') or []
        if isinstance(logs, list):
            for i, log in enumerate(logs):
                try:
                    if not isinstance(log, dict):
                        continue
                    topics = log.get('topics') or []
                    if not topics:
                        continue
                    # ERC20 Transfer topic
                    if topics[0] == '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef':
                        transfer_data: Dict[str, Any] = {
                            'log_index': i + 1,
                            'contractAddress': (log.get('address') or '').lower(),
                            'from': '',
                            'to': '',
                            'value': '0',
                            'tokenSymbol': '',
                            'tokenName': '',
                            'tokenDecimal': 18,
                            'value_scaled': None,
                            'usd_value': None,
                        }
                        if len(topics) > 1 and isinstance(topics[1], str):
                            transfer_data['from'] = '0x' + topics[1][-40:]
                        if len(topics) > 2 and isinstance(topics[2], str):
                            transfer_data['to'] = '0x' + topics[2][-40:]
                        data_hex = log.get('data') or '0x0'
                        try:
                            transfer_data['value'] = str(int(data_hex, 16))
                        except Exception:
                            transfer_data['value'] = '0'
                        db_tx['token_transfers'].append(transfer_data)
                except Exception:
                    continue

        return db_tx
    except Exception:
        logger.exception('Error preparing transaction for DB')
        return {
            'chain_id': 0,
            'hash': tx.get('hash', ''),
            'blockNumber': int(tx.get('blockNumber', 0) or 0),
            'timeStamp': int(tx.get('timeStamp', 0) or 0),
            'from': (tx.get('from') or '').lower(),
            'to': (tx.get('to') or '').lower(),
            'value': tx.get('value', '0'),
            'gasUsed': int(tx.get('gasUsed', 0) or 0),
            'gasPrice': int(tx.get('gasPrice', 0) or 0),
            'txreceipt_status': 1,
            'input': '',
            'logs': [],
            'protocol': 'unknown',
            'action_type': 'transfer',
            'token_transfers': [],
        }


def create_wallet_analysis(wallet_address: str, raw_transactions: List[Dict[str, Any]], networks: List[str]) -> Dict[str, Any]:
    """Create a small summary analysis for a wallet.

    Returns counts, gas totals, unique contracts, protocols used and a
    simple defi score.
    """
    try:
        total_transactions = len(raw_transactions)
        total_gas_used = sum(int(tx.get('gasUsed', 0) or 0) for tx in raw_transactions)
        total_gas_cost = sum(int(tx.get('gasUsed', 0) or 0) * int(tx.get('gasPrice', 0) or 0) for tx in raw_transactions)

        unique_contracts = set()
        protocols_used = set()

        for tx in raw_transactions:
            if tx.get('to'):
                unique_contracts.add((tx['to'] or '').lower())
            if tx.get('protocol') and tx['protocol'] != 'unknown':
                protocols_used.add(tx['protocol'])

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
            'defi_score': min(len(protocols_used) * 10, 100),
        }
    except Exception:
        logger.exception('Error creating wallet analysis')
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
            'defi_score': 0,
        }


def prefetch_token_meta_bulk(contract_addresses: List[str], network: str, max_workers: int = 10) -> None:
    """Best-effort background prefetch of token metadata.

    Delegates to `app.get_token_meta` if available; otherwise it's a no-op.
    """
    addrs_norm: List[str] = []
    for a in contract_addresses:
        if not a:
            continue
        s = (a or '').lower()
        if not s.startswith('0x'):
            s = '0x' + s
        addrs_norm.append(s)

    def _prefetch(addr: str) -> None:
        try:
            # Use cache-aware runtime shim which will delegate to the monolith
            # when present and populate the in-memory cache to avoid repeated RPCs.
            if hasattr(runtime, 'get_token_meta_cached'):
                runtime.get_token_meta_cached(addr, network)
            else:
                runtime.get_token_meta(addr, network)
        except Exception:
            pass

    if not addrs_norm:
        return

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(max_workers, max(2, len(addrs_norm)))) as ex:
        futures = [ex.submit(_prefetch, a) for a in addrs_norm]
        for f in concurrent.futures.as_completed(futures):
            try:
                f.result()
            except Exception:
                pass


def analyze_defi_interaction(tx: Dict[str, Any], network: str) -> Dict[str, Any]:
    """Ported protocol detection logic (conservative, self-contained).

    Uses constants from `defi_config.py` and lazy RPC/token helpers when
    needed. Returns a dict with keys: is_defi, protocol, action, type, group, exchange.
    """
    result: Dict[str, Optional[Any]] = {
        'is_defi': False,
        'protocol': None,
        'action': None,
        'type': None,
        'group': None,
        'exchange': None,
    }

    try:
        from defi_config import (
            FLARE_DEFI_PROTOCOLS,
            ARBITRUM_DEFI_PROTOCOLS,
            AAVE_V3_CONFIG,
            OPENOCEAN_CONFIG,
            SPARKDEX_V3_CONFIG,
            UNISWAP_V3_CONFIG,
            SUSHISWAP_CONFIG,
            KINETIC_MARKET_CONFIG,
            FLARE_STAKING_CONFIG,
            ERC20_METHODS,
            CURVE_LP_PATTERNS,
            ANGLE_PATTERNS,
            LIQUITY_PATTERNS,
            TRANSACTION_TYPES,
            EXCHANGE_NAMES,
        )
    except Exception:
        logger.debug('defi_config import failed; returning conservative default')
        return result

    to_address = (tx.get('to') or '').lower()
    input_data = tx.get('input') or ''

    if not input_data or input_data == '0x':
        return result

    method_signature = input_data[:10] if len(input_data) >= 10 else ''
    # ignore simple ERC20 passthroughs
    if method_signature in [ERC20_METHODS.get('transfer'), ERC20_METHODS.get('approve'), ERC20_METHODS.get('transfer_from')]:
        return result

    fn_name_raw = tx.get('functionName') or ''
    fn_name = ''
    if isinstance(fn_name_raw, str) and fn_name_raw:
        fn_name = fn_name_raw.split('(')[0].strip()

    def _is_contract(addr: str, net: str) -> bool:
        # Use runtime shim which will delegate to the monolith if available
        try:
            return runtime.get_address_info(addr, net).get('is_contract', False) or False
        except Exception:
            try:
                # Fallback to runtime helper if available
                if hasattr(runtime, 'is_contract'):
                    return runtime.is_contract(addr, net)
            except Exception:
                pass
        return False

    def _get_token_meta(addr: str, net: str) -> Dict[str, str]:
        try:
            # Prefer cached getter which will call through to runtime.get_token_meta
            # and then cache the result. This reduces repeated RPCs in analysis.
            if hasattr(runtime, 'get_token_meta_cached'):
                return runtime.get_token_meta_cached(addr, net)
            return runtime.get_token_meta(addr, net) if hasattr(runtime, 'get_token_meta') else runtime.get_address_info(addr, net)
        except Exception:
            # Best-effort empty metadata
            return {'name': '', 'symbol': ''}

    try:
        # FLARE-specific checks
        if network == 'flare':
            for protocol_name, protocol_info in FLARE_DEFI_PROTOCOLS.items():
                addrs = [a for a in protocol_info.get('addresses', []) if a and a != '0x0000000000000000000000000000000000000000']
                if any(to_address == a.lower() for a in addrs):
                    result['is_defi'] = True
                    result['protocol'] = protocol_name
                    result['exchange'] = protocol_info.get('name')
                    if protocol_name in ['sparkdex_v3', 'openocean', 'flare_swap', 'flare_dex']:
                        result['group'] = 'DEX Trading'
                    elif protocol_name in ['aave_v3', 'kinetic_market', 'flare_lending']:
                        result['group'] = 'Lending'
                    elif protocol_name in ['flare_network']:
                        result['group'] = 'Stacking (passiv)'
                    else:
                        result['group'] = 'Other'

                    if fn_name:
                        result['action'] = fn_name
                        result['type'] = TRANSACTION_TYPES.get(fn_name, 'Trade')
                        return result

                    for action, method in protocol_info.get('methods', {}).items():
                        if method_signature == method:
                            result['action'] = action
                            result['type'] = TRANSACTION_TYPES.get(action, 'Trade')
                            break

                    if not result['action']:
                        result['action'] = 'interaction'
                        result['type'] = 'Trade'
                    return result

            # Staking shortcuts
            flare_cfg = FLARE_STAKING_CONFIG
            if to_address in [flare_cfg.get('wflr_contract', '').lower(), flare_cfg.get('ftso_manager', '').lower()]:
                result['is_defi'] = True
                result['protocol'] = 'flare_staking'
                result['exchange'] = EXCHANGE_NAMES.get('flare_staking')
                result['group'] = 'Stacking (passiv)'
                if fn_name:
                    result['action'] = fn_name
                    result['type'] = TRANSACTION_TYPES.get(fn_name, 'Staking')
                    return result
                for action, method in flare_cfg.get('methods', {}).items():
                    if method_signature == method:
                        result['action'] = action
                        result['type'] = TRANSACTION_TYPES.get(action, 'Staking')
                        break
                if not result['action']:
                    result['action'] = 'stake'
                    result['type'] = 'Staking'
                return result

        # ARBITRUM-specific checks
        if network == 'arbitrum':
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
                    cfg = protocol_config[network]
                    addresses_to_check: List[str] = []
                    for k in ('pool_addresses', 'router_addresses', 'pool_address', 'router_address', 'lending_pool'):
                        v = cfg.get(k)
                        if isinstance(v, list):
                            addresses_to_check.extend(v)
                        elif isinstance(v, str) and v:
                            addresses_to_check.append(v)

                    addrs = [a for a in addresses_to_check if a and a != '0x0000000000000000000000000000000000000000']
                    if any(to_address == a.lower() for a in addrs):
                        result['is_defi'] = True
                        result['protocol'] = protocol_name
                        result['exchange'] = EXCHANGE_NAMES.get(protocol_name, protocol_name.title())
                        result['group'] = default_group
                        if fn_name:
                            result['action'] = fn_name
                            result['type'] = TRANSACTION_TYPES.get(fn_name, 'Trade')
                            if protocol_name in ['uniswap_v3', 'sparkdex_v3']:
                                result['group'] = 'DEX Liquidity Mining'
                            elif protocol_name in ['aave_v3', 'kinetic_market']:
                                result['group'] = 'Lending'
                            elif protocol_name in ['openocean', 'sushiswap']:
                                result['group'] = 'DEX Trading'
                            return result

                        for action, method in cfg.get('methods', {}).items():
                            if method_signature == method:
                                result['action'] = action
                                result['type'] = TRANSACTION_TYPES.get(action, 'Trade')
                                if protocol_name in ['uniswap_v3', 'sparkdex_v3'] and action in ['mint', 'burn', 'collect']:
                                    result['group'] = 'DEX Liquidity Mining'
                                elif protocol_name in ['aave_v3', 'kinetic_market']:
                                    result['group'] = 'Lending'
                                elif protocol_name in ['openocean', 'sushiswap']:
                                    result['group'] = 'DEX Trading'
                                break

                        if not result['action']:
                            result['action'] = 'interaction'
                            result['type'] = 'Trade'
                        return result

            # Fallback method signature map (fast heuristic)
            method_fallback_map = {
                '0x38ed1739': 'openocean',
                '0x7ff36ab5': 'openocean',
                '0x18cbafe5': 'openocean',
                '0x12aa3caf': 'openocean',
                '0x414bf389': 'sparkdex_v3',
                '0xc04b8d59': 'sparkdex_v3',
                '0xdb3e2198': 'sparkdex_v3',
                '0xf28c0498': 'sparkdex_v3',
                '0x88316456': 'sparkdex_v3',
                '0xa34123a7': 'sparkdex_v3',
                '0xfc6f7865': 'sparkdex_v3',
                '0x128acb08': 'sparkdex_v3',
                '0x617ba037': 'aave_v3',
                '0x693ec85e': 'aave_v3',
                '0xa415bcad': 'aave_v3',
                '0x573ade81': 'aave_v3',
                '0x80e670ae': 'aave_v3',
                '0xab9c4b5d': 'aave_v3',
                '0x47e7ef24': 'kinetic_market',
                '0x5c19a95c': 'flare_network',
                '0x3d18b912': 'flare_network',
                '0xd0e30db0': 'flare_network',
                '0x2e1a7d4d': 'flare_network',
            }

            if input_data and len(input_data) >= 10:
                msig = input_data[:10]
                mapped = method_fallback_map.get(msig)
                if mapped and not result['is_defi']:
                    result['is_defi'] = True
                    result['protocol'] = mapped
                    result['exchange'] = EXCHANGE_NAMES.get(mapped, mapped.title())
                    if mapped in ['sparkdex_v3', 'openocean', 'sushiswap', 'uniswap_v3']:
                        result['group'] = 'DEX Trading'
                    elif mapped in ['aave_v3', 'compound', 'kinetic_market']:
                        result['group'] = 'Lending'
                    elif mapped in ['flare_network']:
                        result['group'] = 'Stacking (passiv)'
                    else:
                        result['group'] = 'Other'

                    # try to map action name from known configs
                    action_name = None
                    network_key = 'arbitrum' if network == 'arbitrum' else 'flare'
                    for proto_conf in (
                        AAVE_V3_CONFIG.get(network_key, {}).get('methods', {}),
                        SPARKDEX_V3_CONFIG.get(network_key, {}).get('methods', {}),
                        OPENOCEAN_CONFIG.get(network_key, {}).get('methods', {}),
                        KINETIC_MARKET_CONFIG.get(network_key, {}).get('methods', {}),
                        FLARE_STAKING_CONFIG.get('methods', {}),
                    ):
                        for act, sig in proto_conf.items():
                            if sig == msig:
                                action_name = act
                                break
                        if action_name:
                            break
                    result['action'] = action_name or 'interaction'
                    result['type'] = TRANSACTION_TYPES.get(result['action'], 'Trade')
                    return result

            for protocol_name, protocol_info in ARBITRUM_DEFI_PROTOCOLS.items():
                if any(to_address == a.lower() for a in protocol_info.get('addresses', [])):
                    result['is_defi'] = True
                    result['protocol'] = protocol_name
                    result['exchange'] = protocol_info.get('name')
                    if protocol_name in ['sparkdex_v3', 'openocean', 'curve', 'balancer', 'sushiswap']:
                        result['group'] = 'DEX Trading'
                    elif protocol_name in ['aave_v3', 'kinetic_market', 'compound']:
                        result['group'] = 'Lending'
                    else:
                        result['group'] = 'Other'

                    for action, method in protocol_info.get('methods', {}).items():
                        if method_signature == method:
                            result['action'] = action
                            result['type'] = TRANSACTION_TYPES.get(action, 'Trade')
                            break

                    if not result['action']:
                        result['action'] = 'interaction'
                        result['type'] = 'Trade'
                    return result

            # heuristics based on token metadata (curve, angle, liquity)
            try:
                if to_address and to_address != '' and _is_contract(to_address, 'arbitrum'):
                    meta = _get_token_meta(to_address, 'arbitrum')
                    sym = (meta.get('symbol') or '').upper()
                    name = (meta.get('name') or '').lower()
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
                pass

        # generic heuristics for unlabeled contracts / complex calls
        if not result['is_defi']:
            if (fn_name or (len(input_data) > 10 and method_signature not in ERC20_METHODS.values())):
                gas_used = int(tx.get('gasUsed', 0) or 0)

                has_complex_input = len(input_data) > 10 and method_signature not in ERC20_METHODS.values()
                has_function_name = fn_name and fn_name not in ['transfer', 'approve', 'transferFrom']
                has_very_high_gas = gas_used > 200000

                if has_complex_input and (has_function_name or has_very_high_gas):
                    result['is_defi'] = True
                    result['protocol'] = 'unknown'
                    result['action'] = fn_name or 'interaction'
                    result['type'] = 'Trade'
                    result['group'] = 'Other'
                    if method_signature in ['0x88316456', '0xa34123a7', '0xfc6f7865']:
                        result['exchange'] = EXCHANGE_NAMES.get('sparkdex_v3', 'SparkDEX V3')
                    else:
                        result['exchange'] = 'Unknown DeFi'

    except Exception as e:
        logger.exception('analyze_defi_interaction error: %s', e)
        return {'is_defi': False, 'protocol': None, 'action': None, 'type': None, 'group': None, 'exchange': None}

    return result


def convert_to_required_format(tx: Dict[str, Any], defi_analysis: Dict[str, Any], network: str, wallet_address: str) -> Dict[str, Any]:
    """Convert a normalized transaction to CoinTracking/CSV friendly row.

    This function currently delegates to runtime helpers in `app` for price
    and address metadata (lazy import) during incremental migration.
    """
    # Prefer runtime shims which will lazy-delegate to the monolith when
    # available but provide safe fallbacks for imports and tests.
    NETWORKS = runtime.get_networks()
    EXCHANGE_NAMES = runtime.get_exchange_names()
    get_eth_price = runtime.get_eth_price
    get_address_info = runtime.get_address_info
    method_mapping = runtime.get_method_signature_mapping()

    timestamp = int(tx.get('timeStamp', 0) or 0)
    date_utc = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%dT%H:%M:%S.000Z')

    tx_hash = tx.get('hash', '')
    block_number = tx.get('blockNumber', '')
    from_address = tx.get('from', '')
    to_address = tx.get('to', '')
    contract_address = to_address

    value_wei = int(tx.get('value', 0) or 0)
    value_eth = value_wei / 1e18

    gas_used = int(tx.get('gasUsed', 0) or 0)
    gas_price = int(tx.get('gasPrice', 0) or 0)
    gas_fee_wei = gas_used * gas_price
    gas_fee_eth = gas_fee_wei / 1e18

    if from_address.lower() == wallet_address.lower():
        value_in_eth = 0
        value_out_eth = value_eth
    else:
        value_in_eth = value_eth
        value_out_eth = 0

    current_eth_price = get_eth_price(int(__import__('time').time()))
    historical_eth_price = get_eth_price(timestamp)

    txn_fee_usd = gas_fee_eth * current_eth_price

    is_error = tx.get('isError', '0')
    status = 'true' if is_error == '0' else 'false'
    err_code = '' if is_error == '0' else 'Error'

    input_data = tx.get('input', '')
    method = 'Transfer'
    if input_data and len(input_data) >= 10:
        method_signature = input_data[:10]
        method = method_mapping.get(method_signature, 'Unknown')

    chain_id = NETWORKS[network]['chain_id']
    chain_name = NETWORKS[network]['name']
    fn_name = ''
    fn_raw = tx.get('functionName') or ''
    if isinstance(fn_raw, str) and fn_raw:
        fn_name = fn_raw.split('(')[0].strip()

    token_id = tx.get('tokenID') or tx.get('tokenId') or tx.get('token_id') or tx.get('tokenIDHex') or ''

    protocol_key = (defi_analysis.get('protocol') if isinstance(defi_analysis, dict) else None) or ''
    platform_label = ''
    if isinstance(defi_analysis, dict) and defi_analysis.get('exchange'):
        platform_label = str(defi_analysis.get('exchange'))
    elif protocol_key:
        platform_label = EXCHANGE_NAMES.get(protocol_key, protocol_key.title())

    row: Dict[str, Any] = {
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
        'TokenId': str(token_id),
    }

    try:
        addr_info = get_address_info(to_address, network)
        row['dAppPlatform'] = addr_info.get('platform') or ''
        row['ToTokenName'] = addr_info.get('token_name') or ''
    except Exception:
        row['dAppPlatform'] = ''
        row['ToTokenName'] = ''

    try:
        from_addr_info = get_address_info(from_address, network)
        row['FromContractName'] = from_addr_info.get('platform') or ''
        row['FromTokenName'] = from_addr_info.get('token_name') or ''
    except Exception:
        row['FromContractName'] = ''
        row['FromTokenName'] = ''

    try:
        if contract_address and contract_address != to_address and contract_address != from_address:
            contract_addr_info = get_address_info(contract_address, network)
            row['ContractName'] = contract_addr_info.get('platform') or ''
            row['ContractTokenName'] = contract_addr_info.get('token_name') or ''
        else:
            if contract_address == to_address:
                row['ContractName'] = row.get('dAppPlatform', '')
                row['ContractTokenName'] = row.get('ToTokenName', '')
            elif contract_address == from_address:
                row['ContractName'] = row.get('FromContractName', '')
                row['ContractTokenName'] = row.get('FromTokenName', '')
            else:
                row['ContractName'] = ''
                row['ContractTokenName'] = ''
    except Exception:
        row['ContractName'] = ''
        row['ContractTokenName'] = ''

    return row


__all__ = [
    'prepare_transaction_for_db',
    'create_wallet_analysis',
    'prefetch_token_meta_bulk',
    'analyze_defi_interaction',
    'convert_to_required_format',
]


# Type hints for important shapes used in this module


class TokenTransfer(TypedDict, total=False):
    log_index: int
    contractAddress: str
    from_: str
    to: str
    value: str
    tokenSymbol: str
    tokenName: str
    tokenDecimal: int
    value_scaled: Optional[float]
    usd_value: Optional[float]

