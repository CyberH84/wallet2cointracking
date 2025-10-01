import builtins
import json
import types
from app_new.services import explorer
from app_new.services import runtime


class MockResponse:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code

    def json(self):
        return self._data

    def raise_for_status(self):
        if not (200 <= self.status_code < 300):
            raise Exception(f"HTTP {self.status_code}")


def test_fetch_token_transfers_primary_explorer(monkeypatch):
    wallet = '0x' + 'a' * 40

    def fake_get(url, params=None, timeout=None, headers=None):
        # Return a typical tokentx response
        data = {
            'status': '1',
            'result': [
                {
                    'hash': '0xdead',
                    'contractAddress': '0x' + '1' * 40,
                    'tokenDecimal': '18',
                    'value': '1000000000000000000',
                    'from': wallet,
                    'to': '0x' + '2' * 40,
                    'blockNumber': '100'
                }
            ]
        }
        return MockResponse(data)

    monkeypatch.setattr(explorer.requests, 'get', fake_get)
    transfers, meta = explorer.fetch_token_transfers(wallet, 'flare', limit=50)
    assert isinstance(transfers, list)
    assert len(transfers) == 1
    assert transfers[0]['hash'] == '0xdead'
    assert isinstance(meta, dict)


def test_fetch_token_balances_primary_explorer(monkeypatch):
    wallet = '0x' + 'b' * 40
    token_contract = '0x' + 'c' * 40
    tokens = [{'contract': token_contract, 'decimals': 6}]

    def fake_get(url, params=None, timeout=None, headers=None):
        # Simulate explorer tokenbalance response
        return MockResponse({'result': '123450000'})

    monkeypatch.setattr(explorer.requests, 'get', fake_get)
    res = explorer.fetch_token_balances(wallet, 'arbitrum', tokens)
    assert isinstance(res, dict)
    assert ('0x' + token_contract.lower().replace('0x', '')) in res
    key = '0x' + token_contract.lower().replace('0x', '')
    # 123450000 / 10**6 == 123.45
    assert abs((res[key] or 0) - 123.45) < 1e-6


def test_fetch_flare_token_details_aggregation(monkeypatch):
    wallet = '0x' + 'd' * 40

    def fake_get(url, params=None, timeout=None, headers=None):
        data = {
            'status': '1',
            'result': [
                {
                    'contractAddress': '0x' + 'e' * 40,
                    'tokenDecimal': '18',
                    'tokenName': 'MockToken',
                    'tokenSymbol': 'MTK',
                    'value': '2000000000000000000',
                    'to': wallet,
                    'from': '0x' + 'f' * 40,
                    'blockNumber': '123'
                }
            ]
        }
        return MockResponse(data)

    monkeypatch.setattr(explorer.requests, 'get', fake_get)
    tokens = explorer.fetch_flare_token_details(wallet, limit=100)
    assert isinstance(tokens, list)
    assert len(tokens) == 1
    t = tokens[0]
    assert t['contract'] == ('0x' + 'e' * 40)
    assert abs(t['quantity'] - 2.0) < 1e-9


def test_runtime_wrappers_call_explorer(monkeypatch):
    # Ensure runtime uses local explorer implementation when app is not present
    wallet = '0x' + 'a' * 40

    def fake_get(url, params=None, timeout=None, headers=None):
        return MockResponse({'status': '1', 'result': []})

    monkeypatch.setattr(explorer.requests, 'get', fake_get)
    # runtime should delegate to explorer which we patched
    transfers, meta = runtime.fetch_token_transfers(wallet, 'flare', limit=10)
    assert isinstance(transfers, list)
    assert isinstance(meta, dict)
