# Display, multi-monitor and window-architecture audit — v0.1b

**Trigger:** owner's question — will the app support every monitor/display scenario, can widget
stacks be dragged across monitors, and what needs adjusting for full break-apart windows/widgets
(resize · drag · move · monitor swap · pinning).
**Tree:** `C:\Users\Moddy\OrderFlow-Analysis-Pro` · HEAD `fa202d6`, nothing committed or changed in
this pass — this is an audit with actionables.
**Method:** code read + a live probe matrix driven over CDP against a sandboxed server
(`APPDATA=$LOCALAPPDATA/Temp/ofap_display_sandbox`, port 8092): 16 viewport/DPI scenarios, real
reloads, canvas-geometry measurements, DPR changes without reload, and widget drag/resize through
the shell's own handlers. This host has one display (2560×1440 @ 96 dpi / 100%), so physical
multi-monitor moves and mixed-DPI window migration were **simulated** (viewport + devicePixelRatio)
and cross-checked against the code that consumes those signals — limits are stated in §5.

---

## 0. Verdict in one paragraph

The board layer is genuinely multi-monitor-capable in the ways that matter *inside* the window: a
ten-widget layout built on a 5120-px span re-opens on a 1024-px display with every widget intact,
drag and resize work and clamp identically at 1024, 1920 and 5120 px, no scenario produced a single
JS error, the page never overflows, and the DPI-refit machinery (`scale.js`) correctly detects a
live devicePixelRatio change (i.e. the window arriving on a differently-scaled monitor). What is
**not** there yet: the window itself has no memory (fixed 1500×940, min 1080×680, no position, no
monitor choice, no restore-after-unplug), layouts carry a `screen_key` that nothing auto-applies on
boot, widgets cannot leave the window (no detach/second window/pinning anywhere), and — the one
outright defect class — several chart canvases are not DPI-correct: the **Engine view paints at 1×
on every scaled display (blurry)**, and the CVD view's Market Pressure canvas **inflates by ×dpr on
every fit pass** (measured 480×285 → 720×428 in one pass, growing).

---

## 1. What already works (measured, not assumed)

| # | Scenario | Evidence |
|---|---|---|
| W1 | 16 viewport/DPI scenarios (4K@100/200, 1440p@100/125/150, 1080p@100/125/150, 1366×768@100/125, 720p, 1024×640, 3440×1440 ultrawide, 1440×2560 portrait, 5120×1440 dual-span, 1920×700) | No page overflow anywhere; rail/top/status bars always inside the viewport; terminal grid renders at all sizes; grid scrolls only at 1024×640 (`sh=504 > ch=442`) as designed; `ui-compact` engages below 760 px height; **0 JS errors in all 16** |
| W2 | Widget move + resize through the real handlers at 1024×640, 1920×1080, 5120×1440 | move `+3 cols/+1 row` → `x=3,y=1`; grip `+2 cols` → `w=8`; a hard-right drag on an edge widget clamps unchanged; gesture ends cleanly (`gesture: ''`), 0 errors |
| W3 | Dense board built at 5120×1440 (10 widgets) re-opened at 1024×640 | All 10 widgets and frames intact, no overflow, board scrolls — a layout made on a big monitor is usable on a small one |
| W4 | Live DPR change with no reload (the "window moved to a 150% monitor" signal) | `scale.js` detects it (`reason: resize-observer`, state dpr → 1.5) and refits what it owns (draw-layer canvas crisp); chart, heatmap, orderflow/atlas canvases are DPI-correct at 150% |
| W5 | Layout persistence | Drags/saves land in the store (`config.json → layouts`), per-layout `screen_key` is written, the Layout menu labels rows "this screen"/"saved on WxH@dpr", export/import + reset + auto-arrange all exist; auto-save on gesture end |
| W6 | Session hygiene | 0 `client error:` lines in the app log across every scenario above |

---

## 2. Defects found (with receipts)

### D1 — The Engine view renders at 1× on scaled displays (blur) — **High, user-visible today**
`desktop/ui/ofx.js` `resize()` sets `c.width = width; c.height = height` (CSS px) and the file
contains **zero** `devicePixelRatio` references (`ofx.js`, `ofx-view.js`). Measured at 150%:
`ofxBase/ofxHeat/ofxLive` css 1406×624 vs correct backing 2109×936; `ofxSpark` 305×68 vs 458×102.
Every Windows display at 125/150/200% scaling (the default on most laptops) shows a soft heatmap;
the engine is the app's flagship view. At 100% it looks correct — which is why it was never seen.
*Contrast: `atlas.js:28`, `drawings.js:672`, `heatmap-pro.js:152`, `market-pressure.js:100` all
multiply by dpr — those panels are crisp.*

