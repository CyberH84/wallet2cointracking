import uuid
import time
from decimal import Decimal

import pytest

from database import db_manager, db_config, parse_value_to_raw_and_scaled
from sqlalchemy import text


def test_store_transactions_idempotent_and_value_parsing():
    """Integration test: store a synthetic transaction with a token transfer
    whose value is provided as a decimal string. Assert that the DB stores
    the correct raw and scaled values and that repeated upserts do not
    create duplicate token_transfer rows (idempotence).
    """

    tx_hash = f"testtx_{uuid.uuid4().hex}"
    now_ts = int(time.time())

    tx = {
        'chain_id': 42161,
        'hash': tx_hash,
        'blockNumber': 12345678,
        'timeStamp': now_ts,
        # use valid 42-char hex addresses (0x + 40 hex chars)
        'from': '0x' + 'a' * 40,
        'to': '0x' + 'b' * 40,
        'value': '0.5',
        'gasUsed': '21000',
        'gasPrice': '1000000000',
        'txreceipt_status': '1',
        'input': '',
        'logs': [],
        'protocol': None,
        'action_type': None,
        'token_transfers': [
            {
                'log_index': 0,
                'contractAddress': '0x' + 'c' * 40,
                'from': '0x' + 'd' * 40,
                'to': '0x' + 'e' * 40,
                'value': '0.1156',
                'tokenDecimal': '18',
                'tokenSymbol': 'TKN',
                'tokenName': 'TestToken'
            }
        ]
    }

    engine = db_config.initialize_engine()

    # Ensure we clean up after ourselves even if assertions fail
    try:
        # First upsert
        ok = db_manager.store_transactions([tx])
        assert ok is True

        # Verify token_transfer was stored with correct raw/scaled values
        expected_raw, expected_scaled = parse_value_to_raw_and_scaled('0.1156', 18)

        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT value_raw, value_scaled FROM token_transfers WHERE tx_hash = :h AND log_index = 0"),
                {'h': tx_hash}
            ).fetchone()

            assert row is not None, "token_transfer row was not found"

            stored_raw = int(row[0]) if row[0] is not None else None
            stored_scaled = Decimal(row[1]) if row[1] is not None else None

            assert stored_raw == expected_raw
            # Numeric column should preserve the Decimal string value
            assert stored_scaled == expected_scaled

        # Run store_transactions again with the same payload to test idempotence
        ok2 = db_manager.store_transactions([tx])
        assert ok2 is True

        with engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(1) FROM token_transfers WHERE tx_hash = :h"),
                {'h': tx_hash}
            ).fetchone()[0]

            assert count == 1, "Upsert created duplicate token_transfer rows"

    finally:
        # Cleanup inserted rows
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM token_transfers WHERE tx_hash = :h"), {'h': tx_hash})
            conn.execute(text("DELETE FROM ethereum_transactions WHERE tx_hash = :h"), {'h': tx_hash})
