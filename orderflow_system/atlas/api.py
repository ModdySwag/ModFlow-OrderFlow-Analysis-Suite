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
    /api/atlas/market-read/{symbol}      the deterministic tape/profile/radar read of one instrument
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Body, HTTPException, Query

from orderflow_system.atlas import feed_extras
from orderflow_system.data.enums import as_value
from orderflow_system.atlas.hub import hub as global_hub
from orderflow_system.atlas.replay import MarketReplay
from orderflow_system.desktop import config_store, orders as orders_mod

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


@router.get("/heatmap/{symbol}/bin")
async def heatmap_bin(symbol: str, columns: int = Query(default=300, le=900),
                      rows: int = Query(default=220, le=400)):
    """The same snapshot as /heatmap/{symbol}, packed as typed sections (§56) — the engine view's
    client reads floats without parsing 48 k JSON objects."""
    from fastapi import Response

    from orderflow_system.atlas.wire import pack_heatmap_bin

    h = get_hub()
    if symbol not in h.symbols:
        snap = {"symbol": symbol, "buckets": [], "prices": [], "values": [], "traded": [],
                "events": [], "note": "no data yet — start the engine or a replay"}
    else:
        snap = attach_wall_ages(h.snapshot_heatmap(symbol, columns=columns, max_rows=rows),
                                h.ensure(symbol).heatmap)
    return Response(content=pack_heatmap_bin(snap), media_type="application/octet-stream",
                    headers={"Cache-Control": "no-store"})


@router.get("/heatmap/{symbol}")
async def heatmap(symbol: str, columns: int = Query(default=300, le=900),
                  rows: int = Query(default=220, le=400),
                  until: int = Query(default=0, ge=0)) -> dict[str, Any]:
    # §121: `until` (epoch ms, 0 = live edge) is the time anchor the UI's pan and
    # zoom-at-cursor ride; the slice still spans `columns` buckets.
    h = get_hub()
    if symbol not in h.symbols:
        return {"symbol": symbol, "buckets": [], "prices": [], "values": [], "traded": [],
                "events": [], "stats": {}, "note": "no data yet — start the engine or a replay"}
    snap = h.snapshot_heatmap(symbol, columns=columns, max_rows=rows,
                              until_ms=(until or None))
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
            if profiles:
                from orderflow_system.analytics.volume_profile import shape_story
                latest = profiles[-1]
                # SEC-14: the stored profile's own fabrication count rides to the screen —
                # a shape/POC read partly built from even-smeared candles says so.
                snap["derived_candles"] = int(getattr(latest, "derived_candles", 0) or 0)
                words = shape_story(getattr(latest, "shape", "") or "")
                snap["shape"] = {"value": getattr(latest, "shape", "") or "unknown",
                                 "label": words["label"], "story": words["story"],
                                 "session": getattr(latest, "session_date", "")}
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
#: G-07: a small LRU bound on top of the 2 s read TTL — the map was write-only by access, so a
#: venue walk (200 configured symbols) kept every pair's payload resident.
_SNAPSHOT_CACHE_MAX = 128


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
        if len(_SNAPSHOT_CACHE) > _SNAPSHOT_CACHE_MAX:
            for stale in [k for k, (at, _v) in _SNAPSHOT_CACHE.items() if now - at >= 2.0]:
                _SNAPSHOT_CACHE.pop(stale, None)
        while len(_SNAPSHOT_CACHE) > _SNAPSHOT_CACHE_MAX:
            oldest = min(_SNAPSHOT_CACHE.items(), key=lambda item: item[1][0])[0]
            _SNAPSHOT_CACHE.pop(oldest, None)

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


@router.get("/radar")
async def radar_all() -> dict[str, Any]:
    """The level radar across every streaming instrument (fold-in plan §4 / G1)."""
    return get_hub().snapshot_radar()


@router.get("/radar/{symbol}")
async def radar_symbol(symbol: str) -> dict[str, Any]:
    """One instrument's tracked levels and their lifecycle states."""
    return get_hub().snapshot_radar(symbol)


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


# ── notifications (T14/B7): the inbox reading the engine's own firings ──

@router.get("/notifications")
async def notifications(limit: int = Query(default=200, le=500)) -> dict[str, Any]:
    """The inbox: the engine's recent firings + the reading state the config keeps.

    Nothing new is recorded here — this is the same AlertEngine.history the Alerts view
    exports, sliced for the tiles and paired with the read watermark.
    """
    h = get_hub()
    cfg = config_store.load_config()
    prefs = ((cfg.get("ui") or {}).get("notifications") or {})
    read_ms = int(prefs.get("read_ms") or 0)
    items = h.alerts.recent(limit=limit)
    unread = len([a for a in items if int(a.get("ts_ms") or 0) > read_ms])
    return {"ok": True, "items": items, "unread": unread,
            "prefs": {"read_ms": read_ms, "dnd": bool(prefs.get("dnd", False)),
                      "priority": bool(prefs.get("priority", False))}}


