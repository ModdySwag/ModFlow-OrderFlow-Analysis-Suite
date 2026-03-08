# OrderFlow Analysis Pro

**5-Pattern Orderflow Scanner -- Volume Profile Framing -- State Machine Trade Lifecycle -- MT5 + Bybit -- Dash + Telegram**

A real-time orderflow trading system based on Fabio Testa's methodology that analyzes market microstructure (tick-level data, footprint charts, volume profiles, L2 orderbook) to detect 5 core patterns -- absorption, initiative, sweep, exhaustion, and divergence -- then routes them through a state machine trade lifecycle with automated Telegram alerts. Supports 30+ instruments via MT5 and Bybit feeds with a live FastAPI dashboard.

---

## Architecture

```
Data Sources (MT5 + Bybit)
        |
        v
  Tick Stream --> Candle Builder (1m aggregation)
        |
        v
  Analytics Engines (parallel)
    +-- Volume Profile (POC, VAH, VAL, LVN, shape)
    +-- Delta Engine (vertical, horizontal, cumulative)
    +-- Footprint Engine (bid/ask per level, imbalance)
    +-- Orderbook Tracker (L2 depth, thin levels)
        |
        v
  5 Pattern Detectors
    +-- Absorption (effort >> result)
    +-- Initiative (effort = result)
    +-- Sweep (thin book displacement)
    +-- Exhaustion (declining effort at extreme)
    +-- Divergence (price vs delta disagreement)
        |
        v
  Profile Framing --> Daily Bias (P/b/D shape, qualified levels)
        |
        v
  Signal Aggregator (state machine)
    WATCHING --> ABSORPTION --> POSITION --> BREAK_EVEN --> TRAILING --> CLOSED
        |
        v
  Telegram Alerts + Dashboard (FastAPI + WebSocket) + SQLite Journal
```

---

## The 5 Core Patterns

| # | Pattern | Logic | Signal |
|---|---------|-------|--------|
| 1 | **Absorption** | High aggressive volume at a level with minimal price displacement (effort >> result) | Entry signal at VAH/VAL |
| 2 | **Initiative** | Strong delta + volume acceleration + price displacement aligned (effort = result) | Break-even / trail trigger |
| 3 | **Sweep** | Price moves through thin orderbook levels with low volume | Liquidity grab, reversal |
| 4 | **Exhaustion** | Price making new extremes but volume/delta declining 30%+ | Weakening momentum |
| 5 | **Divergence** | Price new high/low but cumulative delta fails to confirm | Trend reversal warning |

Each pattern outputs a strength score (0-100) and directional bias.

---

## Volume Profile Framing (Daily Bias)

Implements Fabio Testa's profile shape analysis:

| Shape | POC Position | Bias | Trading Plan |
|-------|-------------|------|-------------|
| **P-shape** | POC > 65% | LONG | Buyers in control, buy dips to VAL |
| **b-shape** | POC < 35% | SHORT | Sellers in control, sell rallies to VAH |
| **D-shape** | POC ~50% | NEUTRAL | Balanced, fade extremes |
| **Double Distribution** | Bimodal | TRANSITION | Watch for breakout direction |

**Qualified Levels** (trade from these):
- VAH (Value Area High) -- sell zone
- VAL (Value Area Low) -- buy zone
- POC (Point of Control) -- pivot
- LVN (Low Volume Nodes) -- rebalancing levels
- Merged multi-day levels -- confluence

---

## State Machine Trade Lifecycle

```
WATCHING --> price near qualified level
    | (absorption detected)
ABSORPTION_DETECTED --> entry signal sent
    | (trade opened)
POSITION_OPEN --> waiting for initiative
    | (first initiative auction)
BREAK_EVEN --> SL moved to entry
    | (subsequent initiative)
TRAILING --> SL trailed to candle extremes
    | (exit signal or SL hit)
CLOSED --> trade logged to journal
```

---

## Supported Instruments (30+)

| Category | Instruments |
|----------|------------|
| Indices | NAS100, SP500, DJ30, UK100, DAX40, NIKKEI225, CAC40, ASX200, HK50 |
| Metals | XAUUSDT (Gold), XAGUSD (Silver) |
| Energy | USOIL, UKOIL |
| Forex Majors | EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, USDCHF, NZDUSD |
| Forex Crosses | EURGBP, EURJPY, GBPJPY |
| US Stocks | AAPL, TSLA, AMZN, MSFT, NVDA, META, GOOGL |
| Crypto | BTCUSDT |

Each instrument has pre-tuned thresholds for all 5 pattern detectors.

---

## Dashboard (FastAPI + WebSocket)

