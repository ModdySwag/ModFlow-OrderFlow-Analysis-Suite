"""Pins for the MT5 feed's DOM parsing.

Written after the real-terminal verification (2026-09-17) caught the feed reading
``volume_real`` off BookInfo objects that have never had it: a live MetaQuotes-Demo
terminal, package 5.0.6180, exposed ``BookInfo(type, price, volume, volume_dbl)`` and
every DOM poll raised — killing the book silently behind one ERROR per cycle. The
helper must read whatever the installed package actually exposes, and fall back
cleanly for the older documented shapes.
"""

from __future__ import annotations

import types
from collections import namedtuple

import pytest

from orderflow_system.data.mt5_feed import _book_quantity


def test_book_quantity_reads_volume_dbl() -> None:
    e = types.SimpleNamespace(type=1, price=1.15, volume=2_000_000, volume_dbl=2_000_000.0)
    assert _book_quantity(e) == 2_000_000.0


def test_book_quantity_reads_legacy_volume_real() -> None:
    old_book_info = namedtuple("MqlBookInfo", "type price volume volume_real")
    e = old_book_info(2, 1.15, 0, 1500.0)
    assert _book_quantity(e) == 1500.0


def test_book_quantity_falls_back_to_integer_volume() -> None:
    e = types.SimpleNamespace(type=2, price=1.15, volume=75)
    assert _book_quantity(e) == 75.0


def test_book_quantity_zero_when_nothing_usable() -> None:
    e = types.SimpleNamespace(type=1, price=1.15, volume=0)
    assert _book_quantity(e) == 0.0


def test_book_quantity_reads_the_installed_packages_book_info() -> None:
    """The shape pin: whatever MetaTrader5 the environment ships must parse to its volume."""
    mt5 = pytest.importorskip("MetaTrader5")
    try:
        # BookInfo is a structseq: construct from the value sequence, in field order
        # (type, price, volume, volume_dbl) — measured on package 5.0.6180.
        entry = mt5.BookInfo((1, 1.23456, 42, 42.5))
    except TypeError:  # pragma: no cover - other package builds
        pytest.skip("this BookInfo build is not constructible directly")
    assert _book_quantity(entry) in (42.0, 42.5)  # int lots or the float twin
