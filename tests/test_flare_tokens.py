import json
from unittest.mock import patch

from app import fetch_flare_token_details


SAMPLE_RESPONSE = {
    'status': '1',
    'message': 'OK',
    'result': [
        {
            'blockNumber': '100',
            'timeStamp': '1690000000',
            'hash': '0xabc',
            'nonce': '1',
            'blockHash': '0xblock',
            'from': '0x1111111111111111111111111111111111111111',
            'to': '0xB3a2f25d7956f96703c9ed3ce6ea25e4d47295d3',
            'contractAddress': '0xTokenA',
            'value': '1000000000000000000',
            'tokenName': 'Token A',
            'tokenSymbol': 'TKA',
            'tokenDecimal': '18'
        },
        {
            'blockNumber': '101',
            'timeStamp': '1690000100',
            'hash': '0xdef',
            'nonce': '2',
            'blockHash': '0xblock2',
            'from': '0xB3a2f25d7956f96703c9ed3ce6ea25e4d47295d3',
            'to': '0x2222222222222222222222222222222222222222',
            'contractAddress': '0xTokenA',
            'value': '500000000000000000',
            'tokenName': 'Token A',
            'tokenSymbol': 'TKA',
            'tokenDecimal': '18'
        },
        {
            'blockNumber': '102',
            'timeStamp': '1690000200',
            'hash': '0xghi',
            'nonce': '3',
            'blockHash': '0xblock3',
            'from': '0x3333333333333333333333333333333333333333',
            'to': '0xB3a2f25d7956f96703c9ed3ce6ea25e4d47295d3',
            'contractAddress': '0xTokenB',
            'value': '7000000',
            'tokenName': 'Token B',
            'tokenSymbol': 'TKB',
            'tokenDecimal': '6'
        }
    ]
}


@patch('app.requests.get')
def test_fetch_flare_token_details(mock_get):
    # Arrange: mock the requests.get to return our sample response
    class MockResp:
        def raise_for_status(self):
            return None

        def json(self):
            return SAMPLE_RESPONSE

    mock_get.return_value = MockResp()

    # Act
    wallet = '0xb3a2f25d7956f96703c9ed3ce6ea25e4d47295d3'
    tokens = fetch_flare_token_details(wallet)

    # Assert: Token A net = 1.0 - 0.5 = 0.5, Token B = 7.0
    mapping = {t['symbol']: t for t in tokens}

    assert 'TKA' in mapping
    assert abs(mapping['TKA']['quantity'] - 0.5) < 1e-9

    assert 'TKB' in mapping
    assert abs(mapping['TKB']['quantity'] - 7.0) < 1e-9
