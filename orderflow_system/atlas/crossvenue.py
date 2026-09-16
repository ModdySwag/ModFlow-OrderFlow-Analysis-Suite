"""
Cross-venue top of book — the function of the reference platform's "Cross BBO" and (as far as the data
allows) "the reference platform": one instrument, every venue that can answer, side by side.

Why it belongs here: this build already talks to more than one venue. Bybit publishes
depth, Alpaca publishes top-of-book quotes (its crypto snapshot answers with no account at
all), and a trader watching one venue while trading another wants to see the other's best
bid/offer without opening a second platform.

What this is and is not — stated plainly because overselling it would be the same lie the
live/demo bridge existed to remove:

* it **is** a per-venue top of book with spread, mid, age and a consolidated best
  (highest bid, lowest ask) naming the venue that owns each side;
* it is **not** a synthetic merged book: full "the reference platform" consolidation needs two venues
  that both publish depth, and Alpaca publishes quotes only. The consolidated row is a
  top-of-book, and the payload says so.

A venue whose quote is older than ``stale_ms`` is marked ``stale`` and excluded from the
consolidated best rather than silently dropped — a frozen venue is information, and it is
exactly the state that makes a consolidated number wrong.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

#: The age policy lives in ONE module now (atlas/freshness.py): P1-10 made the engine status and
#: the UI chips read the same windows, so this module imports the policy instead of owning it.
#: These names stay importable from here for older callers.
from orderflow_system.atlas import freshness as _freshness

DEFAULT_STALE_MS = _freshness.DEFAULT_WINDOW_MS
STALE_DEPTH_MS = _freshness.STALE_DEPTH_MS
STALE_QUOTE_MS = _freshness.STALE_QUOTE_MS


def stale_window_ms(kind: str) -> int:
    """How long a row of this kind may go without an update before it is called stale."""
    return _freshness.window_ms(kind)


@dataclass
class VenueTop:
    """One venue's best bid/offer for the instrument, with provenance."""
    venue: str
    label: str = ""
    kind: str = "depth"                 # "depth" (real book) or "quote" (top only)
    bid: float = 0.0
    bid_size: float = 0.0
    ask: float = 0.0
    ask_size: float = 0.0
    ts_ms: int = 0
    ok: bool = True
    note: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, now_ms: int, stale_ms: Optional[int] = None) -> dict[str, Any]:
        #: ts_ms == 0 means the venue's clock is not comparable to ours (documented in the
        #: caller): an unknown age is reported as unknown, not as stale — inventing an age
        #: would be worse than saying nothing. The assessment itself lives in atlas/freshness.py.
        a = _freshness.assess(self.kind, self.ts_ms, now_ms, window=stale_ms)
        valid = self.ok and self.bid > 0 and self.ask > 0 and self.ask >= self.bid
        stale = a["stale"]
        spread = (self.ask - self.bid) if valid else 0.0
        mid = ((self.ask + self.bid) / 2) if valid else 0.0
        return {
            "venue": self.venue,
            "label": self.label or self.venue,
            "kind": self.kind,
            "bid": self.bid,
            "bid_size": self.bid_size,
            "ask": self.ask,
            "ask_size": self.ask_size,
            "ts_ms": self.ts_ms,
            "age_ms": a["age_ms"],
            "age_known": a["age_known"],
            "stale_after_ms": a["window_ms"],
            "stale": stale,
            "ok": bool(valid and not stale),
            "spread": round(spread, 10),
            "mid": round(mid, 10),
            "spread_bps": round((spread / mid) * 10_000, 4) if mid else 0.0,
            "note": self.note,
            **({"extra": self.extra} if self.extra else {}),
        }


def build(entries: Iterable[VenueTop], now_ms: Optional[int] = None,
          stale_ms: Optional[int] = None) -> dict[str, Any]:
    """Per-venue rows plus the consolidated best bid/ask over the fresh venues.

    ``stale_ms`` is a testing/explicit override; left as None each row uses the policy for
    its kind (see ``stale_window_ms``).
    """
    now = int(now_ms if now_ms is not None else time.time() * 1000)
    rows = [e.to_dict(now, stale_ms) for e in entries]

    usable = [r for r in rows if r["ok"]]
    consolidated: dict[str, Any] = {"available": False, "reason": ""}
    if usable:
        best_bid = max(usable, key=lambda r: r["bid"])
        best_ask = min(usable, key=lambda r: r["ask"])
        spread = best_ask["ask"] - best_bid["bid"]
        mid = (best_bid["bid"] + best_ask["ask"]) / 2
        consolidated = {
            "available": True,
            "bid": best_bid["bid"],
            "bid_size": best_bid["bid_size"],
            "bid_venue": best_bid["venue"],
            "ask": best_ask["ask"],
            "ask_size": best_ask["ask_size"],
            "ask_venue": best_ask["venue"],
            "spread": round(spread, 10),
            "spread_bps": round((spread / mid) * 10_000, 4) if mid else 0.0,
            "mid": round(mid, 10),
            # a negative spread means the best bid sits above the best ask: the two venues
            # disagree by more than their combined spread (worth knowing, not a trade call)
            "crossed": spread < 0,
            "venues_used": [r["venue"] for r in usable],
            "reason": "",
        }
    else:
        reasons = [f"{r['label']}: {r['note'] or ('stale' if r['stale'] else 'no quote')}" for r in rows]
        consolidated["reason"] = ("no venue could answer — " + "; ".join(reasons)) if reasons else "no venues configured"

    multibook_capable = len([r for r in rows if r["kind"] == "depth"]) > 1
    note = ("Top-of-book consolidation across venues: the best bid and best ask may come from "
            "different venues. A fully merged book needs depth from more than one venue "
            f"({'available here' if multibook_capable else 'only one venue publishes depth here'}).")
    return {
        "venues": rows,
        "consolidated": consolidated,
        "stale_policy": {"depth_ms": _freshness.STALE_DEPTH_MS, "quote_ms": _freshness.STALE_QUOTE_MS,
                         "override_ms": stale_ms},
        "kind": "top_of_book" if not multibook_capable else "depth_merge",
        "note": note,
    }
