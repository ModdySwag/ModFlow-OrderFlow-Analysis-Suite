# Resume here — ModFlow OrderFlow Analysis Suite

One page for picking this up cold. The full trail lives in `docs/SESSION_HANDOFF.md`
(§24–§38 cover the terminal-mode build, the bus, the panels, the commit series, the P0 trust pass, the
theme/token layer, the cursor spine, selection-as-measurement, the strips' keys, the feedback cosmetics
and the map's duration answer); `docs/DX_TERMINAL_AND_QUANTOWER_PLAN.md` is the phase plan with the
decisions behind it, and `docs/UPGRADE_ACTION_PLAN.md` is the prioritised plan of action — from
`report1.txt`, corrected against the tree. **P0 (§32) and P1-1 through P1-6 (§33–§38) are done; the next
work item is P1-7, alerts that manage, scope and read like sentences.**

## Where it stands

- **Branch `master`, HEAD = the `docs:` commit that closes P1-6** (top of the branch, tree clean,
  nothing pushed; `git log -1` names it). Recent work, by area: the four P0 fixes (`443008d` desktop,
  `7a81bf6` the cursor-trace contract, `65672f2` book integrity, `d83e7a0` broadcast queues), then the
  theme layer — the token block + `themes/` + `theme.js` + the Appearance card.
- **Nothing is pushed.** `origin` is `github.com/mahmoud20138/OrderFlow-Analysis-Pro` — the original
  project, not Moddy's. Putting this on his own GitHub is a remote/fork decision, one command when asked.
- Local identity is `ModdySwag <ModdySwag@users.noreply.github.com>` (repo-local, nothing global changed).

## Gates — run these before believing anything

```bash
unset PYTHONPATH
.venv/Scripts/python.exe -m pytest orderflow_system -q        # expect 508 passed / 2 skipped
.venv/Scripts/python.exe scripts/audit_ui_refs.py             # expect AUDIT CLEAN
node orderflow_system/desktop/ui/shell.selftest.js            # 22   (also: bus 13, links 10,
node orderflow_system/desktop/ui/bus.selftest.js              # 13    watchlist 17, news 17,
node orderflow_system/desktop/ui/options.selftest.js          # 21    options 21, fundamentals 18,
node orderflow_system/desktop/ui/watchlist.selftest.js        # 17    market-pressure 12, ofx 119)
node orderflow_system/desktop/ui/fundamentals.selftest.js     # 18
```

Live checks are done against a **sandbox**: `APPDATA="$LOCALAPPDATA/Temp/ofap_<name>_sandbox"
.venv/Scripts/python.exe -m orderflow_system.desktop --headless --port 809x` (ports 8090–8094 only, never
Moddy's own install), driven over CDP at `http://127.0.0.1:809x/desktop/`. Stop every process afterwards and
check `orderflow.log` for `client error:` lines.

## Open items

| What | Where |
|---|---|
| The upgrade plan's **P1** work: P1-1 through P1-6 are done (tokens, the cursor spine, selection as measurement, the strips' keys, the feedback cosmetics, the map's duration answer) — continue with P1-7 (alerts: manage, scope, read like sentences), then P1-8 to P1-10. | plan §2, handoff §38 |
| Three `window.prompt` sites left in the frozen shell's path: the drawing text tool (`drawings.js:365,417`) and the workspace-name prompt (`menubar.js:557`). Both need in-place affordances; a prompt that does not render reads as a dead button. | handoff §38 |
| A live level held ≥ 2 min: caught by a 20 s poller (the engine's `wall_age` event at 76800.0, "held 2.4 min") — but the events list keeps only the last 120, so such an event is gone within ~2 min, and the Held column covers the 12 heaviest walls only. | handoff §38 |
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
