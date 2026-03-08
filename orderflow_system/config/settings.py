"""
Global settings and instrument-specific configuration.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


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
    BOTH = "both"                # Run both feeds simultaneously


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


def get_nas100_config() -> InstrumentConfig:
    """NAS100USDT (Bybit perpetual) — proxy for NASDAQ futures."""
    return InstrumentConfig(
        instrument=Instrument.NAS100,
        tick_size=0.1,
        absorption=AbsorptionConfig(
            min_aggressive_volume=50,
            max_price_displacement_ticks=2,
            rolling_window_seconds=30,
            min_attempts=2,
            big_trade_filter=5,
        ),
        initiative=InitiativeConfig(
            min_delta_threshold=30,
            volume_acceleration_min=1.5,
            min_price_displacement_ticks=3,
        ),
        sweep=SweepConfig(
            min_levels_swept=3,
            max_volume_per_level=15,
            max_time_ms=2000,
            thin_book_threshold=8,
        ),
        exhaustion=ExhaustionConfig(
            min_bars_declining=3,
            volume_decline_pct=0.3,
        ),
        volume_profile=VolumeProfileConfig(
            session=SessionType.NY_CASH,
            tick_size=1.0,
        ),
    )


def get_gold_config() -> InstrumentConfig:
    """XAUUSDT (Bybit perpetual) — proxy for Gold futures."""
    return InstrumentConfig(
        instrument=Instrument.GOLD,
        tick_size=0.01,
        absorption=AbsorptionConfig(
            min_aggressive_volume=30,
            max_price_displacement_ticks=3,
            rolling_window_seconds=30,
            min_attempts=2,
            big_trade_filter=3,
        ),
        initiative=InitiativeConfig(
            min_delta_threshold=20,
            volume_acceleration_min=1.5,
            min_price_displacement_ticks=4,
        ),
        sweep=SweepConfig(
            min_levels_swept=3,
            max_volume_per_level=10,
            max_time_ms=3000,
            thin_book_threshold=5,
        ),
        exhaustion=ExhaustionConfig(
            min_bars_declining=3,
            volume_decline_pct=0.25,
        ),
        volume_profile=VolumeProfileConfig(
            session=SessionType.NY_CASH,
            tick_size=0.50,
        ),
    )


# ─────────────────────────────────────────────
# Index Configs
# ─────────────────────────────────────────────

def get_sp500_config() -> InstrumentConfig:
    """S&P 500 index CFD."""
    return InstrumentConfig(
        instrument=Instrument.SP500,
        tick_size=0.1,
        absorption=AbsorptionConfig(
            min_aggressive_volume=40,
            max_price_displacement_ticks=2,
            rolling_window_seconds=30,
            min_attempts=2,
            big_trade_filter=5,
        ),
        initiative=InitiativeConfig(
            min_delta_threshold=25,
            volume_acceleration_min=1.5,
            min_price_displacement_ticks=3,
        ),
        sweep=SweepConfig(
            min_levels_swept=3,
            max_volume_per_level=15,
            max_time_ms=2000,
            thin_book_threshold=8,
        ),
        exhaustion=ExhaustionConfig(
            min_bars_declining=3,
            volume_decline_pct=0.3,
        ),
        volume_profile=VolumeProfileConfig(
            session=SessionType.NY_CASH,
            tick_size=1.0,
        ),
    )


def get_dj30_config() -> InstrumentConfig:
    """Dow Jones 30 index CFD."""
    return InstrumentConfig(
        instrument=Instrument.DJ30,
        tick_size=1.0,
        absorption=AbsorptionConfig(
            min_aggressive_volume=40,
            max_price_displacement_ticks=2,
            rolling_window_seconds=30,
            min_attempts=2,
            big_trade_filter=5,
        ),
        initiative=InitiativeConfig(
            min_delta_threshold=25,
            volume_acceleration_min=1.5,
            min_price_displacement_ticks=3,
        ),
        sweep=SweepConfig(
            min_levels_swept=3,
            max_volume_per_level=15,
            max_time_ms=2000,
            thin_book_threshold=8,
        ),
        exhaustion=ExhaustionConfig(
            min_bars_declining=3,
            volume_decline_pct=0.3,
        ),
        volume_profile=VolumeProfileConfig(
            session=SessionType.NY_CASH,
            tick_size=5.0,
        ),
    )


def get_uk100_config() -> InstrumentConfig:
    """FTSE 100 index CFD."""
    return InstrumentConfig(
        instrument=Instrument.UK100,
        tick_size=0.1,
        absorption=AbsorptionConfig(
            min_aggressive_volume=30,
            max_price_displacement_ticks=2,
            rolling_window_seconds=30,
            min_attempts=2,
            big_trade_filter=4,
        ),
        initiative=InitiativeConfig(
            min_delta_threshold=20,
            volume_acceleration_min=1.5,
            min_price_displacement_ticks=3,
        ),
        sweep=SweepConfig(
            min_levels_swept=3,
            max_volume_per_level=12,
            max_time_ms=2000,
            thin_book_threshold=6,
        ),
        exhaustion=ExhaustionConfig(
            min_bars_declining=3,
            volume_decline_pct=0.3,
        ),
        volume_profile=VolumeProfileConfig(
            session=SessionType.LONDON,
            tick_size=1.0,
        ),
    )


def get_dax40_config() -> InstrumentConfig:
    """DAX 40 index CFD."""
    return InstrumentConfig(
        instrument=Instrument.DAX40,
        tick_size=0.1,
        absorption=AbsorptionConfig(
            min_aggressive_volume=30,
            max_price_displacement_ticks=2,
            rolling_window_seconds=30,
            min_attempts=2,
            big_trade_filter=4,
        ),
        initiative=InitiativeConfig(
            min_delta_threshold=20,
            volume_acceleration_min=1.5,
            min_price_displacement_ticks=3,
        ),
        sweep=SweepConfig(
            min_levels_swept=3,
            max_volume_per_level=12,
            max_time_ms=2000,
            thin_book_threshold=6,
        ),
        exhaustion=ExhaustionConfig(
            min_bars_declining=3,
            volume_decline_pct=0.3,
        ),
        volume_profile=VolumeProfileConfig(
            session=SessionType.LONDON,
            tick_size=2.0,
        ),
    )


def get_nikkei225_config() -> InstrumentConfig:
    """Nikkei 225 index CFD."""
    return InstrumentConfig(
        instrument=Instrument.NIKKEI225,
        tick_size=1.0,
        absorption=AbsorptionConfig(
            min_aggressive_volume=30,
            max_price_displacement_ticks=2,
            rolling_window_seconds=30,
            min_attempts=2,
            big_trade_filter=4,
        ),
        initiative=InitiativeConfig(
            min_delta_threshold=20,
            volume_acceleration_min=1.5,
            min_price_displacement_ticks=3,
        ),
        sweep=SweepConfig(
            min_levels_swept=3,
            max_volume_per_level=12,
            max_time_ms=2000,
            thin_book_threshold=6,
        ),
        exhaustion=ExhaustionConfig(
            min_bars_declining=3,
            volume_decline_pct=0.3,
        ),
        volume_profile=VolumeProfileConfig(
            session=SessionType.ASIAN,
            tick_size=50.0,
        ),
    )


def get_cac40_config() -> InstrumentConfig:
    """CAC 40 index CFD."""
    return InstrumentConfig(
        instrument=Instrument.CAC40,
        tick_size=0.1,
        absorption=AbsorptionConfig(
            min_aggressive_volume=25,
            max_price_displacement_ticks=2,
            rolling_window_seconds=30,
            min_attempts=2,
            big_trade_filter=3,
        ),
        initiative=InitiativeConfig(
            min_delta_threshold=18,
            volume_acceleration_min=1.5,
            min_price_displacement_ticks=3,
        ),
        sweep=SweepConfig(
            min_levels_swept=3,
            max_volume_per_level=10,
            max_time_ms=2000,
            thin_book_threshold=5,
        ),
        exhaustion=ExhaustionConfig(
            min_bars_declining=3,
            volume_decline_pct=0.3,
        ),
        volume_profile=VolumeProfileConfig(
            session=SessionType.LONDON,
            tick_size=1.0,
        ),
    )


def get_asx200_config() -> InstrumentConfig:
    """ASX 200 index CFD."""
    return InstrumentConfig(
        instrument=Instrument.ASX200,
        tick_size=0.1,
        absorption=AbsorptionConfig(
            min_aggressive_volume=25,
            max_price_displacement_ticks=2,
            rolling_window_seconds=30,
            min_attempts=2,
            big_trade_filter=3,
        ),
        initiative=InitiativeConfig(
            min_delta_threshold=18,
            volume_acceleration_min=1.5,
            min_price_displacement_ticks=3,
        ),
        sweep=SweepConfig(
            min_levels_swept=3,
            max_volume_per_level=10,
            max_time_ms=2000,
            thin_book_threshold=5,
        ),
        exhaustion=ExhaustionConfig(
            min_bars_declining=3,
            volume_decline_pct=0.3,
        ),
        volume_profile=VolumeProfileConfig(
            session=SessionType.ASIAN,
            tick_size=1.0,
        ),
    )


def get_hk50_config() -> InstrumentConfig:
    """Hang Seng 50 index CFD."""
    return InstrumentConfig(
        instrument=Instrument.HK50,
        tick_size=1.0,
        absorption=AbsorptionConfig(
            min_aggressive_volume=25,
            max_price_displacement_ticks=2,
            rolling_window_seconds=30,
            min_attempts=2,
            big_trade_filter=3,
        ),
        initiative=InitiativeConfig(
            min_delta_threshold=18,
            volume_acceleration_min=1.5,
            min_price_displacement_ticks=3,
        ),
        sweep=SweepConfig(
            min_levels_swept=3,
            max_volume_per_level=10,
            max_time_ms=2000,
            thin_book_threshold=5,
        ),
        exhaustion=ExhaustionConfig(
            min_bars_declining=3,
            volume_decline_pct=0.3,
        ),
        volume_profile=VolumeProfileConfig(
            session=SessionType.ASIAN,
            tick_size=5.0,
        ),
    )


# ─────────────────────────────────────────────
# Metal & Energy Configs
# ─────────────────────────────────────────────

def get_silver_config() -> InstrumentConfig:
    """XAGUSD — Silver CFD."""
    return InstrumentConfig(
        instrument=Instrument.SILVER,
        tick_size=0.001,
        absorption=AbsorptionConfig(
            min_aggressive_volume=25,
            max_price_displacement_ticks=3,
            rolling_window_seconds=30,
            min_attempts=2,
            big_trade_filter=3,
        ),
        initiative=InitiativeConfig(
            min_delta_threshold=15,
            volume_acceleration_min=1.5,
            min_price_displacement_ticks=4,
        ),
        sweep=SweepConfig(
            min_levels_swept=3,
            max_volume_per_level=8,
            max_time_ms=3000,
            thin_book_threshold=5,
        ),
        exhaustion=ExhaustionConfig(
            min_bars_declining=3,
            volume_decline_pct=0.25,
        ),
        volume_profile=VolumeProfileConfig(
            session=SessionType.FULL_DAY,
            tick_size=0.05,
        ),
    )


def get_usoil_config() -> InstrumentConfig:
    """WTI Crude Oil CFD."""
    return InstrumentConfig(
        instrument=Instrument.USOIL,
        tick_size=0.01,
        absorption=AbsorptionConfig(
            min_aggressive_volume=30,
            max_price_displacement_ticks=3,
            rolling_window_seconds=30,
            min_attempts=2,
            big_trade_filter=3,
        ),
        initiative=InitiativeConfig(
            min_delta_threshold=20,
            volume_acceleration_min=1.5,
            min_price_displacement_ticks=4,
        ),
        sweep=SweepConfig(
            min_levels_swept=3,
            max_volume_per_level=10,
            max_time_ms=2000,
            thin_book_threshold=5,
        ),
        exhaustion=ExhaustionConfig(
            min_bars_declining=3,
            volume_decline_pct=0.25,
        ),
        volume_profile=VolumeProfileConfig(
            session=SessionType.NY_CASH,
            tick_size=0.10,
        ),
    )


def get_ukoil_config() -> InstrumentConfig:
    """Brent Crude Oil CFD."""
    return InstrumentConfig(
        instrument=Instrument.UKOIL,
        tick_size=0.01,
        absorption=AbsorptionConfig(
            min_aggressive_volume=30,
            max_price_displacement_ticks=3,
            rolling_window_seconds=30,
            min_attempts=2,
            big_trade_filter=3,
        ),
        initiative=InitiativeConfig(
            min_delta_threshold=20,
            volume_acceleration_min=1.5,
            min_price_displacement_ticks=4,
        ),
        sweep=SweepConfig(
            min_levels_swept=3,
            max_volume_per_level=10,
            max_time_ms=2000,
            thin_book_threshold=5,
        ),
        exhaustion=ExhaustionConfig(
            min_bars_declining=3,
            volume_decline_pct=0.25,
        ),
        volume_profile=VolumeProfileConfig(
            session=SessionType.LONDON,
            tick_size=0.10,
        ),
    )


# ─────────────────────────────────────────────
# Forex Configs
# ─────────────────────────────────────────────

def _forex_major_config(
    instrument: Instrument,
    tick_size: float = 0.00001,
    vp_tick_size: float = 0.0005,
) -> InstrumentConfig:
    """Template for major forex pairs (high liquidity)."""
    return InstrumentConfig(
        instrument=instrument,
        tick_size=tick_size,
        absorption=AbsorptionConfig(
            min_aggressive_volume=20,
            max_price_displacement_ticks=2,
            rolling_window_seconds=30,
            min_attempts=2,
            big_trade_filter=3,
        ),
        initiative=InitiativeConfig(
            min_delta_threshold=15,
            volume_acceleration_min=1.4,
            min_price_displacement_ticks=3,
        ),
        sweep=SweepConfig(
            min_levels_swept=3,
            max_volume_per_level=8,
            max_time_ms=2000,
            thin_book_threshold=5,
        ),
        exhaustion=ExhaustionConfig(
            min_bars_declining=3,
            volume_decline_pct=0.25,
        ),
        volume_profile=VolumeProfileConfig(
            session=SessionType.FULL_DAY,
            tick_size=vp_tick_size,
        ),
    )


def get_eurusd_config() -> InstrumentConfig:
    """EUR/USD — most liquid forex pair."""
    return _forex_major_config(Instrument.EURUSD)


def get_gbpusd_config() -> InstrumentConfig:
    """GBP/USD — Cable."""
    return _forex_major_config(Instrument.GBPUSD)


def get_usdjpy_config() -> InstrumentConfig:
    """USD/JPY — 3-digit pricing."""
    return _forex_major_config(Instrument.USDJPY, tick_size=0.001, vp_tick_size=0.05)


def get_audusd_config() -> InstrumentConfig:
    """AUD/USD — Aussie."""
    return _forex_major_config(Instrument.AUDUSD)


def get_usdcad_config() -> InstrumentConfig:
    """USD/CAD — Loonie."""
    return _forex_major_config(Instrument.USDCAD)


def get_usdchf_config() -> InstrumentConfig:
    """USD/CHF — Swissie."""
    return _forex_major_config(Instrument.USDCHF)


def get_nzdusd_config() -> InstrumentConfig:
    """NZD/USD — Kiwi."""
    return _forex_major_config(Instrument.NZDUSD)


def get_eurgbp_config() -> InstrumentConfig:
    """EUR/GBP — cross pair."""
    return _forex_major_config(Instrument.EURGBP)


def get_eurjpy_config() -> InstrumentConfig:
    """EUR/JPY — 3-digit pricing."""
    return _forex_major_config(Instrument.EURJPY, tick_size=0.001, vp_tick_size=0.05)


def get_gbpjpy_config() -> InstrumentConfig:
    """GBP/JPY — volatile cross."""
    return _forex_major_config(Instrument.GBPJPY, tick_size=0.001, vp_tick_size=0.05)


# ─────────────────────────────────────────────
# Stock Configs (US CFDs)
# ─────────────────────────────────────────────

def _stock_config(instrument: Instrument) -> InstrumentConfig:
    """Template for US stock CFDs."""
    return InstrumentConfig(
        instrument=instrument,
        tick_size=0.01,
        absorption=AbsorptionConfig(
            min_aggressive_volume=20,
            max_price_displacement_ticks=2,
            rolling_window_seconds=30,
            min_attempts=2,
            big_trade_filter=3,
        ),
        initiative=InitiativeConfig(
            min_delta_threshold=15,
            volume_acceleration_min=1.5,
            min_price_displacement_ticks=3,
        ),
        sweep=SweepConfig(
            min_levels_swept=3,
            max_volume_per_level=8,
            max_time_ms=2000,
            thin_book_threshold=5,
        ),
        exhaustion=ExhaustionConfig(
            min_bars_declining=3,
            volume_decline_pct=0.3,
        ),
        volume_profile=VolumeProfileConfig(
            session=SessionType.NY_CASH,
            tick_size=0.50,
        ),
    )


def get_aapl_config() -> InstrumentConfig:
    return _stock_config(Instrument.AAPL)


def get_tsla_config() -> InstrumentConfig:
    return _stock_config(Instrument.TSLA)


def get_amzn_config() -> InstrumentConfig:
    return _stock_config(Instrument.AMZN)


def get_msft_config() -> InstrumentConfig:
    return _stock_config(Instrument.MSFT)


def get_nvda_config() -> InstrumentConfig:
    return _stock_config(Instrument.NVDA)


def get_meta_config() -> InstrumentConfig:
    return _stock_config(Instrument.META)


def get_googl_config() -> InstrumentConfig:
    return _stock_config(Instrument.GOOGL)


# ─────────────────────────────────────────────
# Crypto Configs
# ─────────────────────────────────────────────

def get_btcusd_config() -> InstrumentConfig:
    """BTCUSDT — Bitcoin."""
    return InstrumentConfig(
        instrument=Instrument.BTCUSD,
        tick_size=0.01,
        absorption=AbsorptionConfig(
            min_aggressive_volume=20,
            max_price_displacement_ticks=3,
            rolling_window_seconds=30,
            min_attempts=2,
            big_trade_filter=3,
        ),
        initiative=InitiativeConfig(
            min_delta_threshold=15,
            volume_acceleration_min=1.5,
            min_price_displacement_ticks=4,
        ),
        sweep=SweepConfig(
            min_levels_swept=3,
            max_volume_per_level=8,
            max_time_ms=2000,
            thin_book_threshold=5,
        ),
        exhaustion=ExhaustionConfig(
            min_bars_declining=3,
            volume_decline_pct=0.25,
        ),
        volume_profile=VolumeProfileConfig(
            session=SessionType.FULL_DAY,
            tick_size=10.0,
        ),
    )


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
    ]


# ── Data Source ──
# Change this to select your data feed:
#   DataSource.MT5   → Use MetaTrader 5 (real broker data for NAS100, XAUUSD)
#   DataSource.BYBIT → Use Bybit perpetuals (free crypto data)
#   DataSource.BOTH  → Run both feeds simultaneously
DATA_SOURCE = DataSource.MT5

# ── MT5 Configuration ──
# Adjust symbol names to match your broker!
# Common alternatives:
#   NAS100: "USTEC", "NAS100", "US100", "USTEC.cash", "USTECH100", "#NAS100"
#   Gold:   "XAUUSD", "GOLD", "XAUUSD.cash"
MT5 = MT5Config()

# Telegram config — user fills in their token/chat_id
TELEGRAM = TelegramConfig()

# ── Dashboard ──
# Web dashboard at http://localhost:8080
DASHBOARD = DashboardConfig()

# Database
DB_PATH = "orderflow_data.db"

# Logging
LOG_LEVEL = "INFO"
