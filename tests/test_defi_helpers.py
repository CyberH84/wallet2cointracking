from __future__ import annotations

import time
from typing import Dict, Any

import pytest

from app_new.services import defi, runtime


def test_prepare_transaction_for_db_inline_transfer(monkeypatch):
    tx = {
        'hash': '0xabc',
        'blockNumber': '123',
        'timeStamp': '1600000000',
        'from': '0xFromAddr',
        'to': '0xToAddr',
        'contractAddress': '0xToken',
        'value': '1000000',
        'tokenDecimal': '6',
        'gasUsed': '21000',
        'gasPrice': '100'
    }
    # ensure runtime decimals path is not required
    monkeypatch.setattr(runtime, 'get_token_decimals_cached', lambda addr, net: 6)

    db = defi.prepare_transaction_for_db(tx, {}, 'arbitrum', '0xFromAddr')
    assert isinstance(db, dict)
    assert db['token_transfers'] and len(db['token_transfers']) == 1
    tt = db['token_transfers'][0]
    assert tt['tokenDecimal'] == 6
    # value 1_000_000 with 6 decimals -> 1.0
    assert tt['value_scaled'] == 1.0


def test_create_wallet_analysis_basic():
    txs = [
        {'to': '0xC1', 'protocol': 'aave', 'timeStamp': 1600000000, 'gasUsed': '1000', 'gasPrice': '1'},
        {'to': '0xC2', 'protocol': 'unknown', 'timeStamp': 1600003600, 'gasUsed': '2000', 'gasPrice': '1'},
    ]
    res = defi.create_wallet_analysis('0xMyWallet', txs, ['arbitrum'])
    assert res['wallet_address'] == '0xmywallet'
    assert res['total_transactions'] == 2
    assert res['unique_contracts'] == 2
    assert int(res['total_gas_used']) == 3000


def test_prefetch_token_meta_bulk_calls_runtime(monkeypatch):
    calls = []

    def fake_get_token_meta_cached(addr: str, net: str):
        calls.append((addr, net))
        return {'name': 'T', 'symbol': 'T'}

    monkeypatch.setattr(runtime, 'get_token_meta_cached', fake_get_token_meta_cached)

    addrs = ['0xAa', '0xBb']
    defi.prefetch_token_meta_bulk(addrs, 'arbitrum', max_workers=2)
    # normalized addresses should be passed
    assert any('0x' in a[0].lower() for a in calls)
    assert all(c[1] == 'arbitrum' for c in calls)


def test_analyze_defi_interaction_no_input():
    tx = {'to': '0xFoo', 'input': '0x'}
    res = defi.analyze_defi_interaction(tx, 'arbitrum')
    assert res['is_defi'] is False


def test_convert_to_required_format_basic(monkeypatch):
    tx = {
        'hash': '0x1',
        'blockNumber': '10',
        'timeStamp': int(time.time()),
        'from': '0xFrom',
        'to': '0xTo',
        'value': '1000000000000000000',  # 1 ETH
        'gasUsed': '21000',
        'gasPrice': '1000000000',  # 1 gwei
        'input': '0x'
    }

    # stub pricing and address info
    monkeypatch.setattr(runtime, 'get_eth_price', lambda ts: 2000.0)
    monkeypatch.setattr(runtime, 'get_address_info', lambda addr, net: {'platform': 'P', 'token_name': 'Tok'})
    monkeypatch.setattr(runtime, 'get_networks', lambda: runtime.NETWORKS)
    monkeypatch.setattr(runtime, 'get_exchange_names', lambda: {})
    monkeypatch.setattr(runtime, 'get_method_signature_mapping', lambda: {})

    row = defi.convert_to_required_format(tx, {}, 'arbitrum', '0xFrom')
    assert row['Value(ETH)'] == '1.0'
    assert float(row['TxnFee(ETH)']) == pytest.approx((21000 * 1e9) / 1e18)
    assert float(row['TxnFee(USD)']) == pytest.approx(float(row['TxnFee(ETH)']) * 2000.0)


def test_prepare_transaction_for_db_parses_erc20_logs(monkeypatch):
    # Create a fake log with ERC20 Transfer topic and 32-byte topics for from/to
    from_topic = '0x' + '0' * 24 + '111111111111111111111111'
    to_topic = '0x' + '0' * 24 + '222222222222222222222222'
    # data is hex of an integer value
    value = 5000
    data_hex = hex(value)
    tx = {
        'hash': '0xlog',
        'blockNumber': '1',
        'timeStamp': '1600000000',
        'from': '0xsomeone',
        'to': '0xcontract',
        'input': '0xdead',
        'logs': [
            {
                'address': '0xTokenAddr',
                'topics': [
                    '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef',
                    from_topic,
                    to_topic,
                ],
                'data': data_hex,
            }
        ],
    }

    # Ensure runtime functions that might be called are present but not used
    monkeypatch.setattr(runtime, 'get_token_decimals_cached', lambda addr, net: 18)

    db = defi.prepare_transaction_for_db(tx, {}, 'arbitrum', '0xsomeone')
    assert isinstance(db, dict)
    assert db['token_transfers'] and len(db['token_transfers']) == 1
    tt = db['token_transfers'][0]
    assert tt['contractAddress'] == '0xtokenaddr'
    # from/to are constructed from the topic tail
    assert tt['from'].lower().endswith('111111111111111111111111')
    assert tt['to'].lower().endswith('222222222222222222222222')
    assert tt['value'] == str(value)
