"""
Demo data generator for standalone dashboard mode.
Provides realistic-looking orderflow data when no live feed is connected.
"""
import math
import random
import time

# ── Seed for reproducibility within a session ──
_session_seed = int(time.time()) % 10000
random.seed(_session_seed)


def _stable_rng(symbol: str, tf: int = 0, range_s: int = 0) -> random.Random:
    """Return a Random instance seeded by symbol + time-window.

    The time-window reseeds every 60 seconds so the data drifts
    slowly but repeated calls within the same minute return identical data.
    """
    window = int(time.time()) // 60  # changes every 60 s
    seed = hash((symbol, tf, range_s, window, _session_seed))
    return random.Random(seed)

# ── Base prices for instruments (full MT5 coverage) ──
_BASE_PRICES = {
    # Forex (main pairs)
    "EURUSD": 1.0785, "GBPUSD": 1.2615, "USDJPY": 152.30,
    "AUDUSD": 0.6540, "USDCAD": 1.3520, "USDCHF": 0.8850, "NZDUSD": 0.6120,
    "EURGBP": 0.8550, "EURJPY": 164.20, "GBPJPY": 192.10,
    # Metals
    "XAUUSDT": 2920.0, "XAGUSD": 32.50,
    # Indices
    "NAS100USDT": 21450.0, "SP500": 6100.0, "DJ30": 44200.0,
    "DAX40": 18900.0, "UK100": 8350.0,
    # Crypto
    "BTCUSDT": 98500.0, "ETHUSDT": 2680.0, "SOLUSDT": 195.0,
    "XRPUSDT": 2.45, "BNBUSDT": 680.0,
    # Stocks
    "AAPL": 232.0, "TSLA": 365.0, "AMZN": 228.0, "MSFT": 415.0,
    "NVDA": 138.0, "META": 680.0, "GOOGL": 185.0,
}

_TICK_SIZES = {
    # Forex
    **{s: 0.0001 for s in ["EURUSD","GBPUSD","AUDUSD","NZDUSD","USDCAD","USDCHF","EURGBP"]},
    **{s: 0.01 for s in ["USDJPY","EURJPY","GBPJPY"]},
    # Metals
    "XAUUSDT": 0.10, "XAGUSD": 0.01,
    # Indices
    "NAS100USDT": 0.5, "SP500": 0.25, "DJ30": 1.0, "DAX40": 0.5, "UK100": 0.5,
    # Crypto
    "BTCUSDT": 0.5, "ETHUSDT": 0.1, "SOLUSDT": 0.01, "XRPUSDT": 0.0001, "BNBUSDT": 0.1,
    # Stocks
    **{s: 0.01 for s in ["AAPL","TSLA","AMZN","MSFT","NVDA","META","GOOGL"]},
}


def _base_price(symbol: str) -> float:
    return _BASE_PRICES.get(symbol, 1000.0)


def _tick_size(symbol: str) -> float:
    return _TICK_SIZES.get(symbol, 0.5)


def _gen_price_walk(base: float, n: int, volatility: float = 0.001, rng: random.Random | None = None) -> list:
    """Generate a random-walk price series."""
    r = rng or random
    prices = [base]
    for _ in range(n - 1):
        change = base * volatility * r.gauss(0, 1)
        prices.append(prices[-1] + change)
    return prices


# ════════════════════════════════════════════
# Public API — called by app.py endpoints
# ════════════════════════════════════════════


def demo_instruments():
    """Return a list of demo instruments."""
    rng = _stable_rng("__instruments__")
    now_ms = int(time.time() * 1000)
    result = []
    for sym, price in _BASE_PRICES.items():
        drift = price * rng.uniform(-0.002, 0.002)
        result.append({
            "symbol": sym,
            "price": round(price + drift, 5),
            "volume_24h": rng.randint(50000, 500000),
            "tick_count": rng.randint(10000, 100000),
            "candle_count": rng.randint(200, 1000),
            "data_source": "demo",
            "trade_phase": "none",
            "trade_direction": "none",
            "last_update_ms": now_ms,
        })
    return result