@router.post("/notifications")
async def notifications_update(payload: dict = Body(default={})) -> dict[str, Any]:
    """read_all | read(ts_ms) | dnd(bool) | priority(bool) — all of it config, clamped by the store."""
    data = payload or {}
    action = str(data.get("action") or "")
    cfg = config_store.load_config()
    prefs = dict((cfg.get("ui") or {}).get("notifications") or {})
    if action == "read_all":
        items = get_hub().alerts.recent(limit=500)
        prefs["read_ms"] = max([int(a.get("ts_ms") or 0) for a in items] + [int(time.time() * 1000)])
    elif action == "read":
        try:
            ts = int(data.get("ts_ms") or 0)
        except (TypeError, ValueError):
            ts = 0
        if ts > int(prefs.get("read_ms") or 0):
            prefs["read_ms"] = ts
    elif action == "dnd":
        prefs["dnd"] = bool(data.get("dnd"))
    elif action == "priority":
        prefs["priority"] = bool(data.get("priority"))
    else:
        return {"ok": False, "error": f"unknown action {action!r}"}
    config_store.merge_config({"ui": {"notifications": prefs}})
    return {"ok": True, "prefs": prefs}


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


@router.post("/alert-rules/test")
async def test_rule(payload: dict = Body(default={})) -> dict[str, Any]:
    """The condition builder's Test fire: rehearse one candidate rule against the live snapshot.

    Nothing is saved here — the rule is evaluated against the newest real event of its kind, and
    the answer names every gate, each condition's reading, and the exact evidence block a
    notification would carry. When no such event has happened yet, it says so instead of guessing.
    """
    body = payload or {}
    rule = body.get("rule") if isinstance(body.get("rule"), dict) else body
    return get_hub().alerts.test_fire(rule, symbol=str(body.get("symbol") or ""))


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
        # SEC-04: stamp the print and keep the alert channels out of the replay (the views still
        # get every tick — that is what replay is for).
        tick.replay = True
        h.on_tick(rp.status()["symbol"], tick)
        # R9: the simulated account rides the same prints the views do, so a fill is a real print
        # from the tape being replayed (or the live stream) — never an invented price.
        _paper["last_price"] = float(tick.price)
        _paper["last_ts_ms"] = int(tick.timestamp_ms)   # the ledger's tape clock
        account = _paper.get("account")
        if account is not None:
            try:
                fills = account.on_trade(float(tick.price), float(tick.size),
                                         str(as_value(tick.side)), int(tick.timestamp_ms))
                for fill in fills or []:
                    _paper["fills"].append(fill)
                    _paper_event("fill", order_id=fill.get("order_id") or "",
                                 side=fill.get("side") or "", size=fill.get("size"),
                                 price=fill.get("price"), order_kind=fill.get("kind") or "",
                                 note=fill.get("reason") or "", at_ms=int(tick.timestamp_ms))
                del _paper["fills"][:-40]
            except Exception:                     # noqa: BLE001 - a paper fill must never stop replay
                logger.debug("the simulated account refused a print", exc_info=True)
        try:
            from orderflow_system.dashboard.app import ws_manager
            await ws_manager.broadcast_tick(rp.status()["symbol"], tick.price, tick.size,
                                            as_value(tick.side))
        except Exception:
            pass

    hub = get_hub()
    hub.replaying = True
    try:
        return await rp.play(feed, speed=speed)
    finally:
        hub.replaying = False


@router.post("/replay/reset")
async def replay_reset() -> dict[str, Any]:
    """Drop the loaded tape and its rows (MEM-A1-11).

    The replay transport is a module singleton and a load can hold tens of MB of rows; the
    panel's Close button calls this so the memory is released when the user is done, not at
    process exit.
    """
    rp = get_replay()
    await rp.stop()
    rp.reset()
    return {"ok": True, "status": rp.status()}


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


# ── replay: the simulated account (R9) ─────────────────────────────────────

_paper: dict[str, Any] = {"account": None, "fills": [], "last_price": 0.0,
                          "events": [], "event_count": 0, "last_ts_ms": 0}


