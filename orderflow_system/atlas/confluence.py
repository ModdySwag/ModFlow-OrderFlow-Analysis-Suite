"""
Level confluence — independent reads at (nearly) the same price make a stronger level.

The reading (the reference teaching): the best setups are where two independent methods point at
one price — a POC and a VWAP deviation meeting, a virgin POC and a stacked-imbalance zone, an
unfinished-business magnet and a node band. This module is the pure scoring core: take any set of
level references, cluster those within a tolerance, score each cluster by how many members (and
how many *distinct sources*) agree, and return the ranked answer.

    LevelRef            one level: price, source (a free string), optional strength / note
    find_confluences()  cluster + score + rank
    refs_from_pocs()    helper: period POC dicts (see atlas.profiles.period_pocs) -> LevelRefs
    refs_from_nodes()   helper: NodeRun dicts -> LevelRefs
    refs_from_unfinished()  helper: UnfinishedLevel dicts -> LevelRefs

Stdlib only; no alert/UI knowledge. The tolerance is caller-supplied (pass half a tick, one
tick, or a price band) because what counts as "the same level" differs per instrument and per
analysis — the module does not pretend to know.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence


@dataclass
class LevelRef:
    """One level read from one source, ready to be clustered with the others."""

    price: float
    source: str                      # e.g. "poc", "virgin_poc", "node", "vwap_band", "wall"
    strength: float = 1.0            # relative weight (node count, held ms, volume share…)
    ts_ms: int = 0
    note: str = ""

    @classmethod
    def coerce(cls, raw: Any) -> "LevelRef":
        if isinstance(raw, LevelRef):
            return raw
        if isinstance(raw, Mapping):
            return cls(
                price=float(raw.get("price") or 0.0),
                source=str(raw.get("source") or raw.get("kind") or "level"),
                strength=float(raw.get("strength") or 1.0),
                ts_ms=int(raw.get("ts_ms") or 0),
                note=str(raw.get("note") or raw.get("detail") or ""),
            )
        raise TypeError(f"cannot read a level from {type(raw).__name__}")


def _cluster(members: Sequence[LevelRef], tol: float) -> list[dict[str, Any]]:
    """Greedy clustering over price-sorted members, bounded to one tolerance-window per cluster."""
    out: list[dict[str, Any]] = []
    cluster: list[LevelRef] = []
    window_start = 0.0
    for ref in sorted(members, key=lambda r: r.price):
        if cluster and ref.price > window_start + tol:
            out.append(_finish(cluster))
            cluster = []
        if not cluster:
            window_start = ref.price
        cluster.append(ref)
    if cluster:
        out.append(_finish(cluster))
    return out


def _finish(cluster: list[LevelRef]) -> dict[str, Any]:
    total_w = sum(max(0.0, r.strength) for r in cluster) or float(len(cluster))
    price = sum(r.price * max(0.0, r.strength) for r in cluster) / total_w
    sources = sorted({r.source for r in cluster})
    return {
        "price": round(price, 10),
        "members": [{"price": r.price, "source": r.source, "strength": r.strength,
                     "ts_ms": r.ts_ms, "note": r.note} for r in cluster],
        "count": len(cluster),
        "distinct_sources": len(sources),
        "sources": sources,
        "strength": round(sum(max(0.0, r.strength) for r in cluster), 8),
    }


def find_confluences(levels: Iterable[Any], tol: float, min_members: int = 2,
                     min_distinct: int = 1) -> list[dict[str, Any]]:
    """Cluster level references within ``tol`` and rank the agreeing groups.

    ``min_members`` counts total members; ``min_distinct`` counts *distinct sources* (set it to 2
    to demand genuinely independent agreement). Ranked by distinct sources, then member count,
    then strength. Pure function of its inputs.
    """
    refs = [LevelRef.coerce(r) for r in levels]
    if not refs or tol <= 0:
        return []
    groups = [g for g in _cluster(refs, tol)
              if g["count"] >= max(2, int(min_members)) and g["distinct_sources"] >= max(1, int(min_distinct))]
    return sorted(groups, key=lambda g: (-g["distinct_sources"], -g["count"], -g["strength"]))


# ── adapters for the level sources this build already computes ──────────────

def refs_from_pocs(pocs: Iterable[Mapping[str, Any]], source: str = "poc") -> list[LevelRef]:
    """Period POC dicts (atlas.profiles.period_pocs) -> refs (one per period)."""
    out = []
    for p in pocs:
        price = float(p.get("poc") or 0.0)
        if price:
            out.append(LevelRef(price=price, source=source,
                                strength=float(p.get("total_volume") or 1.0),
                                note=str(p.get("period") or "")))
    return out


def refs_from_nodes(nodes: Iterable[Mapping[str, Any]], source: str = "node") -> list[LevelRef]:
    """Node dicts (atlas.nodes.NodeRun.to_dict) -> refs (strength = bar count)."""
    out = []
    for n in nodes:
        price = float(n.get("price") or 0.0)
        if price:
            out.append(LevelRef(price=price, source=source,
                                strength=float(n.get("count") or 1.0),
                                note=f"{n.get('count')}-bar node"))
    return out


def refs_from_unfinished(levels: Iterable[Mapping[str, Any]], source: str = "unfinished") -> list[LevelRef]:
    """UnfinishedLevel dicts (atlas.unfinished.UnfinishedLevel.to_dict) -> refs."""
    out = []
    for lv in levels:
        price = float(lv.get("price") or 0.0)
        if price:
            out.append(LevelRef(price=price, source=source,
                                strength=float(lv.get("arms") or 1.0),
                                note=str(lv.get("side") or "")))
    return out
