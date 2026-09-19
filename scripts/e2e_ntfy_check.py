"""Wait for a real alert to be routed to ntfy, then prove it arrived at ntfy.sh.

Polls the app's alert log for a fired alert whose channels include 'ntfy' (or
'telegram'), then reads the topic back from ntfy's public JSON API.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request

APP = "http://127.0.0.1:8095"
TOPIC = sys.argv[1] if len(sys.argv) > 1 else ""
BUDGET_S = int(sys.argv[2]) if len(sys.argv) > 2 else 240


def get_json(url: str, timeout: float = 30.0):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def main() -> int:
    started = time.time()
    seen = {a.get("id") or f"{a.get('ts_ms')}-{a.get('kind')}": a for a in get_json(f"{APP}/api/atlas/alerts?limit=50")["alerts"]}
    print(f"watching {len(seen)} existing alerts; budget {BUDGET_S}s")

    routed = None
    while time.time() - started < BUDGET_S:
        try:
            alerts = get_json(f"{APP}/api/atlas/alerts?limit=50")["alerts"]
        except Exception as exc:
            print("  app poll failed:", exc)
            time.sleep(5)
            continue
        for a in alerts:
            key = a.get("id") or f"{a.get('ts_ms')}-{a.get('kind')}"
            if key in seen:
                continue
            seen[key] = a
            chans = a.get("channels") or []
            if "ntfy" in chans:
                routed = a
                break
        if routed:
            break
        time.sleep(5)

    if not routed:
        print("no ntfy-routed alert fired within the budget (rules need a market event)")
        return 2

    print(f"FIRED: {routed.get('symbol')} {routed.get('kind')} [{routed.get('severity')}] "
          f"channels={routed.get('channels')}\n  {str(routed.get('message'))[:90]}")

    # give the sender a moment, then read the topic back
    time.sleep(4)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(f"https://ntfy.sh/{TOPIC}/json?poll=1", timeout=20) as resp:
                raw = resp.read().decode()      # F-07: the response is closed with the block
            msgs = [json.loads(l) for l in raw.splitlines() if l.strip() and json.loads(l).get("event") == "message"]
            if msgs:
                print(f"NTFY DELIVERED ({len(msgs)} message(s) on {TOPIC}):")
                for m in msgs[-4:]:
                    print(f"  · {m.get('title')} | prio={m.get('priority')} | {str(m.get('message'))[:70]}")
                return 0
            print(f"  attempt {attempt + 1}: nothing readable yet")
        except Exception as exc:
            print(f"  attempt {attempt + 1} failed: {exc}")
        time.sleep(5)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
