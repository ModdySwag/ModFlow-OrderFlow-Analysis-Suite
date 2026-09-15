"""
FastAPI Dashboard Application
REST endpoints + WebSocket for the real-time orderflow trading terminal.

Endpoints:
  GET  /api/instruments          — Active instruments with current stats
  GET  /api/candles/{symbol}     — Recent candle history
  GET  /api/volume-profile/{sym} — Current VP (POC/VAH/VAL + histogram)
  GET  /api/bias/{symbol}        — Daily bias and qualified levels
  GET  /api/signals/{symbol}     — Signal history
  GET  /api/trade/{symbol}       — Active trade state
  GET  /api/orderbook/{symbol}   — Current L2 orderbook
  GET  /api/delta/{symbol}       — Delta history
  GET  /api/stats                — System-wide stats
  WS   /ws                       — Real-time stream
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from orderflow_system.dashboard.websocket_manager import WebSocketManager, _serialize
from orderflow_system.data.models import TradePhase
from orderflow_system.data.enums import as_value
from orderflow_system.dashboard import demo_data

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# FastAPI app — created here, system ref set at startup
# ──────────────────────────────────────────────

app = FastAPI(
    title="Orderflow Trading Dashboard",
    description="Real-time orderflow analysis terminal",
    version="1.0.0",
)

# WebSocket manager — shared with main.py
ws_manager = WebSocketManager()

# Reference to OrderflowSystem — set by main.py before server starts
_system = None


def set_system(system):
    """Set the OrderflowSystem reference. Called by main.py on startup."""
    global _system
    _system = system


def get_system():
    """Get the OrderflowSystem reference."""
    return _system


# ──────────────────────────────────────────────
# Static files (frontend)
# ──────────────────────────────────────────────

# Disable browser caching for static files during development
class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/static") or request.url.path == "/":
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

app.add_middleware(NoCacheMiddleware)

_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")


@app.get("/", include_in_schema=False)
async def index():
    """Serve the dashboard HTML."""
    index_path = os.path.join(_static_dir, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
    return JSONResponse({"error": "Dashboard frontend not found"}, status_code=404)


# ──────────────────────────────────────────────
# REST Endpoints
# ──────────────────────────────────────────────

@app.get("/api/instruments")
async def get_instruments():
    """List active instruments with current stats."""
    system = get_system()
    if not system:
        return demo_data.demo_instruments()

    result = []
    for sym, pipeline in system.pipelines.items():
        stats = pipeline.stats
        # Add trade state info
        trade = system.aggregator.get_active_trade(sym)
        stats["trade_phase"] = trade.phase.value if trade else "none"
        stats["trade_direction"] = trade.direction.value if trade else "none"
        result.append(stats)

    return result


# ── Trade Scanner — ranked strategy status for ALL pairs ──

# Priority scores for strategy overall statuses (higher = closer to trade)
_STATUS_PRIORITY = {
    "IN_TRADE": 100,
    "TRAILING": 95,
    "BREAK_EVEN": 90,
    "ENTRY_READY": 85,
    "AT_LEVEL_SCANNING": 70,
    "WATCHING": 60,
    "WAITING_FOR_PRICE": 40,
    "NO_LEVELS": 20,
    "NO_DATA": 10,
    "OFFLINE": 5,
    "IDLE": 0,
}


@app.get("/api/scanner")
async def get_scanner():
    """Return strategy status for ALL pairs, ranked by trade proximity."""
    system = get_system()
    if not system:
        return demo_data.demo_scanner()

    results = []
    for sym in system.pipelines:
        try:
            status = await get_strategy_status(sym)
            overall = status.get("overall", "IDLE")
            priority = _STATUS_PRIORITY.get(overall, 0)

            # Boost priority if there are more completed steps
            steps = status.get("steps", [])
            completed = sum(
                1 for s in steps
                if s.get("status") in ("completed", "triggered", "active")
            )
            priority += completed * 3  # up to +18 for 6 steps

            results.append({
                "symbol": sym,
                "overall": overall,
                "reason": status.get("reason", ""),
                "priority": priority,
                "steps_done": completed,
                "steps_total": len(steps),
                "bias_direction": status.get("bias_direction", "neutral"),
                "bias_confidence": status.get("bias_confidence", 0),
                "current_price": status.get("current_price", 0),
            })
        except Exception:
            results.append({
                "symbol": sym,
                "overall": "OFFLINE",
                "reason": "Error",
                "priority": 0,
                "steps_done": 0,
                "steps_total": 6,
                "bias_direction": "neutral",
                "bias_confidence": 0,
                "current_price": 0,
            })

    # Sort by priority descending
    results.sort(key=lambda x: x["priority"], reverse=True)
    return results


# ── Chart Markers — signal events formatted for the chart library ──

def _signal_to_marker(sig, is_buy: bool, action: str, time_s: int) -> dict:
    """Convert a signal to chart marker format."""
    sig_type = as_value(sig.signal_type)

    if action == "enter":
        return {"time": time_s, "position": "belowBar" if is_buy else "aboveBar",
                "color": "#00e676" if is_buy else "#ff1744", "shape": "circle",
                "text": "ENTRY \u25b2" if is_buy else "ENTRY \u25bc"}
    elif action == "break_even":
        return {"time": time_s, "position": "aboveBar", "color": "#42a5f5",
                "shape": "square", "text": "BE"}
    elif action == "trail":
        return {"time": time_s, "position": "aboveBar", "color": "#26c6da",
                "shape": "square", "text": "TRAIL"}
    elif action == "exit":
        return {"time": time_s, "position": "aboveBar", "color": "#ff1744",
                "shape": "circle", "text": "EXIT"}
    elif action == "exit_warning":
        return {"time": time_s, "position": "aboveBar", "color": "#ffeb3b",
                "shape": "circle", "text": "WARN"}
    else:
        if sig_type == "absorption":
            return {"time": time_s, "position": "belowBar" if is_buy else "aboveBar",
                    "color": "#26a69a" if is_buy else "#ef5350",
                    "shape": "arrowUp" if is_buy else "arrowDown", "text": "ABS"}
        elif sig_type == "initiative_auction":
            return {"time": time_s, "position": "belowBar" if is_buy else "aboveBar",
                    "color": "#66bb6a" if is_buy else "#ffa726",
                    "shape": "arrowUp" if is_buy else "arrowDown", "text": "INIT"}
        elif sig_type == "book_sweep":
            return {"time": time_s, "position": "aboveBar", "color": "#ab47bc",
                    "shape": "arrowDown", "text": "SWEEP"}
        elif sig_type == "exhaustion":
            return {"time": time_s, "position": "aboveBar", "color": "#ffeb3b",
                    "shape": "circle", "text": "EXHAUST"}
        elif sig_type == "delta_divergence":
            return {"time": time_s, "position": "aboveBar", "color": "#ff9800",
                    "shape": "circle", "text": "DIV"}
        else:
            return {"time": time_s, "position": "aboveBar", "color": "#9e9e9e",
                    "shape": "circle", "text": sig_type[:5]}


@app.get("/api/markers/{symbol}")
async def get_markers(symbol: str, limit: int = Query(default=200, le=500)):
    """Get chart markers for signal events on this instrument."""
    system = get_system()
    if not system:
        return demo_data.demo_markers(symbol)

    pipeline = system.pipelines.get(symbol)
    if not pipeline:
        return []

    raw_signals = []
    for det in [pipeline.absorption, pipeline.initiative, pipeline.sweep,
                pipeline.exhaustion, pipeline.divergence]:
        for sig in getattr(det, '_signal_history', []):
            raw_signals.append(sig)

    # Build lookup: timestamp → aggregated action
    agg_by_ts = {}
    for agg in system.aggregator.signal_history:
        if agg.signals:
            for s in agg.signals:
                agg_by_ts[s.timestamp_ms] = agg

    markers = []
    for sig in raw_signals:
        is_buy = as_value(sig.direction) == "buy"
        time_s = sig.timestamp_ms // 1000
        agg = agg_by_ts.get(sig.timestamp_ms)
        action = agg.action if agg else "alert_only"
        markers.append(_signal_to_marker(sig, is_buy, action, time_s))

    markers.sort(key=lambda x: x["time"])
    return markers[-limit:]


@app.get("/api/candles/{symbol}")
async def get_candles(
    symbol: str,
    count: int = Query(default=500, le=5000),
    tf: int = Query(default=60, description="Timeframe in seconds"),
    range_s: int = Query(default=86400, alias="range", description="History range in seconds"),
):
    """Get candle history, optionally aggregated to a higher timeframe."""
    system = get_system()
    if not system:
        return demo_data.demo_candles(symbol, tf=tf, range_s=range_s)

    pipeline = system.pipelines.get(symbol)
    if not pipeline:
        return JSONResponse({"error": f"Unknown symbol: {symbol}"}, status_code=404)

    # Get raw 1-minute candles
    raw_candles = pipeline.candle_builder.get_recent_candles(5000)

    if not raw_candles:
        return []

    # Filter by time range
    import time as _time
    now_s = _time.time()
    cutoff_ms = (now_s - range_s) * 1000
    raw_candles = [c for c in raw_candles if c.timestamp_ms >= cutoff_ms]

    if not raw_candles:
        return []

    # Aggregate to requested timeframe
    base_interval = pipeline.candle_builder.interval_ms // 1000  # seconds
    tf_seconds = max(tf, base_interval)  # can't go below base TF

    if tf_seconds <= base_interval:
        # No aggregation needed — deduplicate by timestamp (keep latest)
        deduped = {}
        for c in raw_candles:
            deduped[c.timestamp_ms] = c
        sorted_candles = sorted(deduped.values(), key=lambda c: c.timestamp_ms)
        result = []
        for c in sorted_candles:
            result.append({
                "time": int(c.timestamp_ms // 1000),
                "open": round(c.open, 6),
                "high": round(c.high, 6),
                "low": round(c.low, 6),
                "close": round(c.close, 6),
                "volume": round(c.volume, 2),
                "buy_volume": round(c.buy_volume, 2),
                "sell_volume": round(c.sell_volume, 2),
                "delta": round(c.delta, 2),
                "tick_count": c.tick_count,
            })
        return result

    # Aggregate candles into higher TF
    tf_ms = tf_seconds * 1000
    aggregated = {}
    for c in raw_candles:
        bucket = (c.timestamp_ms // tf_ms) * tf_ms
        if bucket not in aggregated:
            aggregated[bucket] = {
                "time": int(bucket // 1000),
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
                "buy_volume": c.buy_volume,
                "sell_volume": c.sell_volume,
                "delta": c.delta,
                "tick_count": c.tick_count,
            }
        else:
            agg = aggregated[bucket]
            agg["high"] = max(agg["high"], c.high)
            agg["low"] = min(agg["low"], c.low)
            agg["close"] = c.close
            agg["volume"] += c.volume
            agg["buy_volume"] += c.buy_volume
            agg["sell_volume"] += c.sell_volume
            agg["delta"] += c.delta
            agg["tick_count"] += c.tick_count

    # Sort by time and round (range already filters)
    result = sorted(aggregated.values(), key=lambda x: x["time"])
    for r in result:
        r["open"] = round(r["open"], 6)
        r["high"] = round(r["high"], 6)
        r["low"] = round(r["low"], 6)
        r["close"] = round(r["close"], 6)
        r["volume"] = round(r["volume"], 2)
        r["buy_volume"] = round(r["buy_volume"], 2)
        r["sell_volume"] = round(r["sell_volume"], 2)
        r["delta"] = round(r["delta"], 2)
    return result


@app.get("/api/volume-profile/{symbol}")
async def get_volume_profile(
    symbol: str,
    days: int = Query(default=5, le=30),
    range_s: int = Query(default=0, alias="range", description="History range in seconds (0=use days param)"),
):
    """
    Get volume profile data.
    If range > 0, compute VP from raw candles in that time range (matches chart view).
    Otherwise fall back to DB profiles by days.
    """
    system = get_system()
    if not system:
        return demo_data.demo_volume_profile(symbol)

    pipeline = system.pipelines.get(symbol)
    if not pipeline:
        return JSONResponse({"error": f"Unknown symbol: {symbol}"}, status_code=404)

    # ── Range-based VP: compute from candles matching chart view ──
    if range_s > 0:
        import time as _time
        raw_candles = pipeline.candle_builder.get_recent_candles(5000)
        if not raw_candles:
            return []

        now_s = _time.time()
        cutoff_ms = (now_s - range_s) * 1000
        candles_in_range = [c for c in raw_candles if c.timestamp_ms >= cutoff_ms]

        if not candles_in_range:
            return []

        # Build VP from these candles
        tick_size = pipeline.config.tick_size
        volume_at_price: dict[float, float] = {}
        for c in candles_in_range:
            # Distribute volume across candle range at tick_size granularity
            if tick_size > 0 and c.high > c.low:
                price = c.low
                levels = max(1, int((c.high - c.low) / tick_size))
                vol_per_level = c.volume / levels if levels > 0 else c.volume
                for _ in range(min(levels, 500)):  # cap levels to avoid huge loops
                    rounded = round(price / tick_size) * tick_size
                    volume_at_price[rounded] = volume_at_price.get(rounded, 0) + vol_per_level
                    price += tick_size
            else:
                # Single-price candle
                rounded = round(c.close / tick_size) * tick_size if tick_size > 0 else c.close
                volume_at_price[rounded] = volume_at_price.get(rounded, 0) + c.volume

        if not volume_at_price:
            return []

        # Compute POC, VAH, VAL
        total_vol = sum(volume_at_price.values())
        sorted_prices = sorted(volume_at_price.items(), key=lambda x: x[1], reverse=True)
        poc_price = sorted_prices[0][0] if sorted_prices else 0

        # Value area: 70% of volume around POC
        sorted_by_price = sorted(volume_at_price.items(), key=lambda x: x[0])
        prices_list = [p for p, _ in sorted_by_price]
        vols_list = [v for _, v in sorted_by_price]
        poc_idx = prices_list.index(poc_price) if poc_price in prices_list else 0

        va_vol = vols_list[poc_idx]
        va_target = total_vol * 0.70
        lo, hi = poc_idx, poc_idx
        while va_vol < va_target and (lo > 0 or hi < len(vols_list) - 1):
            add_lo = vols_list[lo - 1] if lo > 0 else 0
            add_hi = vols_list[hi + 1] if hi < len(vols_list) - 1 else 0
            if add_lo >= add_hi and lo > 0:
                lo -= 1
                va_vol += vols_list[lo]
            elif hi < len(vols_list) - 1:
                hi += 1
                va_vol += vols_list[hi]
            else:
                break
        val_price = prices_list[lo]
        vah_price = prices_list[hi]

        # Downsample volume_at_price for rendering (max 200 levels)
        render_data = sorted_by_price
        max_render_levels = 200
        if len(sorted_by_price) > max_render_levels:
            all_p = [p for p, _ in sorted_by_price]
            p_min, p_max = all_p[0], all_p[-1]
            bucket_sz = (p_max - p_min) / max_render_levels
            if bucket_sz > 0:
                downsampled: dict[float, float] = {}
                for p, v in sorted_by_price:
                    bk = round(p_min + ((p - p_min) // bucket_sz) * bucket_sz, 6)
                    downsampled[bk] = downsampled.get(bk, 0) + v
                render_data = sorted(downsampled.items())

        poc_pct = poc_idx / max(len(prices_list) - 1, 1)
        if poc_pct > 0.65:
            vp_shape = "p_shape"
        elif poc_pct < 0.35:
            vp_shape = "b_shape"
        else:
            vp_shape = "d_shape"

        return [{
            "session_date": "range",
            "poc": poc_price,
            "vah": vah_price,
            "val": val_price,
            "total_volume": total_vol,
            "shape": vp_shape,
            "poc_position_pct": poc_pct,
            "lvn_levels": [],
            "volume_at_price": {
                str(round(p, 6)): round(v, 2)
                for p, v in render_data
            },
        }]

    # ── Fallback: DB-based profiles by days ──
    profiles = await system.db.get_volume_profiles(symbol, days=days)

    result = []
    for vp in profiles:
        result.append({
            "session_date": vp.session_date,
            "poc": vp.poc,
            "vah": vp.vah,
            "val": vp.val,
            "total_volume": vp.total_volume,
            "shape": vp.shape,
            "poc_position_pct": vp.poc_position_pct,
            "lvn_levels": vp.lvn_levels,
            "volume_at_price": {
                str(price): vol
                for price, vol in sorted(vp.volume_at_price.items())
            },
        })
    return result


@app.get("/api/bias/{symbol}")
async def get_bias(symbol: str):
    """Get current daily bias and qualified levels."""
    system = get_system()
    if not system:
        return _with_source(demo_data.demo_bias(symbol), "demo")

    pipeline = system.pipelines.get(symbol)
    if not pipeline:
        return JSONResponse({"error": f"Unknown symbol: {symbol}"}, status_code=404)

    bias = pipeline.profile_framing.current_bias
    if not bias:
        return {
            "direction": "neutral",
            "confidence": 0,
            "qualified_levels": [],
            "notes": "No profile data yet",
            "source": "engine",
        }

    return _with_source(_serialize(bias), "engine")


@app.get("/api/signals/{symbol}")
async def get_signals(symbol: str, limit: int = Query(default=50, le=200)):
    """Get signal history."""
    system = get_system()
    if not system:
        return demo_data.demo_signals()

    history = system.aggregator.signal_history
    # Filter by symbol if the signal has instrument info
    filtered = []
    for sig in reversed(history):
        # AggregatedSignal doesn't have instrument, but we can check direction
        filtered.append(_serialize(sig))
        if len(filtered) >= limit:
            break

    return filtered


@app.get("/api/trade/{symbol}")
async def get_trade(symbol: str):
    """Get active trade state for an instrument."""
    system = get_system()
    if not system:
        return {"phase": "none", "instrument": symbol}

    trade = system.aggregator.get_active_trade(symbol)
    if not trade:
        return {"phase": "none", "instrument": symbol}

    return _serialize(trade)


@app.get("/api/strategy-status/{symbol}")
async def get_strategy_status(symbol: str):
    """
    Full Fabio methodology status: what the system is doing and WHY.
    Returns a step-by-step checklist of the strategy pipeline.
    """
    system = get_system()
    if not system:
        return _with_source(demo_data.demo_strategy_status(symbol), "demo")

    pipeline = system.pipelines.get(symbol)
    if not pipeline:
        return _empty_strategy_status(symbol, f"Unknown symbol: {symbol}")

    trade = system.aggregator.get_active_trade(symbol)
    bias = pipeline.profile_framing.current_bias
    current_price = pipeline.current_price
    recent_candles = pipeline.candle_builder.get_recent_candles(10)
    last_candle = recent_candles[-1] if recent_candles else None

    # ── Step 1: Profile Framing ──
    step_profile = {
        "step": 1,
        "name": "Profile Framing",
        "status": "inactive",
        "icon": "📊",
        "detail": "No profile data yet",
        "sub": [],
    }
    if bias:
        step_profile["status"] = "active"
        step_profile["detail"] = bias.notes or f"{bias.profile_shape} profile"
        step_profile["sub"] = [
            f"Shape: {bias.profile_shape}",
            f"Direction: {as_value(bias.direction)}",
            f"Confidence: {bias.confidence:.0f}%",
            f"POC: {bias.poc:.2f}" if bias.poc else "POC: --",
            f"VAH: {bias.vah:.2f}" if bias.vah else "VAH: --",
            f"VAL: {bias.val:.2f}" if bias.val else "VAL: --",
        ]
        if bias.merged_vah:
            step_profile["sub"].append(f"Merged VAH: {bias.merged_vah:.2f}")
        if bias.merged_val:
            step_profile["sub"].append(f"Merged VAL: {bias.merged_val:.2f}")

    # ── Step 2: Qualified Levels ──
    step_levels = {
        "step": 2,
        "name": "Qualified Levels",
        "status": "inactive",
        "icon": "🎯",
        "detail": "No levels qualified",
        "sub": [],
    }
    nearest_level = None
    nearest_dist = float("inf")
    if bias and bias.qualified_levels:
        step_levels["status"] = "active"
        step_levels["detail"] = f"{len(bias.qualified_levels)} level(s) qualified"
        for lv in bias.qualified_levels:
            dist_pct = abs(current_price - lv.price) / max(current_price, 1) * 100 if current_price > 0 else 0
            proximity = "AT LEVEL" if dist_pct < 0.2 else f"{dist_pct:.2f}% away"
            dir_label = "LONG" if lv.direction.value == "buy" else "SHORT"
            step_levels["sub"].append(
                f"{lv.level_type.value.upper()} @ {lv.price:.2f} → {dir_label} | Str: {lv.strength:.0f}% | {proximity}"
            )
            if current_price > 0 and abs(current_price - lv.price) < nearest_dist:
                nearest_dist = abs(current_price - lv.price)
                nearest_level = lv

    # ── Step 3: Price at Level? ──
    at_level = False
    proximity_pct = system.aggregator.price_proximity_pct if hasattr(system.aggregator, 'price_proximity_pct') else 0.002
    step_price = {
        "step": 3,
        "name": "Price at Level",
        "status": "inactive",
        "icon": "📍",
        "detail": "Waiting for price to reach a qualified level",
        "sub": [],
    }
    if current_price > 0 and nearest_level:
        dist_pct = abs(current_price - nearest_level.price) / max(current_price, 1)
        if dist_pct < proximity_pct:
            at_level = True
            step_price["status"] = "triggered"
            step_price["detail"] = f"Price AT {nearest_level.level_type.value.upper()} @ {nearest_level.price:.2f}"
        else:
            step_price["status"] = "waiting"
            step_price["detail"] = f"Price {current_price:.2f} is {dist_pct*100:.2f}% from nearest level ({nearest_level.level_type.value.upper()} @ {nearest_level.price:.2f})"
        step_price["sub"].append(f"Current: {current_price:.2f}")
        step_price["sub"].append(f"Nearest: {nearest_level.level_type.value.upper()} @ {nearest_level.price:.2f}")
        step_price["sub"].append(f"Proximity threshold: {proximity_pct*100:.1f}%")

    # ── Step 4: Absorption Check ──
    step_absorption = {
        "step": 4,
        "name": "Absorption",
        "status": "inactive",
        "icon": "🛡️",
        "detail": "Waiting for absorption at level",
        "sub": [],
    }
    has_absorption = False
    if trade and trade.absorption_signals:
        has_absorption = True
        step_absorption["status"] = "triggered"
        step_absorption["detail"] = f"{len(trade.absorption_signals)} absorption signal(s) detected"
        for sig in trade.absorption_signals:
            s = _serialize(sig)
            step_absorption["sub"].append(
                f"Str: {s.get('strength', 0):.0f} | Price: {s.get('price_level', 0):.2f} | {s.get('direction', '?')}"
            )
    elif at_level:
        step_absorption["status"] = "watching"
        step_absorption["detail"] = "Price at level — scanning for absorption patterns"

    # ── Step 5: Entry Decision ──
    step_entry = {
        "step": 5,
        "name": "Entry Decision",
        "status": "inactive",
        "icon": "🚪",
        "detail": "No entry conditions met",
        "sub": [],
    }
    if trade and trade.phase in ("absorption", "position_open", "break_even", "trailing"):
        phase_val = as_value(trade.phase)
        if phase_val in ("absorption", "position_open", "break_even", "trailing"):
            step_entry["status"] = "triggered"
            if trade.entry_price > 0:
                step_entry["detail"] = f"Entered {'LONG' if as_value(trade.direction) == 'buy' else 'SHORT'} @ {trade.entry_price:.2f}"
            else:
                step_entry["detail"] = "Absorption confirmed — awaiting position fill"
            step_entry["sub"].append(f"Phase: {phase_val}")
            if trade.entry_price:
                step_entry["sub"].append(f"Entry: {trade.entry_price:.2f}")
            if trade.stop_loss:
                step_entry["sub"].append(f"SL: {trade.stop_loss:.2f}")
            if trade.take_profit:
                step_entry["sub"].append(f"TP: {trade.take_profit:.2f}")
            if trade.rr_ratio:
                step_entry["sub"].append(f"R:R: {trade.rr_ratio:.1f}x")
    elif has_absorption:
        step_entry["status"] = "watching"
        step_entry["detail"] = "Absorption seen — evaluating composite score"
        score = system.aggregator.min_composite_score
        step_entry["sub"].append(f"Min score needed: {score}")

    # ── Step 6: Trade Management ──
    step_mgmt = {
        "step": 6,
        "name": "Trade Management",
        "status": "inactive",
        "icon": "⚙️",
        "detail": "No active trade to manage",
        "sub": [],
    }
    if trade:
        phase_val = as_value(trade.phase)
        if phase_val == "position_open":
            step_mgmt["status"] = "active"
            step_mgmt["detail"] = "Position open — waiting for initiative to move to BE"
            step_mgmt["sub"].append("Next: Initiative print → Break-Even trigger")
        elif phase_val == "break_even":
            step_mgmt["status"] = "active"
            step_mgmt["detail"] = "Break-even set — waiting for more initiative to trail"
            step_mgmt["sub"].append(f"BE Price: {trade.break_even_price:.2f}")
            step_mgmt["sub"].append("Next: Initiative print → Trail stop")
        elif phase_val == "trailing":
            step_mgmt["status"] = "active"
            step_mgmt["detail"] = f"Trailing stop @ {trade.trail_stop:.2f}"
            step_mgmt["sub"].append(f"Trail: {trade.trail_stop:.2f}")
            step_mgmt["sub"].append(f"Initiative signals: {len(trade.initiative_signals)}")
            step_mgmt["sub"].append("Next: More initiative → tighter trail | Exhaustion/Divergence → exit")
        elif phase_val == "closed":
            step_mgmt["status"] = "completed"
            step_mgmt["detail"] = f"Trade closed — PnL: {trade.pnl_ticks:.1f} ticks"
            if trade.notes:
                step_mgmt["sub"].append(f"Reason: {trade.notes}")

    # ── Build overall status ──
    if not bias:
        overall = "NO_DATA"
        reason = "No volume profile data — waiting for market data and profile computation"
    elif not bias.qualified_levels:
        overall = "NO_LEVELS"
        reason = "Profile computed but no levels qualified — flat/unclear market structure"
    elif not at_level and (not trade or trade.phase == TradePhase.CLOSED):
        overall = "WAITING_FOR_PRICE"
        reason = f"Levels ready but price ({current_price:.2f}) hasn't reached them — patience"
    elif at_level and not has_absorption and (not trade or trade.phase == TradePhase.CLOSED):
        overall = "AT_LEVEL_SCANNING"
        reason = f"Price at {nearest_level.level_type.value.upper()} — scanning for absorption patterns"
    elif trade and trade.phase == TradePhase.WATCHING:
        overall = "WATCHING"
        reason = f"Watching level @ {trade.qualified_level:.2f} for absorption"
    elif trade and trade.phase == TradePhase.ABSORPTION_DETECTED:
        overall = "ENTRY_READY"
        reason = "Absorption confirmed — entry signal active"
    elif trade and trade.phase == TradePhase.POSITION_OPEN:
        overall = "IN_TRADE"
        reason = "Position open — managing trade"
    elif trade and trade.phase == TradePhase.BREAK_EVEN:
        overall = "BREAK_EVEN"
        reason = "Break-even set — trailing mode pending"
    elif trade and trade.phase == TradePhase.TRAILING:
        overall = "TRAILING"
        reason = f"Trailing stop @ {trade.trail_stop:.2f}"
    else:
        overall = "IDLE"
        reason = "System active — monitoring"

    return {
        "symbol": symbol,
        "overall": overall,
        "reason": reason,
        "current_price": current_price,
        "steps": [step_profile, step_levels, step_price, step_absorption, step_entry, step_mgmt],
        "trade": _serialize(trade) if trade else None,
        "bias_direction": as_value(bias.direction, "neutral") if bias else "neutral",
        "bias_confidence": bias.confidence if bias else 0,
        "source": "engine",
    }


def _empty_strategy_status(symbol: str, reason: str):
    """Return empty strategy status."""
    return {
        "symbol": symbol,
        "overall": "OFFLINE",
        "reason": reason,
        "current_price": 0,
        "steps": [],
        "trade": None,
        "bias_direction": "neutral",
        "bias_confidence": 0,
        "source": "engine",
    }


@app.get("/api/orderbook/{symbol}")
async def get_orderbook(symbol: str, levels: int = Query(default=10, le=25)):
    """Get current orderbook state."""
    system = get_system()
    if not system:
        return _with_source(demo_data.demo_orderbook(symbol), "demo")

    pipeline = system.pipelines.get(symbol)
    if not pipeline:
        return JSONResponse({"error": f"Unknown symbol: {symbol}"}, status_code=404)

    tracker = pipeline.orderbook_tracker
    snapshot = tracker.latest_snapshot
    if not snapshot:
        return {"bids": [], "asks": [], "imbalance": 0.0, "source": "engine"}

    return {
        "timestamp_ms": snapshot.timestamp_ms,
        "bids": [
            {"price": b.price, "quantity": b.quantity}
            for b in snapshot.bids[:levels]
        ],
        "asks": [
            {"price": a.price, "quantity": a.quantity}
            for a in snapshot.asks[:levels]
        ],
        "best_bid": snapshot.best_bid,
        "best_ask": snapshot.best_ask,
        "mid_price": snapshot.mid_price,
        "spread": snapshot.spread,
        "imbalance": round(snapshot.imbalance_ratio(), 4),
        "source": "engine",
    }


@app.get("/api/delta/{symbol}")
async def get_delta(
    symbol: str,
    count: int = Query(default=500, le=5000),
    tf: int = Query(default=60, description="Timeframe in seconds"),
    range_s: int = Query(default=86400, alias="range", description="History range in seconds"),
):
    """Get cumulative delta history, aggregated to requested timeframe."""
    system = get_system()
    if not system:
        return demo_data.demo_delta(symbol, tf=tf, range_s=range_s)

    pipeline = system.pipelines.get(symbol)
    if not pipeline:
        return JSONResponse({"error": f"Unknown symbol: {symbol}"}, status_code=404)

    # Get raw candles
    raw_candles = pipeline.candle_builder.get_recent_candles(5000)

    if not raw_candles:
        return []

    # Filter by time range
    import time as _time
    now_s = _time.time()
    cutoff_ms = (now_s - range_s) * 1000
    raw_candles = [c for c in raw_candles if c.timestamp_ms >= cutoff_ms]

    base_interval = pipeline.candle_builder.interval_ms // 1000
    tf_seconds = max(tf, base_interval)
    tf_ms = tf_seconds * 1000

    # Aggregate delta per TF bucket
    buckets = {}
    for c in raw_candles:
        bucket = (c.timestamp_ms // tf_ms) * tf_ms
        if bucket not in buckets:
            buckets[bucket] = 0.0
        buckets[bucket] += c.delta

    # Build cumulative delta series
    sorted_buckets = sorted(buckets.items())
    cum_delta = 0.0
    result = []
    for ts_ms, bar_delta in sorted_buckets:
        cum_delta += bar_delta
        result.append({
            "time": ts_ms / 1000,
            "value": round(cum_delta, 2),
            "bar_delta": round(bar_delta, 2),
        })
    return result


# ──────────────────────────────────────────────
# Live payload builders
#
# Policy for the live/demo boundary:
#   * an endpoint whose payload is a MAPPING carries "source": "engine"|"demo";
#   * an endpoint whose payload is a LIST (tape, footprint, candles, delta,
#     signals, instruments, scanner, markers) cannot carry a top-level key
#     without breaking the JS, so the live/demo truth for those comes from
#     /api/control/live-status (see engine.live_status()).
# ──────────────────────────────────────────────

def _with_source(payload, source: str):
    """Tag a mapping payload with its data source; pass lists through untouched."""
    if isinstance(payload, dict):
        payload = dict(payload)
        payload["source"] = source
    return payload


def _ms_to_utc_midnight() -> int:
    """Milliseconds until the next UTC day rollover (session countdown)."""
    from datetime import datetime, time, timedelta, timezone

    now = datetime.now(timezone.utc)
    midnight = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    return int((midnight + timedelta(days=1) - now).total_seconds() * 1000)


def _live_tape_rows(ticks) -> list:
    """Demo-shaped tape rows from the pipeline's bounded tick buffer."""
    return [
        {
            "time": t.timestamp_ms / 1000,
            "price": round(t.price, 6),
            "size": round(t.size, 6),
            "side": as_value(t.side),
        }
        for t in ticks
    ]


