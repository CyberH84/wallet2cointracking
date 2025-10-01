from __future__ import annotations

"""Runtime helper shims for incremental migration.

This module provides a small surface that defers to the top-level `app`
module when available (lazy import) but provides safe fallbacks so services
can be imported and unit-tested without starting the whole monolith.
"""

from typing import Any, Dict
import importlib
import logging
import os
import json
import time
import threading
import requests
from typing import Optional

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


def abi_decode(data: str) -> Dict[str, Any]:
    """Lightweight ABI decode helper.

    Returns a dict with 'method_signature' (0x...) and 'params' list of hex strings.
    This is intentionally minimal — full ABI decoding requires type info and
    external libs, but this helper extracts the method id and raw params for
    heuristic uses.
    """
    out: Dict[str, Any] = {"method_signature": "", "params": []}
    if not data or not isinstance(data, str):
        return out
    if data.startswith("0x"):
        data_hex = data[2:]
    else:
        data_hex = data
    if len(data_hex) < 8:
        return out
    out["method_signature"] = "0x" + data_hex[:8]
    params_hex = []
    rest = data_hex[8:]
    # split into 32-byte (64 hex char) words
    for i in range(0, len(rest), 64):
        word = rest[i:i+64]
        if word:
            params_hex.append("0x" + word)
    out["params"] = params_hex
    return out
