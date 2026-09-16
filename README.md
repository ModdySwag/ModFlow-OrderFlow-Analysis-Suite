# ModFlow OrderFlow Analysis Suite

> **Real-time orderflow trading system** — tick-level microstructure analysis, 5 pattern detectors, volume profile framing, state machine trade lifecycle, dual data feeds (MT5 + Bybit), FastAPI dashboard with WebSocket, Telegram alerts. Built on Fabio Testa's methodology.

[![Python](https://img.shields.io/badge/python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](.)
[![License](https://img.shields.io/badge/license-MIT-informational?style=for-the-badge)](LICENSE)
[![Instruments](https://img.shields.io/badge/instruments-49-blue?style=for-the-badge)](.)
[![Code](https://img.shields.io/badge/code-~68k%20lines-brightgreen?style=for-the-badge)](.)
[![API](https://img.shields.io/badge/API-133%20routes-orange?style=for-the-badge)](.)
[![Tests](https://img.shields.io/badge/tests-843%20passing-brightgreen?style=for-the-badge)](CONTRIBUTING.md)

---

## Table of Contents

- [What Is OrderFlow Analysis?](#what-is-orderflow-analysis)
- [System Overview](#system-overview)
- [Architecture](#architecture)
- [The 5 Core Patterns](#the-5-core-patterns)
- [Volume Profile Framing](#volume-profile-framing-daily-bias)
- [State Machine Trade Lifecycle](#state-machine-trade-lifecycle)
- [Supported Instruments (49)](#supported-instruments-49)
- [Data Sources](#data-sources)
- [Dashboard](#dashboard)
- [Telegram Alerts](#telegram-alerts)
- [Database](#database)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [File Inventory](#file-inventory)
- [API Reference](#api-reference)
- [Demo Mode](#demo-mode)
- [Signal Output Examples](#signal-output-examples)
- [How Pattern Detection Works](#how-pattern-detection-works)
- [Composite Scoring System](#composite-scoring-system)
- [Contributing](#contributing)
- [License](#license)
- [Disclaimer](#disclaimer)

---

## What Is OrderFlow Analysis?

OrderFlow analysis reads **market microstructure** — the tick-by-tick footprint of buyers and sellers — to understand who is in control before price reflects it. Unlike traditional technical analysis that looks at candles and indicators, orderflow looks **inside the candle**:

```
Traditional Analysis              OrderFlow Analysis
─────────────────────             ─────────────────────
Looks at: OHLC candles             Looks at: Every tick (price + volume + side)
Timeframe: 1m, 5m, 1H             Timeframe: Tick-level (milliseconds)
Answers: What happened?            Answers: WHO did it and WHY?
Indicators: RSI, MACD, MA         Engines: Delta, Footprint, Volume Profile, Orderbook
Lagging: Yes (averages)            Leading: No (real-time microstructure)
```

### Key Concepts

| Concept | What It Measures | Why It Matters |
|---------|-----------------|----------------|
| **Delta** | Buy volume minus sell volume per candle/level | Who is aggressive — buyers or sellers? |
| **Cumulative Delta** | Running total of delta over time | Is buying/selling pressure building or fading? |
| **Footprint** | Volume at each price level split by bid/ask | Where did the heavy trading happen inside the candle? |
| **Volume Profile** | Total volume traded at each price over a session | Where is the "fair value" — POC, VAH, VAL? |
| **Orderbook** | Limit orders waiting at each price level | Where are the walls? Thin levels = easy to sweep. |
| **Absorption** | Aggressive volume with no price movement | Someone is defending a level with limit orders. |
| **Initiative** | Aggressive volume WITH price movement | Institutional conviction pushing price. |

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ModFlow OrderFlow Analysis Suite                              │
│                                                                             │
│  ┌──────────────────────┐     ┌──────────────────────────────────────┐      │
│  │   DATA SOURCES       │     │   ANALYTICS ENGINES (per instrument) │      │
│  │                      │     │                                      │      │
│  │  ┌────────┐ ┌──────┐ │     │  Volume Profile  ── POC, VAH, VAL,  │      │
│  │  │  MT5   │ │Bybit │ │────▶│  Delta Engine    ── vertical, horiz,│      │
│  │  │  Feed  │ │ Feed │ │     │  Footprint       ── bid/ask/level,  │      │
│  │  └────────┘ └──────┘ │     │  Orderbook       ── L2 depth, thin  │      │
│  └──────────────────────┘     └───────────────┬──────────────────────┘      │
│                                               │                              │
│  ┌────────────────────────────────────────────▼──────────────────────────┐  │
│  │                    5 PATTERN DETECTORS                                 │  │
│  │  Absorption · Initiative · Sweep · Exhaustion · Divergence            │  │
│  └────────────────────────────────────────────┬──────────────────────────┘  │
│                                               │                              │
│  ┌────────────────────────────────────────────▼──────────────────────────┐  │
│  │                    SIGNAL PROCESSING                                   │  │
│  │  Profile Framing (P/b/D shapes) → Qualified Levels → Daily Bias      │  │
│  │  Signal Aggregator (state machine) → Composite Score (0-100)         │  │
│  └────────────┬──────────────────────────────────┬───────────────────────┘  │
│               │                                  │                          │
│  ┌────────────▼──────────┐  ┌───────────────────▼────────────────────┐     │
│  │   Telegram Alerts     │  │   FastAPI Dashboard                    │     │
│  │   Entry/BE/Trail/Exit │  │   133 REST/WS routes + streams         │     │
│  │   Daily Bias updates  │  │   Charts, VP, Footprint, Orderbook     │     │
│  └───────────────────────┘  │   Scanner, Strategy Status, Tape       │     │
│                              └───────────────────────────────────────┘     │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │   SQLite Database (WAL mode)                                       │     │
│  │   ticks · candles · volume_profiles · signals · trade_journal     │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Architecture

### Data Flow Pipeline

```
                     ┌─────────────┐
                     │  MT5 Feed   │──── Tick polling (100ms)
                     │  (493L)     │──── Market Book (DOM)
                     │             │──── Historical download
                     └──────┬──────┘
                            │
     ┌──────────────┐       │       ┌──────────────┐
     │  Bybit Feed  │───────┤       │   Database   │
     │  (339L)      │       ├──────▶│  (472L)      │
     │  WebSocket   │       │       │  SQLite WAL  │
     │  Free, no key│       │       └──────────────┘
     └──────────────┘       │
                            ▼
                   ┌─────────────────┐
                   │ Candle Builder  │ ← Tick → 1m aggregation
                   │ (132L)          │ ← Footprint per level
                   └────────┬────────┘
                            │
              ┌─────────────┼──────────────┐
              ▼             ▼              ▼
     ┌──────────────┐ ┌──────────┐ ┌──────────────┐
     │ Volume Prof. │ │  Delta   │ │  Footprint   │
     │ Engine (283L)│ │Engine    │ │  Engine      │
     │              │ │ (207L)   │ │ (349L)       │
     │ POC/VAH/VAL  │ │ Vert/Hor│ │ Bid/Ask/Lvl  │
     │ LVN/Shape    │ │ Cumul.   │ │ Imbalance    │
     └──────┬───────┘ └────┬─────┘ └──────┬───────┘
            │              │              │
            ▼              ▼              ▼
     ┌─────────────────────────────────────────┐
     │        ORDERBOOK TRACKER (208L)          │
     │  L2 depth · Thin levels · Consumptions  │
     │  Path of least resistance               │
     └──────────────────┬──────────────────────┘
                        │
        ┌───────┬───────┼───────┬───────┬───────┐
        ▼       ▼       ▼       ▼       ▼       │
   ┌────────┐┌────────┐┌──────┐┌────────┐┌────────┐
   │Absorp- ││Initia- ││Sweep ││Exhaus- ││Diverg- │
   │tion    ││tive    ││      ││tion    ││ence    │
   │(266L)  ││(136L)  ││(142L)││(237L)  ││(159L)  │
   └───┬────┘└───┬────┘└──┬───┘└───┬────┘└───┬────┘
       │         │        │        │         │
       └─────────┴────┬───┴────────┴─────────┘
                      ▼
            ┌─────────────────────┐
            │  Profile Framing    │ ← P/b/D shape → Daily Bias
            │  (343L)             │ ← Qualified Levels (VAH/VAL/POC/LVN/Merged)
            └─────────┬───────────┘
                      ▼
            ┌─────────────────────┐
            │  Signal Aggregator  │ ← State machine (6 states)
            │  (516L)             │ ← Composite scoring (0-100)
            │                     │ ← SL/TP calculation
            └──────┬──────────────┘
                   │
       ┌───────────┼───────────────┐
       ▼           ▼               ▼
 ┌──────────┐ ┌──────────┐  ┌───────────────┐
 │ Telegram │ │Dashboard │  │  Database     │
 │ Bot      │ │ FastAPI  │  │  Journal      │
 │ (201L)   │ │ (1371L)  │  │  Logging      │
 └──────────┘ └──────────┘  └───────────────┘
```

### Module Dependency Graph

```
main.py (857L) ─── System orchestrator
    │
    ├── config/settings.py (821L) ─── 31 instrument configs, 14 config dataclasses
    │
    ├── data/
    │   ├── models.py (330L) ─── 9 dataclasses: Tick, Candle, Signal, FootprintLevel, TradeState...
    │   ├── candle_builder.py (132L) ─── Tick → 1m aggregation + footprint
    │   ├── mt5_feed.py (493L) ─── MT5 terminal: ticks, book, history
    │   ├── bybit_feed.py (339L) ─── Bybit WebSocket: trades + orderbook
    │   └── database.py (472L) ─── SQLite: 5 tables, WAL mode
    │
    ├── analytics/
    │   ├── volume_profile.py (283L) ─── POC/VAH/VAL/LVN/shape
    │   ├── delta.py (207L) ─── Vertical + horizontal + cumulative delta
    │   ├── footprint.py (349L) ─── Bid/ask per level, imbalance detection
    │   └── orderbook.py (208L) ─── L2 depth, thin levels, consumption tracking
    │
    ├── patterns/
    │   ├── absorption.py (266L) ─── Effort >> result detection
    │   ├── initiative.py (136L) ─── Effort = result (momentum)
    │   ├── sweep.py (142L) ─── Thin book displacement
    │   ├── exhaustion.py (237L) ─── Declining volume at extremes
    │   └── divergence.py (159L) ─── Price vs delta disagreement
    │
    ├── signals/
    │   ├── profile_framing.py (343L) ─── Daily bias + qualified levels
    │   └── aggregator.py (516L) ─── State machine + composite scoring
    │
    ├── alerts/
    │   └── telegram_bot.py (201L) ─── Telegram notifications
    │
    └── dashboard/
        ├── app.py ─── FastAPI host: REST + WebSocket (the app mounts its routers here)
        ├── websocket_manager.py ─── 10-channel broadcast with throttling
        ├── demo_data.py ─── Deterministic demo data generator
        ├── __main__.py ─── Standalone launcher
        └── static/ ─── the legacy page's assets, served at /static/

    ├── atlas/ ─── live analytics (CVD, heatmap, imbalance, tapeflow, profiles)
    │   └── api.py ─── the /api/atlas/* surface (45 routes)
    │
    ├── desktop/ ─── the desktop application
    │   ├── launcher.py ─── pywebview window / --headless server
    │   ├── api.py ─── /api/control/* (config, feeds, alerts, exports, layouts)
    │   ├── engine.py ─── the live pipeline host the UI reads from
    │   └── ui/ ─── vanilla-JS modules (~30,100L across 75 files) + index.html
```

---

## The 5 Core Patterns

The system detects 5 microstructure patterns based on Fabio Testa's methodology. Each outputs a **strength score (0-100)** and **directional bias (BUY/SELL)**.

### Pattern Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                     5 PATTERN DETECTORS                             │
│                                                                     │
│  1. ABSORPTION        2. INITIATIVE       3. SWEEP                  │
│  Effort >> Result     Effort = Result     Thin Book Displacement    │
│  ██████████           ██████████          ██████                    │
│  ██████████  (no      ██████████  (price  ██░░░░░░░ (price          │
│  ██████████   move)   ██████████   moves) ░░░░░░░░   moves fast)   │
│  Buyers/Sellers       Directional         Low volume                │
│  defending level      conviction          through empty levels      │
│                                                                     │
│  4. EXHAUSTION        5. DIVERGENCE                                 │
│  Declining Effort     Price vs Delta Disagreement                   │
│  ██  █  █            Price: ↗↗↗ NEW HIGH                            │
│  █  █  ▓             Delta: ↗↗↘  (failing)                         │
│  █  ▓  ░             Trend reversal warning                        │
│  ▓  ░  ░                                                           │
│  Volume fading                                                     │
│  at extremes                                                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Detection Details

| # | Pattern | Detection Logic | Source Data | Signal Purpose |
|---|---------|----------------|-------------|----------------|
| 1 | **Absorption** | 2 methods: (a) Delta/price mismatch — positive delta + red candle = sellers absorbing, (b) High volume at level + low displacement + repeated attempts | Delta, Footprint, Price | **Entry signal** at VAH/VAL |
| 2 | **Initiative** | 5 criteria: delta ≥ threshold, volume ≥ 1.5x average, body ≥ 3 ticks, delta/price aligned, one-sided imbalance bonus | Delta, Footprint, Volume | **Break-even / trail trigger** |
| 3 | **Sweep** | Price through ≥3 thin orderbook levels + low volume per level + thin book confirmation (≥2 thin levels on swept side) | Orderbook, Price | **Liquidity grab / reversal alert** |
| 4 | **Exhaustion** | Price trending + volume declining >30% + negative volume/delta trend + optional contrarian imbalance at extreme | Volume trend, Delta ROC, Footprint | **Exit warning** — momentum fading |
| 5 | **Divergence** | Price new high/low but cumulative delta peak/trough fails to confirm (<80% of prior) | Price, Cumulative Delta peaks | **Trend reversal warning** |

### Strength Score Calculation

| Pattern | Score Formula | Range |
|---------|--------------|-------|
| Absorption | `(volume / min_aggressive) * 40` or `(vol / min_aggressive) * 30 + attempts * 15` | 0-75 |
| Initiative | `(delta/threshold)*20 + vol_accel*15 + body_ticks*5 + imbalance_count*10` | 0-50+ |
| Sweep | `levels*15 + efficiency*20 + displacement*1000 + thin_confirm*15` | 30-100 |
| Exhaustion | `40 + |vol_trend|*5 + |delta_roc|*5 + contrarian_bonus(20)` | 40-70 |
| Divergence | `30 + (1 - ratio)*40 + price_new_extreme*10` | 30-80 |

---

## Volume Profile Framing (Daily Bias)

Implements Fabio Testa's **profile shape analysis** to determine the daily directional bias and identify **qualified levels** to trade from.

### Profile Shapes

```
P-SHAPE (Buyers in Control)        b-SHAPE (Sellers in Control)
Volume │                           Volume │
  █    │                                  │ █
  ██   │                                  │ ██
  ███  │     POC > 65%                    │ ███     POC < 35%
  ████ │     Bias: LONG                   │ ████    Bias: SHORT
  █████│                                  │ ██████
───────┼────────── Price            ──────┼────────── Price
  VAL  │  POC  VAH                         VAH  POC  VAL

D-SHAPE (Balanced)                  DOUBLE DISTRIBUTION
Volume │                           Volume │
  █    │       █                          │ ████    ████
  ██   │      ██                          │ ████    ████
  ███  │     ███   POC ~50%               │  ░░░░░░░░░░   (valley)
  ████ │    ████  Bias: NEUTRAL           │ ████    ████  Bias: TRANSITION
───────┼────────── Price            ──────┼────────────────── Price
  VAL  │ POC │ VAH                         VAH₁  VAL₁  VAH₂  VAL₂
```

| Shape | POC Position | Bias | Confidence Base | Trading Plan |
|-------|-------------|------|----------------|-------------|
| **P-shape** | >65% from bottom | LONG | 40 + poc_pct×30 | Buyers in control, buy dips to VAL |
| **b-shape** | <35% from bottom | SHORT | 40 + (1-poc_pct)×30 | Sellers in control, sell rallies to VAH |
| **D-shape** | ~50% | NEUTRAL | 20 | Balanced, fade extremes |
| **Double Distribution** | Bimodal (valley <50% of peaks) | NEUTRAL | 30 | Transition — watch for breakout |

### Qualified Levels

```
┌─────────────────────────────────────────────────────────────────┐
│                  QUALIFIED LEVELS (Trade From These)             │
│                                                                  │
│  Price ▲                                                         │
│       │     ┌─── VAH (Value Area High) ─── SELL ZONE            │
│       │     │                                                    │
│       │     │    ┌── MERGED VAH ─── Strong SELL (str=70)        │
│       │     │    │  (confluent across multiple days)             │
│       │     │                                                    │
│       │     │  ┌── LVN (Low Volume Node) ─── Rebalancing        │
│       │     │  │  (price magnet — gaps fill fast)                │
│       │     │  │                                                │
│       │  ┌──┤  │  ┌── POC (Point of Control) ─── Pivot          │
│       │  │  │  │  │  (highest volume = fair value)               │
│       │  │  │  │  │                                            │
│       │  │  ├──┤  │  ┌── MERGED VAL ─── Strong BUY (str=70)    │
│       │  │  │  │  │  │  (confluent across multiple days)        │
│       │  │  │  │  │  │                                        │
│       │  └──┤  │  │  │  └── VAL (Value Area Low) ─── BUY ZONE  │
│       │     │  │  │                                           │
│       └─────┘  │  └────────────────────────────────────         │
│                │                                                 │
│  Confluence Bonus: +20 strength when level matches across days  │
│  Multi-day merge: overlapping profiles (>30% VA overlap) merged │
└─────────────────────────────────────────────────────────────────┘
```

### Multi-Day Context Checks

| Check | What It Does | Effect |
|-------|-------------|--------|
| Value accepted higher | Current VA above prior VA | +15 confidence if aligned with bias |
| VAH rejection | Price rejected at VAH across multiple days | Bias → WARNING, -10 penalty to composite score |
| Failed auction ("hooks") | Bullish hook below VAL, bearish hook above VAH | Reduces confidence |

---

## State Machine Trade Lifecycle

Every instrument runs an independent state machine. The system watches qualified levels, detects absorption entries, manages the trade through break-even and trailing stops, and auto-closes on strong exit signals.

```
╔══════════════════════════════════════════════════════════════════════════╗
║                    STATE MACHINE TRADE LIFECYCLE                        ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║   ┌─────────────────────────────────────────────────────────────┐        ║
║   │  NO ACTIVE TRADE                                            │        ║
║   │  Price approaches qualified level (strength >= 50)          │        ║
║   │  Aggregator auto-watches level                              │        ║
║   └────────────────────────┬────────────────────────────────────┘        ║
║                            │                                             ║
║                            ▼                                             ║
║   ┌─────────────────────────────────────────────────────────────┐        ║
║   │  WATCHING                                                   │        ║
║   │  Monitoring level for absorption or sweep signals           │        ║
║   └───────┬────────────────────────────────┬────────────────────┘        ║
║           │ ABSORPTION detected            │ SWEEP detected              ║
║           │ (composite >= 40)              │ (thin book displacement)    ║
║           ▼                                 ▼                            ║
║   ┌──────────────┐               ┌──────────────────────┐               ║
║   │ ABSORPTION   │               │ ALERT ONLY           │               ║
║   │ DETECTED     │               │ (sweep notification, │               ║
║   │ (transient)  │               │  no entry)           │               ║
║   └──────┬───────┘               └──────────────────────┘               ║
║          │ Entry signal sent, SL/TP calculated                            ║
║          ▼                                                                ║
║   ┌─────────────────────────────────────────────────────────────┐        ║
║   │  POSITION_OPEN                                              │        ║
║   │  Trade entered. Waiting for initiative (BE trigger)         │        ║
║   │  OR watching for exit warnings (exhaustion/divergence)      │        ║
║   └───────┬────────────────────────────────┬────────────────────┘        ║
║           │ INITIATIVE (same dir)          │ EXIT WARNING (opposite dir) ║
║           │ Move SL to entry price         │ str >= 70 → auto-close      ║
║           ▼                                 ▼                            ║
║   ┌──────────────┐               ┌──────────────────────┐               ║
║   │ BREAK_EVEN   │               │ CLOSED               │               ║
║   │ SL = entry   │               │ (auto-close on strong │               ║
║   │ Risk-free    │               │  exit signal)         │               ║
║   └──────┬───────┘               └──────────────────────┘               ║
║          │ INITIATIVE (same dir)                                             ║
║          │ Trail SL to candle extreme                                        ║
║          ▼                                                                  ║
║   ┌─────────────────────────────────────────────────────────────┐         ║
║   │  TRAILING                                                   │         ║
║   │  SL trails to candle low (longs) or high (shorts)           │         ║
║   │  Each new initiative print moves the trail                  │         ║
║   └───────┬────────────────────────────────┬────────────────────┘         ║
║           │ More INITIATIVE               │ EXIT WARNING (str>=70)        ║
║           │ Keep trailing                 │ or SL hit                     ║
║           ▼                                 ▼                              ║
║   ┌──────────────┐               ┌──────────────────────┐                ║
║   │ (loop back)  │               │ CLOSED               │                ║
║   │ TRAILING     │──────────────▶│ Trade logged to      │                ║
║   │              │               │ journal + Telegram   │                ║
║   └──────────────┘               └──────────────────────┘                ║
║                                                                            ║
╚══════════════════════════════════════════════════════════════════════════╝
```

---

## Supported Instruments (49)

Each instrument has **pre-tuned thresholds** for all 5 pattern detectors, optimized for its volatility and tick size.
49 ship configured in total — the 31 base specs tabled below plus 18 crypto majors that carry the same pre-tuned
thresholds (`GET /api/instruments` lists them all).

### Index Futures (9)

| Instrument | Tick Size | Absorption Min Vol | Initiative Min Delta | VP Tick Size | Session |
|-----------|-----------|-------------------|---------------------|-------------|---------|
| NAS100 | 0.1 | 50 | 30 | 1.0 | NY Cash |
| SP500 | 0.1 | 40 | 25 | 1.0 | NY Cash |
| DJ30 | 1.0 | 40 | 25 | 5.0 | NY Cash |
| UK100 | 0.1 | 30 | 20 | 1.0 | London |
| DAX40 | 0.1 | 30 | 20 | 2.0 | London |
| NIKKEI225 | 1.0 | 30 | 20 | 50.0 | Asian |
| CAC40 | 0.1 | 25 | 18 | 1.0 | London |
| ASX200 | 0.1 | 25 | 18 | 1.0 | Asian |
| HK50 | 1.0 | 25 | 18 | 5.0 | Asian |

### Metals, Energy, Crypto

| Instrument | Category | Tick Size | VP Tick Size | Session |
|-----------|----------|-----------|-------------|---------|
| XAUUSDT (Gold) | Metal | 0.01 | 0.50 | NY Cash |
| XAGUSD (Silver) | Metal | 0.001 | 0.05 | Full Day |
| USOIL | Energy | 0.01 | 0.10 | NY Cash |
| UKOIL | Energy | 0.01 | 0.10 | London |
| BTCUSDT | Crypto | 0.01 | 10.0 | Full Day |

### Forex (10 Pairs)

| Instrument | Tick Size | VP Tick Size | Session |
|-----------|-----------|-------------|---------|
| EURUSD | 0.00001 | 0.0005 | Full Day |
| GBPUSD | 0.00001 | 0.0005 | Full Day |
| USDJPY | 0.001 | 0.05 | Full Day |
| AUDUSD | 0.00001 | 0.0005 | Full Day |
| USDCAD | 0.00001 | 0.0005 | Full Day |
| USDCHF | 0.00001 | 0.0005 | Full Day |
| NZDUSD | 0.00001 | 0.0005 | Full Day |
| EURGBP | 0.00001 | 0.0005 | Full Day |
| EURJPY | 0.001 | 0.05 | Full Day |
| GBPJPY | 0.001 | 0.05 | Full Day |

### US Stocks (7)

| Instrument | Tick Size | VP Tick Size | Session |
|-----------|-----------|-------------|---------|
| AAPL | 0.01 | 0.50 | NY Cash |
| TSLA | 0.01 | 0.50 | NY Cash |
| AMZN | 0.01 | 0.50 | NY Cash |
| MSFT | 0.01 | 0.50 | NY Cash |
| NVDA | 0.01 | 0.50 | NY Cash |
| META | 0.01 | 0.50 | NY Cash |
| GOOGL | 0.01 | 0.50 | NY Cash |

---

## Data Sources

### Dual Feed Architecture

```
┌────────────────────────────────────────────────────────────┐
│                     DATA SOURCE OPTIONS                     │
│                                                             │
│  ┌─────────────────────┐    ┌─────────────────────────┐   │
│  │      MT5 FEED        │    │      BYBIT FEED         │   │
│  │                      │    │                         │   │
│  │  Source: MT5 terminal│    │  Source: Bybit WebSocket│   │
│  │  Requires: Account   │    │  Requires: Nothing      │   │
│  │  Ticks: 100ms polling│    │  Ticks: Real-time stream│   │
│  │  Orderbook: DOM data │    │  Orderbook: 50 levels   │   │
│  │  History: Up to 3 days│   │  History: None          │   │
│  │  Aggressor: Buy/Sell │    │  Aggressor: Trade side  │   │
│  │  flag from MT5       │    │  from Bybit API         │   │
│  └──────────┬───────────┘    └───────────┬─────────────┘   │
│             │                             │                  │
│             │  DATA_SOURCE = "MT5"        │  "BYBIT"         │
│             │  DATA_SOURCE = "BOTH" ──────┘                  │
│             │                                                │
│             ▼                                                │
│  ┌─────────────────────────────────────┐                    │
│  │  Symbol Auto-Discovery (MT5)        │                    │
│  │  200+ broker-specific name variants │                    │
│  │  e.g. USTEC, USTECm, NAS100, US100 │                    │
│  └─────────────────────────────────────┘                    │
└────────────────────────────────────────────────────────────┘
```

### MT5 Symbol Mapping

The system auto-discovers instruments across 200+ broker-specific naming variants:

| Internal | MT5 Symbol | Alternatives |
|----------|-----------|-------------|
| NAS100 | USTECm | USTEC, NAS100, US100, NQ100, NAS100USD... |
| XAUUSDT | XAUUSDm | XAUUSD, GOLD... |
| EURUSD | EURUSDm | EURUSD, EUR/USD... |
| BTCUSDT | BTCUSDm | BTCUSD, BTC/USD... |

---

## Dashboard

### Frontend Components

The current UI is the desktop suite: **75 vanilla-JS modules** (22 of them selftests) in `orderflow_system/desktop/ui/`
(shell and menus, chart, the order-flow engine, heatmap, tape, alerts, options, fundamentals, news,
search, watchlist, studies — no build step, no framework). The 8 modules listed below are the legacy
dashboard page's assets, still served at `/static/`:

```
┌──────────────────────────────────────────────────────────────────────┐
│                     ORDERFLOW DASHBOARD                              │
│                                                                      │
│  ┌───────────────────────────────────┐  ┌────────────────────────┐  │
│  │        PRICE CHART (app.js)       │  │   VOLUME PROFILE       │  │
│  │   the chart library lightweight-charts  │  │   Horizontal bars      │  │
│  │   Signal markers overlay:         │  │   POC, VAH, VAL marks  │  │
│  │   ▲ Absorption (teal)            │  │   Shape classification  │  │
│  │   ▲ Initiative (green)           │  │   LVN markers          │  │
│  │   ▲ Sweep (purple)               │  └────────────────────────┘  │
│  │   ● Exhaustion (yellow)                                        │
│  │   ● Divergence (orange)          ┌────────────────────────┐    │
│  │   ● Entry/Exit markers           │   FOOTPRINT CHART      │    │
│  └───────────────────────────────────┘│   Bid/Ask per level   │    │
│                                       │   Imbalance highlights │    │
│  ┌───────────────────────────────────┐└────────────────────────┘  │
│  │        SIGNAL CARDS (signals.js)  │                             │
│  │   Real-time trade recommendations │  ┌────────────────────────┐│
│  │   Entry/SL/TP/RR display          │  │  ORDERBOOK DEPTH       ││
│  │   Pattern breakdown               │  │  Bid/Ask ladder        ││
│  │   Grade (A+/A/B/C)                │  │  Thin level markers    ││
│  └───────────────────────────────────┘  │  Spread indicator      ││
│                                         └────────────────────────┘│
│  ┌───────────────────────────────────┐  ┌────────────────────────┐│
│  │  PERFORMANCE (performance.js)     │  │  TIME & SALES (tape.js)││
│  │  Win rate, PnL, RR distribution   │  │  Tick-by-tick feed     ││
│  │  Trade history                    │  │  Big trade highlights  ││
│  └───────────────────────────────────┘  └────────────────────────┘│
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │              MICROSTRUCTURE (microstructure.js)               │  │
│  │  Market state · Session · Absorption · Delta · Exhaustion     │  │
│  └───────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### WebSocket Channels (9)

| Channel | Data | Throttle | Priority |
|---------|------|----------|----------|
| `tick` | Price, size, side | 200ms | High |
| `candle` | OHLCV + delta | None (immediate) | Critical |
| `signal` | AggregatedSignal | None (immediate) | Critical |
| `trade_state` | TradePhase transitions | None (immediate) | Critical |
| `volume_profile` | POC/VAH/VAL/shape | None | Normal |
| `bias` | DailyBias updates | None | Normal |
| `orderbook` | L2 depth + imbalance | 500ms | Normal |
| `delta` | Cumulative delta history | 200ms | Normal |
| `stats` | System-wide per-instrument | 5000ms | Low |

---

## Telegram Alerts

Automated notifications for every trade lifecycle event:

| Alert Type | Trigger | Content |
|-----------|---------|---------|
| **ENTRY SIGNAL** | Absorption at qualified level, composite ≥40 | Direction, score, pattern, delta, volume, bias, entry/SL/TP/RR |
| **BREAK EVEN** | First initiative auction after entry | SL moved to entry price — risk-free trade |
| **TRAIL UPDATE** | Subsequent initiative prints | New SL level, trail progress |
| **EXIT SIGNAL** | Trade closed (SL hit or auto-close) | PnL ticks, RR achieved, trade summary |
| **EXIT WARNING** | Exhaustion or divergence detected | Pattern details, strength, direction warning |
| **DAILY BIAS** | New VP shape computed | Shape, direction, confidence, POC/VAH/VAL, qualified levels |

---

## Database

### SQLite Schema (5 Tables)

```
┌─────────────────────────────────────────────────────────────────┐
│                    orderflow_data.db (WAL mode)                  │
│                                                                  │
│  ┌──────────┐ ┌──────────┐ ┌────────────────┐ ┌──────────┐    │
│  │  ticks    │ │ candles  │ │ volume_profiles│ │ signals  │    │
│  ├──────────┤ ├──────────┤ ├────────────────┤ ├──────────┤    │
│  │ id (PK)  │ │ id (PK)  │ │ id (PK)        │ │ id (PK)  │    │
│  │instrument│ │instrument│ │ instrument     │ │instrument│    │
│  │timestamp │ │timestamp │ │ session_date   │ │timestamp │    │
│  │ price    │ │timeframe │ │ poc, vah, val  │ │sig_type  │    │
│  │ size     │ │ OHLCV    │ │ total_volume   │ │direction │    │
│  │ side     │ │ buy/sell │ │ shape          │ │price_lvl │    │
│  │ trade_id │ │ delta    │ │ poc_pos_pct    │ │ strength │    │
│  └──────────┘ │footprint │ │ lvn (JSON)     │ │details   │    │
│               └──────────┘ │ vol_at_price   │ │  (JSON)  │    │
│                             └────────────────┘ └──────────┘    │
│                                                                  │
│  ┌──────────────┐                                               │
│  │ trade_journal│                                               │
│  ├──────────────┤                                               │
│  │ id (PK)      │                                               │
│  │ instrument   │                                               │
│  │ direction    │                                               │
│  │ entry/exit   │                                               │
│  │  time (ms)   │                                               │
│  │ entry/exit   │                                               │
│  │  price       │                                               │
│  │ SL, TP       │                                               │
│  │ pnl_ticks    │                                               │
│  │ rr_ratio     │                                               │
│  │ signals(JSON)│                                               │
│  │ notes        │                                               │
│  └──────────────┘                                               │
│                                                                  │
│  Indexes: (instrument, timestamp), (instrument, session_date)   │
│  PRAGMA: journal_mode=WAL, synchronous=NORMAL                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Installation

### Prerequisites

- **Windows 10/11** for the packaged desktop build (source installs also run on Linux/macOS; the
  frozen-build script targets Windows)
- **Python 3.11 or newer** when running from source
- **MetaTrader 5 terminal** (optional, Windows only — the MT5 feed) or the built-in **Bybit** feed,
  which needs no account and no key

### Setup (from source)

```bash
git clone https://github.com/ModdySwag/OrderFlow-Analysis-Pro.git
cd OrderFlow-Analysis-Pro

python -m venv .venv
.venv\Scripts\activate              # Windows;  source .venv/bin/activate on Linux/macOS

pip install -e ".[dev]"             # app + test tooling
pip install -e ".[mt5]"             # optional: MetaTrader 5 feed support
```

### Run the desktop app

```bash
python -m orderflow_system.desktop                          # native window (pywebview)
python -m orderflow_system.desktop --headless --port 8099   # server only
```

The UI is served at `/desktop` on that port (the window opens it directly); the REST API and its
OpenAPI schema (`/docs`) are on the same origin.

### Headless pipeline (feeds → detectors → Telegram)

```bash
python -m orderflow_system.main       # the original CLI orchestrator, config-driven
```

### Demo mode (no feed required)

```bash
python -m orderflow_system.dashboard  # deterministic demo data — the render test bed
```

### Standalone executable

```bash
python scripts/build_exe.py           # -> dist/ModFlowOrderFlowAnalysisSuite/
```

---

## Configuration

All configuration is in `orderflow_system/config/settings.py`:

```python
# Data source: "MT5", "BYBIT", or "BOTH"
DATA_SOURCE = DataSource.BYBIT

# MT5 credentials (only if using MT5 feed)
MT5 = MT5Config(
    login=12345678,
    password="your_password",
    server="YourBroker-Server",
    poll_interval_ms=100,       # Tick polling frequency
    enable_book=True,           # Enable market book (DOM)
    download_history_days=3,    # Download M1 history for warmup
)

# Telegram alerts
TELEGRAM = TelegramConfig(
    bot_token="your_bot_token",
    chat_id="your_chat_id",
    send_chart_snapshots=True,
)

# Dashboard
DASHBOARD = DashboardConfig(
    enabled=True,
    host="127.0.0.1",          # loopback by default; "0.0.0.0" exposes the API to your LAN
    port=8080,
    log_level="warning",
)

# Database
DB_PATH = "orderflow_data.db"
LOG_LEVEL = "INFO"
```

### Per-Instrument Threshold Tuning

Each instrument has its own config with tuned thresholds. Example for NAS100:

```python
AbsorptionConfig(
    min_aggressive_volume=50,      # Min volume to qualify as absorption
    max_price_displacement_ticks=2, # Max ticks price can move
    rolling_window_seconds=30,      # Lookback window
    min_attempts=2,                 # Min repeated attempts at level
    big_trade_filter=10,            # Volume threshold for "big" trade
)

InitiativeConfig(
    min_delta_threshold=30,          # Min delta to qualify
    volume_acceleration_min=1.5,     # Must be 1.5x average volume
    min_price_displacement_ticks=3,  # Min body size
    delta_price_alignment=True,      # Delta must align with candle direction
)
```

---

## Usage

### Start the System

```bash
python -m orderflow_system.main
```

The system will:
1. Connect to configured data source(s)
2. Download historical bars (MT5) or connect to live feed (Bybit)
3. Build initial volume profiles from historical data
4. Start 5 pattern detectors for all 49 configured instruments
5. Compute daily bias and qualified levels
6. Auto-watch strong levels (strength ≥ 50)
7. Begin state machine monitoring
8. Send Telegram alerts on signals
9. Serve dashboard at `http://localhost:8080`

### Dashboard Endpoints

```bash
# View all instruments
curl http://localhost:8080/api/instruments

# Get scanner ranking (all pairs by trade proximity)
curl http://localhost:8080/api/scanner

# Get strategy status for NAS100
curl http://localhost:8080/api/strategy-status/NAS100USDT

# Get volume profile
curl http://localhost:8080/api/volume-profile/NAS100USDT?days=5

# Get daily bias
curl http://localhost:8080/api/bias/NAS100USDT

# Get signal history
curl http://localhost:8080/api/signals/NAS100USDT?limit=50

# Get active trade state
curl http://localhost:8080/api/trade/NAS100USDT
```

---

## Project Structure

```
orderflow_system/
├── main.py                          # System orchestrator (857L)
├── __init__.py                      # Package init
├── test_integration.py              # Integration tests (309L)
│
├── config/
│   └── settings.py                  # 31 instrument configs, 14 config dataclasses (821L)
│
├── data/
│   ├── models.py                    # 9 dataclasses: Tick, Candle, Signal, FootprintLevel, TradeState... (330L)
│   ├── candle_builder.py            # Tick → 1m candle aggregation (132L)
│   ├── bybit_feed.py                # Bybit WebSocket feed (339L)
│   ├── mt5_feed.py                  # MT5 terminal feed with auto-discovery (493L)
│   └── database.py                  # SQLite persistence, 5 tables (472L)
│
├── analytics/
│   ├── volume_profile.py            # POC, VAH, VAL, LVN, shape classification (283L)
│   ├── delta.py                     # Vertical, horizontal, cumulative delta (207L)
│   ├── footprint.py                 # Bid/ask per level, imbalance detection (349L)
│   └── orderbook.py                 # L2 depth, thin levels, consumption tracking (208L)
│
├── patterns/
│   ├── absorption.py                # Effort >> result detection (266L)
│   ├── initiative.py                # Effort = result (momentum) (136L)
│   ├── sweep.py                     # Thin book displacement (142L)
│   ├── exhaustion.py                # Declining volume at extremes (237L)
│   └── divergence.py                # Price vs delta disagreement (159L)
│
├── signals/
│   ├── profile_framing.py           # Daily bias + qualified levels (343L)
│   └── aggregator.py                # State machine + composite scoring (516L)
│
├── alerts/
│   └── telegram_bot.py              # Telegram notifications (201L)
│
└── dashboard/
    ├── app.py                       # FastAPI REST + WebSocket (1371L)
    ├── websocket_manager.py         # 10-channel broadcast manager (293L)
    ├── demo_data.py                 # Deterministic demo data generator (806L)
    ├── __main__.py                  # Standalone launcher (35L)
    └── static/
        ├── index.html               # Main HTML shell (121L)
        ├── app.js                   # the chart library charts + WebSocket (939L)
        ├── style.css                # Dashboard styling (566L)
        ├── footprint.js             # Canvas footprint chart (700L)
        ├── signals.js               # Signal recommendation cards (479L)
        ├── performance.js           # Performance analytics (599L)
        ├── orderbook.js             # Orderbook depth ladder (398L)
        ├── microstructure.js        # Microstructure indicators (417L)
        └── tape.js                  # Time & sales (448L)
```

---

## File Inventory

| Area | Files | Python Lines | UI Lines (JS/CSS/HTML) | Total Lines |
|------|-------|-------------|------------------------|-------------|
| Config | 2 | 821 | — | 821 |
| Data feeds + storage | 16 | 6,058 | — | 6,058 |
| Analytics (delta, footprint, volume profile, patterns, signals, alerts) | 17 | 3,077 | — | 3,077 |
| Atlas (live analytics + `/api/atlas/*`) | 26 | 7,558 | — | 7,558 |
| Desktop app (desktop package + packaging scripts) | 25 | 9,529 | — | 9,529 |
| Desktop UI (vanilla JS + CSS + HTML, no build step) | 84 | — | 32,469 | 32,469 |
| Legacy dashboard (host + legacy page assets) | 14 | 2,506 | 4,667 | 7,173 |
| Orchestrator (`main.py`) | 1 | 857 | — | 857 |
| **Total (excluding tests)** | **185** | **30,406** | **37,136** | **67,542** |

Measured with a line count over `orderflow_system/**` and `scripts/`; the pytest suite is another 76 files / 15,091 lines. The desktop UI also ships its icon assets and the four generated alert WAVs (`orderflow_system/desktop/ui/audio/`), which the columns above do not count.

---

## API Reference

### REST Endpoints (legacy dashboard API)

The app additionally serves `/api/atlas/*` (45 routes — heatmap, tape, CVD, profiles, imbalance,
trades, scanner, alerts, replay) and `/api/control/*` (72 routes — config, feeds, exports, layouts).
The always-current list is the running app's OpenAPI schema at `/docs`. The endpoints below are the
legacy dashboard set, kept for compatibility:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Dashboard UI |
| GET | `/api/instruments` | Active instruments with stats + trade phase |
| GET | `/api/scanner` | All pairs ranked by trade proximity (priority 0-118) |
| GET | `/api/markers/{symbol}` | the chart library chart markers for signal events |
| GET | `/api/candles/{symbol}` | OHLCV candle history (params: count, tf, range) |
| GET | `/api/volume-profile/{symbol}` | Volume profile with POC/VAH/VAL (params: days, range) |
| GET | `/api/bias/{symbol}` | Daily bias + qualified levels |
| GET | `/api/signals/{symbol}` | Signal history (params: limit) |
| GET | `/api/trade/{symbol}` | Active trade state |
| GET | `/api/strategy-status/{symbol}` | 6-step Fabio methodology checklist |
| GET | `/api/orderbook/{symbol}` | Current L2 orderbook (params: levels) |
| GET | `/api/delta/{symbol}` | Cumulative delta history (params: count, tf, range) |
| GET | `/api/footprint/{symbol}` | Footprint chart data (params: tf, range) |
| GET | `/api/tape/{symbol}` | Time & sales (params: count) |
| GET | `/api/microstructure/{symbol}` | Microstructure snapshot |
| GET | `/api/stats` | System-wide stats |

### Strategy Status Labels

| Status | Meaning |
|--------|---------|
| NO_DATA | No data received yet |
| NO_LEVELS | No qualified levels identified |
| WAITING_FOR_PRICE | Levels exist, price not nearby |
| AT_LEVEL_SCANNING | Price near a qualified level |
| WATCHING | Aggregator actively watching a level |
| ENTRY_READY | Absorption detected, composite score ≥ threshold |
| IN_TRADE | Position open |
| BREAK_EVEN | SL moved to entry |
| TRAILING | SL trailing on initiative |
| IDLE | No active monitoring |

### Scanner Priority Scoring

| State | Base Score | Bonus |
|-------|-----------|-------|
| IN_TRADE | 100 | +3 per completed step |
| TRAILING | 95 | +3 per completed step |
| BREAK_EVEN | 90 | +3 per completed step |
| ENTRY_READY | 85 | +3 per completed step |
| AT_LEVEL_SCANNING | 70 | +3 per completed step |
| WATCHING | 60 | +3 per completed step |
| WAITING_FOR_PRICE | 40 | — |
| NO_LEVELS | 20 | — |
| NO_DATA | 10 | — |
| OFFLINE | 5 | — |
| IDLE | 0 | — |

---

## Demo Mode

The system includes a **deterministic demo data generator** that produces realistic data for every shipped instrument (plus the Alpaca example symbols) — no data feed required. Runs via:

```bash
python -m orderflow_system.dashboard
```

Generates:
- OHLCV candles via random walk (seeded per symbol/timeframe)
- Volume profiles with Gaussian distributions
- Cumulative delta with bar-level noise
- Orderbooks with ~15% thin levels
- 6 institutional-grade signal templates with narrative, thesis, edge, invalidation, HTF context, session, regime, MTF confluence, blockers, and grade

### Signal Quality Grading

| Grade | Score | Meaning |
|-------|-------|---------|
| **A+** | ≥85 | Exceptional — multiple confirmations, high confluence |
| **A** | ≥70 | Strong — solid pattern + level + bias alignment |
| **B** | ≥55 | Good — pattern detected, partial confluence |
| **C** | <55 | Weak — pattern only, consider skipping |

---

## Signal Output Examples

### Entry Signal

```
ENTRY SIGNAL: NAS100 LONG
  Composite Score: 72/100
  Pattern: ABSORPTION at VAL (17,845.50)
  Delta: +1,250 (buyers absorbing sells)
  Volume: 3.2x average
  Bias: P-shape (LONG), confidence 85%
  Entry: 17,846.00 | SL: 17,830.00 | TP: 17,878.00
  R:R: 1:2.0
  Grade: A
```

### Daily Bias Update

```
DAILY BIAS: NAS100
  Shape: P-shape (buyers in control)
  Direction: LONG | Confidence: 85%
  POC: 17,852.00 | VAH: 17,890.00 | VAL: 17,820.00
  LVN: [17,835.00, 17,868.00]
  Qualified Levels: VAL (buy, str=50), MERGED_VAL (buy, str=70)
```

### Strategy Status

```
STRATEGY STATUS: NAS100
  Step 1: Profile Framing    ✓ P-shape, LONG, 85%
  Step 2: Qualified Levels   ✓ VAL=17820, MERGED_VAL=17815
  Step 3: Price at Level     ✓ Price 17825 near VAL
  Step 4: Absorption Scan    ✓ Detected, strength 72
  Step 5: Entry Decision     ✓ Composite 72 ≥ 40
  Step 6: Trade Management   ⏳ Waiting for initiative
  Overall: ENTRY_READY
```

---

## How Pattern Detection Works

### Absorption Detection (2 Methods)

```
Method 1: Delta/Close Mismatch
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Delta: +500 (buying)     Delta: -400 (selling)
  Candle: RED (closed ↓)   Candle: GREEN (closed ↑)
  → SELLERS absorbing      → BUYERS absorbing
  → Signal: SELL            → Signal: BUY

  Strength = (|delta| / min_aggressive_volume) * 40

Method 2: Level Absorption
━━━━━━━━━━━━━━━━━━━━━━━━━━
  Track aggressive volume at each price level over rolling window.
  If volume >= min_aggressive AND attempts >= min_attempts:
    → ABSORPTION signal
    Strength = (vol / min_aggressive) * 30 + attempts * 15
```

### Initiative Detection (5 Criteria)

```
┌──────────────────────────────────────────────────────────┐
│  INITIATIVE = Aggressive Conviction                      │
│                                                          │
│  All 5 must be met:                                      │
│  ┌─────────────────────────────────────────────┐        │
│  │ 1. |delta| >= min_delta_threshold (30)       │  ✓/✗  │
│  │ 2. volume / avg >= volume_accel (1.5x)       │  ✓/✗  │
│  │ 3. body_size >= min_displacement (3 ticks)   │  ✓/✗  │
│  │ 4. delta direction == candle direction       │  ✓/✗  │
│  │ 5. Bonus: one-sided imbalance prints (>3.0)  │  +10  │
│  └─────────────────────────────────────────────┘        │
│                                                          │
│  Strength = delta*20 + accel*15 + body*5 + imbalance*10 │
└──────────────────────────────────────────────────────────┘
```

---

## Composite Scoring System

The `SignalAggregator` computes a composite score (0-100) that determines whether a signal becomes a trade:

```
┌──────────────────────────────────────────────────────────┐
│              COMPOSITE SCORE CALCULATION                  │
│                                                          │
│  Signal Weight (varies by pattern):                      │
│  ┌────────────────┬────────┐                             │
│  │ Absorption     │  ×0.30 │  ← Highest weight          │
│  │ Divergence     │  ×0.25 │                             │
│  │ Initiative     │  ×0.20 │                             │
│  │ Sweep          │  ×0.20 │                             │
│  │ Other          │  ×0.15 │                             │
│  └────────────────┴────────┘                             │
│                                                          │
│  Level Strength:     ×0.25                               │
│  Bias Alignment:     ×0.20 (if direction matches)        │
│  Bias WARNING:       -10   (penalty if VA rejected)      │
│                                                          │
│  Final: clamped to [0, 100]                              │
│  Minimum to enter:   40 (configurable)                   │
└──────────────────────────────────────────────────────────┘
```

### SL/TP Calculation

| Scenario | SL (LONG) | TP (LONG) | SL (SHORT) | TP (SHORT) |
|----------|-----------|-----------|------------|------------|
| **With bias** | `val - (vah-val)×0.1` | `vah` | `vah + (vah-val)×0.1` | `val` |
| **No bias** | `price × 0.997` (-0.3%) | `price × 1.006` (+0.6%) | `price × 1.003` (+0.3%) | `price × 0.994` (-0.6%) |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines. PRs welcome — bug fixes, new pattern detectors, additional instruments, dashboard improvements.

Security reports: see [SECURITY.md](SECURITY.md) — please use the private channel there rather than a public issue.

## License

[MIT](LICENSE) — use freely in personal and commercial projects.

This distribution is a modified fork of
[mahmoud20138/OrderFlow-Analysis-Pro](https://github.com/mahmoud20138/OrderFlow-Analysis-Pro)
(forked from upstream commit `b2ff4ee`). The original MIT copyright notice is retained in
[LICENSE](LICENSE), alongside the notice for the changes made here.

## Disclaimer

This software is for **educational and research purposes only**. It is not financial advice. Trading involves substantial risk of loss. Past performance is not indicative of future results. Use at your own risk.
