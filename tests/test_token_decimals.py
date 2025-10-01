from app_new.services import defi, runtime


def test_prepare_transaction_uses_cached_decimals(monkeypatch):
    tx = {
        'hash': '0x1',
        'blockNumber': '123',
        'timeStamp': '1600000000',
        'from': '0xsender',
        'to': '0xcontract',
        'value': '1000000000000000000',  # 1 token in wei-style
        # no tokenDecimal provided
        'contractAddress': '0xTokenAddr'
    }

    # monkeypatch decimals cache getter to return 9 decimals
    monkeypatch.setattr(runtime, 'get_token_decimals_cached', lambda a, n: 9)

    res = defi.prepare_transaction_for_db(tx, {}, 'arbitrum', '0xsender')
    assert res['token_transfers']
    tt = res['token_transfers'][0]
    # value_scaled should be 1e18 / 10**9 = 1e9
    assert tt['tokenDecimal'] == 9
    assert tt['value_scaled'] == 1000000000