### D2 — CVD view's Market Pressure canvas inflates by ×dpr on every pass — **High**
`market-pressure.js` renders `<canvas id="mpCanvas" height="190">` and `mpDraw()` sets
`el.width = cssW*dpr; el.height = 190*dpr` — but **never sets a CSS size on the canvas**, and a
canvas without CSS size displays at its backing size. So the box follows the backing, and the
generic fit pass (`scale.js fitView`) then sizes the backing from that box again. Measured at 150%:
`480×285 → (one OFAPScale.fit) → 720×428` — and every later draw multiplies again (×1.5 per pass).
The card grows without bound and the chart geometry inside it is wrong on any scaled display.

### D3 — Engine ribbon backing ≠ its CSS box (stretch) — **Medium**
`.ofx-ribbon { width:100%; height:84px }` while `OFX.resize()` sets the ribbon canvas to the
*stage* width (`r.width = width`, `r.height = 84`). Measured: css 1652×82 vs backing 1406×84 in a
terminal widget, and css 1754×82 vs backing 1508×84 at 4K full-window. The volume/delta lanes are
horizontally stretched (and vertically off by the 2 px border) whenever panel width ≠ stage width
— i.e. in every terminal widget and in any layout with a readout column. Carries D1's 1× as well.

### D4 — Only the *focused* view's canvases are generically refit; the fitter registry is unused — **Medium**
`scale.js fitView()` walks `.view.active` only, and `OFAPScale.register()` (the per-panel fitter
hook) has **zero callers** in the codebase. In terminal mode only the focused widget carries
`.active`, so any panel that paints a canvas and does *not* listen to `ofap:relayout`
(atlas, heatmap-pro, ofx-view, strips and menubar do listen; **market-pressure and drawings do
not**) can keep a stale backing store after a window/DPI change until its own next data repaint.