def _query_value(value: Any, default: Any, cast) -> Any:
    """Coerce a handler parameter that may still be FastAPI's `Query(...)` object.

    Endpoints here are also called directly (the test suite does it, and so does the replay
    path), and in that case an unset parameter arrives as the `Query` marker rather than its
    default. Falling back to the documented default keeps both call styles honest.
    """
    if value is None or isinstance(value, (int, float, str, bool)):
        try:
            return cast(value)
        except (TypeError, ValueError):
            return default
    return default


def _annotate_footprint_bars(bars: list, mode: str = "same_price", threshold: float = 3.0,
                             equal_tolerance: float = 0.0) -> list:
    """Add the Numbers-Bars analysis pack to serialised footprint bars, in place.

    One implementation for live, stored and demo bars: `analyse_levels` works on the
    price→(bid, ask) mapping every path already produces, so the demo panels and the live
    panels show the same numbers for the same shape of data.
    """
    from orderflow_system.analytics.footprint import analyse_levels

    for bar in bars:
        if not isinstance(bar, dict):
            continue
        rows = {}
        for level in bar.get("levels") or []:
            try:
                rows[float(level.get("price"))] = (float(level.get("bid") or 0.0),
                                                   float(level.get("ask") or 0.0))
            except (TypeError, ValueError):
                continue
        bar["calc"] = analyse_levels(rows, tick_size=0.0, threshold=threshold, mode=mode,
                                     equal_tolerance=equal_tolerance)
    return bars