def _paper_event(kind: str, **fields: Any) -> dict[str, Any]:
    """Append one lifecycle record to the session's ledger (the order log replay keeps).

    ``at_ms`` is the replay clock — the last print's stamp — so the log reads in tape time
    beside the chart it traded on; ``wall_ms`` is when the click happened. Capped oldest-first: a
    long session must not grow without bound.
    """
    import time as _time

    _paper["event_count"] = int(_paper.get("event_count") or 0) + 1
    row = {"n": _paper["event_count"], "kind": str(kind),
           "at_ms": int(fields.pop("at_ms", None) or _paper.get("last_ts_ms") or 0),
           "wall_ms": int(_time.time() * 1000)}
    row.update(fields)
    events = _paper.setdefault("events", [])
    events.append(row)
    del events[:-300]
    return row


def _paper_exports_dir() -> "Path":
    """The same exports folder the control router writes to (config dir / exports)."""
    import os as _os
    from pathlib import Path as _Path

    try:
        base = _Path(config_store.config_dir())
    except Exception:                                # pragma: no cover - a broken home dir
        base = _Path(_os.environ.get("APPDATA") or _Path.home()) / "OrderFlowAnalysisPro"
    return base / "exports"


def _paper_state() -> dict[str, Any]:
    """The session's account as the panel reads it: position, marks, orders, fills, closed."""
    account = _paper.get("account")
    ledger = {"exits": {"stop_loss": None, "take_profit": None},
              "events": list(_paper.get("events") or [])[-120:],
              "event_count": int(_paper.get("event_count") or 0)}
    if account is None:
        return {"running": False, "symbol": "", "tick_size": 0.0, "position": {"side": "flat", "size": 0},
                "stats": {}, "orders": [], "fills": [], "closed": [], "plan": None,
                "last_price": _paper["last_price"], **ledger}
    return {"running": True, "symbol": account.symbol, "tick_size": account.tick_size,
            "position": account.position(),
            "mark": account.mark(float(_paper["last_price"] or 0)),
            "stats": account.stats(), "orders": account.open_orders(),
            "fills": list(_paper["fills"]), "closed": account.closed_trades(),
            "last_price": _paper["last_price"], "exits": account.exits(), "plan": account.plan(),
            "events": ledger["events"], "event_count": ledger["event_count"]}


@router.post("/replay/paper/start")
async def paper_start(payload: dict = Body(default={})) -> dict[str, Any]:
    """Open a simulated account on the replaying instrument — no broker, no money, no risk.

    The account consumes the prints the replay already delivers, so its fills are the tape's: a
    market order fills at the next print, a limit fills when a print trades through its price.
    Nothing here touches an exchange.
    """
    from orderflow_system.desktop import paper as paper_mod

    symbol = str(payload.get("symbol") or (get_replay().status() or {}).get("symbol") or "").strip().upper()
    try:
        tick_size = float(payload.get("tick_size") or 0.01)
        balance = float(payload.get("balance") or 100_000.0)
    except (TypeError, ValueError):
        tick_size, balance = 0.01, 100_000.0
    _paper["account"] = paper_mod.PaperAccount(symbol=symbol, tick_size=max(1e-8, tick_size),
                                               starting_balance=balance)
    # §148: the session's router — every order from here runs the risk gates (max size, the day's
    # loss cap, concurrent positions, the bridge refusal). Measured before this fix: `bind_account`
    # had no production caller, so an order placed at this route bypassed all of them.
    orders_mod.bind_account(_paper["account"], settings=orders_mod._stored("orders"))
    _paper["fills"] = []
    _paper["events"] = []                      # a new session starts a new ledger
    _paper["event_count"] = 0
    _paper["last_ts_ms"] = 0
    _paper_event("start", note=symbol or "session")
    return {"ok": True, "state": _paper_state()}


@router.get("/replay/paper/state")
async def paper_get_state() -> dict[str, Any]:
    return {"ok": True, "state": _paper_state()}


