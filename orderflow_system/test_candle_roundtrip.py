"""The DB candle round trip must keep the footprint (v0.1b audit Tier 1.5 pin).

`insert_candle` always serialised the per-level bid/ask into `footprint_json`, but
`get_candles` never read that column back. Anything loading candles from the DB — the
hourly volume-profile rebuild first of all — therefore ran with empty footprints and
silently fell back to "distribute the candle's volume evenly across its OHLC range", a
cruder profile than the live path on a system that claims tick-level microstructure.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from orderflow_system.data.database import Database
from orderflow_system.data.models import Candle, FootprintLevel, Side, Tick

TS = 1_700_000_000_000


def _candle_with_footprint() -> Candle:
    levels = {
        18500.0: FootprintLevel(price=18500.0, bid_volume=12.0, ask_volume=31.5),
        18501.0: FootprintLevel(price=18501.0, bid_volume=7.25, ask_volume=0.0),
    }
    return Candle(
        timestamp_ms=TS, open=18500.0, high=18502.0, low=18499.0, close=18501.5,
        volume=50.75, buy_volume=31.5, sell_volume=19.25, tick_count=9, footprint=levels,
    )


def test_footprint_survives_the_db_round_trip():
    asyncio.run(_scenario())


async def _scenario():
    with tempfile.TemporaryDirectory() as td:
        db = Database(str(Path(td) / "t.db"))
        await db.connect()

        candle = _candle_with_footprint()
        await db.insert_candle("NAS100USDT", "1m", candle)

        # A candle without a footprint must stay empty, not become something invented.
        bare = Candle(timestamp_ms=TS + 60_000, open=1.0, high=1.0, low=1.0, close=1.0, volume=1.0)
        await db.insert_candle("NAS100USDT", "1m", bare)

        rows = await db.get_candles("NAS100USDT", "1m", TS - 1, TS + 120_000)
        assert len(rows) == 2

        got = rows[0]
        assert set(got.footprint) == set(candle.footprint), got.footprint
        for price, lv in candle.footprint.items():
            assert got.footprint[price] == lv, price
        assert got.footprint[18501.0].ask_volume == 0.0        # exact-zero sides survive

        # The rebuild path consumes it: the profile must reflect the real per-level
        # volumes, not the even-distribution fallback (which would invent 18499/18502).
        from orderflow_system.analytics.volume_profile import VolumeProfileEngine
        from orderflow_system.config.settings import VolumeProfileConfig

        engine = VolumeProfileEngine(VolumeProfileConfig(tick_size=1.0))
        vp = engine.compute_from_candles(rows, session_date="t")
        assert 18499.0 not in vp.volume_at_price, "the empty-range fallback leaked in"
        assert vp.volume_at_price.get(18500.0, 0.0) == 43.5     # 12.0 + 31.5

        assert rows[1].footprint == {}

        await db.close()


def test_legacy_and_malformed_footprint_cells_read_as_empty():
    """Rows written earlier (or with no footprint) carry '{}' or NULL — not an error."""
    assert Database._decode_footprint(None) == {}
    assert Database._decode_footprint("") == {}
    assert Database._decode_footprint("{}") == {}
    assert Database._decode_footprint("not-json") == {}
    decoded = Database._decode_footprint('{"18500.0": {"bid": 1.5, "ask": 2.5}}')
    assert decoded == {18500.0: FootprintLevel(price=18500.0, bid_volume=1.5, ask_volume=2.5)}


def test_ticks_still_round_trip_unchanged():
    """Guard the neighbouring path this change sat next to (insert_ticks_batch)."""

    async def scenario():
        with tempfile.TemporaryDirectory() as td:
            db = Database(str(Path(td) / "t.db"))
            await db.connect()
            await db.insert_ticks_batch("BTCUSDT", [
                Tick(timestamp_ms=TS, price=98000.0, size=1.5, side=Side.BUY),
            ])
            snap = await db.storage_snapshot()
            assert snap["tables"]["ticks"] == 1
            await db.close()

    asyncio.run(scenario())