def _live_footprint_bars(pipeline, limit: int = 200, mode: str = "same_price",
                         threshold: float = 3.0, equal_tolerance: float = 0.0) -> list:
    """Demo-shaped footprint bars from the pipeline's footprint history."""
    history = list(getattr(pipeline.footprint_engine, "history", []) or [])[-limit:]
    bars = []
    for bar in history:
        levels = [
            {
                "price": float(price),
                "bid": round(lv.bid_volume, 6),
                "ask": round(lv.ask_volume, 6),
            }
            for price, lv in sorted(bar.levels.items())
        ]
        poc = max(levels, key=lambda lv: lv["bid"] + lv["ask"])["price"] if levels else None
        bars.append({
            "time": bar.timestamp_ms / 1000,
            "open": round(bar.open, 6),
            "high": round(bar.high, 6),
            "low": round(bar.low, 6),
            "close": round(bar.close, 6),
            "poc": poc,
            "levels": levels,
        })
    return _annotate_footprint_bars(bars, mode=mode, threshold=threshold,
                                    equal_tolerance=equal_tolerance)


def _market_state(candles) -> str:
    """Documented heuristic for the microstructure snapshot: TRENDING when the recent
    range and net delta lean the same way, COMPRESSION when the range is tiny,
    REBALANCING otherwise. It is a summary of what the tape did, not advice."""
    closes = [c.close for c in candles if c.close]
    if len(closes) < 3:
        return "REBALANCING"
    last = closes[-1] or 1.0
    rng_pct = (max(closes) - min(closes)) / last * 100.0
    net = sum(c.delta for c in candles)
    volume = sum(c.volume for c in candles) or 1.0
    tilt = net / volume
    if rng_pct >= 0.5 and abs(tilt) >= 0.15:
        return "TRENDING"
    if rng_pct <= 0.15:
        return "COMPRESSION"
    return "REBALANCING"


