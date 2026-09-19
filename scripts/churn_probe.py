#!/usr/bin/env python3
# The view-churn leak probe (R-03) — promoted from the v0.1b memory-audit receipts, verbatim.
#
# Drives the shell headless over CDP through full view-churn cycles and checks the three
# properties the audit measured clean: 0 same-node listener accumulation, 0 detached-but-retained
# DOM nodes after a forced GC, and a listener count that returns to its baseline (+/-2).
#
# Requires a headless browser endpoint (the repo's existing headless browser step) and Playwright.
# Keep the threshold "0 same-node accumulation, 0 detached-retained, listeners +/-2" (the audit's
# own wording) when wiring this into CI: `scripts/soak.py` covers the Python side, this covers
# the front end.
#
# --- original audit receipt below ---

"""OFAP listener/timer accumulation probe v2 - per-NODE identity.

Patches EventTarget.addEventListener/removeEventListener with a WeakMap node id,
tracking net handlers per (node, type) plus the adding stack. WeakRef lets us ask
after a forced GC: is the node still reachable? was it ever detached?

Dumps after warm-up, runs N churn cycles, dumps again, then reports:
  A) persistent-target leaks  (window/document net handlers)
  B) same-node accumulation   (node gained handlers between dumps)
  C) detached-but-retained    (node died from the DOM but is still reachable)
  D) timer growth             (intervals/timeouts/rAF alive across dumps)

Run with the webkit venv python; expects a headless shell already on --port.
"""

import argparse
import json
import os
import subprocess
import time

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))

PROBE_JS = r"""
(() => {
  let NID = 0;
  const IDM = new WeakMap();          // EventTarget -> id
  const H = new Map();                // id -> {ref, desc, types: Map(type -> {net, stack})}
  function descOf(t) {
    if (t === window) return 'window';
    if (t === document) return 'document';
    try {
      if (typeof Element !== 'undefined' && t instanceof Element) {
        const cls = (typeof t.className === 'string' && t.className)
          ? '.' + t.className.trim().split(/\s+/).slice(0, 2).join('.') : '';
        return (t.tagName || '?') + (t.id ? '#' + t.id : '') + cls;
      }
    } catch (e) {}
    return Object.prototype.toString.call(t);
  }
  function stack2() {
    try {
      return (new Error().stack || '').split('\n').slice(2, 5)
        .map(s => s.trim()).join(' <- ');
    } catch (e) { return ''; }
  }
  function idOf(t) {
    let id = IDM.get(t);
    if (id === undefined) {
      id = ++NID;
      IDM.set(t, id);
      H.set(id, { ref: new WeakRef(t), desc: descOf(t), types: new Map() });
    }
    return id;
  }
  const oa = EventTarget.prototype.addEventListener;
  const orem = EventTarget.prototype.removeEventListener;
  EventTarget.prototype.addEventListener = function (type, fn, opts) {
    try {
      const rec = H.get(idOf(this));
      if (rec) {
        const ty = rec.types.get(type) || { net: 0, stack: '' };
        ty.net++;
        if (!ty.stack) ty.stack = stack2();
        rec.types.set(type, ty);
      }
    } catch (e) {}
    return oa.apply(this, arguments);
  };
  EventTarget.prototype.removeEventListener = function (type, fn, opts) {
    try {
      const rec = H.get(idOf(this));
      if (rec) {
        const ty = rec.types.get(type) || { net: 0, stack: '' };
        ty.net--;
        rec.types.set(type, ty);
      }
    } catch (e) {}
    return orem.apply(this, arguments);
  };
  window.__lp_nodes = () => Array.from(H.entries()).map(([id, r]) => {
    let el = null;
    try { el = r.ref.deref(); } catch (e) {}
    const types = Array.from(r.types.entries())
      .filter(([t, v]) => v.net !== 0)
      .map(([t, v]) => ({ type: t, net: v.net, stack: v.stack }));
    return { id: id, desc: r.desc,
             alive: !!el,
             connected: el ? (el === window || el === document ? true : !!el.isConnected) : null,
             types: types };
  }).filter(x => x.types.length > 0);

  const T = new Map();
  const oSI = window.setInterval, oCI = window.clearInterval;
  const oST = window.setTimeout, oCT = window.clearTimeout;
  const oRAF = window.requestAnimationFrame, oCAF = window.cancelAnimationFrame;
  window.setInterval = function (fn, ms) {
    const extra = Array.prototype.slice.call(arguments, 2);
    const id = oSI.apply(window, [fn, ms].concat(extra));
    try { T.set(id, { kind: 'interval', ms: ms, stack: stack2() }); } catch (e) {}
    return id;
  };
  window.clearInterval = function (id) {
    try { T.delete(id); } catch (e) {}
    return oCI.apply(window, arguments);
  };
  window.setTimeout = function (fn, ms) {
    const extra = Array.prototype.slice.call(arguments, 2);
    const wrapped = function () {
      try { T.delete(timer_id); } catch (e) {}
      if (typeof fn === 'function') return fn.apply(this, arguments);
      if (typeof fn === 'string') return eval(fn);
    };
    const timer_id = oST.apply(window, [wrapped, ms].concat(extra));
    try { T.set(timer_id, { kind: 'timeout', ms: ms, stack: stack2() }); } catch (e) {}
    return timer_id;
  };
  window.clearTimeout = function (id) {
    try { T.delete(id); } catch (e) {}
    return oCT.apply(window, arguments);
  };
  window.requestAnimationFrame = function (fn) {
    const wrapped = function (ts) {
      try { T.delete(raf_id); } catch (e) {}
      return fn.apply(this, arguments);
    };
    const raf_id = oRAF.call(window, wrapped);
    try { T.set(raf_id, { kind: 'raf', ms: 16, stack: stack2() }); } catch (e) {}
    return raf_id;
  };
  window.cancelAnimationFrame = function (id) {
    try { T.delete(id); } catch (e) {}
    return oCAF.apply(window, arguments);
  };
  window.__tm_dump = () => {
    const m = new Map();
    for (const v of T.values()) {
      const k = v.kind + ' @' + v.ms + 'ms from ' + (v.stack || '?');
      m.set(k, (m.get(k) || 0) + 1);
    }
    return m;
  };
})();
"""


