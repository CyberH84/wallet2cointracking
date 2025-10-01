import tempfile
import os
import json
from app_new.services import runtime


def test_token_meta_disk_cache_roundtrip(tmp_path, monkeypatch):
    tmp_file = tmp_path / 'token_meta_cache.json'
    # Point runtime to the temp path
    monkeypatch.setattr(runtime, '_TOKEN_META_CACHE_PATH', str(tmp_file))
    # Ensure fresh state
    if '_TOKEN_META_CACHE' in runtime.__dict__:
        runtime.__dict__['_TOKEN_META_CACHE'].clear()
    runtime.__dict__['_TOKEN_META_CACHE_LOADED'] = False

    # Initially write a file that the runtime should load
    sample = {'arbitrum:0xabc': {'name': 'Sample', 'symbol': 'SMP'}}
    with open(str(tmp_file), 'w', encoding='utf-8') as fh:
        json.dump(sample, fh)

    # Now call get_token_meta_cached which should load from disk
    res = runtime.get_token_meta_cached('0xabc', 'arbitrum')
    assert res['name'] == 'Sample'

    # Now set a new entry and ensure it persists
    runtime.set_token_meta('0xdef', 'arbitrum', {'name': 'New', 'symbol': 'NW'})
    # Reload file contents
    with open(str(tmp_file), 'r', encoding='utf-8') as fh:
        on_disk = json.load(fh)
    assert 'arbitrum:0xdef' in on_disk
    assert on_disk['arbitrum:0xdef']['symbol'] == 'NW'
