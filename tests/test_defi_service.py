import sys
sys.path.insert(0, r'D:\wallet2cointracking')
from app_new.services import defi


def test_exports_present():
    assert 'prepare_transaction_for_db' in getattr(defi, '__all__', [])
    assert 'convert_to_required_format' in getattr(defi, '__all__', [])


def test_prepare_transaction_for_db_basic():
    sample_tx = {'hash': '0xabc', 'blockNumber': '1', 'timeStamp': '1600000000', 'gasUsed': '21000', 'gasPrice': '1000000000', 'from': '0x1', 'to': '0x2', 'value': '0'}
    dbtx = defi.prepare_transaction_for_db(sample_tx, {'protocol': 'unknown'}, 'arbitrum', '0x1')
    assert isinstance(dbtx, dict)
    assert dbtx['hash'] == '0xabc'


def test_analyze_defi_interaction_conservative():
    sample_tx = {'hash': '0xabc', 'blockNumber': '1', 'timeStamp': '1600000000', 'from': '0x1', 'to': '0x2'}
    res = defi.analyze_defi_interaction(sample_tx, 'arbitrum')
    assert isinstance(res, dict)
    # When top-level app is not imported, detection should be conservative
    assert res.get('protocol') in (None, 'unknown')