@router.post("/replay/paper/order")
async def paper_order(payload: dict = Body(default={})) -> dict[str, Any]:
    """Place a simulated order: market, limit or stop, with an optional stop loss / take profit."""
    import time as _time

    account = _paper.get("account")
    if account is None:
        return {"ok": False, "error": "no simulated account — start one with /replay/paper/start"}
    body = dict(payload or {})

    def _number(key: str) -> Any:
        value = body.get(key)
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"{key} is not a number: {value!r}") from None

    try:
        size = float(body.get("size") or 0)
        price = _number("price")
        stop_loss = _number("stop_loss")
        take_profit = _number("take_profit")
    except HTTPException:
        raise
    # §148: the order leaves by the session's router, not straight into the account — that is where
    # the risk gates live (max size, the day's loss cap, concurrent positions, the bridge refusal).
    # The template is passed through as it arrives: the ladder packs its plan-bar template as an
    # OBJECT (`ladder.js`: `body.template = d.template`) and `paper._resolve_template` takes either a
    # dict or a shipped id — `str()` here had made every planned order a rejected one.
    bound = orders_mod.session_router()
    if bound is None or bound.account is not account:
        bound = orders_mod.bind_account(account, settings=orders_mod._stored("orders"))
    receipt = bound.route(str(body.get("side") or "").lower(), size,
                          kind=str(body.get("kind") or "market").lower(), price=price,
                          stop_loss=stop_loss, take_profit=take_profit,
                          template=body.get("template") or "",
                          ts_ms=int(_time.time() * 1000))
    order = receipt.get("order")
    ok = bool(receipt.get("ok"))
    if not ok and order is None:
        # §148: a refusal still takes an id and a row, the way one the account refused itself does —
        # the session's ledger keeps its trace of the click (and its `orders_rejected` count).
        order = account.refuse(str(body.get("side") or "").lower(), size,
                               receipt.get("reason") or "",
                               kind=str(body.get("kind") or "market").lower(), price=price,
                               ts_ms=int(_time.time() * 1000))
    _paper_event("submit" if ok else "reject", order_id=(order or {}).get("id") or "",
                 side=(order or {}).get("side") or str(body.get("side") or "").lower(),
                 size=(order or {}).get("size", size), price=(order or {}).get("price", price),
                 order_kind=(order or {}).get("kind") or str(body.get("kind") or "market").lower(),
                 note=str(receipt.get("reason") or ""))
    return {"ok": ok, "order": order, "error": str(receipt.get("reason") or ""),
            "gate": receipt.get("gate") or "", "state": _paper_state()}


@router.post("/replay/paper/cancel")
async def paper_cancel(payload: dict = Body(default={})) -> dict[str, Any]:
    """Cancel one working order by id, or every working order when none is named."""
    account = _paper.get("account")
    if account is None:
        return {"ok": False, "error": "no simulated account"}
    order_id = str((payload or {}).get("order_id") or "")
    if order_id:
        done = bool(account.cancel(order_id))
        if done:
            _paper_event("cancel", order_id=order_id, note="by id")
        return {"ok": done, "cancelled": [order_id], "state": _paper_state()}
    cancelled = [order["id"] for order in account.open_orders() if account.cancel(order["id"])]
    for oid in cancelled:
        _paper_event("cancel", order_id=oid, note="cancel all")
    return {"ok": True, "cancelled": cancelled, "state": _paper_state()}


@router.post("/replay/paper/flatten")
async def paper_flatten() -> dict[str, Any]:
    """Close the open position at the last printed price."""
    import time as _time

    account = _paper.get("account")
    if account is None:
        return {"ok": False, "error": "no simulated account"}
    price = float(_paper.get("last_price") or 0)
    if price <= 0:
        return {"ok": False, "error": "no print has arrived yet — play the session first"}
    fills = account.flatten(price, int(_time.time() * 1000))
    for fill in fills or []:
        _paper["fills"].append(fill)
        _paper_event("fill", order_id="", side=fill.get("side") or "", size=fill.get("size"),
                     price=fill.get("price"), order_kind="flatten", note="flatten")
    return {"ok": True, "fills": fills, "state": _paper_state()}


@router.post("/replay/paper/exits")
async def paper_exits(payload: dict = Body(default={})) -> dict[str, Any]:
    """Move or clear the open position's stop-loss / take-profit — the bracket, edited as a pair.

    Both fields are applied together (a positive price sets a level, an empty value clears it): a
    bracket is one intent pair, so a caller can never leave the other leg ambiguous by omission.
    """
    import time as _time

    account = _paper.get("account")
    if account is None:
        return {"ok": False, "error": "no simulated account"}
    body = payload or {}
    result = account.set_exits(stop_loss=body.get("stop_loss"), take_profit=body.get("take_profit"),
                               ts_ms=int(_time.time() * 1000))
    if result.get("ok"):
        def _fmt(v: Any) -> str:
            return ("%g" % float(v)) if v not in (None, "") else "—"

        _paper_event("exits", note="stop %s · target %s" % (_fmt(result.get("stop_loss")),
                                                               _fmt(result.get("take_profit"))))
    return {"ok": bool(result.get("ok")), "error": str(result.get("reason") or ""),
            "changed": bool(result.get("changed")), "state": _paper_state()}