def _live_microstructure(system, pipeline) -> dict:
    """Microstructure snapshot built from live engine state, in the demo payload's shape."""
    candles = pipeline.candle_builder.get_recent_candles(20)
    signals = system.recent_signals(pipeline.symbol, 20) if hasattr(system, "recent_signals") else []

    by_type: dict[str, list] = {}
    for sig in signals:
        by_type.setdefault(as_value(sig.signal_type), []).append(sig)

    last_abs = by_type.get("absorption", [None])[-1]
    last_init = by_type.get("initiative_auction", [None])[-1]
    divergence = by_type.get("delta_divergence", [])
    exhaustion = by_type.get("exhaustion", [])
    session = as_value(getattr(pipeline.config.volume_profile, "session", None), "24/7")
    net = sum(c.delta for c in candles)

    return {
        "source": "engine",
        "marketState": _market_state(candles),
        "session": {"name": session, "remaining": _ms_to_utc_midnight()},
        "absorption": {
            "level": round(last_abs.price_level, 6) if last_abs else None,
            "attempts": int(last_abs.details.get("attempts", 0)) if last_abs else 0,
            "strength": round(last_abs.strength) if last_abs else 0,
            "side": as_value(last_abs.direction, "neutral") if last_abs else "neutral",
        },
        "initiative": {
            "count": len(by_type.get("initiative_auction", [])),
            "direction": ("up" if as_value(last_init.direction) == "buy" else "down") if last_init else "none",
            "strength": round(last_init.strength) if last_init else 0,
        },
        "delta": {
            "cumulative": round(pipeline.delta_engine.cumulative_delta, 1),
            "direction": (1 if net > 0 else -1 if net < 0 else 0),
            "divergence": bool(divergence),
        },
        "exhaustion": round(exhaustion[-1].strength) if exhaustion else 0,
        "patterns": [
            {
                "type": as_value(sig.signal_type),
                "confidence": round(min(max(sig.strength / 100.0, 0.0), 0.99), 2),
                "price": round(sig.price_level, 6),
            }
            for sig in signals[-4:]
        ],
    }


