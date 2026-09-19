#!/usr/bin/env python3
"""Hover-info audit (owner's directive): read every hover surface as the USER receives it.

Runs a headless chromium over the app (the frozen build in CI, a dev server locally) and reports,
per page: hover surface count, hint cards, the live shortcut registry, controls with no hover
information and no visible name (a real gap), internal case/ticket ids leaking into user text, and
shortcuts said twice or not bound at all.

    python scripts/hover_audit.py --port 8099 --csv hover_audit.json

Needs playwright + a chromium build (the churn job installs both). The static half of the same
contract lives in orderflow_system/test_hover_contract.py and runs with the suite.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

def _args():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8099, help="the app's port")
    ap.add_argument("--csv", default="hover_audit.json", help="where to write the JSON receipt")
    return ap.parse_args()


ARGS = _args()
PORT = ARGS.port
OUT = Path(ARGS.csv)

JS = r"""
() => {
  const attrs = ['title', 'data-hint-title', 'data-hint-body', 'aria-keyshortcuts'];
  const rows = [];
  const all = document.querySelectorAll('*');
  all.forEach((el) => {
    const rec = { tag: el.tagName.toLowerCase(), id: el.id || '', cls: (el.className || '').toString().slice(0, 60) };
    let any = false;
    attrs.forEach((a) => { const v = el.getAttribute(a); if (v) { rec[a] = v; any = true; } });
    if (any) rows.push(rec);
  });
  const registry = (window.OFAPKEYS && typeof window.OFAPKEYS.list === 'function')
    ? window.OFAPKEYS.list().map((r) => ({ id: r.id, keys: String(r.keys || ''), label: r.label, scope: r.scope }))
    : null;
  const interactiveMissing = [];
  /* what the user can actually SEE naming this control: its own text/placeholder, its <label>,
     the label that points at it, its wrapping label, or the text of the row it sits in */
  function visibleName(el) {
    const own = (el.textContent || '').trim();
    if (own.length > 2 && /[A-Za-z]/.test(own)) return own;
    const ph = el.getAttribute('placeholder') || '';
    if (ph.length > 2) return ph;
    try {
      if (el.labels && el.labels.length) {
        const t = Array.from(el.labels).map((l) => (l.textContent || '').trim()).join(' ').trim();
        if (t.length > 1) return t;
      }
      if (el.id) {
        const lf = document.querySelector('label[for="' + CSS.escape(el.id) + '"]');
        if (lf) { const t = (lf.textContent || '').trim(); if (t.length > 1) return t; }
      }
      const wrap = el.closest('label');
      if (wrap) { const t = (wrap.textContent || '').trim(); if (t.length > 1) return t; }
      const cell = el.closest('td, .field, .row, .kv, .set-row, fieldset, .card-body, .sy-tile');
      if (cell) { const t = (cell.textContent || '').trim(); if (t.length >= 2 && /[A-Za-z]/.test(t)) return t.slice(0, 60); }
      const prev = el.previousElementSibling;
      if (prev) { const t = (prev.textContent || '').trim(); if (t.length > 2) return t.slice(0, 60); }
    } catch (e) { /* a stub node in a template: reported as a gap */ }
    return '';
  }

  document.querySelectorAll('button[id], select[id], input[id], textarea[id]').forEach((el) => {
    if (el.disabled) return;
    const has = el.getAttribute('title') || el.getAttribute('data-hint-title') || el.getAttribute('aria-label');
    if (has) return;
    const name = visibleName(el);
    const text = (el.textContent || '').trim();
    interactiveMissing.push({ tag: el.tagName.toLowerCase(), id: el.id,
        text: text.slice(0, 40), placeholder: (el.getAttribute('placeholder') || '').slice(0, 40),
        visible_name: name.slice(0, 60), gap: !name });
  });
  return { rows, registry, interactiveMissing, url: location.pathname,
           hintCards: document.querySelectorAll('[data-hint-title]').length };
}
"""


def audit(page, label):
    data = page.evaluate(JS)
    rows = data["rows"]
    missing = data["interactiveMissing"]
    problems = {"internal_ids": [], "shortcut_twice": [], "unknown_shortcut": [],
                "missing_info": [m for m in missing if m.get("gap")],
                "missing_info_labelled": [m for m in missing if not m.get("gap")]}
    internal = re.compile(r"[\u00a7] ?\d|\bT\d{1,2}/B\d{1,2}\b|\bB\d{1,2} \u2014")
    for rec in rows:
        for attr in ("title", "data-hint-title", "data-hint-body"):
            text = rec.get(attr)
            if not text:
                continue
            if internal.search(text):
                problems["internal_ids"].append(f"{rec['tag']}#{rec['id']} [{attr}]: {text[:90]}")
            if attr == "title":
                if (text.count("Shortcut") + text.count("Press ")) > 1:
                    problems["shortcut_twice"].append(f"#{rec['id']}: {text[-70:]}")
                m = re.search(r"\(([^)]*)\)", text)
                if m and re.search(r"\b(Ctrl|Alt|Shift)\b", m.group(1)) and "Shortcut" in text:
                    problems["shortcut_twice"].append(f"#{rec['id']}: static + annotated ({text[-70:]})")
    registry = data.get("registry") or []
    known = set()
    for r in registry:
        for k in re.split(r" or | / ", str(r.get("keys") or "")):
            if k.strip():
                known.add(k.strip().lower())
    # shortcut mentions in hover text must be in the live registry
    for rec in rows:
        text = rec.get("title") or ""
        for m in re.finditer(r"((?:Ctrl|Alt|Shift|Win)(?:\+[A-Za-z0-9=+\-_]+)+|\bF\d{1,2}\b|\bEsc\b)", text):
            token = m.group(1)
            if token.lower() == "esc":
                token = "escape"
            if known and token.lower() not in known:
                problems["unknown_shortcut"].append(f"#{rec['id']}: {token}")
    print(f"[{label}] hover surfaces: {len(rows)} · hint cards: {data['hintCards']} · "
          f"registry rows: {len(registry)} · unlabelled gaps: {len(problems['missing_info'])} "
          f"(labelled-but-titleless: {len(problems['missing_info_labelled'])}) · "
          f"internal ids: {len(problems['internal_ids'])} · said-twice: {len(problems['shortcut_twice'])}")
    return data, problems


def main() -> int:
    receipt = {"url_port": PORT, "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "pages": {}}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 900})
        page.goto(f"http://127.0.0.1:{PORT}/desktop", wait_until="domcontentloaded", timeout=45000)
        page.wait_for_selector(".nav-item[data-view]", timeout=45000)
        page.wait_for_timeout(6000)
        data, problems = audit(page, "/desktop")
        receipt["pages"]["/desktop"] = {"surfaces": len(data["rows"]), "problems": problems}

        # the shortcut annotation must survive a changing rail: inserting a view shifts every
        # digit below it, and the old text must be REPLACED (this is how a control once read
        # "· Shortcut 8 · Shortcut 9"). Insert a clone, re-annotate, remove it, re-annotate.
        shuffle = page.evaluate("""() => {
            const rail = document.querySelector('.rail');
            const items = rail.querySelectorAll('.nav-item[data-view]');
            const first = items[0];
            const clone = first.cloneNode(true);
            clone.dataset.view = 'audit-probe-view';
            rail.insertBefore(clone, first);
            if (window.OFAPKEYS && window.OFAPKEYS.annotate) window.OFAPKEYS.annotate();
            const stacked = Array.from(rail.querySelectorAll('.nav-item[data-view]'))
                .map((el) => (el.getAttribute('title') || ''))
                .filter((t) => (t.match(/Shortcut |Press /g) || []).length > 1);
            clone.remove();
            if (window.OFAPKEYS && window.OFAPKEYS.annotate) window.OFAPKEYS.annotate();
            const stale = Array.from(rail.querySelectorAll('.nav-item[data-view]'))
                .map((el) => (el.getAttribute('title') || ''))
                .filter((t) => (t.match(/Shortcut |Press /g) || []).length > 1);
            const digits = Array.from(rail.querySelectorAll('.nav-item[data-view]')).slice(0, 9)
                .map((el, i) => ({ view: el.dataset.view,
                    ok: (el.getAttribute('title') || '').indexOf('Press ' + (i + 1) + ' ') >= 0 }));
            return { stacked_after_insert: stacked, stacked_after_remove: stale, digits };
        }""")
        print(f"[shuffle] stacked after insert: {len(shuffle['stacked_after_insert'])} · "
              f"after remove: {len(shuffle['stacked_after_remove'])} · "
              f"digits wrong: {sum(1 for d in shuffle['digits'] if not d['ok'])}")
        for bad in shuffle["stacked_after_insert"][:3]:
            print("     STACKED:", bad[-90:])
        receipt["shuffle"] = shuffle

        # walk every view so each module's injected controls are present, then re-read
        views = page.evaluate("Array.from(new Set(Array.from(document.querySelectorAll('.nav-item[data-view]')).map(e => e.dataset.view))).filter(Boolean)")
        receipt["views"] = views
        for v in views:
            page.evaluate("""(v) => { const el = document.querySelector('.nav-item[data-view="' + v + '"]'); if (el) el.click(); }""", v)
            page.wait_for_timeout(220)
        page.wait_for_timeout(2000)
        data2, problems2 = audit(page, "/desktop after a full view walk")
        receipt["pages"]["/desktop after walk"] = {"surfaces": len(data2["rows"]), "problems": problems2}

        # the legacy dashboard page ships its own tooltips
        page.goto(f"http://127.0.0.1:{PORT}/static/index.html", wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(5000)
        data3, problems3 = audit(page, "/static (legacy)")
        receipt["pages"]["/static"] = {"surfaces": len(data3["rows"]), "problems": problems3}
        browser.close()

    receipt["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    OUT.write_text(json.dumps(receipt, indent=1), encoding="utf-8")
    print("receipt:", OUT)
    total = sum(len(p["problems"]["internal_ids"]) + len(p["problems"]["shortcut_twice"])
                for p in receipt["pages"].values())
    print("internal-id + said-twice findings:", total)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
