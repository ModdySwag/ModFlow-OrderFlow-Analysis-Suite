"""
the reference layout feature API — every analyzer behind REST, plus the replay transport.

Mounted by the desktop launcher as part of the control router family:

    /api/atlas/status                    what is available + counters
    /api/atlas/capabilities              which features this venue supports
    /api/atlas/heatmap/{symbol}          depth heatmap matrix (+ events, walls)
    /api/atlas/tape/{symbol}             big trades / sweeps / stop runs / icebergs
    /api/atlas/cvd/{symbol}              CVD + CVD Pro series and divergences
    /api/atlas/profile/{symbol}          Market Profile (TPO) snapshot
    /api/atlas/frames/{symbol}/{frame}   range | renko | reversal | tick | volume
    /api/atlas/alerts                    alert log; /alert-rules CRUD
    /api/atlas/replay/*                  load / play / pause / resume / seek / status
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException, Query

from orderflow_system.atlas import feed_extras
from orderflow_system.data.enums import as_value
from orderflow_system.atlas.hub import hub as global_hub
from orderflow_system.atlas.replay import MarketReplay
from orderflow_system.desktop import config_store

router = APIRouter(prefix="/api/atlas", tags=["atlas"])

#: replay transport is created lazily (needs the config DB path)
_replay: Optional[MarketReplay] = None


def get_hub():
    """The hub owned by the running engine (falls back to the module singleton)."""
    try:
        from orderflow_system.desktop import engine as engine_mod
        system = engine_mod.engine.system
        if system is not None and getattr(system, "_atlas_hub", None) is not None:
            return system._atlas_hub
    except Exception:
        pass
    _ensure_services(global_hub)
    return global_hub


def _ensure_services(hub) -> None:
    """Attach history + Telegram to a hub the engine has not wired (replay-only use)."""
    if getattr(hub, "history", None) is not None and getattr(hub, "notifier", None) is not None:
        return
    try:
        from orderflow_system.atlas.services import attach_services
        from orderflow_system.desktop import config_store
        cfg = config_store.load_config()
        attach_services(hub, cfg.get("atlas") or {}, cfg.get("telegram") or {},
                        notify_cfg=cfg.get("notify") or {})
    except Exception:
        pass


def get_replay() -> MarketReplay:
    global _replay
    if _replay is None:
        _replay = MarketReplay(str(config_store.db_path()), speed=10.0)
    return _replay


# ── status / capabilities ───────────────────────────────────────────────────

@router.get("/status")
async def atlas_status() -> dict[str, Any]:
    h = get_hub()
    return {"ok": True, "hub": h.status(), "replay": get_replay().status()}


@router.get("/capabilities")
async def atlas_capabilities() -> dict[str, Any]:
    """Honest feature map: what the venue gives us vs what is inferred."""
    cfg = config_store.load_config()
    atlas_cfg = cfg.get("atlas", {})
    return {
        "ok": True,
        "venue": "bybit-linear-perpetuals",
        "features": [
            {"id": "heatmap", "name": "Market-depth heatmap", "native": True,
             "source": "orderbook.200 + publicTrade", "params": ["bucket_ms", "wall_quantile", "pull_pct", "stack_pct"]},
            {"id": "big_trades", "name": "Big trades / blocks", "native": True,
             "source": "publicTrade (adaptive percentile + exchange BT flag)", "params": ["big_quantile", "block_multiple"]},
            {"id": "sweeps", "name": "Sweeps", "native": True,
             "source": "publicTrade", "params": ["sweep_levels", "sweep_max_ms", "sweep_min_size"]},
            {"id": "speed_of_tape", "name": "Speed of tape", "native": True,
             "source": "publicTrade", "params": ["z-score window"]},
            {"id": "iceberg", "name": "Iceberg tracker", "native": False,
             "source": "INFERRED from repeated equal prints at one price + L2 refills",
             "note": "true MBO (order-id) data is not published by any public Bybit feed",
             "params": ["iceberg_min_fills", "iceberg_size_tol"]},
            {"id": "stop_runs", "name": "Stop runs", "native": False,
             "source": "INFERRED from fast range expansion + volume z-score, confirmed by allLiquidation clusters",
             "params": ["stoprun_ticks", "stoprun_ms", "stoprun_vol_z"]},
            {"id": "liquidations", "name": "Liquidation feed", "native": True,
             "source": "allLiquidation", "params": []},
            {"id": "cvd", "name": "CVD / CVD Pro", "native": True,
             "source": "publicTrade", "params": ["bucket_ms", "divergence_lookback", "divergence_min_ticks"]},
            {"id": "market_profile", "name": "Market Profile (TPO)", "native": True,
             "source": "publicTrade", "params": ["bracket_minutes", "value_area_pct"]},
            {"id": "volume_profile", "name": "Volume profile + extensions", "native": True,
             "source": "candles/ticks", "params": ["value_area_pct", "days"]},
            {"id": "frames", "name": "Range / Renko / Reversal / Tick / Volume bars", "native": True,
             "source": "publicTrade", "params": ["range_ticks", "brick_ticks", "reversal_ticks", "ticks_per_bar", "volume_per_bar"]},
            {"id": "replay", "name": "Market replay", "native": True,
             "source": "local SQLite history or exchange tape", "params": ["speed", "seek"]},
            {"id": "alerts", "name": "Order-flow alert rules", "native": True,
             "source": "all detections", "params": ["per-rule thresholds + cooldown"]},
        ],
        "config": atlas_cfg,
    }


# ── analyzers ───────────────────────────────────────────────────────────────

def attach_wall_ages(snapshot: dict[str, Any], heatmap: Any) -> dict[str, Any]:
    """The walls the map draws, each with how long it has held.

    `wall_prices` answers size and freshness; `wall_durations` answers the streak the `wall_age` alert
    fires on. The map could only ever show the first, so a level that had held for ten minutes looked
    exactly like one that appeared a second ago. One shape here serves the walls table, the cursor
    readout and the age tint, and the threshold travels with it so the UI can say "held" with the
    engine's own definition rather than one of its own.
    """
    walls = heatmap.wall_prices(top=12)
    held = {r["price"]: int(r.get("held_ms") or 0) for r in heatmap.wall_durations()}
    for w in walls:
        w["held_ms"] = int(held.get(w["price"], 0))
    snapshot["walls"] = walls
    snapshot["wall_age_ms"] = int(getattr(heatmap, "wall_age_ms", 120_000))
    return snapshot


@router.get("/heatmap/{symbol}")
async def heatmap(symbol: str, columns: int = Query(default=300, le=900),
                  rows: int = Query(default=220, le=400)) -> dict[str, Any]:
    h = get_hub()
    if symbol not in h.symbols:
        return {"symbol": symbol, "buckets": [], "prices": [], "values": [], "traded": [],
                "events": [], "stats": {}, "note": "no data yet — start the engine or a replay"}
    snap = h.snapshot_heatmap(symbol, columns=columns, max_rows=rows)
    return attach_wall_ages(snap, h.ensure(symbol).heatmap)


@router.get("/tape/{symbol}")
async def tape(symbol: str) -> dict[str, Any]:
    return get_hub().snapshot_tape(symbol)


@router.get("/cvd/{symbol}")
async def cvd(symbol: str, buckets: int = Query(default=400, le=1500)) -> dict[str, Any]:
    return get_hub().snapshot_cvd(symbol, buckets=buckets)


@router.post("/cvd/{symbol}/reanchor")
async def cvd_reanchor(symbol: str) -> dict[str, Any]:
    feats = get_hub().ensure(symbol)
    feats.cvd.reanchor()
    return {"ok": True, "cvd": feats.cvd.snapshot(series_buckets=10)}


@router.get("/profile/{symbol}")
async def profile(symbol: str, levels: int = Query(default=160, le=400)) -> dict[str, Any]:
    snap = get_hub().snapshot_profile(symbol, max_levels=levels)
    # pull the repo's own session profiles for developing VA + virgin POCs
    try:
        from orderflow_system.desktop import engine as engine_mod
        system = engine_mod.engine.system
        if system is not None:
            profiles = await system.db.get_volume_profiles(symbol, days=10)
            from orderflow_system.atlas.profiles import developing_value_area, virgin_pocs
            snap["developing_value_area"] = developing_value_area(profiles)
            snap["virgin_pocs"] = virgin_pocs(profiles)
    except Exception:
        pass
    return snap


@router.get("/frames/{symbol}/{frame}")
async def frames(symbol: str, frame: str, count: int = Query(default=200, le=1000)) -> dict[str, Any]:
    if frame not in ("range", "renko", "reversal", "tick", "volume", "delta"):
        raise HTTPException(status_code=400, detail="frame must be range|renko|reversal|tick|volume|delta")
    return get_hub().snapshot_frames(symbol, frame, count=count)


@router.get("/imbalance/{symbol}")
async def imbalance(symbol: str, levels: int = Query(default=120, le=400)) -> dict[str, Any]:
    """Stacked bid/ask imbalance ladder (the reference layout rule: bid at a level vs the ask one level up)."""
    return get_hub().snapshot_imbalance(symbol, max_levels=levels)


# ── VWAP suite, trade detector and the cross-instrument scanner ─────────────

@router.get("/dots/{symbol}")
async def dots(symbol: str, max_dots: int = Query(default=600, le=1_200),
               min_size: float | None = Query(default=None, ge=0.0),
               side: str = Query(default="", pattern="^(buy|sell|)$")) -> dict[str, Any]:
    """Trade-cluster map: prints as price×time bubbles, sized by volume (atlas/dots.py)."""
    return get_hub().snapshot_dots(symbol, max_dots=max_dots, min_size=min_size, side=side)


async def _backfill_correlation(hub: Any, min_buckets: int = 3) -> int:
    """Seed the correlation series from stored 1-minute candles (falling back to the bars
    the engine holds in memory).

    A 60-second bucket needs ten minutes of live data before one pair is reportable, which
    would make the panel look broken at the start of every session. The SQLite candle store
    already keeps hours of 1-minute closes per instrument, so it seeds the tracker instead;
    live buckets keep accumulating on top and stay authoritative. Instruments already
    holding live buckets are left alone, and the DB is consulted once per instrument.
    """
    import time as _time

    try:
        from orderflow_system.desktop import engine as engine_mod
        system = getattr(engine_mod.engine, "system", None)
        if system is None:
            return 0
        now_ms = int(_time.time() * 1000)
        start_ms = now_ms - 4 * 3600 * 1000          # four hours is plenty for a 120-bucket window
        seeded = 0
        for symbol, pipeline in list(system.pipelines.items()):
            if hub.correlation.coverage(symbol) >= min_buckets:
                continue
            series: list[tuple[int, float]] = []
            db = getattr(system, "db", None)
            if db is not None:
                try:
                    rows = await db.get_candles(symbol, "1m", start_ms, now_ms)
                    series = [(int(c.timestamp_ms), float(c.close)) for c in rows if c.close]
                except Exception:                              # noqa: BLE001 — history is optional
                    series = []
            if len(series) < min_buckets:
                bars = list(getattr(pipeline.footprint_engine, "history", []) or [])
                series = [(int(bar.timestamp_ms), float(bar.close)) for bar in bars if bar.close]
            if len(series) >= min_buckets:
                hub.correlation.backfill(symbol, series)
                seeded += 1
        return seeded
    except Exception:                                          # noqa: BLE001 — never break the panel
        return 0


@router.get("/correlation")
async def correlation(top: int = Query(default=12, le=40),
                      symbols: str = Query(default="", description="comma-separated subset")) -> dict[str, Any]:
    """Rolling correlation across instruments, with per-pair shared-bucket counts."""
    wanted = [s.strip().upper() for s in str(symbols or "").split(",") if s.strip()]
    hub = get_hub()
    seeded = await _backfill_correlation(hub)
    payload = hub.snapshot_correlation(symbols=wanted or None, top=top)
    payload["backfilled"] = seeded
    payload["source"] = "stored candles + live buckets" if seeded else "live buckets"
    return payload


def _alpaca_pair(symbol: str) -> str:
    """The Alpaca symbol for an internal one (BTCUSDT → BTC/USD), from the config."""
    try:
        from orderflow_system.desktop import config_store
        cfg = config_store.load_config()
        spec = config_store.instrument_cfg(cfg, symbol) or {}
        return str(spec.get("alpaca_symbol") or "")
    except Exception:                                          # noqa: BLE001 — never break the panel
        return ""


_SNAPSHOT_CACHE: dict[str, tuple[float, Any]] = {}


def _venue_tops(symbol: str) -> list:
    """One VenueTop per venue that can answer right now: Bybit depth, Alpaca quotes.

    Alpaca's crypto snapshot needs no account, which is what makes the cross-venue panel
    work out of the box for crypto; equity quotes require a linked account and say so.
    Snapshots are cached for two seconds so a polling panel cannot burn the REST budget.
    """
    import time as _time

    from orderflow_system.atlas.crossvenue import VenueTop
    tops: list[VenueTop] = []

    # Bybit — the engine's live book (real depth)
    try:
        from orderflow_system.desktop import engine as engine_mod
        system = getattr(engine_mod.engine, "system", None)
        pipeline = system.pipelines.get(symbol) if system is not None else None
        snap = getattr(getattr(pipeline, "orderbook_tracker", None), "latest_snapshot", None) if pipeline else None
        if snap is not None and snap.bids and snap.asks:
            # The book's own timestamp is on the venue's clock (not epoch), so it is carried
            # for reference and NOT used as an age: the engine holding a non-empty book is
            # itself the freshness evidence. ts_ms=0 means "age unknown", which the row
            # reports instead of pretending.
            tops.append(VenueTop(venue="bybit", label="Bybit (perpetual)", kind="depth",
                                 bid=float(snap.bids[0].price), bid_size=float(snap.bids[0].quantity),
                                 ask=float(snap.asks[0].price), ask_size=float(snap.asks[0].quantity),
                                 ts_ms=0, extra={"book_ts": int(snap.timestamp_ms or 0)}))
        else:
            tops.append(VenueTop(venue="bybit", label="Bybit (perpetual)", kind="depth", ok=False,
                                 note="waiting for the book" if system is not None else "engine not running"))
    except Exception as exc:                                   # noqa: BLE001 — report, never raise
        tops.append(VenueTop(venue="bybit", label="Bybit (perpetual)", kind="depth", ok=False,
                             note=f"{type(exc).__name__}"))

    pair = _alpaca_pair(symbol)
    if not pair:
        tops.append(VenueTop(venue="alpaca", label="Alpaca", kind="quote", ok=False,
                             note="no Alpaca symbol mapped for this instrument"))
        return tops

    now = _time.time()
    cached = _SNAPSHOT_CACHE.get(pair)
    if cached and now - cached[0] < 2.0:
        payload = cached[1]
    else:
        try:
            from orderflow_system.data.alpaca_feed import AlpacaData
            from orderflow_system.desktop import config_store
            alp = (config_store.load_config().get("alpaca") or {})
            data = AlpacaData(key_id=str(alp.get("key_id") or ""), secret=str(alp.get("secret") or ""),
                              feed=str(alp.get("feed") or "iex"))
            payload = data.crypto_snapshot(pair) if "/" in pair else (
                data.snapshot(pair) if data.key_id else None)
        except Exception as exc:                               # noqa: BLE001
            payload = {"error": f"{type(exc).__name__}: {exc}"}
        _SNAPSHOT_CACHE[pair] = (now, payload)

    if not isinstance(payload, dict) or payload.get("error"):
        tops.append(VenueTop(venue="alpaca", label="Alpaca", kind="quote", ok=False,
                             note=(payload or {}).get("error") or "no snapshot"))
        return tops
    quote = payload.get("latestQuote") or payload.get("quote") or {}
    if not quote:
        tops.append(VenueTop(venue="alpaca", label="Alpaca", kind="quote", ok=False,
                             note="quote unavailable on this feed (equities need a linked account)"))
        return tops
    ts = _alpaca_ts_ms(quote.get("t"))
    tops.append(VenueTop(venue="alpaca", label=f"Alpaca ({pair})", kind="quote",
                         bid=float(quote.get("bp") or 0.0), bid_size=float(quote.get("bs") or 0.0),
                         ask=float(quote.get("ap") or 0.0), ask_size=float(quote.get("as") or 0.0),
                         ts_ms=ts))
    return tops


def _alpaca_ts_ms(stamp: Any) -> int:
    """RFC3339 → ms (Alpaca quotes carry nanoseconds; we keep the millisecond)."""
    try:
        text = str(stamp or "")
        if not text:
            return 0
        from datetime import datetime, timezone
        clean = text.replace("Z", "+00:00")
        if "." in clean:
            head, tail = clean.split(".", 1)
            digits = "".join(ch for ch in tail if ch.isdigit())[:6]
            rest = "".join(ch for ch in tail if not ch.isdigit() and ch not in "+-:")
            clean = f"{head}.{digits}{rest}" if digits else head
        return int(datetime.fromisoformat(clean).replace(tzinfo=timezone.utc).timestamp() * 1000)
    except Exception:                                          # noqa: BLE001
        return 0


@router.get("/crossvenue/{symbol}")
async def crossvenue(symbol: str, stale_ms: Optional[int] = Query(default=None, ge=250, le=600_000)) -> dict[str, Any]:
    """Per-venue top of book + a consolidated best (see atlas/crossvenue.py).

    Staleness is per kind unless ``stale_ms`` overrides it: a depth feed is stale after
    seconds, a quote feed after a minute.
    """
    from orderflow_system.atlas.crossvenue import build
    return {"symbol": symbol, **build(_venue_tops(symbol), stale_ms=stale_ms)}


@router.get("/vwap/{symbol}")
async def vwap(symbol: str, points: int = Query(default=240, le=600)) -> dict[str, Any]:
    """Session (rolling-window) VWAP + sigma bands, with the anchored line if set."""
    return get_hub().snapshot_vwap(symbol, points=points)


@router.post("/vwap/{symbol}/anchor")
async def vwap_anchor(symbol: str, payload: dict = Body(default={})) -> dict[str, Any]:
    """Anchor the second VWAP at a moment (defaults to now). `clear: true` removes it."""
    hub = get_hub()
    feats = hub.ensure(symbol)
    if payload.get("clear"):
        feats.vwap.clear_anchor()
        return {"ok": True, "anchor_ms": 0}
    ts = payload.get("ts_ms")
    return {"ok": True, **feats.vwap.set_anchor(int(ts) if ts else None)}


@router.get("/tradedepth/{symbol}")
async def tradedepth(symbol: str, rows: int = Query(default=30, le=200)) -> dict[str, Any]:
    """Executions that ate resting depth, and refills of those levels (inference)."""
    return get_hub().snapshot_trade_depth(symbol, max_rows=rows)


@router.get("/scanner")
async def scanner(sort: str = Query(default="score"), limit: int = Query(default=50, le=200)) -> dict[str, Any]:
    """One ranked row per streaming instrument (Market Analyzer analogue)."""
    return get_hub().snapshot_scanner(sort=sort, limit=limit)


# ── durable history ─────────────────────────────────────────────────────────

@router.get("/history/{symbol}")
async def get_history(symbol: str, kind: str = "", limit: int = Query(default=200, le=1000),
                      hours: float = 0) -> dict[str, Any]:
    """Detections written to disk — post-session review instead of live-only."""
    hist = getattr(get_hub(), "history", None)
    if hist is None:
        return {"ok": False, "error": "history unavailable", "events": [], "counts": {}, "total": 0}
    since = int((time.time() - hours * 3600) * 1000) if hours else 0
    await hist.flush()                                   # make sure the newest rows are on disk
    events = await asyncio.to_thread(hist.recent, symbol, kind, limit, since)
    counts = await asyncio.to_thread(hist.counts, symbol, since)
    return {"ok": True, "symbol": symbol, "kind": kind, "events": events,
            "counts": counts, "total": sum(counts.values()),
            "written": getattr(hist, "written", 0), "pending": getattr(hist, "pending", 0)}


@router.get("/history")
async def get_history_all(kind: str = "", limit: int = Query(default=200, le=1000),
                          hours: float = 0) -> dict[str, Any]:
    """Same as /history/{symbol} but across every instrument."""
    hist = getattr(get_hub(), "history", None)
    if hist is None:
        return {"ok": False, "error": "history unavailable", "events": [], "counts": {}, "total": 0}
    since = int((time.time() - hours * 3600) * 1000) if hours else 0
    await hist.flush()
    events = await asyncio.to_thread(hist.recent, "", kind, limit, since)
    counts = await asyncio.to_thread(hist.counts, "", since)
    return {"ok": True, "events": events, "counts": counts, "total": sum(counts.values()),
            "written": getattr(hist, "written", 0), "pending": getattr(hist, "pending", 0)}


# ── alerts ──────────────────────────────────────────────────────────────────

@router.get("/alerts")
async def alerts(limit: int = Query(default=100, le=500), symbol: str = "") -> dict[str, Any]:
    h = get_hub()
    return {"ok": True, "alerts": h.alerts.recent(limit=limit, symbol=symbol), "stats": h.alerts.stats()}


@router.post("/alerts/clear")
async def clear_alerts() -> dict[str, Any]:
    """Empty the alert log (the rules themselves are untouched)."""
    h = get_hub()
    h.alerts.history.clear()
    return {"ok": True, "stats": h.alerts.stats()}


@router.get("/alert-rules")
async def get_rules() -> dict[str, Any]:
    return {"ok": True, "rules": [r.to_dict() for r in get_hub().alerts.rules]}


@router.post("/alert-rules")
async def upsert_rule(rule: dict = Body(...)) -> dict[str, Any]:
    rules = get_hub().alerts.upsert(rule)
    _persist_rules([r for r in rules])
    return {"ok": True, "rules": rules}


@router.delete("/alert-rules/{rule_id}")
async def delete_rule(rule_id: str) -> dict[str, Any]:
    rules = get_hub().alerts.remove(rule_id)
    _persist_rules(rules)
    return {"ok": True, "rules": rules}


def _persist_rules(rules: list[dict[str, Any]]) -> None:
    try:
        cfg = config_store.load_config()
        cfg.setdefault("atlas", {})["alert_rules"] = [
            {k: v for k, v in r.items() if k not in ("fired", "last_fired_ms")} for r in rules
        ]
        config_store.save_config(cfg)
    except Exception:
        pass


# ── replay ──────────────────────────────────────────────────────────────────

@router.post("/replay/load")
async def replay_load(payload: dict = Body(default={})) -> dict[str, Any]:
    symbol = str(payload.get("symbol") or "").strip().upper()
    if not symbol:
        return {"ok": False, "error": "symbol is required"}
    rp = get_replay()
    if payload.get("source") == "exchange":
        status = await rp.load_from_exchange(symbol, limit=int(payload.get("limit", 1000)))
    else:
        status = await rp.load(symbol, payload.get("start_ms"), payload.get("end_ms"))
    return {"ok": bool(status.get("total")), "status": status,
            "error": "" if status.get("total") else "no recorded ticks/candles for that range — try source=exchange"}


@router.post("/replay/play")
async def replay_play(payload: dict = Body(default={})) -> dict[str, Any]:
    rp = get_replay()
    if not rp.status()["total"]:
        return {"ok": False, "error": "nothing loaded — call /replay/load first"}
    speed = float(payload.get("speed") or rp.status()["speed"])

    async def feed(tick) -> None:
        h = get_hub()
        h.on_tick(rp.status()["symbol"], tick)
        try:
            from orderflow_system.dashboard.websocket_manager import _serialize
            from orderflow_system.dashboard.app import ws_manager
            await ws_manager.broadcast_tick(rp.status()["symbol"], tick.price, tick.size,
                                            as_value(tick.side))
        except Exception:
            pass

    return await rp.play(feed, speed=speed)


@router.post("/replay/pause")
async def replay_pause() -> dict[str, Any]:
    return {"ok": True, "status": get_replay().pause()}


@router.post("/replay/resume")
async def replay_resume() -> dict[str, Any]:
    return {"ok": True, "status": get_replay().resume()}


@router.post("/replay/stop")
async def replay_stop() -> dict[str, Any]:
    return {"ok": True, "status": await get_replay().stop()}


@router.post("/replay/seek")
async def replay_seek(payload: dict = Body(default={})) -> dict[str, Any]:
    rp = get_replay()
    if "fraction" in payload:
        return {"ok": True, "status": rp.seek_fraction(float(payload["fraction"]))}
    return {"ok": True, "status": rp.seek(int(payload.get("index", 0)))}


@router.post("/replay/speed")
async def replay_speed(payload: dict = Body(default={})) -> dict[str, Any]:
    return {"ok": True, "status": get_replay().set_speed(float(payload.get("speed", 10)))}


@router.get("/replay/status")
async def replay_status() -> dict[str, Any]:
    return {"ok": True, "status": get_replay().status()}


# ── seeds (useful without a live feed) ──────────────────────────────────────

@router.get("/trades/recent/{symbol}")
async def recent_trades(symbol: str, limit: int = Query(default=200, le=1000)) -> dict[str, Any]:
    try:
        rows = await asyncio.to_thread(feed_extras.fetch_recent_trades, symbol, limit)
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "trades": []}
    return {"ok": True, "trades": rows, "count": len(rows)}


@router.get("/klines/{symbol}")
async def klines(symbol: str, interval: str = "1", limit: int = Query(default=200, le=1000)) -> dict[str, Any]:
    try:
        rows = await asyncio.to_thread(feed_extras.fetch_klines, symbol, interval, limit)
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "bars": []}
    return {"ok": True, "bars": rows, "count": len(rows)}

# ── exports + webhook (the reference layout: CSV export, alert forwarding) ──────────────────

@router.get("/export/alerts.csv")
async def export_alerts_csv(limit: int = Query(default=500, le=5000)) -> Any:
    """CSV of the alert log — the reference layout 'CSV export' equivalent for detections."""
    from fastapi.responses import PlainTextResponse

    csv_text = get_hub().alerts.to_csv(limit=limit)
    return PlainTextResponse(csv_text, media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=atlas_alerts.csv"})


@router.get("/export/tape/{symbol}.csv")
async def export_tape_csv(symbol: str, limit: int = Query(default=500, le=5000)) -> Any:
    """CSV of the tape detections (big trades, sweeps, stop runs, icebergs)."""
    from fastapi.responses import PlainTextResponse

    return PlainTextResponse(get_hub().tape_csv(symbol, limit=limit), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename=tape_{symbol}.csv"})


@router.get("/export/heatmap/{symbol}.csv")
async def export_heatmap_csv(symbol: str, columns: int = Query(default=240, le=900),
                             rows: int = Query(default=200, le=400)) -> Any:
    """CSV of the depth-heatmap matrix (price rows x time buckets)."""
    from fastapi.responses import PlainTextResponse

    return PlainTextResponse(get_hub().heatmap_csv(symbol, columns=columns, rows=rows),
                             media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename=heatmap_{symbol}.csv"})


@router.get("/webhook")
async def webhook_state() -> dict[str, Any]:
    engine = get_hub().alerts
    return {"ok": True, "url": engine.webhook_url, "stats": dict(engine.webhook_stats),
            "rules_forwarding": [r.id for r in engine.rules if "webhook" in (r.channels or [])]}


@router.post("/webhook")
async def webhook_set(body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """Set (or clear) the alert webhook URL."""
    url = str(body.get("url") or "").strip()
    if url and not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(status_code=400, detail="url must be http(s)")
    alerts = get_hub().alerts
    alerts.webhook_url = url
    return {"ok": True, "url": alerts.webhook_url}


@router.post("/webhook/test")
async def webhook_test(body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """Send a synthetic alert to the configured URL and report the outcome."""
    alerts = get_hub().alerts
    url = str(body.get("url") or alerts.webhook_url or "").strip()
    if not url:
        return {"ok": False, "error": "no webhook url configured"}
    alerts.webhook_url = url
    from orderflow_system.atlas.alerts import Alert

    probe = Alert(rule_id="test", name="webhook test", kind="big_trade", symbol=str(body.get("symbol") or "TEST"),
                  ts_ms=int(time.time() * 1000), message="webhook connectivity test",
                  severity="info", data={"test": True}, channels=["webhook"])
    before_sent = alerts.webhook_stats["sent"]
    sent = await alerts.dispatch_webhooks([probe])
    return {"ok": sent > 0, "sent": sent, "url": url,
            "stats": dict(alerts.webhook_stats), "sent_delta": alerts.webhook_stats["sent"] - before_sent}


@router.post("/cvd/{symbol}/pro")
async def cvd_pro_filter(symbol: str, body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """the reference layout 'CVD Pro' (Market Power): only count prints inside a size band."""
    feats = get_hub().ensure(symbol)
    out: dict[str, Any] = {"ok": True, "symbol": symbol,
                           "filter": feats.cvd.set_pro_filter(float(body.get("min_size") or 0.0),
                                                              float(body.get("max_size") or 0.0))}
    if "bands" in body:
        out["bands"] = feats.cvd.set_pro_bands(body.get("bands") or [])
    return out


# ══════════════════════════════════════════════════════════════
# Participants' intent (order-book reading, no keys)
# ══════════════════════════════════════════════════════════════

@router.get("/intent/{symbol}")
async def participants_intent(symbol: str) -> dict[str, Any]:
    """What the book says about each side's intentions right now.

    DOM pressure (weighted liquidity per side, normalised against its own sliding
    maximum), aggression-vs-displacement absorption, depth adds/removes, tape
    quality, pulled size and trapped side — plus one plain-language verdict line.
    """
    hub = get_hub()
    if symbol not in hub.symbols:
        return {"ok": False, "symbol": symbol,
                "note": "no data yet — start the engine or run a replay"}
    snap = hub.ensure(symbol).intent.snapshot()
    snap["ok"] = True
    return snap

# ══════════════════════════════════════════════════════════════
# Free market context (no keys, no accounts) + notifier channels
# ══════════════════════════════════════════════════════════════

def _context_settings() -> dict[str, Any]:
    try:
        return config_store.load_config().get("context") or {}
    except Exception:                                  # pragma: no cover - never break the view
        return {}


@router.get("/context/{symbol}")
async def market_context(
    symbol: str,
    news_url: str = Query(default=""),
    news_limit: int = Query(default=0, ge=0, le=30),
) -> dict[str, Any]:
    """Funding / open interest / long-short ratio, Fear & Greed and headlines.

    All three sources are public and keyless; each section degrades to
    ``{"ok": false}`` on its own so one dead feed never blanks the card.
    """
    from orderflow_system.atlas.context import shared_context

    cfg = _context_settings()
    if not bool(cfg.get("enabled", True)):
        return {"ok": False, "error": "market context is disabled in settings", "symbol": symbol.upper()}

    include = [name for name, key in (("positioning", "positioning"), ("fear_greed", "fear_greed"),
                                      ("news", "news")) if bool(cfg.get(key, True))]
    ctx = shared_context()
    out = await ctx.snapshot(
        symbol,
        include=include,
        news_limit=int(news_limit or cfg.get("news_limit") or 8),
        feed_url=str(news_url or cfg.get("news_url") or ""),
    )
    out["stats"] = ctx.stats()
    return out


@router.get("/notify/status")
async def notify_status() -> dict[str, Any]:
    """Which alert channels are configured and how they are doing."""
    notifier = getattr(get_hub(), "notifier", None)
    if notifier is None:
        return {"ok": True, "channels": [], "stats": {}, "hint": "no notifier attached"}
    stats = notifier.stats() if hasattr(notifier, "stats") else {}
    return {"ok": True, "channels": sorted(getattr(notifier, "channels", {}) or {}), "stats": stats}


@router.post("/notify/test")
async def notify_test(body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """Force a test alert through one channel — the wizard's Test buttons.

    Accepts overrides so the user can test BEFORE saving: any of the ntfy /
    email / telegram fields passed in the body are applied to a throwaway
    notifier for this call only.
    """
    from orderflow_system.atlas.notify import build_notifiers

    channel = str(body.get("channel") or "ntfy").lower()
    cfg = config_store.load_config()
    telegram_cfg = dict(cfg.get("telegram") or {})
    notify_cfg = {k: dict(v) if isinstance(v, dict) else v for k, v in (cfg.get("notify") or {}).items()}

    # one-shot overrides from the form
    for key in ("topic", "server"):
        if body.get(key):
            notify_cfg.setdefault("ntfy", {})[key] = str(body[key])
    for key in ("host", "username", "password", "to", "from"):
        if body.get(key):
            notify_cfg.setdefault("email", {})[key] = str(body[key])
    if body.get("port"):
        notify_cfg.setdefault("email", {})["port"] = int(body["port"])
    if body.get("use_tls") is not None:
        notify_cfg.setdefault("email", {})["use_tls"] = bool(body["use_tls"])
    if body.get("bot_token"):
        telegram_cfg["bot_token"] = str(body["bot_token"])
    if body.get("chat_id"):
        telegram_cfg["chat_id"] = str(body["chat_id"])
    if body.get("bot_token") or body.get("chat_id"):
        telegram_cfg["enabled"] = True           # an explicit test outranks the saved on/off flag
    if body.get("topic") or body.get("server"):
        notify_cfg.setdefault("ntfy", {})["enabled"] = True
    if body.get("host"):
        notify_cfg.setdefault("email", {})["enabled"] = True

    notifier = build_notifiers(telegram_cfg=telegram_cfg, notify_cfg=notify_cfg)
    if channel not in notifier.channels:
        return {"ok": False, "channel": channel,
                "error": "channel not configured — fill in its fields first",
                "configured": sorted(notifier.channels)}
    started = await notifier.start()

    probe = {
        "rule_id": "test", "name": f"{channel} test", "kind": "big_trade",
        "symbol": str(body.get("symbol") or "TEST").upper(), "severity": "info",
        "ts_ms": int(time.time() * 1000),
        "message": "Connectivity test from ModFlow OrderFlow Analysis Suite — if you can read this, alerts will reach you.",
        "channels": [channel],
    }
    result = await notifier.send_one(channel, probe)
    result["started"] = started
    result["configured"] = sorted(notifier.channels)
    return result