@app.get("/api/footprint/{symbol}")
async def get_footprint(
    symbol: str,
    tf: int = Query(default=60, description="Timeframe in seconds"),
    range_s: int = Query(default=86400, alias="range", description="History range in seconds"),
    mode: str = Query(default="same_price", pattern="^(same_price|diagonal)$",
                      description="Imbalance convention: same price row, or diagonal (the conventional)"),
    threshold: float = Query(default=3.0, ge=1.0, le=50.0, description="Imbalance ratio"),
    equal_tolerance: float = Query(default=0.0, ge=0.0, le=1.0,
                                   description="Relative tolerance for the equal-side highlight"),
):
    """Get footprint chart data with bid/ask at each price level.

    Each bar carries `calc` — the Numbers-Bars analysis pack (delta, POC share, extremes,
    imbalance rows in the requested convention, equal-side rows). See analytics/footprint.py.
    """
    tf = _query_value(tf, 60, int)
    range_s = _query_value(range_s, 86400, int)
    mode = _query_value(mode, "same_price", str)
    threshold = _query_value(threshold, 3.0, float)
    equal_tolerance = _query_value(equal_tolerance, 0.0, float)
    if mode not in ("same_price", "diagonal"):
        mode = "same_price"
    annotate = {"mode": mode, "threshold": threshold, "equal_tolerance": equal_tolerance}
    system = get_system()
    if not system:
        return _annotate_footprint_bars(demo_data.demo_footprint(symbol, tf=tf, range_s=range_s), **annotate)
    pipeline = system.pipelines.get(symbol)
    if not pipeline:
        return JSONResponse({"error": f"Unknown symbol: {symbol}"}, status_code=404)
    bars = _live_footprint_bars(pipeline, mode=mode, threshold=threshold,
                                equal_tolerance=equal_tolerance)
    if not bars:
        # Engine running but no candle has closed yet. Fill from the demo generator
        # only when it actually models this symbol — for anything else (a venue symbol
        # added from the catalogue) an invented price is worse than an empty chart
        # while it warms up, and the UI shows its warming state from live-status.
        if not demo_data.models_symbol(symbol):
            return []
        return _annotate_footprint_bars(demo_data.demo_footprint(symbol, tf=tf, range_s=range_s), **annotate)
    return bars