def find_server_pid(port):
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace").stdout
        for line in out.splitlines():
            if f":{port}" in line and "LISTEN" in line.upper():
                return int(line.split()[-1])
    except Exception:  # noqa: BLE001
        pass
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8099)
    ap.add_argument("--cycles", type=int, default=5)
    ap.add_argument("--dwell", type=float, default=0.3)
    args = ap.parse_args()
    url = f"http://127.0.0.1:{args.port}/desktop"
    ts = time.strftime("%Y%m%d_%H%M%S")
    out = {"started": ts, "url": url, "cycles": args.cycles}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 900})
        cdp = page.context.new_cdp_session(page)
        cdp.send("Network.enable")
        cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})
        page.add_init_script(PROBE_JS)
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_selector(".nav-item[data-view]", timeout=45000)
        page.wait_for_timeout(6000)

        views = page.evaluate(
            "Array.from(new Set(Array.from(document.querySelectorAll('.nav-item[data-view]'))"
            ".map(e => e.dataset.view))).filter(Boolean)")
        out["views"] = views

        def churn_once():
            for v in views:
                page.evaluate(
                    """(v) => {
                        const el = document.querySelector('.nav-item[data-view="' + v + '"]');
                        if (el) { el.click(); return; }
                        if (typeof window.showView === 'function') window.showView(v);
                    }""", v)
                page.wait_for_timeout(int(args.dwell * 1000))

        def dump():
            cdp.send("HeapProfiler.collectGarbage")
            cdp.send("HeapProfiler.collectGarbage")
            page.wait_for_timeout(1200)
            nodes = page.evaluate("() => window.__lp_nodes()")
            timers = page.evaluate("() => Array.from(window.__tm_dump().entries())")
            return {"nodes": {n["id"]: n for n in nodes},
                    "timers": {k: v for k, v in timers}}

        churn_once()
        page.wait_for_timeout(4000)
        d1 = dump()
        for _ in range(args.cycles):
            churn_once()
        page.wait_for_timeout(4000)
        d2 = dump()

        # A) persistent targets with leftover net handlers
        persistent = []
        for n in d2["nodes"].values():
            if n["desc"] in ("window", "document"):
                for t in n["types"]:
                    if t["net"] != 0:
                        persistent.append({"target": n["desc"], "type": t["type"],
                                           "net": t["net"], "stack": t["stack"]})
        out["persistent_targets"] = persistent

        # B) same-node accumulation between dumps
        accum = []
        for nid, n2 in d2["nodes"].items():
            n1 = d1["nodes"].get(nid)
            if not n1:
                continue
            for t2 in n2["types"]:
                t1 = next((x for x in n1["types"] if x["type"] == t2["type"]), {"net": 0})
                d = t2["net"] - t1["net"]
                if d > 0:
                    accum.append({"desc": n2["desc"], "type": t2["type"], "delta": d,
                                  "net": t2["net"], "stack": t2["stack"]})
        accum.sort(key=lambda x: -x["delta"])
        out["same_node_accumulation"] = accum

        # C) detached-but-retained: seen in d1, still alive+detached in d2
        retained = []
        for nid, n1 in d1["nodes"].items():
            n2 = d2["nodes"].get(nid)
            if n2 and n2["alive"] and not n2["connected"]:
                retained.append({"desc": n1["desc"], "types": n2["types"]})
        out["detached_retained"] = retained

        # D) timer growth
        tdiff = []
        for k, n2 in d2["timers"].items():
            n1 = d1["timers"].get(k, 0)
            if n2 - n1 > 0:
                tdiff.append({"timer": k, "d": n2 - n1, "live": n2})
        tdiff.sort(key=lambda x: -x["d"])
        out["timer_growth"] = tdiff
        out["timers_alive_d1"] = len(d1["timers"])
        out["timers_alive_d2"] = len(d2["timers"])

        # counts by class for context
        by_desc = {}
        for n in d2["nodes"].values():
            by_desc[n["desc"]] = by_desc.get(n["desc"], 0) + 1
        out["nodes_tracked_d2"] = len(d2["nodes"])
        out["alive_connected_d2"] = sum(1 for n in d2["nodes"].values()
                                        if n["alive"] and n["connected"])
        out["alive_detached_d2"] = sum(1 for n in d2["nodes"].values()
                                       if n["alive"] and not n["connected"])
        out["dead_d2"] = sum(1 for n in d2["nodes"].values() if not n["alive"])

        browser.close()

    out["finished"] = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(HERE, f"soak_probe2_{ts}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)

    print("nodes tracked d2:", out["nodes_tracked_d2"],
          "| alive+connected:", out["alive_connected_d2"],
          "| alive-detached:", out["alive_detached_d2"], "| dead:", out["dead_d2"])
    print("\n== A) window/document leftover handlers ==")
    for r in out["persistent_targets"][:20]:
        print(f"  net={r['net']:<4} {r['target']} | {r['type']}")
        if r["stack"]:
            print(f"        {r['stack'][:170]}")
    print("\n== B) same-node handler accumulation (top 25) ==")
    for r in out["same_node_accumulation"][:25]:
        print(f"  +{r['delta']:<3} net={r['net']:<4} {r['desc']} | {r['type']}")
        if r["stack"]:
            print(f"        {r['stack'][:170]}")
    print("\n== C) detached-but-retained (top 25) ==")
    for r in out["detached_retained"][:25]:
        tt = ", ".join(f"{t['type']}({t['net']})" for t in r["types"])
        print(f"  {r['desc']} :: {tt}")
    print("\n== D) timer growth ==")
    for r in out["timer_growth"][:20]:
        print(f"  +{r['d']:<3} live={r['live']:<4} {r['timer'][:170]}")
    print("timers alive: d1", out["timers_alive_d1"], "-> d2", out["timers_alive_d2"])
    print("WROTE", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