@router.post("/replay/paper/export")
async def paper_export() -> dict[str, Any]:
    """Write the session's ledger (submits, refusals, fills, exits, cancels) as a CSV file.

    The tape-time column comes first: reviewing a replay session means lining your orders up with
    the chart they traded on, and that clock is the prints' own, not the wall's.
    """
    import csv as _csv
    import datetime as _dt
    import io as _io

    events = list(_paper.get("events") or [])
    account = _paper.get("account")
    symbol = (account.symbol if account is not None else "") or "paper"

    def _iso(ms: int) -> str:
        if not ms:
            return ""
        try:
            return _dt.datetime.fromtimestamp(int(ms) / 1000.0).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        except (OverflowError, OSError, ValueError):
            return ""

    buf = _io.StringIO()
    writer = _csv.writer(buf)
    writer.writerow(["n", "event", "tape_time", "action_time", "order", "side", "size",
                     "price", "order_kind", "note"])
    for evt in events:
        writer.writerow([evt.get("n"), evt.get("kind"), _iso(evt.get("at_ms") or 0),
                         _iso(evt.get("wall_ms") or 0), evt.get("order_id") or "",
                         evt.get("side") or "",
                         evt.get("size") if evt.get("size") is not None else "",
                         evt.get("price") if evt.get("price") is not None else "",
                         evt.get("order_kind") or "", evt.get("note") or ""])
    folder = _paper_exports_dir()
    folder.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    safe = "".join(ch for ch in str(symbol) if ch.isalnum() or ch in "._-")[:24] or "session"
    target = folder / ("paper-%s-%s.csv" % (safe, stamp))
    with open(target, "w", encoding="utf-8", newline="") as fh:   # csv owns the line ends
        fh.write(buf.getvalue())
    logger.info("[paper] ledger exported: %s (%d rows)", target, len(events))
    return {"ok": True, "path": str(target), "rows": len(events)}


@router.post("/replay/paper/close")
async def paper_close() -> dict[str, Any]:
    """End the session; its closed trades are written into the journal (the app's own table)."""
    import sqlite3

    from orderflow_system.desktop import journal as journal_mod

    account = _paper.get("account")
    if account is None:
        return {"ok": False, "error": "no simulated account to close"}
    rows = account.closed_trades()
    written = 0
    if rows:
        conn = sqlite3.connect(str(config_store.db_path()), timeout=15)
        try:
            conn.execute("PRAGMA busy_timeout=15000")
            # A fresh install has no trade_journal until the data layer first runs; this
            # endpoint writes the table, so it owns creating it (measured: a clean sandbox
            # 500ed here with "no such table" the first time a session ended).
            conn.execute(journal_mod.TRADE_JOURNAL_DDL)
            # §148: CREATE TABLE IF NOT EXISTS never alters an existing table, so the writer
            # migrates what it is about to write. profile_id came with the profiles feature and
            # mae_ticks/mfe_ticks with the excursion writers; the data layer runs the same guarded
            # ADD COLUMNs when it opens the file, but this path must not depend on the engine
            # having started (measured: a legacy table without profile_id made this INSERT raise).
            cols = {r[1] for r in conn.execute("PRAGMA table_info(trade_journal)").fetchall()}
            if "profile_id" not in cols:
                conn.execute(
                    "ALTER TABLE trade_journal ADD COLUMN profile_id TEXT NOT NULL DEFAULT ''")
            for column in ("mae_ticks", "mfe_ticks"):
                if column not in cols:
                    conn.execute(f"ALTER TABLE trade_journal ADD COLUMN {column} REAL")
            for row in rows:
                conn.execute(
                    "INSERT INTO trade_journal (instrument, direction, entry_time_ms, exit_time_ms, "
                    "entry_price, exit_price, stop_loss, take_profit, pnl_ticks, rr_ratio, "
                    "mae_ticks, mfe_ticks, "
                    "signals_json, notes, profile_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (row.get("instrument") or account.symbol, row.get("direction") or "",
                     row.get("entry_time_ms"), row.get("exit_time_ms"), row.get("entry_price"),
                     row.get("exit_price"), row.get("stop_loss"), row.get("take_profit"),
                     row.get("pnl_ticks"), row.get("rr_ratio"),
                     row.get("mae_ticks"), row.get("mfe_ticks"), '{"source": "paper"}',
                     "simulated session",
                     (config_store.load_config().get("profiles") or {}).get("active") or ""))
                written += 1
            conn.commit()
        finally:
            conn.close()
        logger.info("[paper] session closed: %d trade(s) saved to the journal", written)
    _paper_event("end", note=(str(written) + " trade(s) saved to the journal"))
    _paper["account"] = None
    _paper["fills"] = []
    orders_mod.unbind_account()          # §148: no router outlives the session it was bound to
    return {"ok": True, "saved": written, "trades": [dict(r) for r in rows],
            "note": ("saved to the Journal view" if written else "nothing was closed — the session had no completed trades")}


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