### D5 — The window has no memory, no placement, no per-screen restore — **High for multi-monitor use**
`launcher.py` creates one window at fixed 1500×940 with `min_size=(1080, 680)`, no `x/y/screen`,
no persistence (the config `ui` block holds theme/accent/density only — verified). Consequences:
(a) the window always opens on the primary monitor, same size; (b) on a 1024×640 or
1366×768@150% work area (effective ≈911×512) the window cannot fit at all — WinForms applies
`MinimumSize` regardless, so content sits off-screen (code-reasoned; marked §5); (c) after a
monitor is unplugged there is nothing to re-validate against — the OS may leave the window
off-screen; (d) layouts are tagged `screen_key` but **nothing applies a layout by screen at boot**
(shell `boot()` trusts the store's `active` id only); and `screen_key` = `WxH@dpr`, which is
identical for two identical monitors.

### D6 — No break-apart: no second window, no detach, no pinning — **Missing feature, by design so far**
Widgets live only inside the one pywebview window; there is no `window.open`, no aux-window
concept, no always-on-top, no widget pinning, no "send to monitor". The pieces that make this
cheap to add are already in place: the server is HTTP on loopback (a second window is just another
client), the WS manager handles many clients, layouts are server-side, and **pywebview 6.2.1 ships
everything needed** — `create_window(x=, y=, screen=, on_top=, resizable=, minimizable=)` and
`Window.move/resize/maximize/restore/on_top/events`, plus `webview.screens` (measured on this host:
`[2560x1440 at 0,0, scale 1.0, dpi 96]`).

**Deliberate behaviour that is not a defect** (checked, documented): overlapping widgets are
allowed by design (z-order, like a desktop); a drag beyond the grid clamps to it by construction;
external links open in the system browser, not in-app; the grid is a fixed 12×8 regardless of
viewport (cells scale with the window).

---

## 3. Scenario matrix (the sweep the owner asked for)

| Scenario | Result | Notes |
|---|---|---|
| Single monitor, all common resolutions/scales | ✅ | 16-size matrix above |
| Two monitors, same DPI, window maximised across the span (5120×1440) | ✅ | grid 4864 wide, all widgets fill; cells very large (see A-C4) |
| Two monitors, different DPI (window moved 100% → 150%) | ⚠️ | refit fires correctly; **Engine + Market Pressure + ribbon wrong (D1–D3)** |
| Laptop panel only, 125/150% scaling | ⚠️ | same as above |
| Small display (1024×640 work area) | ⚠️ | the *page* handles it (compact, grid scrolls, no overflow) but the **window cannot fit** (min 1080×680, D5) |
| Portrait/rotated monitor | ✅ | 1440×2560 renders; compact off; grid fills |
| Ultrawide (3440×1440) | ✅ | no overflow; grid fills width |
| Layout made on a big display, opened on a small one | ✅ | W3 |
| Window resize while widgets are placed | ✅ | canvases that listen refit; others stale (D4) |
| Drag/resize/auto-arrange/tabs/export/import | ✅ | W2, W5 |
| Monitor unplugged / RDP reconnect / virtual display change | ❓ | not testable here; D5 lacks the re-validation hook to handle it well |
| Mixed content across monitors (widgets on A, chart on B) | ❌ | impossible today — one window only (D6) |
| Always-on-top / pinned window while trading | ❌ | not present (D6) |

---

## 4. Actionables, in the order they should land

**P0 — display correctness (safe, small, pinned; do first, nothing else depends on it)**
1. **A1 · Engine DPI**: size the ofx layers × dpr and scale the paint transforms (or equivalent),
   refit on relayout. Reduces to today's exact numbers at dpr = 1 (that is the regression pin).
   Files: `ui/ofx.js` (resize + painters), `ui/ofx-view.js`. Risk: medium (paint paths) — the
   existing `ofx.selftest` (178 checks) plus a new geometry case + a live 1×/1.25/1.5/2 probe.
2. **A2 · mpCanvas**: give the canvas a CSS box (`style.height=190px; width:100%`), size the
   backing from clientWidth×dpr, listen to `ofap:relayout`. Add a pin that `OFAPScale.fit()` never
   changes any canvas's *client* box (kills the whole self-referential class).
3. **A3 · Ribbon**: size from its own client box × dpr instead of the stage width.
4. **A4 · Generic refit scope**: refit every placed widget frame's canvases (not just `.view.active`)
   — one loop in `scale.js` — and either remove the unused `OFAPScale.register` hook or start using
   it (market-pressure, drawings first). Acceptance: post-change probe shows
   `backing == round(client × dpr)` for every visible canvas at 1 / 1.25 / 1.5 / 2.

**P1 — window memory & per-monitor fit (small-to-medium; unlocks real multi-monitor work)**
5. **B1 · Window geometry**: new `ui.window` config block `{w,h,x,y,monitor, maximised}` + launcher
   applies at boot, clamps to the target screen's work area, falls back to the primary when the
   stored monitor is absent, and stores what it used (no silent lying). `min_size` adapts:
   `min(1080, workarea_w)` × `min(680, workarea_h)` so 1366×768@150% and 1024×640 finally fit.
   `webview.screens` provides x/y/w/h/scale/dpi (verified available).
6. **B2 · Per-screen layouts**: expose the screens list in `/api/control/bootstrap`; boot picks the
   layout whose `screen_key` matches the current screen (falling back to `active`); upgrade
   `screen_key` to a real identity (e.g. `DISPLAY1 2560x1440@1`) with backward compatibility for
   existing keys. UI already labels rows "this screen" — the missing piece is the auto-apply.
7. **B3 · Always-on-top toggle** (window-level, persisted): `on_top` on the pywebview window + a
   View-menu toggle. Trader-useful, one line of API each side.

**P2 — break apart (the build; phased, each phase shippable)**
8. **C1 · Widget windows**: (a) an aux-window URL contract (`/desktop#<view>?aux=1` = single-widget
   shell), (b) a “Detach panel” command (widget menu + panel menu) that opens a pywebview window on
   the pointer's monitor, always-on-top optional; (c) a `windows` list in the layouts store
   `{view, screen, x, y, w, h, on_top}` restored at boot; (d) “Dock back” returns the widget to the
   board. This is what makes "one widget stack per monitor, coordinated by one layout" real.
9. **C2 · Send to monitor / pinning**: a “Send to monitor ▸” submenu (per widget and per window) is
   the workable form of “drag a widget across monitors” — **WebView2 cannot start an OS-level window
   drag from inside the page**, so literal tear-out dragging is a platform limit; the menu + aux
   windows deliver the same outcome. Pin-to-front per widget (z-order + stored flag) and
   pin-to-monitor (window↔screen binding in the store) land with it.
10. **C3 · Scale-aware board (optional)**: allow the grid to grow columns above ~3500 px board width
    (e.g. 16 or 20 cols) so dual-span boards do not get giant cells; store a per-layout `grid` hint
    with a migration for existing layouts (w ≤ 12 stays valid).

**P3 — documentation**
11. Add a "Multiple monitors" section to the Guide/README once B1/B2 ship (today neither mentions
    monitors at all), including the honest note that detaching is a command, not a drag.

---

## 5. Limits of this audit (state these with any claim)

- One physical display on this host (2560×1440 @ 100%). Everything DPI/size-related was **simulated**
  via CDP viewport + deviceScaleFactor, which exercises the same code paths (`devicePixelRatio`,
  resize events) but not the OS window manager. Window placement, minimum-size behaviour on tiny
  work areas, unplug/RDP re-validation and actual cross-monitor drags need a **physical multi-monitor
  pass by the owner** after B1/B2 (I could not observe a real second monitor).
- The harness's raw CDP input injection did not reach the page, so the drag/resize tests ran through
  **synthetic PointerEvents** dispatched at the shell's own handlers (same code path a real mouse
  hits; `pointerdown`/`pointermove`/`pointerup`), not via OS-level mouse.
