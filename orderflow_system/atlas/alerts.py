"""
Order-flow alert rules (the reference layout "Alerts" equivalent).

the reference layout lets you attach alert conditions to order-flow events (big trade, sweep,
iceberg, stop run, speed of tape, delta divergence) and route them to a sound,
a popup or a log. This is the same idea for our feed: rules are plain dicts,
evaluated against every detection the FeatureHub produces, with per-rule
cooldowns and per-rule minimum-size filters so the alert list stays readable.

Rules are persisted in the desktop config file, so the GUI can manage them.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

KINDS = (
    "big_trade", "block_trade", "sweep", "stop_run", "iceberg",
    "speed_spike", "cvd_divergence", "heat_pull", "heat_stack", "wall",
    "stacked_imbalance", "intent_pressure", "pulled_size", "trapped_traders",
    "vwap_cross", "depth_execution", "depth_refill",
)

DEFAULT_RULES: list[dict[str, Any]] = [
    {"id": "big-default", "name": "Big trade", "kind": "big_trade", "enabled": True,
     "params": {"min_multiple": 1.5, "sides": ["buy", "sell"]}, "cooldown_s": 10, "channels": ["ui", "telegram"]},
    {"id": "blocks", "name": "Block trade", "kind": "block_trade", "enabled": True,
     "params": {"min_multiple": 3.0}, "cooldown_s": 10, "channels": ["ui", "telegram"]},
    {"id": "sweeps", "name": "Sweep ≥5 levels", "kind": "sweep", "enabled": True,
     "params": {"min_levels": 5}, "cooldown_s": 15, "channels": ["ui", "telegram"]},
    {"id": "stopruns", "name": "Stop run", "kind": "stop_run", "enabled": True,
     "params": {"min_ticks": 12.0}, "cooldown_s": 30, "channels": ["ui", "telegram"]},
    {"id": "icebergs", "name": "Iceberg (inferred)", "kind": "iceberg", "enabled": True,
     "params": {"min_fills": 4}, "cooldown_s": 30, "channels": ["ui"]},
    {"id": "speed", "name": "Speed of tape spike", "kind": "speed_spike", "enabled": True,
     "params": {"min_zscore": 3.0}, "cooldown_s": 20, "channels": ["ui"]},
    {"id": "cvd-div", "name": "CVD divergence", "kind": "cvd_divergence", "enabled": True,
     "params": {"kinds": ["bearish", "bullish"], "min_strength": 50}, "cooldown_s": 60, "channels": ["ui", "telegram"]},
    {"id": "heat-pull", "name": "Liquidity pulled near price", "kind": "heat_pull", "enabled": True,
     "params": {}, "cooldown_s": 30, "channels": ["ui"]},
    {"id": "heat-stack", "name": "Liquidity stacking", "kind": "heat_stack", "enabled": True,
     "params": {}, "cooldown_s": 30, "channels": ["ui"]},
    {"id": "stacked-imb", "name": "Stacked imbalance ≥3 levels", "kind": "stacked_imbalance", "enabled": True,
     "params": {"min_levels": 3, "min_volume": 0.0}, "cooldown_s": 60, "channels": ["ui", "telegram"]},
    # participants' intent (order-book reading) — UI by default, quieter than the tape rules
    {"id": "vwap-cross", "name": "Price crosses VWAP", "kind": "vwap_cross", "enabled": True,
     "params": {"min_ticks": 0.0}, "cooldown_s": 60, "channels": ["ui"]},
    {"id": "depth-execution", "name": "Trade eats resting depth", "kind": "depth_execution",
     "enabled": True, "params": {"min_share": 0.3}, "cooldown_s": 30, "channels": ["ui"]},
    {"id": "depth-refill", "name": "Level refills after being eaten", "kind": "depth_refill",
     "enabled": True, "params": {"min_share": 0.3}, "cooldown_s": 45, "channels": ["ui"]},
    {"id": "intent-pressure", "name": "Book pressure ≥80% of normal", "kind": "intent_pressure", "enabled": True,
     "params": {"min_pct": 80.0}, "cooldown_s": 60, "channels": ["ui"]},
    {"id": "intent-pull", "name": "Large size pulled near price", "kind": "pulled_size", "enabled": True,
     "params": {"min_size": 0.0, "max_distance_ticks": 10.0}, "cooldown_s": 30, "channels": ["ui"]},
    {"id": "intent-trap", "name": "Break failed — side trapped", "kind": "trapped_traders", "enabled": True,
     "params": {"min_beyond_ticks": 3.0}, "cooldown_s": 60, "channels": ["ui"]},
]


def _payload_dict(payload: Any) -> dict[str, Any]:
    """Detections arrive as dicts or as small objects; read either without guessing."""
    if isinstance(payload, dict):
        return payload
    to_dict = getattr(payload, "to_dict", None)
    if callable(to_dict):
        try:
            return to_dict() or {}
        except Exception:
            return {}
    return getattr(payload, "__dict__", {}) or {}
def _price_of(payload: Any) -> Optional[float]:
    d = _payload_dict(payload)
    for key in ("price", "level", "px", "p"):
        v = d.get(key)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v)
    return None


@dataclass
class AlertRule:
    id: str
    name: str
    kind: str
    params: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    cooldown_s: float = 30.0
    channels: list[str] = field(default_factory=lambda: ["ui"])
    fired: int = 0
    last_fired_ms: int = 0

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AlertRule":
        return cls(
            id=str(raw.get("id") or f"rule-{int(time.time()*1000)}"),
            name=str(raw.get("name") or raw.get("kind", "rule")),
            kind=str(raw.get("kind", "big_trade")),
            params=dict(raw.get("params") or {}),
            enabled=bool(raw.get("enabled", True)),
            cooldown_s=float(raw.get("cooldown_s", 30) or 0),
            channels=list(raw.get("channels") or ["ui"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "kind": self.kind, "params": self.params,
                "enabled": self.enabled, "cooldown_s": self.cooldown_s, "channels": self.channels,
                "fired": self.fired, "last_fired_ms": self.last_fired_ms}


@dataclass
class Alert:
    rule_id: str
    name: str
    kind: str
    symbol: str
    ts_ms: int
    message: str
    severity: str = "info"          # info | warning | critical
    data: dict[str, Any] = field(default_factory=dict)
    channels: list[str] = field(default_factory=lambda: ["ui"])

    def to_dict(self) -> dict[str, Any]:
        return {"rule_id": self.rule_id, "name": self.name, "kind": self.kind, "symbol": self.symbol,
                "ts_ms": self.ts_ms, "message": self.message, "severity": self.severity,
                "data": self.data, "channels": list(self.channels)}


class AlertEngine:
    """Evaluates detections against the rule set."""

    def __init__(self, rules: Optional[Iterable[dict[str, Any]]] = None, history: int = 500,
                 webhook_url: str = "") -> None:
        self.rules: list[AlertRule] = [AlertRule.from_dict(r) for r in (rules if rules is not None else DEFAULT_RULES)]
        self.history: list[Alert] = []
        self._history_max = history
        # the reference layout parity: indicator alerts can be forwarded to an external
        # automation service. Anything with "webhook" in its channels is POSTed.
        self.webhook_url = webhook_url or ""
        self.webhook_stats = {"sent": 0, "failed": 0, "last_error": ""}

    # ── rule management ───────────────────────────────────────
    def set_rules(self, rules: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        self.rules = [AlertRule.from_dict(r) for r in rules]
        return [r.to_dict() for r in self.rules]

    def upsert(self, rule: dict[str, Any]) -> list[dict[str, Any]]:
        """Create a rule, or patch an existing one by id (partial bodies merge)."""
        rid = (rule or {}).get("id")
        existing = next((r for r in self.rules if r.id == rid), None) if rid else None
        if existing is not None:
            merged = existing.to_dict()
            merged.update({k: v for k, v in rule.items() if v is not None})
            parsed = AlertRule.from_dict(merged)
            parsed.fired, parsed.last_fired_ms = existing.fired, existing.last_fired_ms
            self.rules[self.rules.index(existing)] = parsed
        else:
            parsed = AlertRule.from_dict(rule)
            self.rules.append(parsed)
        return [r.to_dict() for r in self.rules]

    def remove(self, rule_id: str) -> list[dict[str, Any]]:
        self.rules = [r for r in self.rules if r.id != rule_id]
        return [r.to_dict() for r in self.rules]

    # ── evaluation ────────────────────────────────────────────
    def evaluate(self, symbol: str, kind: str, payload: Any, ts_ms: Optional[int] = None) -> list[Alert]:
        """Check one detection against every enabled rule of that kind."""
        ts = int(ts_ms or time.time() * 1000)
        fired: list[Alert] = []
        for rule in self.rules:
            if not rule.enabled or rule.kind != kind:
                continue
            params = rule.params or {}
            # A rule may be bound to one price: the heatmap can turn a selected level into an
            # alert, and "at this level" has to mean the level, not the whole instrument.
            at_price = params.get("at_price")
            if at_price is not None:
                px = _price_of(payload)
                if px is None or abs(px - float(at_price)) > float(params.get("at_tol", 0) or 0):
                    continue
            if not self._passes(rule.kind, params, payload):
                continue
            if rule.cooldown_s and rule.last_fired_ms and ts - rule.last_fired_ms < rule.cooldown_s * 1000:
                continue
            message = self._message(rule, symbol, payload)
            severity = "critical" if kind in ("stop_run", "block_trade") else "warning" if kind in (
                "sweep", "iceberg", "stacked_imbalance", "intent_pressure", "trapped_traders",
                "depth_execution", "depth_refill") else "info"
            alert = Alert(rule_id=rule.id, name=rule.name, kind=kind, symbol=symbol, ts_ms=ts,
                          message=message, severity=severity, data=_safe(payload),
                          channels=list(rule.channels))
            rule.last_fired_ms = ts
            rule.fired += 1
            fired.append(alert)
            self.history.append(alert)
        if len(self.history) > self._history_max:
            self.history = self.history[-self._history_max:]
        return fired

    def recent(self, limit: int = 100, symbol: str = "") -> list[dict[str, Any]]:
        rows = [a for a in self.history if not symbol or a.symbol == symbol]
        return [a.to_dict() for a in rows[-limit:]]

    async def dispatch_webhooks(self, alerts: Iterable[Alert], timeout_s: float = 5.0) -> int:
        """POST fired alerts to the configured webhook.

        the reference layout forwards indicator alerts to an external automation service; rules opt
        in with ``"webhook"`` in their channels. Failures are counted, never raised —
        an unreachable webhook must not affect the trading pipeline.
        """
        if not self.webhook_url:
            return 0
        targets = [a for a in alerts if "webhook" in (a.channels or [])]
        if not targets:
            return 0
        sent = 0
        try:
            import aiohttp
        except Exception as exc:                       # pragma: no cover - dep is present
            self.webhook_stats["failed"] += len(targets)
            self.webhook_stats["last_error"] = f"aiohttp unavailable: {exc}"
            return 0
        try:
            timeout = aiohttp.ClientTimeout(total=timeout_s)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                for alert in targets:
                    payload = self.webhook_payload(alert)
                    try:
                        async with session.post(self.webhook_url, json=payload) as resp:
                            if resp.status < 400:
                                sent += 1
                            else:
                                self.webhook_stats["failed"] += 1
                                self.webhook_stats["last_error"] = f"HTTP {resp.status}"
                    except Exception as exc:
                        self.webhook_stats["failed"] += 1
                        self.webhook_stats["last_error"] = f"{type(exc).__name__}: {exc}"
        except Exception as exc:                        # pragma: no cover - session failure
            self.webhook_stats["failed"] += len(targets)
            self.webhook_stats["last_error"] = f"{type(exc).__name__}: {exc}"
        self.webhook_stats["sent"] += sent
        return sent

    def stats(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for a in self.history:
            counts[a.kind] = counts.get(a.kind, 0) + 1
        return {"rules": len(self.rules), "enabled": sum(1 for r in self.rules if r.enabled),
                "history": len(self.history), "by_kind": counts,
                "webhook": dict(self.webhook_stats),
                "webhook_rules": sum(1 for r in self.rules if "webhook" in (r.channels or []))}

    def to_csv(self, limit: int = 500) -> str:
        """CSV export of the alert log (the reference layout exposes CSV export for its feeds)."""
        import csv
        import io

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["ts_ms", "time", "severity", "kind", "symbol", "rule", "message"])
        for a in self.history[-limit:]:
            writer.writerow([a.ts_ms, time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(a.ts_ms / 1000)),
                             a.severity, a.kind, a.symbol, a.name, a.message])
        return buf.getvalue()

    def webhook_payload(self, alert: Alert) -> dict[str, Any]:
        return {"source": "orderflow-analysis-pro", "type": "orderflow_alert", **alert.to_dict()}

    # ── internals ─────────────────────────────────────────────
    @staticmethod
    def _passes(kind: str, params: dict[str, Any], payload: Any) -> bool:
        get = (lambda key, default=None: payload.get(key, default)) if isinstance(payload, dict) else (lambda key, default=None: getattr(payload, key, default))
        if kind in ("big_trade", "block_trade"):
            if get("multiple", 1.0) < float(params.get("min_multiple", 0) or 0):
                return False
            sides = params.get("sides")
            if sides and str(get("side", "")).lower() not in [s.lower() for s in sides]:
                return False
            if float(get("size", 0) or 0) < float(params.get("min_size", 0) or 0):
                return False
            return True
        if kind == "sweep":
            return int(get("levels", 0) or 0) >= int(params.get("min_levels", 0) or 0) and \
                float(get("size", 0) or 0) >= float(params.get("min_size", 0) or 0)
        if kind == "stop_run":
            return float(get("ticks_moved", 0) or 0) >= float(params.get("min_ticks", 0) or 0)
        if kind == "iceberg":
            return int(get("fills", 0) or 0) >= int(params.get("min_fills", 0) or 0)
        if kind == "speed_spike":
            return float(get("zscore", 0) or 0) >= float(params.get("min_zscore", 0) or 0)
        if kind == "cvd_divergence":
            kinds = params.get("kinds") or []
            if kinds and get("kind", "") not in kinds:
                return False
            return float(get("strength", 0) or 0) >= float(params.get("min_strength", 0) or 0)
        if kind in ("heat_pull", "heat_stack"):
            return float(get("size", 0) or 0) >= float(params.get("min_size", 0) or 0)
        if kind == "wall":
            return float(get("size", 0) or 0) >= float(params.get("min_size", 0) or 0)
        if kind == "vwap_cross":
            return abs(float(get("ticks", 0) or 0)) >= float(params.get("min_ticks", 0) or 0)
        if kind in ("depth_execution", "depth_refill"):
            return float(get("share", 0) or 0) >= float(params.get("min_share", 0) or 0)
        if kind == "stacked_imbalance":
            return int(get("levels", 0) or 0) >= int(params.get("min_levels", 0) or 0) and \
                float(get("volume", 0) or 0) >= float(params.get("min_volume", 0) or 0)
        if kind == "intent_pressure":
            return float(get("pct", 0) or 0) >= float(params.get("min_pct", 0) or 0)
        if kind == "pulled_size":
            return float(get("size", 0) or 0) >= float(params.get("min_size", 0) or 0) and \
                float(get("distance_ticks", 99) or 99) <= float(params.get("max_distance_ticks", 99) or 99)
        if kind == "trapped_traders":
            return float(get("beyond_ticks", 0) or 0) >= float(params.get("min_beyond_ticks", 0) or 0)
        return True

    @staticmethod
    def _message(rule: AlertRule, symbol: str, payload: Any) -> str:
        get = (lambda key, default=None: payload.get(key, default)) if isinstance(payload, dict) else (lambda key, default=None: getattr(payload, key, default))
        k = rule.kind
        if k in ("big_trade", "block_trade"):
            return f"{symbol}: {get('side', '?').upper()} {get('size')} @ {get('price')} ({get('multiple')}× big-trade threshold)"
        if k == "sweep":
            return f"{symbol}: {get('side', '?').upper()} sweep through {get('levels')} levels ({get('size')} in {get('duration_ms')}ms)"
        if k == "stop_run":
            note = get("note", "") or ""
            return f"{symbol}: stop run {get('direction')} {get('ticks_moved')} ticks in {get('duration_ms')}ms" + (f" — {note}" if note else "")
        if k == "iceberg":
            return f"{symbol}: iceberg inference — {get('fills')} refills @ {get('price')} (modal {get('modal_size')})"
        if k == "speed_spike":
            return f"{symbol}: speed of tape z={get('zscore')} ({get('volume_5s')} in 5s)"
        if k == "cvd_divergence":
            return f"{symbol}: {get('kind')} CVD divergence — {get('note')}"
        if k in ("heat_pull", "heat_stack"):
            return f"{symbol}: {get('detail', k)} @ {get('price')}"
        if k == "vwap_cross":
            return (f"{symbol}: price crossed {'above' if get('side') == 'above' else 'below'} VWAP "
                    f"({float(get('ticks', 0)):+.2f} ticks, VWAP {get('vwap')})")
        if k == "depth_execution":
            return (f"{symbol}: {str(get('side', '')).upper()} print of {get('size')} took "
                    f"{float(get('share', 0)) * 100:.0f}% of the {get('resting')} resting at {get('price')}")
        if k == "depth_refill":
            return (f"{symbol}: level {get('price')} refilled {float(get('refill_ms', 0)) / 1000:.1f}s after "
                    f"being eaten ({get('size')} traded) — refreshed liquidity (inferred)")
        if k == "stacked_imbalance":
            return (f"{symbol}: stacked {str(get('side', '')).upper()} imbalance over {get('levels')} levels "
                    f"({get('from_price')} → {get('to_price')}, peak {get('max_ratio_pct')}%)")
        if k == "intent_pressure":
            side = "buy side" if str(get("side", "")) == "bid" else "sell side"
            return (f"{symbol}: {side} of the book at {get('pct')}% of its normal weight "
                    f"(threshold {get('threshold')}%) — buyers/sellers are showing size")
        if k == "pulled_size":
            return (f"{symbol}: {get('size')} pulled from the {get('side')} {get('distance_ticks')} ticks "
                    f"from mid @ {get('price')} without being traded")
        if k == "trapped_traders":
            return (f"{symbol}: {get('side')} trapped — break past {get('level')} failed, "
                    f"reclaimed in {round((get('reclaim_ms') or 0) / 1000)}s")
        return f"{symbol}: {rule.name}"


def _safe(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return {k: (v if isinstance(v, (int, float, str, bool, type(None))) else str(v)) for k, v in payload.items()}
    if hasattr(payload, "__dict__"):
        return {k: (v if isinstance(v, (int, float, str, bool, type(None))) else str(v)) for k, v in payload.__dict__.items()}
    return {}