def _finnhub_block() -> dict[str, Any]:
    try:
        return config_store.load_config().get("finnhub") or {}
    except Exception:                                  # pragma: no cover - never break the view
        return {}


def _finnhub_headlines(limit: int) -> tuple[list[dict[str, Any]], str]:
    """Finnhub headlines in the News panel's item shape — ``(items, reason when empty)``.

    The key resolves exactly like the calendar lane's: the settings copy first (what the engine
    applied, so a key saved a moment ago is already live), then the stored config block. The
    reason is a sentence the panel prints verbatim, never a stack trace.
    """
    from orderflow_system.config import settings
    from orderflow_system.data import finnhub_feed as fh

    key = str(getattr(settings.FINNHUB, "api_key", "") or "").strip()
    block = _finnhub_block()
    if not key:
        key = str(block.get("api_key") or "").strip()
    if not key:
        return [], "no Finnhub key — add one in Settings ▸ Feed keys"
    category = str(getattr(settings.FINNHUB, "news_category", "") or "").strip() \
        or str(block.get("news_category") or "general").strip() or "general"
    batch = fh.FinnhubFeed(api_key=key).news(category=category)
    if getattr(batch, "error", None):
        return [], f"the Finnhub news API answered: {batch.error}"
    return fh.to_news_items(batch)[: max(0, int(limit))], ""


@router.get("/context/{symbol}")
async def market_context(
    symbol: str,
    news_url: str = Query(default=""),
    news_limit: int = Query(default=0, ge=0, le=30),
    news_source: str = Query(default=""),
) -> dict[str, Any]:
    """Funding / open interest / long-short ratio, Fear & Greed and headlines.

    The positioning and Fear & Greed sources are public and keyless, and each section degrades to
    ``{"ok": false}`` on its own so one dead feed never blanks the card. The headlines come from
    one of two lanes — the built-in public feeds (``context.news_source = "feeds"``, the default)
    or the Finnhub news API (``"finnhub"``, read with the key from Settings ▸ Feed keys); the
    payload's ``stats.lane`` names which one answered, so the panel never calls one the other.
    """
    from orderflow_system.atlas.context import shared_context

    cfg = _context_settings()
    if not bool(cfg.get("enabled", True)):
        return {"ok": False, "error": "market context is disabled in settings", "symbol": symbol.upper()}

    include = [name for name, key in (("positioning", "positioning"), ("fear_greed", "fear_greed"),
                                      ("news", "news")) if bool(cfg.get(key, True))]
    requested = str(news_url or "").strip()
    configured = str(cfg.get("news_url") or "").strip()
    if requested and requested != configured:
        # SEC-28: GET is a "safe" method, so the origin guard never inspects it — any page in any
        # browser could point this server-side fetch at an arbitrary host and use the app as a
        # relay. Only the feed the user configured in Settings is fetchable through the API.
        return {"ok": False, "symbol": symbol.upper(),
                "error": "news_url must match the feed configured in Settings"}
    lane = str(news_source or "").strip().lower() or str(cfg.get("news_source") or "feeds").lower()
    if lane not in ("feeds", "finnhub"):
        lane = "feeds"
    ctx = shared_context()
    # The Finnhub lane REPLACES the headline section rather than adding to it, so the RSS fetch
    # is not asked for at all — one lane, one bill of work, and no half-read cache entry.
    snapshot_include = [name for name in include
                        if not (name == "news" and lane == "finnhub")]
    out = await ctx.snapshot(
        symbol,
        include=snapshot_include,
        news_limit=int(news_limit or cfg.get("news_limit") or 8),
        feed_url=configured,
    )
    out["stats"] = ctx.stats()
    out["stats"]["lane"] = lane
    if lane == "finnhub" and "news" in include:
        items, reason = await asyncio.to_thread(
            _finnhub_headlines, int(news_limit or cfg.get("news_limit") or 8))
        out["news"] = items
        out["stats"]["feeds"] = ["finnhub"] if items else []
        out["stats"]["last_error"] = reason or ""
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


# ── level reads (fold-in plan §3): unfinished magnets, node runs, confluence ──

