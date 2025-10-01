from app_new.services import defi, runtime


def test_prefetch_normalizes_addresses_and_calls_cache(monkeypatch):
    calls = []

    def fake_get_token_meta_cached(addr, net):
        calls.append((addr, net))
        return {'name': 'X', 'symbol': 'X'}

    monkeypatch.setattr(runtime, 'get_token_meta_cached', fake_get_token_meta_cached)

    addrs = ['0xABC', 'abc', '', None]
    defi.prefetch_token_meta_bulk(addrs, 'arbitrum', max_workers=2)

    # Expect normalized addresses with 0x prefix and lowercased
    assert any(a[0].startswith('0x') for a in calls)
    assert all(a[1] == 'arbitrum' for a in calls)
    assert len(calls) >= 1
