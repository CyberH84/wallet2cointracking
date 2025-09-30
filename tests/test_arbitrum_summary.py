from unittest.mock import patch
from app import get_network_summary


# Create fake transactions list of length 147
FAKE_TXS = [{'hash': f'0x{i:064x}', 'from': '0xabc', 'to': '0xdef'} for i in range(147)]

SAMPLE_TOKEN_RESPONSE = {
    'status': '1',
    'message': 'OK',
    'result': [
        {
            'blockNumber': '1',
            'timeStamp': '1690000000',
            'hash': '0xaaa',
            'from': '0x1111',
            'to': '0xB3a2f25d7956f96703c9ed3ce6ea25e4d47295d3',
            'contractAddress': '0xTokenWETH',
            'value': '4000000000000000000',
            'tokenName': 'Aave Arbitrum WETH',
            'tokenSymbol': 'AARBWETH',
            'tokenDecimal': '18'
        },
        {
            'blockNumber': '2',
            'timeStamp': '1690000100',
            'hash': '0xbbb',
            'from': '0x2222',
            'to': '0xB3a2f25d7956f96703c9ed3ce6ea25e4d47295d3',
            'contractAddress': '0xTokenWBTC',
            'value': '599800000',
            'tokenName': 'Aave Arbitrum WBTC',
            'tokenSymbol': 'AARBWBTC',
            'tokenDecimal': '8'
        },
        {
            'blockNumber': '3',
            'timeStamp': '1690000200',
            'hash': '0xccc',
            'from': '0x3333',
            'to': '0xB3a2f25d7956f96703c9ed3ce6ea25e4d47295d3',
            'contractAddress': '0xTokenETH',
            'value': '352',
            'tokenName': 'Ether',
            'tokenSymbol': 'ETH',
            'tokenDecimal': '3'
        }
    ]
}


@patch('app.fetch_transactions_from_explorer')
@patch('app.requests.get')
def test_arbitrum_network_summary(mock_get, mock_fetch_txs):
    # Mock tx fetcher to return 147 transactions
    mock_fetch_txs.return_value = FAKE_TXS

    class MockResp:
        def raise_for_status(self):
            return None

        def json(self):
            return SAMPLE_TOKEN_RESPONSE

    mock_get.return_value = MockResp()

    wallet = '0xb3a2f25d7956f96703c9ed3ce6ea25e4d47295d3'
    summary = get_network_summary(wallet, 'arbitrum')

    assert summary['transaction_count'] == 147
    assert summary['token_count'] == 3
    symbols = {t['symbol'] for t in summary['tokens']}
    assert 'AARBWETH' in symbols
    assert 'AARBWBTC' in symbols
    assert 'ETH' in symbols