@router.get("/levels/{symbol}")
async def atlas_levels(symbol: str, tol_ticks: float = Query(default=2.0, ge=0.1, le=50.0)) -> dict[str, Any]:
    """The level-lifecycle reads: open unfinished-business magnets, node runs, and where the
    level sources agree (confluence).

    ``unfinished`` / ``nodes`` are the live trackers' snapshots — the same objects alerts
    evaluate against, so the drawn line and the alert can never disagree about a level. When
    the engine has not fed this symbol yet, both are ``None`` and ``note`` says so instead of
    inventing levels; ``confluence`` combines them with the stored profiles' virgin POCs and
    the weekly / monthly POC ladder at one tolerance.
    """
    from orderflow_system.atlas.confluence import (
        find_confluences,
        refs_from_nodes,
        refs_from_pocs,
        refs_from_unfinished,
    )

    h = get_hub()
    symbols = getattr(h, "symbols", None) or {}
    feats = symbols.get(symbol) if hasattr(symbols, "get") else None
    if feats is None:
        return {"ok": True, "symbol": symbol,
                "note": "no live readings yet — the level trackers fill while the engine runs",
                "unfinished": None, "nodes": None, "confluence": []}

    tick = float(getattr(feats, "tick_size", 0.0) or 0.0)
    unfinished = feats.unfinished.snapshot()
    nodes = feats.nodes.snapshot()

    refs: list[Any] = []
    refs.extend(refs_from_unfinished(unfinished.get("open") or []))
    node_rows = [n for n in (([nodes.get("current")] if nodes.get("current") else [])
                             + (nodes.get("completed") or []))
                 if int(n.get("count") or 0) >= 2]
    refs.extend(refs_from_nodes(node_rows))
    try:
        from orderflow_system.desktop import engine as engine_mod
        system = engine_mod.engine.system
        if system is not None:
            profiles = await system.db.get_volume_profiles(symbol, days=30)
            from orderflow_system.atlas.profiles import period_pocs, virgin_pocs
            refs.extend(refs_from_pocs(virgin_pocs(profiles), source="virgin_poc"))
            refs.extend(refs_from_pocs(period_pocs(profiles, "week"), source="poc_week"))
            refs.extend(refs_from_pocs(period_pocs(profiles, "month"), source="poc_month"))
    except Exception:
        pass

    tol = (tick * float(tol_ticks)) if tick > 0 else 0.0
    confluence = find_confluences(refs, tol=tol, min_distinct=2) if tol > 0 else []
    return {"ok": True, "symbol": symbol, "tick": tick, "tol": tol,
            "unfinished": unfinished, "nodes": nodes, "confluence": confluence}


# ── market read: the deterministic read of one instrument's live state ──

def _radar_rows(feats: Any) -> tuple[dict[str, Any], ...]:
    """The radar's own levels, so a read quotes the real prices it is tracking.

    Only the live ones: a spent or failed level is history, and the read is about what is in front
    of price now. A tracker that cannot answer returns an empty tuple — the read then falls back to
    the count-anchored path inside ``extract_levels`` instead of failing.
    """
    try:
        snapshot = feats.radar.snapshot()
    except Exception:                       # noqa: BLE001 - a read must not die on one tracker
        return ()
    rows = snapshot.get("levels") if isinstance(snapshot, dict) else None
    return tuple(row for row in (rows or []) if isinstance(row, dict) and row.get("live"))


def _num_or_none(value: Any) -> Optional[float]:
    """A finite float or None — the read's dataclasses take None, never a NaN."""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return num if num == num and abs(num) != float("inf") else None


