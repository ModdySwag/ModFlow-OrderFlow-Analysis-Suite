"""The history routes: starting a backfill, watching it, and reading our own ticks back.

The routes are thin on purpose — the rules live in `data/backfill.py` (the window-replace rule, the
ceiling, the cache) and these tests pin the *interface*: who may start a pass, what it refuses, what
the read endpoint's caps are, and that a JSON row looks exactly like a live tick.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from pathlib import Path

from orderflow_system.data.database import Database
from orderflow_system.data.models import Side, Tick
from orderflow_system.desktop import api, config_store

DAY = dt.date(2026, 9, 12)


def _stub_config(monkeypatch, tmp_path: Path, *, symbols=("BTCUSDT",)) -> Path:
    """Point the store at a scratch dir with one or two instruments configured."""
    db_file = tmp_path / "orderflow_data.db"
    monkeypatch.setattr(config_store, "db_path", lambda: db_file)
    monkeypatch.setattr(config_store, "backfill_cache_dir", lambda: tmp_path / "cache")
    cfg = {"instruments": [{"symbol": s, "enabled": True} for s in symbols], "data_source": "binance"}
    monkeypatch.setattr(config_store, "load_config", lambda: cfg)
    return db_file


def test_the_status_is_idle_before_anything_runs(monkeypatch, tmp_path):
    _stub_config(monkeypatch, tmp_path)
    api._backfill_job.clear()
    api._backfill_job.update({"state": "idle"})
    assert asyncio.run(api.backfill_status())["job"]["state"] == "idle"


def test_a_backfill_may_only_name_a_configured_instrument(monkeypatch, tmp_path):
    _stub_config(monkeypatch, tmp_path)
    api._backfill_job.clear()
    api._backfill_job.update({"state": "idle"})
    out = asyncio.run(api.backfill_start({"symbol": "DOGEUSDT", "from": "2026-09-12"}))
    assert out["ok"] is False and "configured instruments" in out["error"]
    assert asyncio.run(api.backfill_start({"symbol": "", "from": "2026-09-12"}))["ok"] is False


def test_a_backfill_refuses_the_future_and_the_ceiling(monkeypatch, tmp_path):
    _stub_config(monkeypatch, tmp_path)
    api._backfill_job.clear()
    api._backfill_job.update({"state": "idle"})
    today = dt.datetime.now(dt.timezone.utc).date()
    out = asyncio.run(api.backfill_start({"symbol": "BTCUSDT", "from": today.isoformat()}))
    assert out["ok"] is False and "does not publish" in out["error"]

    out = asyncio.run(api.backfill_start({
        "symbol": "BTCUSDT", "days": [(today - dt.timedelta(days=n + 1)).isoformat() for n in range(9)]}))
    assert out["ok"] is False and "at most" in out["error"]

    out = asyncio.run(api.backfill_start({"symbol": "BTCUSDT", "from": "2026-09-12", "to": "2026-09-01"}))
    assert out["ok"] is False and "before" in out["error"]

    out = asyncio.run(api.backfill_start({"symbol": "BTCUSDT", "from": "12/09/2026"}))
    assert out["ok"] is False and "YYYY-MM-DD" in out["error"]


def test_a_second_pass_is_refused_while_one_is_running(monkeypatch, tmp_path):
    _stub_config(monkeypatch, tmp_path)
    api._backfill_job.clear()
    api._backfill_job.update({"state": "running", "symbol": "BTCUSDT"})
    out = asyncio.run(api.backfill_start({"symbol": "BTCUSDT", "from": "2026-09-12"}))
    assert out["ok"] is False and "already running" in out["error"]
    assert out["job"]["symbol"] == "BTCUSDT"
    api._backfill_job.clear()
    api._backfill_job.update({"state": "idle"})


def test_a_single_day_starts_a_pass_and_reports_the_job(monkeypatch, tmp_path):
    _stub_config(monkeypatch, tmp_path)
    api._backfill_job.clear()
    api._backfill_job.update({"state": "idle"})
    started = {"called": False}

    async def fake_run(symbol, days):
        started["called"] = True
        started["symbol"] = symbol
        started["days"] = [d.isoformat() for d in days]

    monkeypatch.setattr(api, "_run_backfill", fake_run)

    async def main():
        out = await api.backfill_start({"symbol": "btcusdt", "from": "2026-09-12"})
        await asyncio.sleep(0)                    # let the created task run
        return out

    out = asyncio.run(main())
    assert out["ok"] is True
    assert out["job"]["state"] == "running" and out["job"]["days"] == [DAY.isoformat()]
    assert started["called"] is True and started["symbol"] == "BTCUSDT"
    assert started["days"] == [DAY.isoformat()]
    api._backfill_job.clear()
    api._backfill_job.update({"state": "idle"})


def test_a_range_starts_one_job_with_every_day(monkeypatch, tmp_path):
    _stub_config(monkeypatch, tmp_path)
    api._backfill_job.clear()
    api._backfill_job.update({"state": "idle"})
    seen = {}

    async def fake_run(symbol, days):
        seen["days"] = [d.isoformat() for d in days]

    monkeypatch.setattr(api, "_run_backfill", fake_run)

    async def main():
        out = await api.backfill_start({"symbol": "BTCUSDT", "from": "2026-09-10", "to": "2026-09-12"})
        await asyncio.sleep(0)
        return out

    out = asyncio.run(main())
    assert out["ok"] is True
    assert seen["days"] == ["2026-09-10", "2026-09-11", "2026-09-12"]
    api._backfill_job.clear()
    api._backfill_job.update({"state": "idle"})


def test_a_failing_pass_is_recorded_not_swallowed(monkeypatch, tmp_path):
    """The job must end up in `failed` with the reason — a silent no-op would look like success."""
    _stub_config(monkeypatch, tmp_path)
    api._backfill_job.clear()
    api._backfill_job.update({"state": "idle"})

    from orderflow_system.data import backfill as bf

    async def boom(*args, **kwargs):
        raise RuntimeError("the venue said no")

    monkeypatch.setattr(bf, "backfill_range", boom)

    async def main():
        await api._run_backfill("BTCUSDT", [DAY])
        return dict(api._backfill_job)

    job = asyncio.run(main())
    assert job["state"] == "failed" and "the venue said no" in job["error"]
    assert "finished_at" in job
    api._backfill_job.clear()
    api._backfill_job.update({"state": "idle"})


# ── the read endpoint ───────────────────────────────────────────────────────

def _seed(db_file: Path, symbol: str = "BTCUSDT") -> None:
    async def main():
        db = Database(str(db_file))
        await db.connect()
        base = 1_789_000_000_000
        await db.insert_ticks_batch(symbol, [
            Tick(timestamp_ms=base + 1_000, price=100.0, size=2.0, side=Side.BUY, trade_id="1"),
            Tick(timestamp_ms=base + 2_000, price=101.0, size=3.0, side=Side.SELL, trade_id="2"),
        ])
        await db.close()

    asyncio.run(main())


def test_the_read_endpoint_returns_the_live_tick_shape(monkeypatch, tmp_path):
    db_file = _stub_config(monkeypatch, tmp_path)
    _seed(db_file)
    base = 1_789_000_000_000
    out = asyncio.run(api.trades(symbol="btcusdt", since=base, until=base + 60_000, limit=100))
    assert out["ok"] is True and out["symbol"] == "BTCUSDT"
    assert out["count"] == 2 and out["total"] == 2 and out["truncated"] is False
    assert set(out["ticks"][0]) == {"ts", "price", "size", "side", "trade_id"}
    assert out["ticks"][0]["side"] == "buy" and out["ticks"][1]["ts"] > out["ticks"][0]["ts"]


def test_the_read_endpoint_caps_the_page_and_says_so(monkeypatch, tmp_path):
    db_file = _stub_config(monkeypatch, tmp_path)
    _seed(db_file)
    base = 1_789_000_000_000
    out = asyncio.run(api.trades(symbol="BTCUSDT", since=base, until=base + 60_000, limit=1))
    assert out["count"] == 1 and out["total"] == 2 and out["truncated"] is True
    assert out["ticks"][0]["trade_id"] == "2", "the page must keep the newest rows"


def test_the_read_endpoint_refuses_unknown_symbols_and_wide_windows(monkeypatch, tmp_path):
    db_file = _stub_config(monkeypatch, tmp_path)
    _seed(db_file)
    out = asyncio.run(api.trades(symbol="NOPE", since=0, until=1))
    assert out["ok"] is False and "configured instruments" in out["error"]

    now = int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
    out = asyncio.run(api.trades(symbol="BTCUSDT", since=now - 90_000_000, until=now))
    assert out["ok"] is False and "24 h" in out["error"]

    out = asyncio.run(api.trades(symbol="BTCUSDT", since=now, until=now - 5))
    assert out["ok"] is False and "after" in out["error"]


def test_the_read_endpoint_defaults_to_the_last_hour(monkeypatch, tmp_path):
    db_file = _stub_config(monkeypatch, tmp_path)
    _seed(db_file)
    # called the way the route is: no window given at all means "the last hour"
    out = asyncio.run(api.trades(symbol="BTCUSDT", since=None, until=None, limit=5_000))
    assert out["ok"] is True
    assert out["to"] - out["from"] == 3_600_000
    assert out["count"] == 0, "the seeded ticks are months old"