@app.get("/api/tape/{symbol}")
async def get_tape(symbol: str, count: int = Query(default=60, le=200)):
    """Get recent time & sales trades for initial tape fill."""
    system = get_system()
    if not system:
        return demo_data.demo_tape_trades(symbol, count=count)
    ticks = system.recent_ticks(symbol, count=count) if hasattr(system, "recent_ticks") else []
    if not ticks:
        # Engine running but nothing streamed for this symbol yet → demo fill, but only
        # for symbols the generator models (see get_footprint).
        if not demo_data.models_symbol(symbol):
            return []
        return demo_data.demo_tape_trades(symbol, count=count)
    return _live_tape_rows(ticks)


@app.get("/api/microstructure/{symbol}")
async def get_microstructure(symbol: str):
    """Get microstructure snapshot (absorption, initiative, delta, exhaustion, patterns)."""
    system = get_system()
    if not system:
        return _with_source(demo_data.demo_microstructure(symbol), "demo")
    pipeline = system.pipelines.get(symbol)
    if not pipeline:
        return demo_data.demo_microstructure(symbol)
    snap = _live_microstructure(system, pipeline)
    if snap["delta"]["cumulative"] == 0 and not snap["patterns"] and not pipeline.candle_builder.current_candle:
        # No live state yet → demo fill, tagged as demo.
        return _with_source(demo_data.demo_microstructure(symbol), "demo")
    return snap


