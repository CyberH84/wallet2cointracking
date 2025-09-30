import json
from unittest.mock import patch

import app


@patch('app.requests.get')
def test_get_token_price_coingecko_simple(mock_get):
    # Simulate CoinGecko simple token_price response
    contract = '0xTokenX'
    network = 'arbitrum'
    addr_lower = contract.lower()

    class MockResp:
        def raise_for_status(self):
            return None

        def json(self):
            return { addr_lower: { 'usd': 2.5 } }

    mock_get.return_value = MockResp()

    price = app.get_token_price_coingecko(contract, network)
    assert isinstance(price, float)
    assert price == 2.5

