#!/usr/bin/env python3
"""Metric-hygiene gate: the standing sweep for the rules this suite settled panel by panel.

Owner asked for a single standing check rather than a request per panel. Three classes are
mechanically decidable and live here; the rest (is this number *semantically* right?) is what the
test suite and the live reconciliations cover, and what the audit walker
(`audit_views.py` in the agent's runtime) exercises by reading every view's rendered text.

  H1 price-by-magnitude   a price written from the size of the number (1000 → 2 dp …) instead of the
                          instrument's tick. Prices must come from the tick the wire states
                          (§138 units, §141 decimals).
  H2 placeholder glyph    a bare "--" standing in for an absent value. Absence reads as an em dash,
                          or better, as a sentence saying why (§140): "--" reads like a minus sign.
                          Time masks ("--:--:--") are a deliberate exception — a pending timestamp
                          keeps its shape — and are allowed here.
  H3 diagnostics on a user surface  a paint/transfer counter or a developer note written into a
                          title, hint or status line (§140: diagnostics ride data-*, not the UI).

Same shape as scripts/audit_ui_refs.py: run it, read it, exit code 1 means findings.

    .venv/Scripts/python.exe scripts/audit_metric_hygiene.py
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Both trees matter: the desktop UI renders two legacy dashboard widgets (OrderbookLadder,
# MicrostructurePanel), so dashboard/static/*.js is a live user surface too.
TREES = [os.path.join(ROOT, "orderflow_system", "desktop", "ui"),
         os.path.join(ROOT, "orderflow_system", "dashboard", "static")]

H1 = re.compile(r">=\s*1000\s*\?[^;]{0,60}toFixed|toFixed\([^)]*\)\s*:\s*\w+\s*>=\s*1")
H2 = re.compile(r"(?<![\w$!-])--(?![\w-])")
H2_SKIP = re.compile(r"var\(--|<!--|-->|\b--of-|@media|url\(|calc\(|--:--")
H3 = re.compile(r"\.title\s*\+\?=\s*[^;]*(painted|skipped|coalesced|Repaints)"
                r"|\.title\s*=\s*[^;]*(painted|skipped|coalesced|frame budget|guidance:)")

findings = []


def scan(path: str) -> None:
    lines = open(path, encoding="utf-8", errors="replace").read().split("\n")
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith(("//", "*", "/*")):
            continue
        rel = os.path.relpath(path, ROOT).replace("\\", "/")
        # A magnitude chain inside a function that already consults a tick is the documented
        # fallback, not the defect: look back over the enclosing statement for a tick reference.
        window = "\n".join(lines[max(0, i - 9): i]).lower()
        if H1.search(line) and "tick" not in window:
            findings.append(("H1 price-by-magnitude", rel, i, stripped[:120]))
        if H2.search(line) and not H2_SKIP.search(line):
            findings.append(("H2 placeholder-glyph", rel, i, stripped[:120]))
        if H3.search(line):
            findings.append(("H3 diagnostics-on-surface", rel, i, stripped[:120]))


for tree in TREES:
    for base, dirs, files in os.walk(tree):
        dirs[:] = [d for d in dirs if d not in ("vendor", "themes", "audio", "__pycache__")]
        for f in sorted(files):
            if f.endswith(".js") and not f.endswith(".selftest.js"):
                scan(os.path.join(base, f))

if not findings:
    print("METRIC HYGIENE CLEAN — no price-by-magnitude, no stray placeholder glyph, "
          "no diagnostics on a user surface.")
    sys.exit(0)

print("%d finding(s):" % len(findings))
for cls, rel, line, text in findings:
    print("  %-28s %s:%s" % (cls, rel, line))
    print("      %s" % text)
sys.exit(1)