@router.get("/market-read/{symbol}")
async def atlas_market_read(symbol: str) -> dict[str, Any]:
    """The deterministic read of one instrument: regime, conviction, levels, confluence, summary.

    Every input comes from the running engine's own analyzers through the hub — the tape's stats,
    the session profile, the radar book, the depth map's walls and the VWAP study. Nothing is
    invented: with no live readings for the symbol the route says so rather than reading a state of
    zeros, and ``inputs`` names which signals were actually measured (the footprint family is not
    fed to the hub yet, so it is reported unmeasured instead of as zeroes).

    Read-only, and cheap: the analyzers' own snapshots, no venue request, nothing stored.
    """
    from orderflow_system.atlas.market_read import (
        HeatmapSnapshot,
        MarketState,
        RadarSnapshot,
        TapeSnapshot,
        VWAPSnapshot,
        VolumeProfileSnapshot,
        read_market,
    )

    h = get_hub()
    symbols = getattr(h, "symbols", None) or {}
    feats = symbols.get(symbol) if hasattr(symbols, "get") else None
    if feats is None:
        return {"ok": False, "symbol": symbol,
                "error": ("no live readings for this instrument — the market read is a function of "
                          "the running engine's tape, profile, radar and book state")}

    try:
        now_ms = int(time.time() * 1000)
        tape = feats.tape.stats()
        profile = feats.profile.snapshot()
        radar = feats.radar.summary()
        depth = feats.heatmap.stats()
        vwap = feats.vwap.snapshot()
        spot = float(getattr(feats, "last_price", 0.0) or 0.0)

        delta = float(tape.get("delta") or 0.0)
        walls = feats.heatmap.wall_prices(top=20)
        walls_above = sum(1 for w in walls if float(w.get("price") or 0.0) > spot)
        walls_below = sum(1 for w in walls if float(w.get("price") or 0.0) < spot and spot > 0)
        events = depth.get("events") or {}

        vwap_price = float(vwap.get("vwap") or 0.0)
        ticks_from = vwap.get("ticks_from_vwap")
        state = MarketState(
            symbol=symbol, spot=spot,
            tape=TapeSnapshot(
                direction=("up" if delta > 0 else ("down" if delta < 0 else "neutral")),
                delta=delta, volume=float(tape.get("volume") or 0.0),
                big_prints=int(tape.get("big_trades") or 0), sweeps=int(tape.get("sweeps") or 0),
                timestamp_ms=now_ms),
            # The footprint family has no hub analyzer yet: the read reports it unmeasured in
            # `inputs` and the absorption/imbalance signals stay at their zero input.
            heatmap=HeatmapSnapshot(
                walls_above=walls_above, walls_below=walls_below,
                # The map's own events: a "stack" is liquidity added at a level, a "pull" is
                # liquidity withdrawn near price — the two words the map already uses.
                wall_refills=int(events.get("stack") or 0), wall_pulls=int(events.get("pull") or 0)),
            radar=RadarSnapshot(
                armed_levels=int(radar.get("armed") or 0),
                approaching_levels=int(radar.get("approaching") or 0),
                held_levels=int(radar.get("defended") or 0) + int(radar.get("confirmed") or 0),
                spent_levels=int(radar.get("spent") or 0) + int(radar.get("failed") or 0),
                levels=_radar_rows(feats)),
            profile=VolumeProfileSnapshot(
                poc=_num_or_none(profile.get("poc")), vah=_num_or_none(profile.get("vah")),
                val=_num_or_none(profile.get("val"))),
            vwap=VWAPSnapshot(price=vwap_price or None,
                              deviation_ticks=_num_or_none(ticks_from)),
            timestamp_ms=now_ms,
        )
        read = read_market(state)
    except Exception as exc:                # noqa: BLE001 - a read failure is a sentence, not a 500
        logger.exception("market read failed for %s", symbol)
        return {"ok": False, "symbol": symbol,
                "error": f"the market read failed: {type(exc).__name__}: {exc}"}

    return {
        "ok": True, "symbol": symbol, "spot": spot, "at": now_ms,
        "regime": {"name": read.regime.name, "description": read.regime.description,
                   "buyer_led": read.regime.buyer_led, "seller_led": read.regime.seller_led,
                   "absorbing": read.regime.absorbing, "absorbing_side": read.regime.absorbing_side},
        "conviction": read.composite_score, "scores": read.score_breakdown,
        "levels": [{"price": lv.price, "kind": lv.kind, "source": lv.source,
                    "strength": lv.strength, "notes": lv.notes} for lv in read.key_levels[:40]],
        "n_levels": read.n_levels,
        "confluence": [{"price": c.price, "signals": list(c.signals), "strength": c.strength}
                       for c in read.confluence_points[:20]],
        "n_confluence": read.n_confluence,
        "summary": read.summary,
        "inputs": {
            "tape": {"measured": bool(tape.get("prints")), "prints": int(tape.get("prints") or 0),
                     "sweeps": int(tape.get("sweeps") or 0), "delta": delta},
            "profile": {"measured": profile.get("poc") is not None, "poc": profile.get("poc")},
            "radar": {"measured": bool(radar.get("live")), "live": int(radar.get("live") or 0)},
            "heatmap": {"measured": bool(depth.get("walls")), "walls": int(depth.get("walls") or 0)},
            "vwap": {"measured": bool(vwap_price), "vwap": vwap_price or None},
            "footprint": {"measured": False,
                          "note": ("footprint imbalances are not fed to the read yet — the "
                                   "absorption and imbalance signals read their zero input")},
        },
        "note": ("a pure function of the engine's live state (atlas/market_read.py), pinned by "
                 "test_market_read.py; nothing here is a forecast"),
    }


def _num_or_none(value: Any) -> Optional[float]:
    """A finite float or None — the read's dataclasses take None, never a NaN."""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return num if num == num and abs(num) != float("inf") else None
