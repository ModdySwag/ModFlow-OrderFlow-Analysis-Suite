"""
Global settings and instrument-specific configuration.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class Instrument(Enum):
    # ── Indices ──
    NAS100 = "NAS100USDT"
    SP500 = "SP500"
    DJ30 = "DJ30"
    UK100 = "UK100"
    DAX40 = "DAX40"
    NIKKEI225 = "NIKKEI225"
    CAC40 = "CAC40"
    ASX200 = "ASX200"
    HK50 = "HK50"
    # ── Metals ──
    GOLD = "XAUUSDT"
    SILVER = "XAGUSD"
    # ── Energy ──
    USOIL = "USOIL"
    UKOIL = "UKOIL"
    # ── Forex Majors ──
    EURUSD = "EURUSD"
    GBPUSD = "GBPUSD"
    USDJPY = "USDJPY"
    AUDUSD = "AUDUSD"
    USDCAD = "USDCAD"
    USDCHF = "USDCHF"
    NZDUSD = "NZDUSD"
    # ── Forex Crosses ──
    EURGBP = "EURGBP"
    EURJPY = "EURJPY"
    GBPJPY = "GBPJPY"
    # ── Stocks (US CFDs) ──
    AAPL = "AAPL"
    TSLA = "TSLA"
    AMZN = "AMZN"
    MSFT = "MSFT"
    NVDA = "NVDA"
    META = "META"
    GOOGL = "GOOGL"
    # ── Crypto ──
    BTCUSD = "BTCUSDT"
    # ── Crypto (Bybit linear perpetuals — streamable out of the box) ──
    ETH = "ETHUSDT"
    SOL = "SOLUSDT"
    XRP = "XRPUSDT"
    BNB = "BNBUSDT"
    DOGE = "DOGEUSDT"
    ADA = "ADAUSDT"
    AVAX = "AVAXUSDT"
    LINK = "LINKUSDT"
    LTC = "LTCUSDT"
    DOT = "DOTUSDT"
    TRX = "TRXUSDT"
    SUI = "SUIUSDT"
    APT = "APTUSDT"
    NEAR = "NEARUSDT"
    ARB = "ARBUSDT"
    OP = "OPUSDT"
    POL = "POLUSDT"
    TON = "TONUSDT"


class SessionType(Enum):
    """Trading sessions - NY cash session is primary for US indices."""
    NY_CASH = "ny_cash"          # 09:30-16:00 ET — primary for US100
    LONDON = "london"            # 08:00-16:30 GMT
    ASIAN = "asian"              # 00:00-09:00 GMT
    FULL_DAY = "full_day"        # 24h


class ProfileShape(Enum):
    P_SHAPE = "p_shape"          # Buyers in control, high volume at top, POC above 50%
    B_SHAPE = "b_shape"          # Sellers in control, high volume at bottom
    D_SHAPE = "d_shape"          # Balanced / normal distribution
    DOUBLE = "double_dist"       # Double distribution — transition day
    UNKNOWN = "unknown"


class DataSource(Enum):
    """Data feed source selection."""
    BYBIT = "bybit"              # Bybit perpetual futures (free WebSocket)
    MT5 = "mt5"                  # MetaTrader 5 terminal (real broker data)
    BOTH = "both"                # Exchange + MT5 simultaneously
    ALPACA = "alpaca"            # Alpaca Markets: US equities/ETFs/options/crypto
    ALL = "all"                  # Every configured source at once


class BiasDirection(Enum):
    LONG = "long"                # Green — buyers in control
    SHORT = "short"              # Red — sellers in control
    NEUTRAL = "neutral"          # Blue — indecision / balanced
    WARNING = "warning"          # Orange — potential shift detected


@dataclass
class AbsorptionConfig:
    """Thresholds for absorption detection."""
    min_aggressive_volume: float = 50.0       # Min contracts at a level to consider
    max_price_displacement_ticks: float = 2.0 # Max ticks price can move (low result)
    rolling_window_seconds: float = 30.0      # Time window to accumulate volume
    min_attempts: int = 2                     # Min repeated absorption attempts
    big_trade_filter: float = 10.0            # Min contract size for "big participant"


@dataclass
class InitiativeConfig:
    """Thresholds for initiative auction detection."""
    min_delta_threshold: float = 30.0         # Min |delta| for signal
    volume_acceleration_min: float = 1.5      # Volume must be 1.5x average
    min_price_displacement_ticks: float = 3.0 # Minimum price move (high result)
    delta_price_alignment: bool = True        # Delta and price must agree


@dataclass
class SweepConfig:
    """Thresholds for book sweep detection."""
    min_levels_swept: int = 3                 # Minimum levels consumed
    max_volume_per_level: float = 20.0        # Low effort threshold
    max_time_ms: float = 2000.0               # Must happen fast
    thin_book_threshold: float = 10.0         # Resting qty below this = thin


@dataclass
class ExhaustionConfig:
    """Thresholds for exhaustion detection."""
    min_bars_declining: int = 3               # Min consecutive bars of declining volume
    volume_decline_pct: float = 0.3           # Volume drops by 30%+
    requires_contrarian_imbalance: bool = True # Imbalance at extreme in opposite direction


@dataclass
class DivergenceConfig:
    """Thresholds for delta divergence detection."""
    lookback_bars: int = 10                   # Bars to look back for peaks
    min_price_new_extreme_ticks: float = 2.0  # Price must make new high/low
    delta_failure_pct: float = 0.8            # Delta peak < 80% of previous


@dataclass
class VolumeProfileConfig:
    """Volume profile computation settings."""
    value_area_pct: float = 0.68              # 68% of volume = value area
    lvn_stddev_factor: float = 1.5            # LVN = volume < mean - 1.5*stddev
    session: SessionType = SessionType.NY_CASH
    merge_max_days: int = 3                   # Max days to merge profiles
    tick_size: float = 0.01                   # Price granularity


@dataclass
class RiskConfig:
    """Risk management settings."""
    break_even_after_initiative: bool = True   # Move SL to BE after first initiative
    trail_on_initiative_prints: bool = True    # Trail stop on each new initiative candle
    min_rr_ratio: float = 2.0                 # Minimum reward:risk
    max_rr_ratio: float = 5.0                 # Maximum target R:R
    signal_cooldown_seconds: float = 60.0     # Min time between signals


@dataclass
class TelegramConfig:
    """Telegram bot settings."""
    bot_token: str = ""
    chat_id: str = ""
    send_chart_snapshots: bool = True


@dataclass
class DashboardConfig:
    """Web dashboard settings."""
    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "warning"        # uvicorn log level


@dataclass
class MT5Config:
    """MetaTrader 5 connection settings."""
    # MT5 terminal connection (leave empty to use default terminal)
    login: int = 0                            # MT5 account number (0 = use already logged in)
    password: str = ""                        # MT5 password (empty = use already logged in)
    server: str = ""                          # MT5 server (empty = use already logged in)
    path: str = ""                            # Path to MT5 terminal (empty = auto-detect)
    # Symbol mapping: internal name → MT5 broker symbol
    # Adjust these to match your broker's symbol names!
    symbols: dict = field(default_factory=lambda: {
        # ── Indices ──
        "NAS100USDT": "USTECm",
        "SP500": "US500m",
        "DJ30": "US30m",
        "UK100": "UK100m",
        "DAX40": "DE30m",
        "NIKKEI225": "JP225m",
        "CAC40": "FR40m",
        "ASX200": "AUS200m",
        "HK50": "HK50m",
        # ── Metals ──
        "XAUUSDT": "XAUUSDm",
        "XAGUSD": "XAGUSDm",
        # ── Energy ──
        "USOIL": "USOILm",
        "UKOIL": "UKOILm",
        # ── Forex Majors ──
        "EURUSD": "EURUSDm",
        "GBPUSD": "GBPUSDm",
        "USDJPY": "USDJPYm",
        "AUDUSD": "AUDUSDm",
        "USDCAD": "USDCADm",
        "USDCHF": "USDCHFm",
        "NZDUSD": "NZDUSDm",
        # ── Forex Crosses ──
        "EURGBP": "EURGBPm",
        "EURJPY": "EURJPYm",
        "GBPJPY": "GBPJPYm",
        # ── Stocks ──
        "AAPL": "AAPLm",
        "TSLA": "TSLAm",
        "AMZN": "AMZNm",
        "MSFT": "MSFTm",
        "NVDA": "NVDAm",
        "META": "METAm",
        "GOOGL": "GOOGLm",
        # ── Crypto ──
        "BTCUSDT": "BTCUSDm",
    })
    poll_interval_ms: int = 100               # Tick polling interval (ms)
    enable_book: bool = True                  # Enable DOM/Market Depth data
    download_history_days: int = 3            # Days of historical M1 bars to download (3d = ~4320 candles, covers 1W range at 1H TF)


@dataclass
class AlpacaConfig:
    """Alpaca market-data settings (keys are runtime values, set from config.json)."""
    key_id: str = ""                          # filled from the user config at start
    secret: str = ""
    paper: bool = True                        # paper keys only work on paper endpoints
    feed: str = "iex"                         # iex | sip | delayed_sip (entitlement)
    snapshot_seconds: float = 5.0             # REST snapshot cadence while open
    history_minutes: int = 240                # 1-minute bars pulled at start
    rest_per_min: int = 150                   # client budget under the plan's 200
    stock_cap: int = 30                       # stream symbols on the free plan
    option_cap: int = 200
    #: app symbol → Alpaca symbol. Alpaca covers US equities/ETFs/options and crypto.
    symbols: dict = field(default_factory=lambda: {
        "AAPL": "AAPL", "TSLA": "TSLA", "AMZN": "AMZN", "MSFT": "MSFT",
        "NVDA": "NVDA", "META": "META", "GOOGL": "GOOGL", "SPY": "SPY", "QQQ": "QQQ",
        "BTCUSDT": "BTC/USD", "ETHUSDT": "ETH/USD", "SOLUSDT": "SOL/USD",
    })


@dataclass
class InstrumentConfig:
    """Per-instrument configuration."""
    instrument: Instrument = Instrument.NAS100
    tick_size: float = 0.1
    absorption: AbsorptionConfig = field(default_factory=AbsorptionConfig)
    initiative: InitiativeConfig = field(default_factory=InitiativeConfig)
    sweep: SweepConfig = field(default_factory=SweepConfig)
    exhaustion: ExhaustionConfig = field(default_factory=ExhaustionConfig)
    divergence: DivergenceConfig = field(default_factory=DivergenceConfig)
    volume_profile: VolumeProfileConfig = field(default_factory=VolumeProfileConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)


# ─────────────────────────────────────────────
# Instrument configs — class banks + per-instrument overrides
# ─────────────────────────────────────────────
#
# This section used to be one ~35-line constructor per instrument: the same numbers
# written out three dozen times, and a page of copying to list one more symbol. A bank
# now carries what an asset class agrees on, a spec adds only what makes an instrument
# different, and `scripts/regen_config_golden.py` (read by test_config_golden.py) pins
# the result key-by-key against testdata/config_golden.json — so this is provably the
# same config the explicit constructors built, and adding an instrument is a two-line
# change (one spec row, one wrapper).

@dataclass(frozen=True)
class Bank:
    """What an asset class agrees on: the sub-configs every member starts from."""
    tick_size: float
    absorption: AbsorptionConfig
    initiative: InitiativeConfig
    sweep: SweepConfig
    exhaustion: ExhaustionConfig
    volume_profile: VolumeProfileConfig


#: One row per asset class. Read the fields as: price tick, aggressive volume,
#: displacement in ticks, attempts, big-trade filter, delta threshold, initiative
#: displacement, volume acceleration, levels swept, volume per level, thin-book
#: threshold, volume decline, session, profile tick — plus sweep window in ms where
#: a class differs. Attempts (2), declining bars (3) and the 30 s rolling window are
#: the same everywhere; they stay settable per instrument from the settings view.
_CONFIG_BANKS: dict[str, dict[str, Any]] = {
    "index_major": dict(tick_size=0.1, aggressive=40, displacement=2, attempts=2, big_trade=5,
                        delta=25, initiative_ticks=3, levels=3, per_level=15, thin_book=8,
                        decline_pct=0.3, session=SessionType.NY_CASH, vp_tick=1.0),
    "index_large": dict(tick_size=0.1, aggressive=30, displacement=2, attempts=2, big_trade=4,
                        delta=20, initiative_ticks=3, levels=3, per_level=12, thin_book=6,
                        decline_pct=0.3, session=SessionType.LONDON, vp_tick=1.0),
    "index_intl": dict(tick_size=0.1, aggressive=25, displacement=2, attempts=2, big_trade=3,
                       delta=18, initiative_ticks=3, levels=3, per_level=10, thin_book=5,
                       decline_pct=0.3, session=SessionType.ASIAN, vp_tick=1.0),
    "stock": dict(tick_size=0.01, aggressive=20, displacement=2, attempts=2, big_trade=3,
                  delta=15, initiative_ticks=3, levels=3, per_level=8, thin_book=5,
                  decline_pct=0.3, session=SessionType.NY_CASH, vp_tick=0.50),
    "forex_major": dict(tick_size=0.00001, aggressive=20, displacement=2, attempts=2, big_trade=3,
                        delta=15, initiative_ticks=3, accel=1.4, levels=3, per_level=8,
                        thin_book=5, decline_pct=0.25, session=SessionType.FULL_DAY, vp_tick=0.0005),
    "forex_jpy": dict(tick_size=0.001, aggressive=20, displacement=2, attempts=2, big_trade=3,
                      delta=15, initiative_ticks=3, accel=1.4, levels=3, per_level=8,
                      thin_book=5, decline_pct=0.25, session=SessionType.FULL_DAY, vp_tick=0.05),
    "metal_gold": dict(tick_size=0.01, aggressive=30, displacement=3, attempts=2, big_trade=3,
                       delta=20, initiative_ticks=4, levels=3, per_level=10, thin_book=5,
                       decline_pct=0.25, session=SessionType.NY_CASH, vp_tick=0.50, sweep_ms=3000),
    "metal_silver": dict(tick_size=0.001, aggressive=25, displacement=3, attempts=2, big_trade=3,
                         delta=15, initiative_ticks=4, levels=3, per_level=8, thin_book=5,
                         decline_pct=0.25, session=SessionType.FULL_DAY, vp_tick=0.05, sweep_ms=3000),
    "energy": dict(tick_size=0.01, aggressive=30, displacement=3, attempts=2, big_trade=3,
                   delta=20, initiative_ticks=4, levels=3, per_level=10, thin_book=5,
                   decline_pct=0.25, session=SessionType.NY_CASH, vp_tick=0.1),
    "crypto": dict(tick_size=0.01, aggressive=20, displacement=3, attempts=2, big_trade=3,
                   delta=15, initiative_ticks=4, levels=3, per_level=8, thin_book=5,
                   decline_pct=0.25, session=SessionType.FULL_DAY, vp_tick=10.0),
}


def _bank(tick_size: float, aggressive: float, displacement: float, attempts: int,
          big_trade: float, delta: float, initiative_ticks: float, levels: int,
          per_level: float, thin_book: float, decline_pct: float, session: SessionType,
          vp_tick: float, accel: float = 1.5, sweep_ms: int = 2000,
          bars_declining: int = 3, rolling_window_s: float = 30) -> Bank:
    """Turn one bank row into sub-configs (kwargs are spelled out at the call sites)."""
    return Bank(
        tick_size=tick_size,
        absorption=AbsorptionConfig(
            min_aggressive_volume=aggressive,
            max_price_displacement_ticks=displacement,
            rolling_window_seconds=rolling_window_s,
            min_attempts=attempts,
            big_trade_filter=big_trade,
        ),
        initiative=InitiativeConfig(
            min_delta_threshold=delta,
            volume_acceleration_min=accel,
            min_price_displacement_ticks=initiative_ticks,
        ),
        sweep=SweepConfig(
            min_levels_swept=levels,
            max_volume_per_level=per_level,
            max_time_ms=sweep_ms,
            thin_book_threshold=thin_book,
        ),
        exhaustion=ExhaustionConfig(
            min_bars_declining=bars_declining,
            volume_decline_pct=decline_pct,
        ),
        volume_profile=VolumeProfileConfig(session=session, tick_size=vp_tick),
    )


@dataclass(frozen=True)
class Spec:
    """What makes one instrument different from its class bank (None = inherit)."""
    bank: str
    tick_size: Optional[float] = None
    aggressive: Optional[float] = None
    delta: Optional[float] = None
    levels: Optional[int] = None
    per_level: Optional[float] = None
    thin_book: Optional[float] = None
    decline_pct: Optional[float] = None
    vp_session: Optional[SessionType] = None
    vp_tick: Optional[float] = None


#: Every instrument the app ships, against its class bank. A row with no overrides
#: means "this one is exactly its class" — which is now visible instead of implied.
INSTRUMENT_SPECS: dict[Instrument, Spec] = {
    # Indices
    Instrument.NAS100:    Spec("index_major", aggressive=50, delta=30),
    Instrument.SP500:     Spec("index_major"),
    Instrument.DJ30:      Spec("index_major", tick_size=1.0, vp_tick=5.0),
    Instrument.UK100:     Spec("index_large"),
    Instrument.DAX40:     Spec("index_large", vp_tick=2.0),
    Instrument.NIKKEI225: Spec("index_large", tick_size=1.0, vp_session=SessionType.ASIAN, vp_tick=50.0),
    Instrument.CAC40:     Spec("index_intl", vp_session=SessionType.LONDON),
    Instrument.ASX200:    Spec("index_intl"),
    Instrument.HK50:      Spec("index_intl", tick_size=1.0, vp_tick=5.0),
    # Metals
    Instrument.GOLD:      Spec("metal_gold"),
    Instrument.SILVER:    Spec("metal_silver"),
    # Energy
    Instrument.USOIL:     Spec("energy"),
    Instrument.UKOIL:     Spec("energy", vp_session=SessionType.LONDON),
    # Forex majors
    Instrument.EURUSD:    Spec("forex_major"),
    Instrument.GBPUSD:    Spec("forex_major"),
    Instrument.AUDUSD:    Spec("forex_major"),
    Instrument.USDCAD:    Spec("forex_major"),
    Instrument.USDCHF:    Spec("forex_major"),
    Instrument.NZDUSD:    Spec("forex_major"),
    # Forex crosses (JPY pairs price in 3 digits)
    Instrument.USDJPY:    Spec("forex_jpy"),
    Instrument.EURJPY:    Spec("forex_jpy"),
    Instrument.GBPJPY:    Spec("forex_jpy"),
    Instrument.EURGBP:    Spec("forex_major"),
    # Stocks (US CFDs)
    Instrument.AAPL:      Spec("stock"),
    Instrument.TSLA:      Spec("stock"),
    Instrument.AMZN:      Spec("stock"),
    Instrument.MSFT:      Spec("stock"),
    Instrument.NVDA:      Spec("stock"),
    Instrument.META:      Spec("stock"),
    Instrument.GOOGL:     Spec("stock"),
    # Crypto
    Instrument.BTCUSD:    Spec("crypto"),
    # Crypto majors without a spec row fall back to the crypto bank + CRYPTO_MAJORS.
}

#: Bybit-listed crypto majors a fresh install can stream, with their default
#: tick sizes. The setup assistant corrects these from the venue when it imports
#: instruments, so a value here only needs to be sane, not exact.
CRYPTO_MAJORS: dict[str, float] = {
    "ETHUSDT": 0.01, "SOLUSDT": 0.01, "XRPUSDT": 0.0001, "BNBUSDT": 0.1,
    "DOGEUSDT": 0.00001, "ADAUSDT": 0.0001, "AVAXUSDT": 0.001, "LINKUSDT": 0.001,
    "LTCUSDT": 0.01, "DOTUSDT": 0.001, "TRXUSDT": 0.00001, "SUIUSDT": 0.0001,
    "APTUSDT": 0.001, "NEARUSDT": 0.001, "ARBUSDT": 0.0001, "OPUSDT": 0.0001,
    "POLUSDT": 0.0001, "TONUSDT": 0.001,
}


def instrument_for(symbol: str) -> Instrument:
    """The Instrument member for a symbol, extending the enum for venue-only ones.

    The enum lists what the app ships, but Bybit lists hundreds of perpetuals and the
    setup assistant can add any of them. Rather than let those symbols die as
    "unknown instrument", a member is created on first use with the documented
    extend-at-runtime recipe — it behaves like any other (same `.value`, same dict and
    JSON round-trip, idempotent per symbol).
    """
    try:
        return Instrument(symbol)
    except ValueError:
        pass
    member = object.__new__(Instrument)
    member._name_ = symbol
    member._value_ = symbol
    Instrument._value2member_map_[symbol] = member
    Instrument._member_map_[symbol] = member
    Instrument._member_names_.append(symbol)      # so iteration sees it too
    return member


def config_for_symbol(symbol: str, tick_size: Optional[float] = None) -> InstrumentConfig:
    """Config for any symbol, shipped or venue-only (`get_config_for` + enum extension).

    This is what the engine calls for an instrument a user added from the venue
    catalogue: a known symbol uses its spec bank, an unknown one gets the crypto
    profile with the tick size the venue reported.
    """
    return get_config_for(instrument_for(symbol), tick_size)


def get_config_for(instrument: Instrument, tick_size: Optional[float] = None) -> InstrumentConfig:
    """Build an instrument's config: class bank, then spec overrides, then a tick.

    The single place an InstrumentConfig is constructed. Precedence for the price tick
    is explicit argument → spec → CRYPTO_MAJORS → bank, so a caller that knows the
    venue's tick (the setup assistant does) always wins.

    Adding an instrument: one `Spec` row above, one wrapper below, and
    `scripts/regen_config_golden.py --write` to record it.
    """
    spec = INSTRUMENT_SPECS.get(instrument)
    bank_key = spec.bank if spec is not None else "crypto"
    if bank_key not in _CONFIG_BANKS:
        raise KeyError(f"{instrument.value}: unknown config bank {bank_key!r}")

    fields = dict(_CONFIG_BANKS[bank_key])
    if spec is not None:
        for name in ("aggressive", "delta", "levels", "per_level", "thin_book", "decline_pct"):
            if getattr(spec, name) is not None:
                fields[name] = getattr(spec, name)
        if spec.vp_session is not None:
            fields["session"] = spec.vp_session
        if spec.vp_tick is not None:
            fields["vp_tick"] = spec.vp_tick

    fields["tick_size"] = float(
        tick_size
        or (spec.tick_size if spec is not None else None)
        or CRYPTO_MAJORS.get(instrument.value)
        or fields["tick_size"]
    )

    bank = _bank(**fields)
    return InstrumentConfig(
        instrument=instrument,
        tick_size=bank.tick_size,
        absorption=bank.absorption,
        initiative=bank.initiative,
        sweep=bank.sweep,
        exhaustion=bank.exhaustion,
        volume_profile=bank.volume_profile,
    )


# ── Thin wrappers (public API: some are imported by name elsewhere) ──

def get_nas100_config() -> InstrumentConfig:
    """NAS100USDT (Bybit perpetual) — proxy for NASDAQ futures."""
    return get_config_for(Instrument.NAS100)


def get_sp500_config() -> InstrumentConfig:
    """S&P 500 index CFD."""
    return get_config_for(Instrument.SP500)


def get_dj30_config() -> InstrumentConfig:
    """Dow Jones 30 index CFD."""
    return get_config_for(Instrument.DJ30)


def get_uk100_config() -> InstrumentConfig:
    """FTSE 100 index CFD."""
    return get_config_for(Instrument.UK100)


def get_dax40_config() -> InstrumentConfig:
    """DAX 40 index CFD."""
    return get_config_for(Instrument.DAX40)


def get_nikkei225_config() -> InstrumentConfig:
    """Nikkei 225 index CFD."""
    return get_config_for(Instrument.NIKKEI225)


def get_cac40_config() -> InstrumentConfig:
    """CAC 40 index CFD."""
    return get_config_for(Instrument.CAC40)


def get_asx200_config() -> InstrumentConfig:
    """ASX 200 index CFD."""
    return get_config_for(Instrument.ASX200)


def get_hk50_config() -> InstrumentConfig:
    """Hang Seng 50 index CFD."""
    return get_config_for(Instrument.HK50)


def get_gold_config() -> InstrumentConfig:
    """XAUUSDT (Bybit perpetual) — proxy for Gold futures."""
    return get_config_for(Instrument.GOLD)


def get_silver_config() -> InstrumentConfig:
    """XAGUSD — Silver."""
    return get_config_for(Instrument.SILVER)


def get_usoil_config() -> InstrumentConfig:
    """WTI Crude Oil."""
    return get_config_for(Instrument.USOIL)


def get_ukoil_config() -> InstrumentConfig:
    """Brent Crude Oil."""
    return get_config_for(Instrument.UKOIL)


def get_eurusd_config() -> InstrumentConfig:
    """EUR/USD — most liquid forex pair."""
    return get_config_for(Instrument.EURUSD)


def get_gbpusd_config() -> InstrumentConfig:
    """GBP/USD — Cable."""
    return get_config_for(Instrument.GBPUSD)


def get_usdjpy_config() -> InstrumentConfig:
    """USD/JPY — 3-digit pricing."""
    return get_config_for(Instrument.USDJPY)


def get_audusd_config() -> InstrumentConfig:
    """AUD/USD — Aussie."""
    return get_config_for(Instrument.AUDUSD)


def get_usdcad_config() -> InstrumentConfig:
    """USD/CAD — Loonie."""
    return get_config_for(Instrument.USDCAD)


def get_usdchf_config() -> InstrumentConfig:
    """USD/CHF — Swissie."""
    return get_config_for(Instrument.USDCHF)


def get_nzdusd_config() -> InstrumentConfig:
    """NZD/USD — Kiwi."""
    return get_config_for(Instrument.NZDUSD)


def get_eurgbp_config() -> InstrumentConfig:
    """EUR/GBP — European cross."""
    return get_config_for(Instrument.EURGBP)


def get_eurjpy_config() -> InstrumentConfig:
    """EUR/JPY — European yen cross."""
    return get_config_for(Instrument.EURJPY)


def get_gbpjpy_config() -> InstrumentConfig:
    """GBP/JPY — Dragon."""
    return get_config_for(Instrument.GBPJPY)


def get_aapl_config() -> InstrumentConfig:
    """Apple — US stock CFD."""
    return get_config_for(Instrument.AAPL)


def get_tsla_config() -> InstrumentConfig:
    """Tesla — US stock CFD."""
    return get_config_for(Instrument.TSLA)


def get_amzn_config() -> InstrumentConfig:
    """Amazon — US stock CFD."""
    return get_config_for(Instrument.AMZN)


def get_msft_config() -> InstrumentConfig:
    """Microsoft — US stock CFD."""
    return get_config_for(Instrument.MSFT)


def get_nvda_config() -> InstrumentConfig:
    """NVIDIA — US stock CFD."""
    return get_config_for(Instrument.NVDA)


def get_meta_config() -> InstrumentConfig:
    """Meta Platforms — US stock CFD."""
    return get_config_for(Instrument.META)


def get_googl_config() -> InstrumentConfig:
    """Alphabet — US stock CFD."""
    return get_config_for(Instrument.GOOGL)


def get_btcusd_config() -> InstrumentConfig:
    """BTCUSDT — Bitcoin."""
    return get_config_for(Instrument.BTCUSD)


def get_crypto_config(symbol: str, tick_size: float = 0.0) -> InstrumentConfig:
    """A crypto perpetual config using the same pattern thresholds as BTC.

    Crypto majors share one profile: the thresholds that work on BTC's tape are
    the sane starting point for the rest, and every value stays editable from the
    desktop settings view.
    """
    return get_config_for(Instrument(symbol), tick_size or None)


def get_all_configs() -> list[InstrumentConfig]:
    """Return config for ALL instruments."""
    return [
        # Indices
        get_nas100_config(),
        get_sp500_config(),
        get_dj30_config(),
        get_uk100_config(),
        get_dax40_config(),
        get_nikkei225_config(),
        get_cac40_config(),
        get_asx200_config(),
        get_hk50_config(),
        # Metals
        get_gold_config(),
        get_silver_config(),
        # Energy
        get_usoil_config(),
        get_ukoil_config(),
        # Forex Majors
        get_eurusd_config(),
        get_gbpusd_config(),
        get_usdjpy_config(),
        get_audusd_config(),
        get_usdcad_config(),
        get_usdchf_config(),
        get_nzdusd_config(),
        # Forex Crosses
        get_eurgbp_config(),
        get_eurjpy_config(),
        get_gbpjpy_config(),
        # Stocks
        get_aapl_config(),
        get_tsla_config(),
        get_amzn_config(),
        get_msft_config(),
        get_nvda_config(),
        get_meta_config(),
        get_googl_config(),
        # Crypto
        get_btcusd_config(),
        # Crypto majors (the setup assistant can import more from the venue)
        *[get_crypto_config(sym) for sym in CRYPTO_MAJORS],
    ]


# ── Footprint ──
#: Prints smaller than this are ignored while building footprint bars (the conventional "Volume
#: Filtering"). Set from the desktop config's `atlas.footprint.min_print_size`.
FOOTPRINT_MIN_PRINT_SIZE: float = 0.0

# ── Data Source ──
# Change this to select your data feed:
#   DataSource.MT5    → Use MetaTrader 5 (real broker data for NAS100, XAUUSD)
#   DataSource.BYBIT  → Use Bybit perpetuals (free crypto data)
#   DataSource.BOTH   → Run the exchange and MT5 feeds simultaneously
#   DataSource.ALPACA → Use Alpaca Markets (US equities, ETFs, options, crypto)
#   DataSource.ALL    → Run every configured source at once
DATA_SOURCE = DataSource.MT5

# ── MT5 Configuration ──
# Adjust symbol names to match your broker!
# Common alternatives:
#   NAS100: "USTEC", "NAS100", "US100", "USTEC.cash", "USTECH100", "#NAS100"
#   Gold:   "XAUUSD", "GOLD", "XAUUSD.cash"
MT5 = MT5Config()

# ── Alpaca Configuration ──
# API keys live in the user config file (config.json → "alpaca"), never in source:
# the desktop app writes them when you validate them in the Alpaca view, and this
# module only carries the non-secret settings plus the symbol translation.
#
# The symbol map is app symbol → Alpaca symbol, the same pattern MT5.symbols uses.
# Equities are plain tickers; Alpaca's crypto pairs are "BASE/QUOTE".
ALPACA = AlpacaConfig()

# Telegram config — user fills in their token/chat_id
TELEGRAM = TelegramConfig()

# ── Dashboard ──
# Web dashboard at http://localhost:8080
DASHBOARD = DashboardConfig()

# Database
DB_PATH = "orderflow_data.db"

# Logging
LOG_LEVEL = "INFO"