@app.get("/api/stats")
async def get_stats():
    """Get system-wide statistics."""
    system = get_system()
    if not system:
        return {
            "data_source": "demo",
            "ws_clients": ws_manager.client_count,
            "instruments": demo_data.demo_instruments(),
            "running": True,
            "source": "demo",
        }

    instruments = []
    for sym, pipeline in system.pipelines.items():
        instruments.append(pipeline.stats)

    return {
        "data_source": system.data_source.value,
        "ws_clients": ws_manager.client_count,
        "instruments": instruments,
        "running": system._running,
        "source": "engine",
    }


# ──────────────────────────────────────────────
# WebSocket Endpoint
# ──────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """
    Real-time data stream.
    Clients receive all broadcasts on all channels.
    """
    await ws_manager.connect(ws)
    try:
        # Send initial state snapshot
        system = get_system()
        if system:
            await _send_initial_state(ws, system)

        # Keep connection alive — listen for client messages (pings, etc.)
        while True:
            data = await ws.receive_text()
            # Could handle subscriptions/commands here
            if data == "ping":
                await ws.send_text('{"channel":"pong","data":{}}')
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"WebSocket error: {e}")
    finally:
        await ws_manager.disconnect(ws)


async def _send_initial_state(ws: WebSocket, system):
    """Send current state snapshot to a newly connected client."""
    import json, time

    for sym, pipeline in system.pipelines.items():
        # Send current stats
        stats = pipeline.stats
        trade = system.aggregator.get_active_trade(sym)
        stats["trade_phase"] = trade.phase.value if trade else "none"

        await ws.send_text(json.dumps({
            "channel": "stats",
            "symbol": sym,
            "data": _serialize(stats),
            "ts": int(time.time() * 1000),
        }))

        # Send current bias
        bias = pipeline.profile_framing.current_bias
        if bias:
            await ws.send_text(json.dumps({
                "channel": "bias",
                "symbol": sym,
                "data": _serialize(bias),
                "ts": int(time.time() * 1000),
            }))

        # Send trade state
        if trade:
            await ws.send_text(json.dumps({
                "channel": "trade_state",
                "symbol": sym,
                "data": _serialize(trade),
                "ts": int(time.time() * 1000),
            }))
