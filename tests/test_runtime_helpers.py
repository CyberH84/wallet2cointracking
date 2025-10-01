from app_new.services import runtime


def test_abi_decode_basic():
    data = "0x1234567800000000000000000000000000000000000000000000000000000001"
    res = runtime.abi_decode(data)
    assert res["method_signature"] == "0x12345678"
    assert isinstance(res["params"], list)
    assert res["params"][0].startswith("0x")


def test_token_meta_cache_set_get():
    addr = "0xAbC"
    net = "arbitrum"
    meta = {"name": "TestToken", "symbol": "TT"}
    runtime.set_token_meta(addr, net, meta)
    cached = runtime.get_token_meta_cached(addr, net)
    assert cached["name"] == "TestToken"
    assert cached["symbol"] == "TT"


def test_token_meta_cached_miss_calls_get_token_meta(monkeypatch):
    addr = "0xdeadbeef"
    net = "flare"

    called = {}

    def fake_get_token_meta(a, n):
        called['ok'] = True
        return {"name": "FB", "symbol": "FB"}

    monkeypatch.setattr(runtime, 'get_token_meta', fake_get_token_meta)
    # ensure cache empty for key
    key = f"{net}:{addr.lower()}"
    if key in runtime.__dict__.get('_TOKEN_META_CACHE', {}):
        runtime.__dict__['_TOKEN_META_CACHE'].pop(key, None)

    res = runtime.get_token_meta_cached(addr, net)
    assert called.get('ok', False) is True
    assert res['symbol'] == 'FB'
