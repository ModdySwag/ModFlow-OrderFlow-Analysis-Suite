"""Market scanner — one ranked table across every streaming instrument.

the reference platform's *Market Analyzer* watches a list of instruments and sorts them by a
column. This is the same idea over the order-flow features this program already
computes: it reads each instrument's live analysers and produces one row per symbol,
so "which of my instruments is doing something right now?" is one glance instead of
nine view switches.

Nothing here is a signal: the columns are what the tape, the book and the intent
reader already say, ranked. The composite `score` is an explicit heuristic — it is
documented in the UI tooltip and in the docs, because a ranking that pretends to be
neutral is worse than one that states its weights.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from orderflow_system.atlas import hub as hub_mod


class MarketScanner:
    """Reads a FeatureHub and ranks its instruments."""

    def __init__(self, hub: "hub_mod.FeatureHub", window_s: float = 900.0) -> None:
        self.hub = hub
        self.window_ms = int(max(60.0, float(window_s)) * 1000)
        self._cache: Optional[dict[str, Any]] = None
        self._cache_key: tuple = ()
        self._cache_ms = 0
        self.builds = 0
        self.cache_hits = 0

    # ── per-instrument ────────────────────────────────────────────
    def _row(self, symbol: str, feats: "hub_mod.SymbolFeatures", now_ms: int) -> dict[str, Any]:
        tape = feats.tape
        stats = tape.stats()
        speed = stats.get("speed") or {}
        row: dict[str, Any] = {
            "symbol": symbol,
            "last": 0.0, "chg_pct": None, "high": None, "low": None,
            "volume": stats.get("volume", 0.0),
            "delta": stats.get("delta", 0.0),
            "delta_pct": None,
            "prints": stats.get("prints", 0),
            "prints_per_s": speed.get("per_s") or speed.get("rate") or 0.0,
            "avg_size": 0.0,
            "big_trades": stats.get("big_trades", 0),
            "sweeps": stats.get("sweeps", 0),
            "stop_runs": stats.get("stop_runs", 0),
            "icebergs": stats.get("icebergs", 0),
            "liquidations": stats.get("liquidations", 0),
            "imbalances": 0,
            "pressure_buy": None, "pressure_sell": None, "pressure_side": None, "pressure_edge": None,
            "absorption_side": None, "absorption_score": None,
            "depth_executions": 0, "depth_refills": 0,
            "vwap": None, "ticks_from_vwap": None, "vwap_side": None,
            "score": 0.0,
        }

        # price window from the tape's recent prints (the hub stays the source of truth
        # for price, so the scanner never needs its own feed)
        recent = tape.recent(240)
        if recent:
            first = recent[0]
            last = recent[-1]
            row["last"] = round(float(last["price"]), 8)
            if first.get("price"):
                row["chg_pct"] = round((float(last["price"]) / float(first["price"]) - 1.0) * 100.0, 4)
            prices = [float(p["price"]) for p in recent if p.get("price")]
            if prices:
                row["high"] = round(max(prices), 8)
                row["low"] = round(min(prices), 8)
            if row["prints"]:
                row["avg_size"] = round(float(row["volume"]) / max(1, int(row["prints"])), 6)
        if row["volume"]:
            row["delta_pct"] = round(100.0 * float(row["delta"]) / float(row["volume"]), 2)

        try:
            imb = feats.imbalance.snapshot()
            row["imbalances"] = len(imb.get("levels") or imb.get("rows") or [])
        except Exception:
            pass

        try:
            p = feats.intent.pressure()
            row["pressure_buy"] = p.get("buy_pct_of_normal")
            row["pressure_sell"] = p.get("sell_pct_of_normal")
            row["pressure_side"] = p.get("side")
            row["pressure_edge"] = p.get("edge_pct")
            a = feats.intent.absorption()
            if a.get("absorbing"):
                row["absorption_side"] = a.get("absorbing")
                row["absorption_score"] = a.get("score")
        except Exception:
            pass

        detector = getattr(feats, "detector", None)
        if detector is not None:
            try:
                dstats = detector.stats()
                row["depth_executions"] = dstats.get("executions", 0)
                row["depth_refills"] = dstats.get("refills", 0)
            except Exception:
                pass

        study = getattr(feats, "vwap", None)
        if study is not None:
            try:
                v = study.snapshot(points=8)
                row["vwap"] = v.get("vwap")
                row["ticks_from_vwap"] = v.get("ticks_from_vwap")
                if v.get("vwap") and row["last"]:
                    row["vwap_side"] = "above" if row["last"] > v["vwap"] else "below"
            except Exception:
                pass

        row["score"] = self._score(row)
        return row

    @staticmethod
    def _score(row: dict[str, Any]) -> float:
        """A stated heuristic, not a verdict.

        Weighted pieces, each capped so no single column can dominate:
          * |delta %|                     → who is winning the tape
          * |pressure edge|               → book imbalance vs its own normal
          * absorption score              → aggression that is not working
          * depth executions + refills    → hidden liquidity being interacted with
          * tape speed                    → whether anything is happening at all
        """
        def cap(value: float, top: float) -> float:
            return min(1.0, abs(value) / top) if top else 0.0

        delta = cap(row.get("delta_pct") or 0.0, 40.0)
        edge = cap(row.get("pressure_edge") or 0.0, 80.0)
        absorb = min(1.0, (row.get("absorption_score") or 0.0) / 100.0)
        depth = cap((row.get("depth_executions") or 0) + 1.5 * (row.get("depth_refills") or 0), 20.0)
        speed = cap(row.get("prints_per_s") or 0.0, 25.0)
        return round(100.0 * (0.28 * delta + 0.22 * edge + 0.18 * absorb + 0.17 * depth + 0.15 * speed), 1)

    # ── table ─────────────────────────────────────────────────────
    def snapshot(self, sort: str = "score", limit: int = 50, max_age_ms: int = 2_000) -> dict[str, Any]:
        now_ms = int(time.time() * 1000)
        key = (len(self.hub.symbols), tuple(sorted(self.hub.symbols)), sort, limit,
               sum(int(getattr(f.tape, "version", 0)) for f in self.hub.symbols.values()))
        if self._cache is not None and key == self._cache_key and now_ms - self._cache_ms <= max_age_ms:
            self.cache_hits += 1
            out = dict(self._cache)
            out["cached"] = True
            return out

        rows = []
        for symbol, feats in sorted(self.hub.symbols.items()):
            try:
                rows.append(self._row(symbol, feats, now_ms))
            except Exception:                      # one broken instrument must not blank the table
                continue

        reverse = sort in ("volume", "delta", "delta_pct", "prints_per_s", "big_trades", "score",
                           "depth_executions", "depth_refills", "absorption_score", "imbalances",
                           "sweeps", "stop_runs", "liquidations", "icebergs", "prints")
        def sort_key(r: dict[str, Any]):
            value = r.get(sort)
            if value is None:
                value = float("-inf") if reverse else float("inf")
            return value
        rows.sort(key=sort_key, reverse=reverse)
        if sort == "symbol":
            rows.sort(key=lambda r: r["symbol"])

        out = {
            "as_of": now_ms,
            "window_s": int(self.window_ms / 1000),
            "sort": sort,
            "count": len(rows),
            "rows": rows[: max(1, limit)],
            "score_note": ("score = 0.28·|Δ%| + 0.22·|pressure edge| + 0.18·absorption "
                           "+ 0.17·depth events + 0.15·tape speed, each capped"),
            "cached": False,
        }
        self.builds += 1
        self._cache = out
        self._cache_key = key
        self._cache_ms = now_ms
        return out

    def stats(self) -> dict[str, Any]:
        return {"builds": self.builds, "cache_hits": self.cache_hits,
                "instruments": len(self.hub.symbols), "window_s": int(self.window_ms / 1000)}
