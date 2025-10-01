import pytest
from decimal import Decimal
from database import parse_value_to_raw_and_scaled


def test_parse_decimal_scaled():
    raw, scaled = parse_value_to_raw_and_scaled('0.1156', 18)
    assert isinstance(raw, int)
    assert isinstance(scaled, Decimal)
    assert scaled == Decimal('0.1156')
    # raw should be scaled * 10**18
    assert raw == int((scaled * (Decimal(10) ** 18)).to_integral_value())


def test_parse_scientific_notation():
    raw, scaled = parse_value_to_raw_and_scaled('2.080533955499e-06', 18)
    assert scaled == Decimal('2.080533955499e-06')
    assert raw == int((scaled * (Decimal(10) ** 18)).to_integral_value())


def test_parse_raw_integer_string():
    raw, scaled = parse_value_to_raw_and_scaled('1234567890000000000', 18)
    assert raw == 1234567890000000000
    assert scaled == Decimal(raw) / (Decimal(10) ** 18)


def test_parse_hex_value():
    raw, scaled = parse_value_to_raw_and_scaled('0x10', 0)
    assert raw == 16
    assert scaled == Decimal(16)


def test_parse_empty_and_none():
    raw, scaled = parse_value_to_raw_and_scaled('', 18)
    assert raw == 0
    assert scaled == Decimal(0)

    raw, scaled = parse_value_to_raw_and_scaled(None, 18)
    assert raw == 0
    assert scaled == Decimal(0)


def test_parse_malformed_fallback():
    # This should not raise, fallback to Decimal or 0
    raw, scaled = parse_value_to_raw_and_scaled('not-a-number', 18)
    assert isinstance(raw, int)
    assert isinstance(scaled, Decimal)
