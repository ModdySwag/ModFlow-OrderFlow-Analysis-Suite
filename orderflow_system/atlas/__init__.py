"""
the reference layout-inspired order-flow feature set for ModFlow OrderFlow Analysis Suite.

the reference layout (atas.net) is the reference platform for this package: market-depth
heatmaps, MBO-style trackers (iceberg / stop runs / sweeps), big-trade detection,
speed of tape, CVD / CVD Pro, Market Profile, frame bars and Market Replay.

Everything here works from what a public crypto venue actually exposes:
Level-2 order book (Bybit ``orderbook.200``), public trade prints
(``publicTrade``), the liquidation stream (``allLiquidation``) and our own
SQLite history. Where the reference layout relies on true market-by-order (MBO) data — which no
public Bybit feed provides — the equivalent is an explicit *inference* from L2 +
prints, and is labelled as such everywhere it surfaces.

Nothing in this package changes the original repo's behaviour: it consumes the
same tick/orderbook callbacks and publishes its own REST + WebSocket surface.
"""

from orderflow_system.atlas.hub import FeatureHub, hub  # noqa: F401

__all__ = ["FeatureHub", "hub"]