def demo_candles(symbol: str, tf: int = 60, range_s: int = 86400):
    """Generate realistic OHLC candle data — stable per symbol/tf/range."""
    rng = _stable_rng(symbol, tf, range_s)
    base = _base_price(symbol)
    tick = _tick_size(symbol)
    now = int(time.time())
    start = now - range_s
    n_candles = range_s // tf

    # Limit to reasonable number
    n_candles = min(n_candles, 1500)

    vol = 0.0004 if base > 1000 else 0.0008
    walk = _gen_price_walk(base, n_candles + 1, vol, rng)

    candles = []
    for i in range(n_candles):
        t = start + i * tf
        o = walk[i]
        c = walk[i + 1]
        h = max(o, c) + abs(rng.gauss(0, base * vol * 0.5))
        l = min(o, c) - abs(rng.gauss(0, base * vol * 0.5))
        volume = rng.randint(50, 800)
        delta = rng.randint(-200, 200)

        candles.append({
            "time": t,
            "open": round(o, 5),
            "high": round(h, 5),
            "low": round(l, 5),
            "close": round(c, 5),
            "volume": volume,
            "delta": delta,
        })

    return candles


def demo_delta(symbol: str, tf: int = 60, range_s: int = 86400):
    """Generate cumulative delta data — stable per symbol/tf/range."""
    rng = _stable_rng(symbol, tf, range_s)
    now = int(time.time())
    start = now - range_s
    n = min(range_s // tf, 1500)

    cum = 0
    result = []
    for i in range(n):
        bar_delta = rng.gauss(0, 50)
        cum += bar_delta
        result.append({
            "time": start + i * tf,
            "value": round(cum, 1),
            "bar_delta": round(bar_delta, 1),
        })
    return result


def demo_volume_profile(symbol: str):
    """Generate a realistic volume profile."""
    rng = _stable_rng(symbol, 0, 0)
    base = _base_price(symbol)
    tick = _tick_size(symbol)
    n_levels = 60

    # Bell-curve volume distribution (P-shape / D-shape / b-shape)
    shape = rng.choice(["P-shape", "D-shape", "b-shape", "Balanced"])
    center = base + rng.uniform(-base * 0.002, base * 0.002)

    volume_at_price = {}
    prices = []
    for i in range(n_levels):
        price = round(center - (n_levels // 2 - i) * tick, 5)
        prices.append(price)

        # Gaussian volume distribution
        dist = abs(i - n_levels // 2) / (n_levels / 4)
        vol = int(max(10, 500 * math.exp(-dist * dist) + rng.randint(5, 50)))
        volume_at_price[str(price)] = vol

    # Find POC (max volume)
    poc_price = max(volume_at_price, key=volume_at_price.get)
    poc = float(poc_price)

    # Value area = 70% of volume
    sorted_levels = sorted(volume_at_price.items(), key=lambda x: x[1], reverse=True)
    total_vol = sum(v for _, v in sorted_levels)
    va_vol = 0
    va_prices = []
    for p, v in sorted_levels:
        va_vol += v
        va_prices.append(float(p))
        if va_vol >= total_vol * 0.7:
            break

    vah = max(va_prices)
    val = min(va_prices)

    return [{
        "poc": round(poc, 5),
        "vah": round(vah, 5),
        "val": round(val, 5),
        "total_volume": total_vol,
        "shape": shape,
        "poc_position_pct": 50.0 + rng.uniform(-15, 15),
        "lvn_levels": [round(prices[n_levels // 4], 5), round(prices[3 * n_levels // 4], 5)],
        "volume_at_price": volume_at_price,
    }]


def demo_bias(symbol: str):
    """Generate daily bias data."""
    rng = _stable_rng(symbol, 0, 1)
    base = _base_price(symbol)
    tick = _tick_size(symbol)
    direction = rng.choice(["long", "short", "neutral"])
    confidence = rng.randint(40, 95)
    shape = rng.choice(["P-shape", "D-shape", "b-shape", "Balanced"])

    poc = round(base + rng.uniform(-base * 0.001, base * 0.001), 5)
    spread = base * 0.003
    vah = round(poc + spread, 5)
    val = round(poc - spread, 5)

    levels = []
    n_levels = rng.randint(1, 4)
    for _ in range(n_levels):
        lv_dir = rng.choice(["buy", "sell"])
        lv_price = round(base + rng.uniform(-base * 0.005, base * 0.005), 5)
        levels.append({
            "price": lv_price,
            "direction": lv_dir,
            "level_type": rng.choice(["POC", "VAH", "VAL", "LVN", "Composite"]),
            "strength": rng.randint(50, 100),
        })

    return {
        "direction": direction,
        "confidence": confidence,
        "profile_shape": shape,
        "poc": poc,
        "vah": vah,
        "val": val,
        "qualified_levels": levels,
        "notes": f"Demo bias — {shape} profile detected, {direction} bias at {confidence}%",
    }


def demo_orderbook(symbol: str):
    """Generate a realistic orderbook snapshot."""
    rng = _stable_rng(symbol, 0, 2)
    base = _base_price(symbol)
    tick = _tick_size(symbol)
    n_levels = 20

    mid = base + rng.uniform(-tick * 2, tick * 2)
    bids = []
    asks = []

    for i in range(n_levels):
        bid_price = round(mid - (i + 1) * tick, 5)
        ask_price = round(mid + (i + 1) * tick, 5)
        bid_size = rng.randint(5, 300)
        ask_size = rng.randint(5, 300)

        # Add some thin levels (sweep targets)
        if rng.random() < 0.15:
            bid_size = rng.randint(1, 5)
        if rng.random() < 0.15:
            ask_size = rng.randint(1, 5)

        bids.append({"price": bid_price, "size": bid_size})
        asks.append({"price": ask_price, "size": ask_size})

    total_bid = sum(b["size"] for b in bids)
    total_ask = sum(a["size"] for a in asks)

    return {
        "snapshot": True,
        "bids": bids,
        "asks": asks,
        "last_price": round(mid, 5),
        "spread": round(tick, 5),
        "bid_total": total_bid,
        "ask_total": total_ask,
        "imbalance": round(total_bid / max(total_bid + total_ask, 1) * 100, 1),
    }


def demo_strategy_status(symbol: str):
    """Generate a strategy status with step checklist."""
    rng = _stable_rng(symbol, 0, 3)
    base = _base_price(symbol)
    direction = rng.choice(["buy", "sell"])
    bias_dir = "long" if direction == "buy" else "short"

    # Pick a random phase
    phases = [
        ("WAITING_FOR_PRICE", 2),
        ("AT_LEVEL_SCANNING", 3),
        ("WATCHING", 4),
        ("ENTRY_READY", 5),
    ]
    overall, steps_done = rng.choice(phases)

    steps = [
        {"name": "Volume Profile", "icon": "📊", "status": "completed", "detail": "D-shape identified, POC at " + str(round(base, 1))},
        {"name": "Daily Bias", "icon": "🧭", "status": "completed", "detail": f"{bias_dir.upper()} bias — confidence 78%"},
        {"name": "Qualified Level", "icon": "📍", "status": "completed" if steps_done >= 3 else "pending",
         "detail": f"{'VAH rejection zone at ' + str(round(base * 1.002, 1)) if steps_done >= 3 else 'Scanning for level...'}"},
        {"name": "Orderflow Confirm", "icon": "🔬", "status": "completed" if steps_done >= 4 else "pending",
         "detail": "Absorption detected (3 attempts)" if steps_done >= 4 else "Waiting for orderflow signal..."},
        {"name": "Entry Trigger", "icon": "🎯", "status": "active" if steps_done >= 5 else "pending",
         "detail": "Initiative buying confirmed" if steps_done >= 5 else "Waiting for trigger..."},
        {"name": "Trade Management", "icon": "⚙️", "status": "pending", "detail": "Not in trade"},
    ]

    return {
        "overall": overall,
        "reason": f"Price approaching qualified level — {overall.replace('_', ' ').lower()}",
        "steps": steps[:6],
        "bias_direction": bias_dir,
        "bias_confidence": rng.randint(60, 95),
        "current_price": round(base, 5),
        "trade": None,
    }


def demo_scanner():
    """Generate scanner data for all demo instruments."""
    rng = _stable_rng("__scanner__", 0, 0)
    results = []
    statuses = ["WAITING_FOR_PRICE", "AT_LEVEL_SCANNING", "WATCHING",
                "ENTRY_READY", "IDLE", "WAITING_FOR_PRICE"]

    for i, sym in enumerate(_BASE_PRICES):
        overall = statuses[i % len(statuses)]
        steps_done = rng.randint(0, 5)
        bias_dir = rng.choice(["buy", "sell", "neutral"])

        results.append({
            "symbol": sym,
            "overall": overall,
            "reason": f"Demo — {overall.replace('_', ' ').lower()}",
            "priority": rng.randint(10, 90),
            "steps_done": steps_done,
            "steps_total": 6,
            "bias_direction": bias_dir,
            "bias_confidence": rng.randint(30, 95),
            "current_price": round(_base_price(sym), 5),
        })

    results.sort(key=lambda x: x["priority"], reverse=True)
    return results


def demo_markers(symbol: str):
    """Generate a few chart markers for demo mode."""
    rng = _stable_rng(symbol, 0, 4)
    base = _base_price(symbol)
    now = int(time.time())
    markers = []

    types = [
        ("ABS", "#26a69a", "arrowUp", "belowBar"),
        ("INIT", "#66bb6a", "arrowUp", "belowBar"),
        ("SWEEP", "#ab47bc", "arrowDown", "aboveBar"),
        ("EXHAUST", "#ffeb3b", "circle", "aboveBar"),
        ("DIV", "#ff9800", "circle", "aboveBar"),
    ]

    for i in range(8):
        t, color, shape, pos = rng.choice(types)
        markers.append({
            "time": now - rng.randint(300, 80000),
            "position": pos,
            "color": color,
            "shape": shape,
            "text": t,
        })

    markers.sort(key=lambda x: x["time"])
    return markers


def demo_footprint(symbol: str, tf: int = 60, range_s: int = 86400):
    """Generate footprint chart data with bid/ask at each price level."""
    rng = _stable_rng(symbol, tf, range_s)
    base = _base_price(symbol)
    tick = _tick_size(symbol)
    now = int(time.time())
    start = now - range_s
    n_bars = min(range_s // tf, 200)

    vol = 0.0004 if base > 1000 else 0.0008
    walk = _gen_price_walk(base, n_bars + 1, vol, rng=rng)
    bars = []

    for i in range(n_bars):
        t = start + i * tf
        o = walk[i]
        c = walk[i + 1]
        h = max(o, c) + abs(rng.gauss(0, base * vol * 0.5))
        l = min(o, c) - abs(rng.gauss(0, base * vol * 0.5))

        # Generate levels from low to high at tick increments
        n_levels = max(3, int((h - l) / tick))
        n_levels = min(n_levels, 60)  # cap
        levels = []
        max_vol = 0
        poc_price = None

        for j in range(n_levels):
            price = round(l + j * tick, 5)
            # Volume distribution — more near open/close, absorption zones
            dist_from_mid = abs(price - (o + c) / 2) / max(h - l, tick)
            base_vol = max(1, int(80 * math.exp(-dist_from_mid * 2)))

            # Simulate bid/ask imbalance
            if price < (o + c) / 2:
                bid = base_vol + rng.randint(0, 40)
                ask = max(1, base_vol - rng.randint(0, 20))
            else:
                bid = max(1, base_vol - rng.randint(0, 20))
                ask = base_vol + rng.randint(0, 40)

            # Random absorption spikes
            if rng.random() < 0.08:
                bid = bid * rng.randint(3, 6)
            if rng.random() < 0.08:
                ask = ask * rng.randint(3, 6)

            total = bid + ask
            if total > max_vol:
                max_vol = total
                poc_price = price

            levels.append({"price": price, "bid": bid, "ask": ask})

        bars.append({
            "time": t,
            "open": round(o, 5),
            "high": round(h, 5),
            "low": round(l, 5),
            "close": round(c, 5),
            "poc": poc_price,
            "levels": levels,
        })

    return bars


def demo_tape_trades(symbol: str, count: int = 60):
    """Generate recent time & sales trades for initial tape fill."""
    rng = _stable_rng(symbol, 0, 5)
    base = _base_price(symbol)
    tick = _tick_size(symbol)
    now = time.time()
    trades = []
    price = base
    for i in range(count):
        price += tick * rng.choice([-2, -1, -1, 0, 1, 1, 2])
        side = rng.choice(["buy", "sell"])
        size = rng.randint(1, 50)
        # occasional big trades
        if rng.random() < 0.08:
            size = rng.randint(80, 500)
        trades.append({
            "time": now - (count - i) * rng.uniform(0.3, 2.0),
            "price": round(price, 5),
            "size": size,
            "side": side,
        })
    return trades


def demo_microstructure(symbol: str):
    """Generate a complete microstructure snapshot for initial panel fill."""
    rng = _stable_rng(symbol, 0, 6)
    base = _base_price(symbol)
    direction = rng.choice(["buy", "sell"])
    market_state = rng.choice(["TRENDING", "COMPRESSION", "REBALANCING"])
    sessions = {
        "London Open": 3600000 * 2,
        "NY Open": 3600000 * 4,
        "NY AM": 3600000 * 3,
        "London PM": 3600000 * 1,
        "Asia": 3600000 * 6,
    }
    session_name = rng.choice(list(sessions.keys()))
    return {
        "marketState": market_state,
        "session": {
            "name": session_name,
            "remaining": sessions[session_name],
        },
        "absorption": {
            "level": round(base + rng.uniform(-base * 0.001, base * 0.001), 5),
            "attempts": rng.randint(1, 4),
            "strength": rng.randint(30, 95),
            "side": direction,
        },
        "initiative": {
            "count": rng.randint(0, 5),
            "direction": "up" if direction == "buy" else "down",
            "strength": rng.randint(40, 90),
        },
        "delta": {
            "cumulative": round(rng.uniform(-5000, 5000), 1),
            "direction": rng.uniform(-1, 1),
            "divergence": rng.random() < 0.2,
        },
        "exhaustion": rng.randint(10, 80),
        "patterns": [
            {
                "type": rng.choice(["absorption", "initiative", "exhaustion", "sweep", "divergence"]),
                "confidence": round(rng.uniform(0.5, 0.95), 2),
                "price": round(base + rng.uniform(-base * 0.002, base * 0.002), 5),
            }
            for _ in range(rng.randint(1, 4))
        ],
    }


def demo_signals():
    """Generate institutional-grade demo signals with deep trade analysis."""
    now = int(time.time() * 1000)
    signals = []

    # ── Detailed pattern library with full narrative context ──
    _setups = [
        {
            "pattern": "Bid Absorption",
            "signal_type": "absorption",
            "narrative": "Institutional buyers are defending {price:.2f} with repeated absorption. {abscount} rejection attempts in the last {minutes}min — each time sellers hit the bid, resting limit orders immediately refill. This is classic accumulation behavior at a key demand zone.",
            "thesis": "Large passive buyers are accumulating. Once the selling pressure is exhausted, expect an aggressive markup move as trapped shorts cover.",
            "edge": "Aggressive sellers are being absorbed at the bid, creating a floor. The orderbook shows {bookimb}% bid-heavy imbalance. Delta is confirming net buying pressure despite the flat price — this divergence suggests hidden accumulation.",
            "invalidation": "Setup fails if {sl:.2f} breaks on volume > 2x average, indicating absorption wall has been removed and genuine supply is present.",
            "htf_context": "HTF context: {htf_bias} on the {htf_tf} with price {htf_position} of the value area. {poc_context}",
        },
        {
            "pattern": "Initiative Auction",
            "signal_type": "initiative_auction",
            "narrative": "Aggressive directional buying detected at {price:.2f}. Market orders are overwhelming the ask side — {init_count} initiative sweeps in the last {minutes}min. Order flow shows {delta_dir} delta acceleration with zero absorption resistance above.",
            "thesis": "Smart money is initiating a move. Market-order aggression + thin liquidity above = high probability of follow-through. The auction is being driven, not responding.",
            "edge": "Initiative buyers are lifting every ask level aggressively. The footprint shows {delta_val:+.0f} net delta in the most recent bars with ask-side depletion. This is not just buying — it's urgent, informed buying that sweeps through resting orders.",
            "invalidation": "Watch for exhaustion candle (long upper wick, declining delta). If initiative volume drops >50% within 3 bars, the move may stall.",
            "htf_context": "HTF alignment: {htf_bias} on {htf_tf}. Price breaking out of {htf_position}, confirmed by higher-timeframe delta momentum.",
        },
        {
            "pattern": "Selling Exhaustion",
            "signal_type": "exhaustion",
            "narrative": "Selling pressure is dying at {price:.2f}. Despite making new lows, each successive push has declining delta: {delta_seq}. Volume is dropping on downside tests — sellers are losing conviction.",
            "thesis": "Diminishing seller follow-through after multiple downside tests = exhaustion. The market is running out of sellers at this level. Expect mean reversion as shorts take profit and new buyers step in.",
            "edge": "Three-test exhaustion pattern: each low is made on declining delta and volume. The delta divergence ({delta_div_pct}% weaker on last push vs first) indicates seller capitulation. Footprint shows ask volume shifting from initiative to responsive.",
            "invalidation": "If fresh initiative selling appears with accelerating delta on the 4th push, exhaustion thesis is negated — treat as breakdown.",
            "htf_context": "Higher timeframe: {htf_bias} with price at {htf_position}. {poc_context} Exhaustion at this level is consistent with HTF demand.",
        },
        {
            "pattern": "Liquidity Sweep",
            "signal_type": "book_sweep",
            "narrative": "Stop-hunt complete at {price:.2f}. Price pierced below {sweep_level:.2f} to trigger clustered stops, then immediately reversed with {reversal_vol} contracts of aggressive buying. Classic institutional liquidity grab.",
            "thesis": "Smart money engineered a liquidity sweep below the obvious support to fill their orders. The immediate reversal with high volume confirms this was a manufactured move, not a genuine breakdown.",
            "edge": "The sweep cleared {stops_cleared} stops at {sweep_level:.2f} and the bid immediately reloaded with {reload_vol} contracts. The V-shaped reversal candle with positive delta ({sweep_delta:+.0f}) confirms aggressive re-entry. Book imbalance flipped from {pre_imb}% ask to {post_imb}% bid within seconds.",
            "invalidation": "If price returns to the sweep low within 15min, the liquidity engineered thesis is invalid — real supply exists below.",
            "htf_context": "HTF positioning: {htf_bias} with sweep occurring at {htf_position}. This level aligns with {poc_context}",
        },
        {
            "pattern": "Delta Divergence",
            "signal_type": "delta_divergence",
            "narrative": "Bearish delta divergence at {price:.2f}. Price made a new high but cumulative delta is {delta_val:+.0f} — {delta_pct}% lower than the previous swing high. Buyers are losing control despite higher prices.",
            "thesis": "Divergence between price and orderflow is an early warning of trend exhaustion. Smart money is distributing into the rally — selling into strength while retail chases the breakout.",
            "edge": "Three indicators confirm distribution: (1) Declining delta on new highs, (2) Increasing ask-side volume in the footprint, (3) Bid depth withdrawing from {depth_from:.2f}-{depth_to:.2f} range. The composite signal has been historically reliable at VP extremes.",
            "invalidation": "Divergence thesis is invalidated if delta accelerates positive on a fresh breakout with initiative buying above {tp:.2f}.",
            "htf_context": "HTF: {htf_bias}. Price is at {htf_position} — a common distribution zone. {poc_context}",
        },
        {
            "pattern": "Composite POC Bounce",
            "signal_type": "poc_bounce",
            "narrative": "Price is testing the composite POC at {poc_level:.2f} — the highest volume node over {days}D. This level has attracted {poc_reactions} reactions in the last 5 sessions with an average bounce of {poc_avg_bounce:.1f}%.",
            "thesis": "The composite POC is 'fair value' — where the most business was transacted. Price tends to rotate around this level. A reaction here with bid absorption confirmation suggests value-buyers are defending the level.",
            "edge": "The POC at {poc_level:.2f} has a volume node of {poc_volume} contracts. The current test shows {abscount} absorption events with bid-side delta strengthening. The footprint profile shows responsive buying appearing at each POC test — institutions are re-accumulating at fair value.",
            "invalidation": "If the POC breaks with initiative selling and delta acceleration, the value area is shifting. Expect a rotation to VAL at {val_level:.2f}.",
            "htf_context": "HTF trend: {htf_bias}. The composite POC at {htf_position}. {poc_context}",
        }
    ]

    _sessions = [
        {"name": "London Open", "detail": "High liquidity, typically large directional moves as European institutions set positioning"},
        {"name": "NY Open", "detail": "Peak volatility as US institutions react to overnight flow and European positioning"},
        {"name": "NY AM", "detail": "Continuation or reversal of NY Open initiative — strongest volume period"},
        {"name": "London PM", "detail": "European close — profit-taking and positioning ahead of US session"},
        {"name": "Asia", "detail": "Lower volume, range-bound. Watch for accumulation/distribution patterns"},
    ]

    _models = ["Fabio Rejection", "Absorption → Initiative", "Sweep & Reverse", "LVN Bounce", "Value Area Rotation", "Composite"]

    _htf_biases = [
        ("Bullish", "above POC", "Price is in the upper value area, favoring longs on pullbacks"),
        ("Bullish", "between POC and VAH", "Healthy uptrend — pullbacks to POC are high-probability entries"),
        ("Bearish", "below POC", "Price is below fair value, favoring shorts on rallies"),
        ("Bearish", "between VAL and POC", "Selling pressure dominant — rallies into POC are distribution zones"),
        ("Neutral", "at POC", "Price is at fair value with no clear directional edge — wait for initiative break"),
    ]

    _market_regimes = [
        {"state": "Trending", "detail": "Strong directional move underway — initiative activity dominating. Favor with-trend entries."},
        {"state": "Ranging", "detail": "Balanced market, rotating between value extremes. Fade the edges, avoid the middle."},
        {"state": "Balanced Volatile", "detail": "Wide range with high participation — institutional battle zone. Wait for resolution."},
        {"state": "Low Volume Grind", "detail": "Thin market, easily manipulated. Reduce size, widen stops, avoid illiquid breakouts."},
        {"state": "Breakout", "detail": "Value area migration in progress — new balance forming. Trail initiative entries."},
    ]

    _blockers_pool = [
        {"text": "High-impact news (NFP/FOMC) in next 30min — defer entry until after release", "severity": "high"},
        {"text": "Spread widening to 3x average — liquidity deteriorating, slippage risk elevated", "severity": "high"},
        {"text": "Counter-trend signal — trade against daily bias, reduce position to 50%", "severity": "medium"},
        {"text": "Near session close — limited follow-through time, consider passing", "severity": "medium"},
        {"text": "VIX spike detected — stop-hunt risk elevated, widen stops or reduce size", "severity": "medium"},
        {"text": "Correlated asset divergence — BTCUSDT and NAS100 moving opposite, caution", "severity": "low"},
    ]

    rng = _stable_rng("__signals__", 0, 7)
    for i in range(8):
        sym = rng.choice(list(_BASE_PRICES.keys()))
        direction = rng.choice(["buy", "sell"])
        setup = rng.choice(_setups)
        score = rng.randint(45, 98)
        session = rng.choice(_sessions)
        regime = rng.choice(_market_regimes)
        htf = rng.choice(_htf_biases)
        model = rng.choice(_models)

        base = _base_price(sym)
        tick = _tick_size(sym)
        entry = round(base + rng.uniform(-base * 0.001, base * 0.001), 5)
        sl_dist = base * rng.uniform(0.001, 0.003)
        tp_dist = sl_dist * rng.uniform(1.5, 3.5)

        if direction == "buy":
            sl = round(entry - sl_dist, 5)
            tp = round(entry + tp_dist, 5)
        else:
            sl = round(entry + sl_dist, 5)
            tp = round(entry - tp_dist, 5)

        risk = abs(entry - sl)
        reward = abs(tp - entry)
        rr = round(reward / risk, 1) if risk > 0 else 0

        bias_dir = "long" if direction == "buy" else "short"

        # Generate rich context values for template formatting
        ctx = {
            "price": entry, "sl": sl, "tp": tp,
            "abscount": rng.randint(2, 6),
            "minutes": rng.randint(5, 30),
            "bookimb": rng.randint(60, 88),
            "htf_bias": htf[0],
            "htf_tf": rng.choice(["4H", "1D", "Weekly"]),
            "htf_position": htf[1],
            "poc_context": htf[2],
            "init_count": rng.randint(3, 8),
            "delta_dir": "positive" if direction == "buy" else "negative",
            "delta_val": rng.uniform(500, 5000) * (1 if direction == "buy" else -1),
            "delta_seq": f"{rng.randint(-800,-200)} → {rng.randint(-600,-100)} → {rng.randint(-300,-30)}",
            "delta_div_pct": rng.randint(30, 65),
            "delta_pct": rng.randint(15, 50),
            "sweep_level": round(entry - (sl_dist * 0.7 * (1 if direction == "buy" else -1)), 5),
            "reversal_vol": rng.randint(150, 800),
            "stops_cleared": rng.randint(40, 200),
            "reload_vol": rng.randint(200, 600),
            "sweep_delta": rng.uniform(300, 2000) * (1 if direction == "buy" else -1),
            "pre_imb": rng.randint(55, 75),
            "post_imb": rng.randint(60, 85),
            "depth_from": round(entry - base * 0.002, 2),
            "depth_to": round(entry + base * 0.002, 2),
            "poc_level": round(entry + rng.uniform(-base * 0.001, base * 0.001), 5),
            "val_level": round(entry - base * rng.uniform(0.003, 0.006), 5),
            "days": rng.choice([5, 10, 20]),
            "poc_reactions": rng.randint(3, 8),
            "poc_avg_bounce": rng.uniform(0.2, 0.8),
            "poc_volume": rng.randint(5000, 50000),
        }

        # Format the deep narrative templates
        try:
            narrative = setup["narrative"].format(**ctx)
            thesis = setup["thesis"]
            edge = setup["edge"].format(**ctx)
            invalidation = setup["invalidation"].format(**ctx)
            htf_context = setup["htf_context"].format(**ctx)
        except (KeyError, ValueError):
            narrative = f"{setup['pattern']} detected at {entry:.2f}"
            thesis = setup["thesis"]
            edge = f"Confidence {score}%"
            invalidation = f"Stop loss at {sl:.2f}"
            htf_context = f"{htf[0]} bias on higher timeframes"

        # Build ordered reasons chain
        reasons = [
            f"1. {setup['pattern']} detected at {entry:.5g}",
            f"2. Daily bias: {bias_dir.upper()} ({htf[0]} on {ctx['htf_tf']})",
            f"3. Session: {session['name']} — {session['detail'][:60]}",
            f"4. {regime['state']}: {regime['detail'][:60]}",
        ]
        if rng.random() > 0.3:
            reasons.append(f"5. Orderbook imbalance {ctx['bookimb']}% on {'bid' if direction == 'buy' else 'ask'} side")
        if rng.random() > 0.4:
            reasons.append(f"6. Composite VP POC confluence at {ctx['poc_level']:.5g}")

        # Blockers
        blockers = []
        if score < 60:
            b = rng.choice(_blockers_pool)
            blockers.append(b["text"])
        if rng.random() < 0.25:
            b = rng.choice(_blockers_pool)
            if b["text"] not in blockers:
                blockers.append(b["text"])

        # Quality grade
        grade = "A+" if score >= 85 else "A" if score >= 70 else "B" if score >= 55 else "C"

        # Multi-timeframe confluence checklist
        mtf_confluence = {
            "weekly_bias": rng.choice(["Bullish", "Bearish", "Neutral"]),
            "daily_bias": htf[0],
            "h4_trend": rng.choice(["Uptrend", "Downtrend", "Sideways"]),
            "h1_structure": rng.choice(["Higher highs", "Lower lows", "Range-bound", "Breakout"]),
            "m15_trigger": setup["pattern"],
        }

        signals.append({
            "id": now - i * 100000 + rng.randint(0, 999),
            "timestamp": now - i * rng.randint(60000, 600000),
            "timestamp_ms": now - i * rng.randint(60000, 600000),
            "symbol": sym,
            "direction": "long" if direction == "buy" else "short",
            "confidence": score / 100,
            "composite_score": score,
            "action": "enter" if score >= 70 else "alert_only",
            "pattern": setup["pattern"],
            "signal_type": setup["signal_type"],
            "entry": entry,
            "stopLoss": sl,
            "takeProfit": tp,
            "entry_price": entry,
            "suggested_sl": sl,
            "suggested_tp": tp,
            "riskReward": rr,
            "bias": bias_dir.upper(),
            "session": session["name"],
            "session_detail": session["detail"],
            "model": model,
            "grade": grade,
            "reasons": reasons,
            "blockers": blockers,
            "notes": f"{setup['pattern']} — {grade} grade — score {score}%",
            "signals": [{"signal_type": setup["signal_type"], "confidence": score}],
            # ── Deep analysis fields ──
            "narrative": narrative,
            "thesis": thesis,
            "edge": edge,
            "invalidation": invalidation,
            "htf_context": htf_context,
            "market_regime": regime,
            "mtf_confluence": mtf_confluence,
            # ── Orderflow metrics ──
            "market_state": regime["state"],
            "volume_context": rng.choice(["Above Average", "Normal", "Below Average", "Spiking"]),
            "key_level_type": rng.choice(["POC", "VAH", "VAL", "LVN", "Composite Node"]),
            "key_level_price": round(entry + rng.uniform(-base * 0.001, base * 0.001), 5),
            "absorption_count": ctx["abscount"] if "absorption" in setup["signal_type"] else rng.randint(0, 3),
            "delta_confirm": rng.choice([True, False]),
            "delta_value": round(ctx["delta_val"], 1),
            "initiative_strength": rng.randint(40, 100),
            "book_imbalance_pct": ctx["bookimb"],
            "footprint_summary": f"{'Bid' if direction == 'buy' else 'Ask'}-heavy profile with {('absorption at bid' if direction == 'buy' else 'supply at ask')}. POC at {ctx['poc_level']:.5g}, delta {'+' if direction == 'buy' else '-'}{abs(ctx['delta_val']):.0f}",
        })
    return signals
