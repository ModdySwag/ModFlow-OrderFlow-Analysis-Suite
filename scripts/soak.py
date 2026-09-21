#!/usr/bin/env python3
"""Headless soak: RSS / task count / log ring / store size against a slope gate (G-08).

The v0.1b memory audit ran this battery by hand and nothing kept it running. This script boots the
app headless in its own scratch profile (so it cannot touch the user's config or store), samples
the process every --interval seconds, writes a CSV, and fails when the post-warm-up RSS slope
exceeds --max-slope-mb-min.

    python scripts/soak.py --minutes 30 --csv soak.csv          # the CI cadence
    python scripts/soak.py --minutes 2  --max-slope-mb-min 5    # a quick smoke of the harness

Warm-up is excluded from the slope on purpose: the audit measured a bounded-fill curve (large
early slope, ~0 later), so "warm-up vs leak" is judged on the tail (default: after minute 3).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def rss_bytes(pid: int) -> int:
    """Resident set size of a process, no third-party dependency."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(counters)
        handle = ctypes.windll.kernel32.OpenProcess(0x0400 | 0x0010, False, pid)
        try:
            ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb)
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
        return int(counters.WorkingSetSize)
    try:                                             # POSIX
        import resource
        with open(f"/proc/{pid}/statm", encoding="utf-8") as fh:
            pages = int(fh.read().split()[1])
        return pages * resource.getpagesize()
    except Exception:
        return 0


def _get(url: str) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minutes", type=float, default=30.0)
    parser.add_argument("--interval", type=float, default=30.0)
    parser.add_argument("--port", type=int, default=8097)
    parser.add_argument("--csv", default="soak.csv")
    parser.add_argument("--warmup-minutes", type=float, default=3.0)
    parser.add_argument("--max-slope-mb-min", type=float, default=0.5)
    parser.add_argument("--scratch", default="")
    args = parser.parse_args()

    scratch = Path(args.scratch) if args.scratch else (ROOT / "build" / "soak-profile")
    scratch.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["APPDATA"] = str(scratch)                    # its own config/db: the user's is untouched
    env["OFAP_SOAK"] = "1"
    proc = subprocess.Popen([sys.executable, "-m", "orderflow_system.desktop",
                             "--headless", "--port", str(args.port)], cwd=str(ROOT), env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out = Path(args.csv)
    fields = ["t_min", "rss_mb", "ws_clients", "db_bytes", "wal_bytes", "reclaimable_bytes",
              "symbols_running", "log_ring"]
    rows: list[dict] = []
    handle = out.open("w", newline="", encoding="utf-8")
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    handle.flush()
    deadline = time.time() + args.minutes * 60.0
    started = time.time()

    def sample_once() -> dict:
        row = {
            "t_min": round((time.time() - started) / 60.0, 3),
            "rss_mb": round(rss_bytes(proc.pid) / 1e6, 2),
            "ws_clients": 0, "db_bytes": 0, "wal_bytes": 0, "reclaimable_bytes": 0,
            "symbols_running": 0, "log_ring": 0,
        }
        base = f"http://127.0.0.1:{args.port}"
        storage = _get(base + "/api/control/storage") or {}
        for key in ("db_bytes", "wal_bytes", "reclaimable_bytes"):
            try:
                row[key] = int(storage.get(key) or 0)
            except (TypeError, ValueError):
                row[key] = 0
        systems = _get(base + "/api/control/systems") or {}
        try:
            row["symbols_running"] = len(systems.get("running") or systems.get("symbols") or [])
        except Exception:
            row["symbols_running"] = 0
        return row

    try:
        ready = False
        while time.time() - started < 30 and not ready:
            ready = _get(f"http://127.0.0.1:{args.port}/healthz") is not None
            time.sleep(1.0)
        # the CSV is written as the run goes: a 2 h soak must not lose its samples to a kill
        while time.time() < deadline:
            sample = sample_once()
            rows.append(sample)
            writer.writerow(sample)
            handle.flush()
            print(f"t={sample['t_min']:7.2f} min  rss={sample['rss_mb']:8.2f} MB  "
                  f"db={sample['db_bytes'] / 1e6:7.2f} MB", flush=True)
            time.sleep(args.interval)
    finally:
        handle.close()
        try:
            proc.terminate()
            proc.wait(timeout=20)
        except Exception:
            proc.kill()

    print(f"csv: {out}  ({len(rows)} samples)")

    tail = [r for r in rows if r["t_min"] >= args.warmup_minutes]
    summary = {"minutes": args.minutes, "samples": len(rows), "warmup_minutes": args.warmup_minutes,
               "gate_mb_min": args.max_slope_mb_min, "rows": len(tail)}
    if len(tail) >= 3:
        first, last = tail[0], tail[-1]
        minutes = max(0.001, last["t_min"] - first["t_min"])
        slope = (last["rss_mb"] - first["rss_mb"]) / minutes
        summary.update({"post_warmup_slope_mb_min": round(slope, 4),
                        "post_warmup_minutes": round(minutes, 2),
                        "rss_first_mb": first["rss_mb"], "rss_last_mb": last["rss_mb"],
                        "peak_rss_mb": max(r["rss_mb"] for r in rows),
                        "db_last_bytes": rows[-1]["db_bytes"] if rows else 0})
        print(f"post-warm-up slope: {slope:+.3f} MB/min "
              f"(gate {args.max_slope_mb_min:+.3f}) over {minutes:.1f} min")
        summary["verdict"] = "fail" if slope > args.max_slope_mb_min else "pass"
    else:
        summary["verdict"] = "insufficient-samples"
    Path(str(out) + ".summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print("summary:", json.dumps(summary))
    if summary["verdict"] == "fail":
        print("SOAK FAILED — the post-warm-up slope is above the gate", file=sys.stderr)
        return 1
    print("soak passed" if summary["verdict"] == "pass" else "soak incomplete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
