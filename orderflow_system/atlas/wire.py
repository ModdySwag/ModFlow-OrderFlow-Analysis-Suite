"""The heat wire — a binary sibling for the depth snapshot (see handoff §56).

The JSON snapshot is a dict of nested lists; the engine's client walks every cell to adapt it
(measured 25.5 ms per 48.4 k cells after the numeric-key rewrite, §50). This module packs the SAME
snapshot into typed sections so the client reads floats without parsing objects:

    b"OFHB" | u32 header length | header JSON (utf-8) | sections

Sections in order (byteorder: native — the suite pins little-endian hosts):
    buckets  f64[cols]            epoch ms (Float32 cannot hold them exactly)
    prices   f32[cols x rows]     per-column ladders — or f32[rows] once when `prices_mode == "flat"`
    values   f32[cols x rows]
    traded   f32[cols x rows]     only when the header's `traded` flag is set
    best     f32 bid, f32 ask, i32 trades  — 12 B per column

`decode_heat_bin` mirrors the layout; the tests round-trip through it and the client's
`math.decodeHeatBin` is pinned against the same shape by the ofx selftest.
"""

from __future__ import annotations

import json
import struct
import sys
from array import array
from typing import Any

MAGIC = b"OFHB"


def _flat_rm(matrix: list, rows: int, cols: int) -> list[float]:
    """ROW-major flatten with zero-fill — the snapshot contract is values[price row][time column]
    (depthmap._build_snapshot builds `values = [[0.0] * len(cols) for _ in range(rows)]` with
    `prices` the flat ladder). The client's reader never has to bounds-check ragged rows, and a
    short row is honestly zeros (the JSON path does the same via `|| 0`)."""
    out: list[float] = []
    for r in range(rows):
        row = matrix[r] if r < len(matrix) and isinstance(matrix[r], list) else []
        for c in range(cols):
            v = row[c] if c < len(row) else 0.0
            try:
                out.append(float(v))
            except (TypeError, ValueError):
                out.append(0.0)
    return out


def _flat_pc(matrix: list, cols: int, rows: int) -> list[float]:
    """Per-column ladders (a legacy producer shape): prices[col][row], flattened column-major."""
    out: list[float] = []
    for c in range(cols):
        col = matrix[c] if c < len(matrix) and isinstance(matrix[c], list) else []
        for r in range(rows):
            v = col[r] if r < len(col) else 0.0
            try:
                out.append(float(v))
            except (TypeError, ValueError):
                out.append(0.0)
    return out


def pack_heatmap_bin(snap: dict[str, Any]) -> bytes:
    assert sys.byteorder == "little", "the wire assumes little-endian hosts (pinned by tests)"
    buckets = [int(b) for b in (snap.get("buckets") or [])]
    cols = len(buckets)
    values = snap.get("values") or []
    prices = snap.get("prices") or []
    prices_mode = "per_column" if (prices and isinstance(prices[0], list)) else "flat"
    # rows = the PRICE axis: the ladder's length when flat, else one column's ladder;
    # a values-only producer gets rows = len(values) (its outer axis is the price row).
    if prices_mode == "flat":
        rows = len(prices)
    else:
        rows = len(prices[0]) if prices else 0
    if not rows and values:
        rows = len(values)
    traded_src = snap.get("traded") or []
    best = snap.get("best") or []

    header = {
        "symbol": snap.get("symbol", ""),
        "version": int(snap.get("version") or 0),
        "step": float(snap.get("step") or 0),
        "tick": float(snap.get("tick") or 0),
        "cols": cols, "rows": rows,
        "prices_mode": prices_mode,
        "traded": bool(traded_src),
        "carry_forward": bool(snap.get("carry_forward")),
        "carried_cells": int(snap.get("carried_cells") or 0),
        "scale_max": float(snap.get("scale_max") or 0),
        "upper_cutoff_pct": float(snap.get("upper_cutoff_pct") or 0),
        "wall_age_ms": int(snap.get("wall_age_ms") or 0),
        "walls": snap.get("walls") or [],
        "events": snap.get("events") or [],
        "note": snap.get("note", ""),
    }
    hj = json.dumps(header, separators=(",", ":")).encode("utf-8")

    parts = [MAGIC, struct.pack("<I", len(hj)), hj]
    parts.append(array("d", buckets).tobytes())
    if prices_mode == "per_column":
        parts.append(array("f", _flat_pc(prices, cols, rows)).tobytes())
    else:
        flat_prices = []
        for v in prices:
            try:
                flat_prices.append(float(v))
            except (TypeError, ValueError):
                flat_prices.append(0.0)
        parts.append(array("f", flat_prices).tobytes())
    parts.append(array("f", _flat_rm(values, rows, cols)).tobytes())
    if header["traded"]:
        parts.append(array("f", _flat_rm(traded_src, rows, cols)).tobytes())
    best_bytes = bytearray()
    for c in range(cols):
        b = best[c] if c < len(best) and isinstance(best[c], dict) else {}
        try:
            bid = float(b.get("bid") or 0.0)
        except (TypeError, ValueError):
            bid = 0.0
        try:
            ask = float(b.get("ask") or 0.0)
        except (TypeError, ValueError):
            ask = 0.0
        try:
            trades = int(b.get("trades") or 0)
        except (TypeError, ValueError):
            trades = 0
        best_bytes += struct.pack("<ffi", bid, ask, trades)
    parts.append(bytes(best_bytes))
    return b"".join(parts)


def decode_heat_bin(data: bytes) -> dict[str, Any]:
    """Mirror reader (tests + a readable spec of the layout)."""
    assert data[:4] == MAGIC, "not an OFHB payload"
    hlen = struct.unpack_from("<I", data, 4)[0]
    header = json.loads(data[8:8 + hlen].decode("utf-8"))
    off = 8 + hlen
    cols, rows = header["cols"], header["rows"]

    def take(fmt: str, count: int):
        nonlocal off
        size = struct.calcsize(fmt) * count
        chunk = data[off:off + size]
        off += size
        return array(fmt, chunk).tolist() if count else []

    buckets = take("d", cols)
    prices = take("f", cols * rows if header["prices_mode"] == "per_column" else rows)
    values = take("f", cols * rows)
    traded = take("f", cols * rows) if header["traded"] else []
    best = []
    for _ in range(cols):
        bid, ask, trades = struct.unpack_from("<ffi", data, off)
        off += 12
        best.append({"bid": bid, "ask": ask, "trades": trades})
    return {
        "header": header, "buckets": buckets, "prices": prices, "values": values,
        "traded": traded, "best": best, "consumed": off,
    }
