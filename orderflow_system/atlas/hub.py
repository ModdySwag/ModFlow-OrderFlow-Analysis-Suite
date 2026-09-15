"""
FeatureHub — one object that owns every reference-style analyzer per instrument.

Wiring (all optional, all additive to the original repo):

    hub = FeatureHub(config)
    hub.set_sink(broadcast)                     # async (channel, symbol, data)
    hub.on_tick(symbol, tick)                   # from the repo feed OR the replay
    hub.on_orderbook(symbol, snapshot)          # repo feed (50 levels)
    await hub.start_feeds({symbol: tick_size})  # extra Bybit streams: 200-level
                                                # book, liquidations, block flags
Detections are pushed to the sink and stored for the REST layer to read.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

from orderflow_system.atlas import feed_extras
from orderflow_system.atlas.alerts import AlertEngine, DEFAULT_RULES
from orderflow_system.atlas.correlation import CorrelationTracker
from orderflow_system.atlas.cvd import CvdTracker
from orderflow_system.atlas.dots import DotMap
from orderflow_system.atlas.depthmap import DepthHeatmap
from orderflow_system.atlas.frames import FrameSet
from orderflow_system.atlas.imbalance import ImbalanceLadder
from orderflow_system.atlas.intent import ParticipantIntent
from orderflow_system.atlas.profiles import MarketProfile
from orderflow_system.atlas.tapeflow import TapeFlow
from orderflow_system.atlas.tradedepth import TradeDetector
from orderflow_system.atlas.vwap import VWAPStudy
from orderflow_system.data.models import OrderbookSnapshot, Tick

logger = logging.getLogger(__name__)

Sink = Callable[[str, str, Any], Awaitable[None]]


@dataclass
class SymbolFeatures:
    """All analyzers for one instrument."""

    symbol: str
    tick_size: float
    heatmap: DepthHeatmap = field(init=False)
    tape: TapeFlow = field(init=False)
    cvd: CvdTracker = field(init=False)
    profile: MarketProfile = field(init=False)
    frames: FrameSet = field(init=False)
    imbalance: ImbalanceLadder = field(init=False)
    intent: ParticipantIntent = field(init=False)
    vwap: VWAPStudy = field(init=False)
    detector: TradeDetector = field(init=False)
    dots: DotMap = field(init=False)
    book: feed_extras.BybitDepthBook = field(init=False)
    first_tick_ms: int = 0

    def __post_init__(self) -> None:
        self.heatmap = DepthHeatmap(self.symbol, tick_size=self.tick_size)
        self.tape = TapeFlow(self.symbol, tick_size=self.tick_size)
        self.cvd = CvdTracker(self.symbol, tick_size=self.tick_size)
        self.profile = MarketProfile(self.symbol, tick_size=self.tick_size)
        self.frames = FrameSet(self.symbol, self.tick_size)
        self.imbalance = ImbalanceLadder(self.symbol, tick_size=self.tick_size)
        self.intent = ParticipantIntent(self.symbol, tick_size=self.tick_size)
        self.vwap = VWAPStudy(self.symbol, tick_size=self.tick_size)
        self.detector = TradeDetector(self.symbol, tick_size=self.tick_size)
        self.dots = DotMap(self.symbol, tick_size=self.tick_size)
        self.book = feed_extras.BybitDepthBook(self.symbol)

    def apply_config(self, cfg: dict[str, Any]) -> None:
        """Re-tune the analyzers from the GUI config (tick_size stays authoritative)."""
        hm = cfg.get("heatmap") or {}
        self.heatmap.bucket_ms = int(hm.get("bucket_ms", self.heatmap.bucket_ms))
        self.heatmap.max_columns = int(hm.get("max_columns", self.heatmap.max_columns))
        self.heatmap.pull_pct = float(hm.get("pull_pct", self.heatmap.pull_pct))
        self.heatmap.pull_window_ms = int(hm.get("pull_window_ms", self.heatmap.pull_window_ms))
        self.heatmap.stack_pct = float(hm.get("stack_pct", self.heatmap.stack_pct))
        self.heatmap.wall_quantile = float(hm.get("wall_quantile", self.heatmap.wall_quantile))
        self.heatmap.upper_cutoff_pct = float(hm.get("upper_cutoff_pct", self.heatmap.upper_cutoff_pct))
        self.heatmap.carry_forward = bool(hm.get("carry_forward", self.heatmap.carry_forward))

        dots = cfg.get("dots") or {}
        self.dots.window_ms = max(1_000, int(dots.get("window_ms", self.dots.window_ms)))
        self.dots.cluster_ms = max(0, int(dots.get("cluster_ms", self.dots.cluster_ms)))
        self.dots.min_size = max(0.0, float(dots.get("min_size", self.dots.min_size)))

        tap = cfg.get("tape") or {}
        self.tape.big_quantile = float(tap.get("big_quantile", self.tape.big_quantile))
        self.tape.big_min_size = float(tap.get("big_min_size", self.tape.big_min_size))
        self.tape.block_multiple = float(tap.get("block_multiple", self.tape.block_multiple))
        self.tape.sweep_levels = int(tap.get("sweep_levels", self.tape.sweep_levels))
        self.tape.sweep_max_ms = int(tap.get("sweep_max_ms", self.tape.sweep_max_ms))
        self.tape.sweep_min_size = float(tap.get("sweep_min_size", self.tape.sweep_min_size))
        self.tape.sweep_min_aggressors = int(tap.get("sweep_min_aggressors", self.tape.sweep_min_aggressors))
        self.tape.sweep_min_range_ticks = float(tap.get("sweep_min_range_ticks", self.tape.sweep_min_range_ticks))
        self.tape.iceberg_min_fills = int(tap.get("iceberg_min_fills", self.tape.iceberg_min_fills))
        self.tape.iceberg_min_size = float(tap.get("iceberg_min_size", self.tape.iceberg_min_size))
        self.tape.iceberg_min_total = float(tap.get("iceberg_min_total", self.tape.iceberg_min_total))
        self.tape.iceberg_min_duration_ms = int(float(tap.get("iceberg_min_duration_s",
                                    self.tape.iceberg_min_duration_ms / 1000)) * 1000)
        self.tape.stoprun_ticks = float(tap.get("stoprun_ticks", self.tape.stoprun_ticks))
        self.tape.stoprun_ms = int(tap.get("stoprun_ms", self.tape.stoprun_ms))
        self.tape.stoprun_min_volume = float(tap.get("stoprun_min_volume", self.tape.stoprun_min_volume))
        self.tape.stoprun_min_prints = int(tap.get("stoprun_min_prints", self.tape.stoprun_min_prints))
        self.tape.reassembly_ms = int(tap.get("reassembly_ms", self.tape.reassembly_ms))
        self.tape.zone_ticks = float(tap.get("zone_ticks", self.tape.zone_ticks))

        imb = cfg.get("imbalance") or {}
        self.imbalance.rate_pct = float(imb.get("rate_pct", self.imbalance.rate_pct))
        self.imbalance.window_ms = int(float(imb.get("window_s", self.imbalance.window_ms / 1000)) * 1000)

        it = cfg.get("intent") or {}
        if it:
            self.intent.levels = max(5, min(50, int(it.get("levels", self.intent.levels))))
            self.intent.decay = max(1.0, min(20.0, float(it.get("decay", self.intent.decay))))
            self.intent.threshold_pct = max(1.0, min(100.0,
                                                      float(it.get("threshold_pct", self.intent.threshold_pct))))
            self.intent.training_s = max(0.0, float(it.get("training_min", self.intent.training_s / 60)) * 60)
            self.intent.absorb_window_ms = int(float(it.get("absorb_window_s",
                                                             self.intent.absorb_window_ms / 1000)) * 1000)
            self.intent.absorb_ref_ticks = float(it.get("absorb_ref_ticks", self.intent.absorb_ref_ticks))
            self.intent.spoof_near_ticks = float(it.get("spoof_near_ticks", self.intent.spoof_near_ticks))
            self.intent.spoof_size_mult = float(it.get("spoof_size_mult", self.intent.spoof_size_mult))
            self.intent.trap_ticks = float(it.get("trap_ticks", self.intent.trap_ticks))
            self.intent.trap_window_ms = int(float(it.get("trap_window_s", self.intent.trap_window_ms / 1000)) * 1000)
            self.intent.trap_reclaim_ms = int(float(it.get("trap_reclaim_s",
                                                           self.intent.trap_reclaim_ms / 1000)) * 1000)
            self.intent.min_observations = max(1, int(it.get("min_observations", self.intent.min_observations)))

        vw = cfg.get("vwap") or {}
        if vw:
            self.vwap.window_ms = int(max(60.0, float(vw.get("window_s", self.vwap.window_ms / 1000))) * 1000)
            self.vwap.cross_min_ticks = float(vw.get("cross_min_ticks", self.vwap.cross_min_ticks))
            bands = vw.get("bands")
            if isinstance(bands, (list, tuple)) and bands:
                self.vwap.bands = tuple(sorted(float(b) for b in bands if float(b) > 0)) or self.vwap.bands

        dt = cfg.get("detector") or {}
        if dt:
            self.detector.min_share = max(0.0, min(1.0, float(dt.get("min_share", self.detector.min_share))))
            self.detector.size_mult = max(1.0, float(dt.get("size_mult", self.detector.size_mult)))
            self.detector.resting_mult = max(1.0, float(dt.get("resting_mult", self.detector.resting_mult)))
            self.detector.refill_pct = max(0.1, min(1.0, float(dt.get("refill_pct", self.detector.refill_pct))))
            self.detector.refill_ms = int(max(200, float(dt.get("refill_ms", self.detector.refill_ms))))

        cvd_cfg = cfg.get("cvd") or {}
        if cvd_cfg:
            self.cvd.set_pro_filter(float(cvd_cfg.get("pro_min_size") or 0.0),
                                    float(cvd_cfg.get("pro_max_size") or 0.0))
            if cvd_cfg.get("pro_bands"):
                self.cvd.set_pro_bands(cvd_cfg["pro_bands"])
        self.imbalance.min_volume = float(imb.get("min_volume", self.imbalance.min_volume))
        self.imbalance.alert_min_levels = int(imb.get("min_levels", self.imbalance.alert_min_levels))

        cv = cfg.get("cvd") or {}
        self.cvd.bucket_ms = int(cv.get("bucket_ms", self.cvd.bucket_ms))
        self.cvd.divergence_lookback = int(cv.get("divergence_lookback", self.cvd.divergence_lookback))
        self.cvd.divergence_min_ticks = float(cv.get("divergence_min_ticks", self.cvd.divergence_min_ticks))

        mp = cfg.get("market_profile") or {}
        self.profile.bracket_ms = int(float(mp.get("bracket_minutes", 30)) * 60_000)
        self.profile.value_area_pct = float(mp.get("value_area_pct", self.profile.value_area_pct))


class FeatureHub:
    """Fans the live stream out to the analyzers, collects detections, raises alerts."""

    def __init__(self, config: Optional[dict[str, Any]] = None) -> None:
        cfg = config or {}
        self.config = cfg
        self.symbols: dict[str, SymbolFeatures] = {}
        self.alerts = AlertEngine(cfg.get("alert_rules") or DEFAULT_RULES,
                                  webhook_url=(cfg.get("webhook_url") or ""))
        self.history: Optional[Any] = None          # atlas.history.EventHistory
        self.notifier: Optional[Any] = None         # atlas.notify.TelegramNotifier
        self._sink: Optional[Sink] = None
        self._feeds: dict[str, feed_extras.BybitExtras] = {}
        self._feed_tasks: list[asyncio.Task] = []
        self.extras_enabled: bool = bool(cfg.get("extras_enabled", True))
        self.counters: dict[str, int] = {"ticks": 0, "orderbooks": 0, "liquidations": 0, "blocks": 0, "alerts": 0}
        self.started_at: float = 0.0
        from orderflow_system.atlas.scanner import MarketScanner     # local import: scanner reads the hub
        self.scanner = MarketScanner(self, window_s=float(cfg.get("scanner_window_s", 900.0)))
        # Cross-instrument by nature, so it lives on the hub rather than per symbol.
        corr = cfg.get("correlation") or {}
        self.correlation = CorrelationTracker(bucket_ms=int(corr.get("bucket_ms", 60_000)),
                                              window=int(corr.get("window", 120)),
                                              min_samples=int(corr.get("min_samples", 10)))

    # ── configuration ─────────────────────────────────────────
    def set_sink(self, sink: Optional[Sink]) -> None:
        self._sink = sink

    def attach_history(self, history: Optional[Any]) -> None:
        """Route every detection into a durable history (see atlas.history)."""
        self.history = history

    def attach_notifier(self, notifier: Optional[Any]) -> None:
        """Route alerts whose rule lists the ``telegram`` channel (atlas.notify)."""
        self.notifier = notifier

    def configure(self, config: dict[str, Any]) -> None:
        self.config = config
        if config.get("alert_rules"):
            self.alerts.set_rules(config["alert_rules"])
        if "webhook_url" in config:
            self.alerts.webhook_url = config.get("webhook_url") or ""
        for feats in self.symbols.values():
            feats.apply_config(config)

    def ensure(self, symbol: str, tick_size: Optional[float] = None) -> SymbolFeatures:
        feats = self.symbols.get(symbol)
        if feats is None:
            feats = SymbolFeatures(symbol=symbol, tick_size=float(tick_size or 1.0))
            feats.apply_config(self.config)
            self.symbols[symbol] = feats
        elif tick_size:
            feats.tick_size = float(tick_size)
        return feats

    def clear(self) -> None:
        for feats in self.symbols.values():
            feats.heatmap.clear()
            feats.tape.clear()
            feats.cvd.clear()
            feats.profile.clear()
            feats.frames.clear()
            feats.imbalance.clear()
            feats.dots.clear()
            feats.intent.clear()
            feats.vwap.clear()
            feats.detector.clear()
        self.counters = {k: 0 for k in self.counters}

    # ── ingest ────────────────────────────────────────────────
    def on_tick(self, symbol: str, tick: Tick) -> dict[str, Any]:
        feats = self.ensure(symbol)
        if not feats.first_tick_ms:
            feats.first_tick_ms = int(tick.timestamp_ms or time.time() * 1000)
        self.counters["ticks"] += 1

        feats.heatmap.on_tick(tick)
        feats.dots.on_tick(tick)
        self.correlation.on_tick(symbol, tick.price, tick.timestamp_ms)
        detections = feats.tape.on_tick(tick)
        feats.cvd.on_tick(tick)
        feats.profile.on_tick(tick)
        feats.frames.on_tick(tick)
        detections.update(feats.imbalance.on_tick(tick))
        # intent: a trap is a tape event; pressure/pulls arrive from the book path
        trap = feats.intent.on_tick(tick).get("trapped")
        if trap is not None:
            detections["trapped_traders"] = trap
        # VWAP cross + executions into resting depth (both read the tick stream)
        for kind, payload in feats.vwap.on_tick(tick).items():
            detections[kind] = payload
        for kind, payload in feats.detector.on_tick(tick).items():
            if payload:
                detections[kind] = payload

        div = feats.cvd.detect_divergence()
        if div is not None:
            detections["cvd_divergence"] = div

        for kind, payload in detections.items():
            self._dispatch(symbol, kind, payload)
        return detections

    def on_orderbook(self, symbol: str, snapshot: OrderbookSnapshot) -> None:
        feats = self.ensure(symbol)
        self.counters["orderbooks"] += 1
        feats.heatmap.on_orderbook(snapshot)
        # participants' intent: DOM pressure + pulled size, both read from this book
        events = feats.intent.on_orderbook(snapshot)
        for ev in events.get("intent_pressure", []):
            self._dispatch(symbol, "intent_pressure", ev)
        for ev in events.get("pulled_size", []):
            self._dispatch(symbol, "pulled_size", ev)
        # trade detector: refills of levels that were just eaten
        det = feats.detector.on_orderbook(snapshot)
        for ev in det.get("depth_refill", []):
            self._dispatch(symbol, "depth_refill", ev)

    def on_liquidation(self, symbol: str, price: float, size: float, side: str, ts_ms: int) -> None:
        feats = self.ensure(symbol)
        self.counters["liquidations"] += 1
        ev = feats.tape.on_liquidation(price, size, side, ts_ms)
        if ev is not None:
            self._dispatch(symbol, "stop_run", ev)
        self._dispatch(symbol, "liquidation", {"price": price, "size": size, "side": side, "ts_ms": ts_ms})

    def on_block_trade(self, symbol: str, price: float, size: float, side: str, ts_ms: int) -> None:
        feats = self.ensure(symbol)
        self.counters["blocks"] += 1
        payload = {"price": price, "size": size, "side": side, "ts_ms": ts_ms, "multiple": 3.0, "exchange_block": True}
        self._dispatch(symbol, "block_trade", payload)

    # ── extras feed (deeper book, liquidations, block flags) ──
    async def start_feeds(self, symbols: dict[str, float]) -> dict[str, Any]:
        """Start one Bybit extras connection per symbol: {symbol: tick_size}."""
        if not self.extras_enabled:
            return {"ok": False, "error": "extras disabled in config"}
        for symbol, tick_size in symbols.items():
            if symbol in self._feeds:
                continue
            self.ensure(symbol, tick_size)
            feed = feed_extras.BybitExtras(
                symbol,
                on_liquidation=self.on_liquidation,
                on_orderbook=self._on_ext_orderbook,
                on_block_trade=self.on_block_trade,
                depth=200,
            )
            self._feeds[symbol] = feed
            self._feed_tasks.append(asyncio.create_task(feed.start()))
            logger.info("the reference layout extras feed started for %s", symbol)
        self.started_at = self.started_at or time.time()
        return {"ok": True, "symbols": list(self._feeds), "feeds": len(self._feeds)}

    async def _on_ext_orderbook(self, symbol: str, msg_type: str, data: dict[str, Any], ts_ms: int = 0) -> None:
        feats = self.ensure(symbol)
        feats.book.apply(msg_type, data, ts_ms)
        self.counters["orderbooks"] += 1
        feats.heatmap.on_orderbook(feats.book.to_snapshot())

    async def stop_feeds(self) -> dict[str, Any]:
        for symbol, feed in list(self._feeds.items()):
            try:
                await feed.stop()
            except Exception:
                logger.debug("feed stop failed for %s", symbol, exc_info=True)
        for task in self._feed_tasks:
            task.cancel()
        self._feed_tasks.clear()
        self._feeds.clear()
        return {"ok": True}

    # ── dispatch ──────────────────────────────────────────────
    def _dispatch(self, symbol: str, kind: str, payload: Any) -> None:
        data = payload.to_dict() if hasattr(payload, "to_dict") else (
            payload.__dict__ if hasattr(payload, "__dict__") and not isinstance(payload, dict) else payload)
        # heat events use their own kinds so alerts match (heat_pull / heat_stack)
        alert_kind = kind
        if kind in ("pull", "stack"):
            alert_kind = f"heat_{kind}"
        elif kind == "liquidation":
            alert_kind = "liquidation"
        ts_ms, price, size = _event_fields(payload)
        fired = self.alerts.evaluate(symbol, alert_kind, payload)
        for alert in fired:
            self.counters["alerts"] += 1
            alert_dict = alert.to_dict()
            self._emit("alert", symbol, alert_dict)
            self._record(symbol, "alert", alert.ts_ms, price, size, alert.message)
            # any channel other than the UI means "somewhere off this screen" —
            # the hub itself decides which configured channels that maps to, so
            # a ntfy-only or email-only setup is not silently skipped
            if self.notifier is not None and any(c != "ui" for c in (alert.channels or [])):
                self._notify(alert_dict)
        if fired and self.alerts.webhook_url:
            self._dispatch_webhooks(fired)
        if kind != "pull" and kind != "stack":
            self._emit(kind, symbol, data)
            self._record(symbol, kind, ts_ms, price, size)
        else:
            # heat events are not broadcast as their own channel, but they are
            # exactly the kind of thing a post-session review wants on disk
            self._record(symbol, alert_kind, ts_ms, price, size)

    # ── side channels: durable history + Telegram ─────────────
    def _record(self, symbol: str, kind: str, ts_ms: int = 0, price: float = 0.0,
                size: float = 0.0, detail: str = "") -> None:
        if self.history is None:
            return
        try:
            self.history.record(symbol, kind, price=price, size=size, detail=detail,
                                ts_ms=int(ts_ms) if ts_ms else None)
        except Exception:
            logger.debug("history record failed", exc_info=True)

    def _notify(self, alert: dict[str, Any]) -> None:
        if self.notifier is None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return                                   # no loop (unit tests) → skip
        loop.create_task(self._safe_notify(alert))

    async def _safe_notify(self, alert: dict[str, Any]) -> None:
        try:
            await self.notifier.send(alert)          # type: ignore[union-attr]
        except Exception:
            logger.debug("notifier failed for %s", alert.get("kind"), exc_info=True)

    def _dispatch_webhooks(self, fired: list[Any]) -> None:
        """Fire-and-forget POST of newly fired alerts to the configured webhook."""
        if not self.alerts.webhook_url:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return                                   # no loop (unit tests) → skip
        loop.create_task(self._safe_webhooks(fired))

    async def _safe_webhooks(self, fired: list[Any]) -> None:
        try:
            await self.alerts.dispatch_webhooks(fired)
        except Exception:
            logger.debug("webhook dispatch failed", exc_info=True)

    def _emit(self, channel: str, symbol: str, data: Any) -> None:
        if self._sink is None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return                                   # no loop (unit tests) → skip
        loop.create_task(self._safe_emit(channel, symbol, data))

    async def _safe_emit(self, channel: str, symbol: str, data: Any) -> None:
        try:
            await self._sink(channel, symbol, data)   # type: ignore[misc]
        except Exception:
            logger.debug("sink failed for %s/%s", symbol, channel, exc_info=True)

    # ── reads for the REST layer ──────────────────────────────
    def snapshot_heatmap(self, symbol: str, columns: int = 300, max_rows: int = 260) -> dict[str, Any]:
        return self.ensure(symbol).heatmap.snapshot(columns=columns, max_rows=max_rows)

    def snapshot_tape(self, symbol: str) -> dict[str, Any]:
        feats = self.ensure(symbol)
        return {"symbol": symbol, "stats": feats.tape.stats(), "events": feats.tape.events(),
                "recent": feats.tape.recent(120)}

    def snapshot_cvd(self, symbol: str, buckets: int = 400) -> dict[str, Any]:
        return self.ensure(symbol).cvd.snapshot(series_buckets=buckets)

    def snapshot_profile(self, symbol: str, max_levels: int = 160) -> dict[str, Any]:
        return self.ensure(symbol).profile.snapshot(max_levels=max_levels)

    def snapshot_frames(self, symbol: str, frame: str, count: int = 200) -> dict[str, Any]:
        feats = self.ensure(symbol)
        return {"symbol": symbol, "frame": frame, "bars": feats.frames.recent(frame, count),
                "all": feats.frames.snapshot()}

    def snapshot_vwap(self, symbol: str, points: int = 240) -> dict[str, Any]:
        feats = self.ensure(symbol)
        return feats.vwap.snapshot(points=points)

    def snapshot_trade_depth(self, symbol: str, max_rows: int = 30) -> dict[str, Any]:
        feats = self.ensure(symbol)
        return feats.detector.snapshot(max_rows=max_rows)

    def snapshot_scanner(self, sort: str = "score", limit: int = 50) -> dict[str, Any]:
        return self.scanner.snapshot(sort=sort, limit=limit)

    def snapshot_imbalance(self, symbol: str, max_levels: int = 120) -> dict[str, Any]:
        return self.ensure(symbol).imbalance.snapshot(max_levels=max_levels)

    def snapshot_dots(self, symbol: str, max_dots: int = 600, min_size: float | None = None,
                      side: str = "") -> dict[str, Any]:
        """Trade-cluster bubbles for one instrument (see atlas/dots.py)."""
        return self.ensure(symbol).dots.snapshot(max_dots=max_dots, min_size=min_size, side=side)

    def snapshot_correlation(self, symbols: Optional[list[str]] = None, top: int = 12) -> dict[str, Any]:
        """Rolling correlation matrix across the streaming instruments."""
        return self.correlation.snapshot(symbols=symbols or None, top=top)

    # ── CSV exports (the reference layout exposes CSV for its feeds and journals) ───────────
    def tape_csv(self, symbol: str, limit: int = 500) -> str:
        """Detections on the tape as CSV: big trades, sweeps, stop runs, icebergs."""
        import csv
        import io

        feats = self.ensure(symbol)
        rows: list[tuple[int, str, float, float, str]] = []
        for bt in feats.tape.big_trades:
            rows.append((bt.ts_ms, "big_trade", bt.price, bt.size, f"{bt.side} {bt.multiple:.1f}x"))
        for sw in feats.tape.sweeps:
            rows.append((sw.ts_ms, "sweep", sw.from_price, sw.size,
                         f"{sw.side} {sw.levels} levels {sw.duration_ms}ms {sw.from_price}->{sw.to_price}"))
        for sr in feats.tape.stop_runs:
            rows.append((sr.ts_ms, "stop_run", sr.from_price, sr.volume,
                         f"{sr.direction} {sr.ticks_moved} ticks/{sr.duration_ms}ms "
                         f"{sr.from_price}->{sr.to_price} liquidations={sr.confirmed_by_liquidations}"))
        for ice in feats.tape.icebergs:
            rows.append((ice.ts_ms, "iceberg", ice.price, ice.total_size,
                         f"{ice.side} {ice.fills} fills, executed {ice.total_size:.4f}, modal {ice.modal_size:.4f}"))
        for liq in feats.tape.liquidations:
            rows.append((liq.ts_ms, "liquidation", liq.price, liq.size, str(liq.side)))
        rows.sort(key=lambda r: r[0])
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["ts_ms", "time", "kind", "price", "size", "detail"])
        for ts, kind, price, size, detail in rows[-limit:]:
            w.writerow([ts, time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts / 1000)),
                        kind, price, size, detail])
        return buf.getvalue()

    def heatmap_csv(self, symbol: str, columns: int = 240, rows: int = 200) -> str:
        """The depth-heatmap matrix as CSV (price rows x time buckets)."""
        import csv
        import io

        snap = self.snapshot_heatmap(symbol, columns=columns, max_rows=rows)
        grid = snap.get("values") or snap.get("matrix") or []
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["price"] + [str(b) for b in snap.get("buckets", [])])
        for i, price in enumerate(snap.get("prices", [])):
            row = grid[i] if i < len(grid) else []
            w.writerow([price] + [f"{v:.4f}" if isinstance(v, (int, float)) else "" for v in row])
        return buf.getvalue()

    def status(self) -> dict[str, Any]:
        return {
            "symbols": list(self.symbols),
            "feeds": {s: f.stats for s, f in self._feeds.items()},
            "extras_enabled": self.extras_enabled,
            "uptime_s": round(time.time() - self.started_at, 1) if self.started_at else 0,
            "counters": dict(self.counters),
            "alerts": self.alerts.stats(),
            "heatmap": {s: f.heatmap.stats() for s, f in self.symbols.items()},
            "imbalance": {s: len(f.imbalance.clusters()) for s, f in self.symbols.items()},
            "history": ({"pending": getattr(self.history, "pending", 0),
                         "written": getattr(self.history, "written", 0),
                         "enabled": getattr(self.history, "enabled", False)}
                        if self.history is not None else None),
            "telegram": (self.notifier.stats() if self.notifier is not None else None),
        }


def _event_fields(payload: Any) -> tuple[int, float, float]:
    """Best-effort (ts_ms, price, size) out of any detection payload."""
    get = ((lambda k, d=None: payload.get(k, d)) if isinstance(payload, dict)
           else (lambda k, d=None: getattr(payload, k, d)))

    def num(key: str, *falls: str) -> float:
        for k in (key, *falls):
            value = get(k)
            try:
                if value is not None:
                    return float(value)
            except (TypeError, ValueError):
                continue
        return 0.0

    try:
        ts = int(get("ts_ms") or 0)
    except (TypeError, ValueError):
        ts = 0
    return ts, num("price"), num("size", "volume", "total")


hub = FeatureHub()