- Screenshots of the visual result were measured geometrically (backing vs box), not eyeballed at
  pixel level; the ofx blur is a resolution ratio (1× vs 1.5×), which is deterministic.
- Everything in this file is read-only: **no source was changed**; gates remain 649/2, and the
  working tree holds only the §70 files already reported.

---

*Files of record for the follow-up: `desktop/ui/scale.js` (refit authority), `desktop/ui/ofx.js` +
`ofx-view.js` (engine canvases), `desktop/ui/market-pressure.js` (mpCanvas), `desktop/ui/shell.js`
(screen_key, layouts, grid maths), `desktop/config_store.py` (layout sanitiser, new `ui.window`
block), `desktop/launcher.py` (window creation), `desktop/api.py` (`/layouts`, bootstrap screens).*

---

## Resolution — §72 (landed)

Everything below was fixed in §72 with pins and live receipts; nothing in this file's measurements
was undone. **A1** `ofx.js` now carries the display scale: `math.layerSize(cssW, cssH, dpr)` is the
single place the backing-store maths lives, `resize()` sizes each layer from its own CSS box, and
`resetLayer(ctx, canvas, dpr)` clears at 1:1 then paints in CSS pixels — so every painter's maths
stays in the logical space it was written for. **A2** `mpCanvas` has a real CSS box
(`width:100%; height:190px`) and repaints from `PRESSURE.lastSeries` on `ofap:relayout`.
**A3** `ofxRibbon`'s box is now the stage width (`r.style.width = stageW + 'px'`) — the legend's own
contract, "volume, delta, CVD on the same X as the bars", was unreachable while CSS `width:100%`
stretched a stage-wide backing store by ~17%. **A4** `fitView()` walks every visible canvas in the
document instead of `.view.active`, so a non-focused terminal widget is refitted too; `drawings.js`
and `market-pressure.js` now listen to `ofap:relayout`.

**P1 items 5/6 also landed:** the window remembers its geometry (`ui.window` in the config store,
`launcher.pick_window_geometry` as a pure, unit-tested choice — a stored position wins while a
screen still contains it, the size and minimum clamp to the chosen screen's work area, and a
position off every desktop falls back to the primary), and `screen_key` is finally *applied*: the
key now carries the screen's origin (`800x600@1.5`, `2560x1440@1@2560,0`) so two identical monitors
are two screens, while the primary keeps the old shape and layouts saved for it still match.

**Not landed (still open):** B3 (always-on-top toggle), P2 (detached widget windows /
send-to-monitor / pinning — pywebview has the APIs; this is a feature build), and the physical
multi-monitor pass, which only the owner can run: this host has one display.

> **§73 update — P2 landed.** Auxiliary windows are built: one widget per native window, placed on a
> monitor of your choosing, pinnable (always-on-top), persisted and restored on the next launch. B3
> (the always-on-top toggle) is the aux window's pin button. The only part of the original P2 plan
> that stays closed is literal drag-out: WebView2 cannot start an OS window drag from inside the
> page, so the command form (Windows ▸ Open / Send to monitor ▸) is what shipped. Details and
> receipts: `docs/SESSION_HANDOFF.md` §73.

**Receipts (§72).** Suite 649 → **679 passed / 2 skipped**; AUDIT CLEAN; ruff clean; both goldens
byte-identical; 20 selftests green (ofx 183, shell 30). Live, at 1440×900 / 150% with a scratch
config: engine layers `1086×520` box → `1629×780` backing (= box × dpr, exactly), ribbon box 1084 →
backing 1626 × 123 with `style.width = 1086px` (stage width, no stretch), `mpCanvas` backing
`1956×285` for a `1304×190` box and **unchanged across three consecutive fit passes** (the old
behaviour was 480×285 → 720×428 → 1080×642), every visible canvas in a 4-widget terminal board
box × dpr with zero mismatches, a synthetic heat frame painted at 200% with no error, boot adopted
the layout saved for this screen and announced it, and the session logged **0 client errors**.
