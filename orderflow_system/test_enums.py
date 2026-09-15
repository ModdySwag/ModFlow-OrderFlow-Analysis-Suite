"""Tests for the enum/string boundary helper (audit P5, plan T3).

The helper replaced ~16 ``hasattr(x, 'value')`` clusters; these tests pin the
semantics that made those replacements behaviour-preserving.
"""

from orderflow_system.data.enums import as_name, as_value
from orderflow_system.data.models import Side, SignalType, TradePhase


def test_enum_returns_value():
    assert as_value(Side.BUY) == "buy"
    assert as_value(Side.SELL) == "sell"
    assert as_value(SignalType.ABSORPTION) == "absorption"
    assert as_value(TradePhase.POSITION_OPEN) == "position_open"


def test_plain_string_passes_through():
    assert as_value("buy") == "buy"
    assert as_value("neutral") == "neutral"


def test_none_uses_default():
    assert as_value(None) is None
    assert as_value(None, "neutral") == "neutral"


def test_other_types_stringified():
    assert as_value(3) == "3"
    assert as_value(2.5) == "2.5"


def test_object_with_value_attribute():
    class Carrier:
        value = "carried"

    assert as_value(Carrier()) == "carried"


def test_as_name_prefers_name():
    assert as_name(Side.BUY) == "BUY"
    assert as_name("buy") == "buy"
