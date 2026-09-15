# Resume here — ModFlow OrderFlow Analysis Suite

One page for picking this up cold. The full trail lives in `docs/SESSION_HANDOFF.md`
(§24–§30 cover the terminal-mode build, the bus, the panels and the commit series);
`docs/DX_TERMINAL_AND_QUANTOWER_PLAN.md` is the phase plan with the decisions behind it.

## Where it stands

- **Branch `master`, HEAD `c41c450`** — the tree is committed and clean. It was stuck at `b2ff4ee` for the
  whole build; the seven commits are grouped by area (docs, desktop, data, atlas, tests, tooling, and the
  earlier-session work in `settings.py`/`dashboard`/`analytics`).
- **Nothing is pushed.** `origin` is `github.com/mahmoud20138/OrderFlow-Analysis-Pro` — the original
  project, not Moddy's. Putting this on his own GitHub is a remote/fork decision, one command when asked.
- Local identity is `ModdySwag <ModdySwag@users.noreply.github.com>` (repo-local, nothing global changed).

## Gates — run these before believing anything

```bash
unset PYTHONPATH
.venv/Scripts/python.exe -m pytest orderflow_system -q        # expect 483 passed / 2 skipped
.venv/Scripts/python.exe scripts/audit_ui_refs.py             # expect AUDIT CLEAN
node orderflow_system/desktop/ui/shell.selftest.js            # 22   (also: bus 12, links 10,
node orderflow_system/desktop/ui/bus.selftest.js              # 12    watchlist 15, news 17,
node orderflow_system/desktop/ui/options.selftest.js          # 21    options 21, fundamentals 18,
node orderflow_system/desktop/ui/watchlist.selftest.js        # 15    market-pressure 12)
node orderflow_system/desktop/ui/fundamentals.selftest.js     # 18
```

Live checks are done against a **sandbox**: `APPDATA="$LOCALAPPDATA/Temp/ofap_<name>_sandbox"
.venv/Scripts/python.exe -m orderflow_system.desktop --headless --port 809x` (ports 8090–8094 only, never
Moddy's own install), driven over CDP at `http://127.0.0.1:809x/desktop/`. Stop every process afterwards and
check `orderflow.log` for `client error:` lines.

## Open items

| What | Where |
|---|---|
| Watchlist: configured-instrument rows ("—" rows beside the demo list) — wired to the 2 s beat, not re-checked live. Recipe: add `ZZZTEST` to the config's instrument list, reload, expect a row. | handoff §27 |
| Bus chip's `sub` count disagrees with `telemetry().subscribers` (measured `1 sub · 2 ch` vs 3) — two counters, one mis-named. | handoff §29 |
| Fundamentals supply cell and the options gamma precision — both fixed, cosmetic residue noted. | handoff §25 |
| The frozen build (`dist/ModFlowOrderFlowAnalysisSuite/`) predates the last few fixes; rebuild with `scripts/build_exe.py` when it matters. | handoff §25 |

## Traps that cost time here (all measured, none theoretical)

- **A `<script>` tag with no file behind it takes the whole UI down** — the module loader replaces the
  shell with a "module error" banner. Land the file, then wire `index.html` and the audit. `test_wiring.py`
  now guards this.
- **Scope every panel's section lookup to `.view[data-view=…]`** — a bare `[data-view="x"]` matches the nav
  button first, and in terminal mode no nav button is ever `.active`, so the panel thinks it is off-screen
  and pauses. Guarded in `test_wiring.py`.
- **The bus coalesces requests that are still in flight** — a settled promise must leave the in-flight map,
  or its first answer stands in for that URL for the page's life (it froze every atlas panel once).
- **`requestAnimationFrame` may never fire in a headless page.** A repaint queued behind it never happens;
  paint directly. Same for `js()` probes: keep each under ~5 s or the CDP call times out.
- **A CDP `Enter` key event does not synthesise a focused button's click** — verify items by what the click
  produces.
- **`POST /api/control/config` patches** (`merge_config`) while `save_config` writes what it is given over
  the defaults — the layout delete path depends on the latter.
- **Terminal mode bypasses `ui.js showView`**, so legacy panels created lazily by `ensurePanel()` need the
  hand-off in `shell.js buildFrame`, and a closed widget's section must drop `.active` (`releaseFrame`).