**REST API:**
- `GET /api/instruments` -- Active instruments + stats
- `GET /api/candles/{symbol}` -- Recent candles
- `GET /api/volume-profile/{symbol}` -- VP histogram + shape
- `GET /api/bias/{symbol}` -- Daily bias + qualified levels
- `GET /api/signals/{symbol}` -- Signal history
- `GET /api/trade/{symbol}` -- Active trade state
- `GET /api/orderbook/{symbol}` -- L2 orderbook depth
- `GET /api/delta/{symbol}` -- Delta history

**WebSocket** (`/ws`):
- Real-time tick stream
- Candle updates with delta
- Volume profile updates
- Signal announcements
- Trade state transitions

**Frontend**: Interactive charts (lightweight-charts), volume profile visualization, orderbook depth, signal timeline.

---

## Telegram Alerts

Automated notifications for each trade lifecycle event:

| Alert Type | When |
|-----------|------|
| ENTRY SIGNAL | Absorption at qualified level, composite score > 40 |
| BREAK EVEN | First initiative auction after entry |
| TRAIL UPDATE | Subsequent initiatives, SL moved |
| EXIT SIGNAL | Trade closed (SL or target) |
| EXIT WARNING | Exhaustion or divergence detected |
| DAILY BIAS | New VP shape + direction + confidence |

---

## Data Sources

### MT5 Feed
- Real-time tick polling from MetaTrader 5
- Historical bar download for backtesting
- Market Book (DOM) data for orderbook analysis
- Symbol mapping (NAS100 -> USTEC, etc.)

### Bybit Feed
- Free WebSocket data from Bybit perpetual futures
- Trade stream with aggressor side (buy/sell)
- L2 orderbook (50 levels)
- No API key required

---

## Installation

### Prerequisites

- Python 3.10+
- MetaTrader 5 terminal (for MT5 feed) or Bybit (free, no account needed)

### Setup

```bash
cd orderflow_system
pip install -e .
# or
pip install websockets aiohttp pandas numpy scipy python-telegram-bot plotly aiosqlite pytz
```

### Configuration

Edit `orderflow_system/config/settings.py`:

```python
# Data source
DATA_SOURCE = "BYBIT"          # "MT5", "BYBIT", or "BOTH"

# MT5 credentials (if using MT5)
MT5_LOGIN = 12345678
MT5_PASSWORD = "your_password"
MT5_SERVER = "YourBroker-Server"

# Telegram alerts
TELEGRAM_BOT_TOKEN = "your_bot_token"
TELEGRAM_CHAT_ID = "your_chat_id"

# Dashboard
DASHBOARD_ENABLED = True
DASHBOARD_PORT = 8080
```

---

## Usage

```bash
# Start the system
python -m orderflow_system.main

# The system will:
# 1. Connect to data source(s)
# 2. Build volume profiles
# 3. Start pattern detection
# 4. Send alerts via Telegram
# 5. Serve dashboard at http://localhost:8080
```

---

## Results & Output

### Signal Example

```
ENTRY SIGNAL: NAS100 LONG
  Composite Score: 72/100
  Pattern: ABSORPTION at VAL (17,845.50)
  Delta: +1,250 (buyers absorbing)
  Volume: 3.2x average
  Bias: P-shape (LONG), confidence 85%
  Entry: 17,846.00 | SL: 17,830.00 | TP: 17,878.00
  R:R: 1:2.0
```

### Daily Bias

```
DAILY BIAS: NAS100
  Shape: P-shape (buyers in control)
  Direction: LONG | Confidence: 85%
  POC: 17,852.00 | VAH: 17,890.00 | VAL: 17,820.00
  LVN: [17,835.00, 17,868.00]
  Qualified Levels: VAL (buy), LVN-17835 (buy)
```

---

## Project Structure

```
orderflow_system/
  main.py                          # System orchestrator
  config/
    settings.py                    # 30+ instrument configs, thresholds
  data/
    models.py                      # Tick, Candle, Signal, TradeState
    candle_builder.py              # Tick -> 1m candle aggregation
    bybit_feed.py                  # Bybit WebSocket (free, no key)
    mt5_feed.py                    # MT5 terminal polling
    database.py                    # SQLite persistence (WAL mode)
  analytics/
    volume_profile.py              # POC, VAH, VAL, LVN, shape
    delta.py                       # Vertical, horizontal, cumulative delta
    footprint.py                   # Bid/ask per level, imbalance
    orderbook.py                   # L2 depth, thin levels, sweeps
  patterns/
    absorption.py                  # Effort >> result detection
    initiative.py                  # Effort = result (momentum)
    sweep.py                       # Thin book displacement
    exhaustion.py                  # Declining volume at extremes
    divergence.py                  # Price vs delta disagreement
  signals/
    profile_framing.py             # Daily bias (P/b/D shape)
    aggregator.py                  # State machine + signal weighting
  alerts/
    telegram_bot.py                # Telegram notifications
  dashboard/
    app.py                         # FastAPI REST + WebSocket
    websocket_manager.py           # Real-time broadcast
    static/                        # Frontend (charts, UI)
```
