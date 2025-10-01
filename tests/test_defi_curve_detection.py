from app_new.services import defi, runtime
from defi_config import CURVE_LP_PATTERNS

from app_new.services import defi, runtime


def test_curve_detection_via_token_meta(monkeypatch):
    # Simulate a to_address that is a contract and whose token meta matches Curve LP patterns
    tx = {
        'to': '0xCurvePool',
        'input': '0xdeadbeefcafebabe',
        'gasUsed': '210000',
        'functionName': 'add_liquidity(uint256,uint256)'
    }

    # Ensure get_address_info reports the address is a contract so heuristics will check token meta
    monkeypatch.setattr(runtime, 'is_contract', lambda a, n: True)
    monkeypatch.setattr(runtime, 'get_address_info', lambda a, n: {'is_contract': True})

    # Monkeypatch get_token_meta_cached to return a token with 'curve' in the name
    # Build a token meta that contains one of the configured name patterns
    name_pattern = ''
    if isinstance(CURVE_LP_PATTERNS, dict):
        names = CURVE_LP_PATTERNS.get('names') or []
        symbols = CURVE_LP_PATTERNS.get('symbols') or []
        if names:
            name_pattern = names[0]
        elif symbols:
            name_pattern = symbols[0]

    meta_name = f"some {name_pattern} token" if name_pattern else 'Curve LP Token'
    meta_symbol = (symbols[0] if 'symbols' in locals() and symbols else 'crvLP')

    monkeypatch.setattr(runtime, 'get_token_meta_cached', lambda a, n: {'name': meta_name, 'symbol': meta_symbol})

    res = defi.analyze_defi_interaction(tx, 'arbitrum')
    assert res['is_defi'] is True
    assert res['protocol'] == 'curve'
    assert res['group'] == 'DEX Liquidity Mining'
    assert res['group'] == 'DEX Liquidity Mining'
