import time
from datetime import datetime

import pytest

from app_new.services import defi, runtime


def test_prepare_transaction_for_db_uses_cached_decimals_when_missing(monkeypatch):
    # Arrange: tx lacks tokenDecimal, runtime provides cached decimals
    tx = {
        "hash": "0xabc",
        "blockNumber": 1,
        "timeStamp": int(time.time()),
        "from": "0xFrom",
        "to": "0xTo",
        "contractAddress": "0xToken",
        "value": "1000",
    }
    defi_analysis = {"protocol": "unknown"}

    called = {}

    def fake_get_token_decimals_cached(addr, net):
        called['addr'] = addr
        called['net'] = net
        return 3

    monkeypatch.setattr(runtime, 'get_token_decimals_cached', fake_get_token_decimals_cached)

    # Act
    db_tx = defi.prepare_transaction_for_db(tx, defi_analysis, 'arbitrum', '0xFrom')

    # Assert
    assert 'token_transfers' in db_tx
    assert len(db_tx['token_transfers']) == 1
    t = db_tx['token_transfers'][0]
    assert t['tokenDecimal'] == 3
    assert t['value_scaled'] == 1000 / 10 ** 3
    assert called['addr'].lower().startswith('0x')
    assert called['net'] == 'arbitrum'


def test_create_wallet_analysis_aggregates_fields():
    now = int(time.time())
    raw_transactions = [
        {"to": "0xA", "gasUsed": "100", "gasPrice": "2", "timeStamp": now, "protocol": "aave_v3"},
        {"to": "0xB", "gasUsed": "200", "gasPrice": "3", "timeStamp": now + 10, "protocol": "openocean"},
    ]
    res = defi.create_wallet_analysis('0xWallet', raw_transactions, ['arbitrum'])
    assert res['wallet_address'] == '0xwallet'
    assert res['total_transactions'] == 2
    assert int(res['total_gas_used']) == 300
    assert int(res['total_gas_cost_wei']) == 100 * 2 + 200 * 3
    assert res['unique_contracts'] == 2
    assert 'aave_v3' in res['protocols_used']
    assert res['defi_score'] >= 10


def test_prefetch_token_meta_bulk_calls_cached_getter(monkeypatch):
    calls = []

    def fake_get_token_meta_cached(addr, net):
        calls.append((addr, net))
        return {"symbol": "TKN", "name": "Token"}

    monkeypatch.setattr(runtime, 'get_token_meta_cached', fake_get_token_meta_cached)

    # Addresses include one without 0x prefix and one already lowercased
    addresses = ["deadbeef", "0xDeAdBeEf"]

    defi.prefetch_token_meta_bulk(addresses, 'arbitrum', max_workers=2)

    # Ensure both normalized addresses were requested (lowercased with 0x prefix)
    normalized = {a[0].lower() for a in calls}
    assert any(a.startswith('0x') for a in normalized)
    assert len(calls) == 2


def test_analyze_defi_interaction_erc20_passthrough_and_complex_cases(monkeypatch):
    from defi_config import ERC20_METHODS

    # ERC20 transfer passthrough should not be considered DeFi
    tx_transfer = {"to": "0xToken", "input": ERC20_METHODS.get('transfer') or '0x', "gasUsed": "21000"}
    r = defi.analyze_defi_interaction(tx_transfer, 'arbitrum')
    assert r['is_defi'] is False

    # Complex function name should be considered DeFi by generic heuristics
    tx_complex = {"to": "0xSomeContract", "input": '0x' + 'a' * 64, "functionName": 'swapExactTokensForTokens(uint256,uint256,address[])', "gasUsed": "250000"}
    r2 = defi.analyze_defi_interaction(tx_complex, 'arbitrum')
    assert r2['is_defi'] is True
    assert r2['protocol'] in (None, 'unknown', 'unknown')
    assert r2['action'] == 'swapExactTokensForTokens' or r2['action'] == 'interaction'


def test_convert_to_required_format_uses_runtime_helpers(monkeypatch):
    # Setup minimal runtime helpers
    monkeypatch.setattr(runtime, 'get_networks', lambda: {'arbitrum': {'chain_id': 42161, 'name': 'Arbitrum'}})
    monkeypatch.setattr(runtime, 'get_exchange_names', lambda: {'curve': 'Curve'})
    monkeypatch.setattr(runtime, 'get_eth_price', lambda ts: 1000.0)
    monkeypatch.setattr(runtime, 'get_address_info', lambda addr, net: {'platform': 'Curve', 'token_name': 'LP Token'})
    monkeypatch.setattr(runtime, 'get_method_signature_mapping', lambda: {})

    tx = {
        'hash': '0xhash',
        'blockNumber': 123,
        'timeStamp': int(time.time()),
        'from': '0xFrom',
        'to': '0xTo',
        'value': str(int(2 * 10 ** 18)),
        'gasUsed': '21000',
        'gasPrice': str(int(50 * 10 ** 9)),
        'input': '0x',
    }
    defi_analysis = {'protocol': 'curve', 'exchange': 'Curve'}

    row = defi.convert_to_required_format(tx, defi_analysis, 'arbitrum', '0xFrom')

    assert row['Transaction Hash'] == '0xhash'
    assert row['Chain'] == 'Arbitrum'
    assert row['Platform'] == 'Curve'
    # TxnFee(ETH) computed as gasUsed * gasPrice / 1e18
    assert float(row['TxnFee(ETH)']) == (21000 * (50 * 10 ** 9)) / 1e18
    assert row['From'] == '0xFrom'
    assert row['To'] == '0xTo'
