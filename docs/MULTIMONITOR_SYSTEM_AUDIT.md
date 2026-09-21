# Multi-monitor system audit — panels, windows and displays, both views (§128)

**Trigger.** Owner's directive (Desktop `monitor.txt`): a full system audit of the program's
multi-monitor capability — complete support for unpinning/moving panels of the TERMINAL view onto
any monitor or combination of monitors/displays, seamless and industry-standard for movement,
pinning, scaling and resizing, with creative, 100% functional solutions for BOTH "TERMINAL" and
"CLASSIC" views.
**Tree.** `C:\Users\Moddy\OrderFlow-Analysis-Pro` · HEAD `797eea0` · work landed uncommitted.
**Method.** Code read at every seam (file:line below), the pure placement/strand maths pinned in
`test_aux_windows.py`, and a live pass on a sandboxed launcher (scratch `APPDATA`, port 8094,
WebView2 remote-debugging on 9223, `EnumWindows` for OS-side truth) where every command was
performed the way a user performs it — clicks on the widget's ⧉ button, rows of the window menu,
the View menu's entry, the dialog's own buttons. This host has ONE display (2560×1440 @ 100%), so
"a second monitor" was exercised as placement maths under test for every screen shape plus a second
real OS window on the one screen; the physical multi-monitor pass remains the owner's.

---

## 0. Verdict in one paragraph

The capability the directive asks for now exists in both views, and the audit found the pieces
that did not actually work. A terminal widget carries its own window button (⧉) that offers every
monitor by name and every snap shape; an open window can be sent to another monitor or snapped
where it is, one click each, from the menu, from the Windows & layouts dialog, from the auxiliary
window's own bar, or by keyboard (Ctrl+Alt+Shift+←/→, Ctrl+Alt+W); any panel can be opened on any
monitor already placed, from a dialog row that works in Classic too (where there is no focused
widget to hang a menu from); positions persist, and a window whose monitor is gone — whether the
store knows it or only the live window does — is called out with a one-click rescue. Four real
defects were found on the way (one of them held the dialog shut completely), all fixed with pins
and live receipts.

---

## 1. Capability inventory (what already existed before this pass)

| Area | Piece | Where |
|---|---|---|
| Screens | `valid_screens`, `screen_label` ("Monitor 2 · 1920×1080 · 150%"), `place_aux` placement for a NEW window (explicit monitor wins, stored position wins while a screen contains it, unplugged falls back to primary, size clamps to the work area, cascade) | `desktop/windows.py` (§73) |
| Host | `WindowHost` seam; `NativeWindowHost` creates real pywebview windows at a resolved rect, persists geometry from the window's own moved/resized events, drops the record on close (either side) | `desktop/launcher.py` (§73, §94) |
| Store | `ui.windows` = the desired set (open adds, close removes, launch restores); clamps: ids, view slugs, 360…6000 × 300…4000, unique, cap 8 | `desktop/config_store.py` |
| Route | `GET/POST /api/control/windows` — state (screens labelled, open, the set, the cap) + `open / close / focus / ontop / reset / close_all`; `native: false` is a first-class answer | `desktop/api.py` |
| Menu | `OFAPWINDOWS.model()` → the widget-window menu (open, focus, pin, close, close-all, open-on-monitor rows), drawn in the terminal bar (Terminal) or the app top bar (Classic), plus the aux window's own bar (pin + close) | `desktop/ui/windows-ui.js` |
| Dialog | View ▸ Windows & layouts…: screens, every window in the set (open or not), Focus / Pin / Reset position / Close / Remove, Close-all | `desktop/ui/windowing.js` |
| Main window | geometry memory + per-screen layout `screen_key` (its size/origin/scale; the primary keeps the old key shape) | §72 (`launcher.pick_window_geometry`, `shell.js math.pickScreenLayout`) |
| Calibration | DPI refit on a live devicePixelRatio change (the "window moved to a 150% monitor" signal) | `desktop/ui/scale.js` (§72) |

## 2. Findings (all fixed in this pass, with receipts)

**F-1 — the View menu's "Windows & layouts…" was DEAD (high, user-visible).** `windowing.js` and
`windows-ui.js` both assigned `window.OFAPWINDOWS`; the later script (windows-ui.js, index.html
line 1432 vs 1424) won, and the menu item's `OFAPWINDOWS.open` was therefore `undefined` — the
dialog was unreachable. Proven live twice: clicking the item returned true and no overlay appeared;
`OFAPWINMGR.open()` by hand rendered it. Fixed by one global per module (dialog = `OFAPWINMGR`,
widget menu = `OFAPWINDOWS`), pinned in `test_windowing_ui.py::test_the_two_window_namespaces_do_not_collide`,
and re-proven through the real menu in **both** modes.

**F-2 — the unplug rescue could not see the very case it exists for (high).** `stranded()` read
the store's records only. Measured live: an aux window pushed to (9000, 40) kept a record that
still said (0, 0) (the store trails the window), so the app reported "nothing stranded" while a
window was off every screen. Fixed: `stranded(records, screens, live=...)` now takes the store AND
the live rects (`open_geometry`), pinned, and the live re-run shows `stranded: ["w42651ea"]`, the
dialog banner "1 window is on a monitor that is gone: w42651ea — Bring them home", and the click
bringing the real window back to (640, 0).

**F-3 — "send to the next monitor" moved a hand-placed window on a single-monitor machine
(medium, found by running it).** With one screen, `step=±1` resolves cyclically to the same screen
and the default `center` preset re-centred the window. Fixed at both layers: the UI's
`sendFocused()` does nothing when `screens.length < 2`, and the API answers a step-move with
nowhere to go as `ok · moved: "" · note: "already on that monitor"` (an explicit `preset` is still
honoured — pinned by `test_an_explicit_centre_still_centres_on_one_screen`). Live: geometry
identical before/after the real Ctrl+Alt+Shift+→ keystroke, and `OFAPKEYS.recent` shows the binding
fired.

**F-4 — an auxiliary window re-acquired a routing hash after §73 cleared it (low, cosmetic,
chased to the second writer).** The aux URL read `?aux=overview&win=…` **plus `#overview`**.
`ui.js`'s `showView` wrote it; the first guard there was not the whole story because the shell's own
`focusView` writes the hash too. Both writers now skip when `window.OFAPAUX` is set (shell.js sets
it from `?aux=`); live: the aux page's `location.hash` is `''` and the URL is clean.

**F-5 — a regression this pass introduced and its own live run caught (medium).** The dialog
rewrite gated every row button on `payload.view`; the consequence was that Bring them home, Focus,
Pin, Reset position, Close and Close-all did nothing at all. Caught by driving the dialog
(live: "clicked: True, stranded unchanged"), fixed, pinned
(`test_the_dialog_buttons_are_not_gated_on_a_view`), re-proven live (banner cleared, OS window
returned home; a per-row shape button moved the window to the left half).

Also closed while in the code: the auxiliary window's bar now says WHICH window it is
("window w9ef12e4 · focus: overview") and which monitor it is on, and the screen row in the dialog
no longer repeats a size its own label already carries.

## 3. What was built (§128 — the solution set)

- **Send and snap, one click each.** `windows.preset_rect` (pure) resolves 10 shapes — left/right/
  top/bottom halves, 4 corners, `fill` (the whole work area) and `center` (the window keeps its own
  size) — inside any screen's work area (height minus the taskbar strip). `windows.move_placement`
  decides the target screen: an explicit index, else `step` monitors from where the window is now
  (cyclic), else the screen containing its position, else the primary. `WindowHost.move` moves the
  real window; the store is written only when the host confirms (a refused move leaves everything
  where it was).
- **The widget's own door.** Every terminal widget frame's title bar carries **⧉** ("Window: send
  this widget to a monitor, snap it, or pin it"), which opens the window menu aimed at THAT widget,
  anchored to the button; when the widget already has a window the menu opens straight into its
  send/snap panel. `shell.js:478`, `windows-ui.js openFor():368`.
- **Any panel, any monitor, both modes.** The dialog's "Another panel, on any monitor" row (panel
  + monitor + shape pickers, built from the document's own view sections) opens any panel already
  placed — this is Classic mode's route, where there is no focused widget. Live: 34 panels,
  1 monitor, 10 shapes listed; TAPE opened at the left half.
- **Per-window controls.** The menu lists each open window with the monitor it is on, a ⇥ send
  panel (every monitor by name, "· here" on its own, then the shapes) and focus/pin/close; the
  dialog gives every row Send buttons and shape buttons plus Focus / Pin / Reset position / Close;
  the auxiliary window's own bar can move **itself** ("⇥ monitor").
- **The rescue.** Stranded windows (store or live) are flagged in the menu (⚠) and the dialog
  banner, with **Bring them home** (`action: "arrange"`) re-placing every one of them on the
  primary; `reset` remains the per-window version.
- **Keyboard.** `Ctrl+Alt+W` = the focused widget's window menu; `Ctrl+Alt+Shift+→ / ←` = send the
  focused panel's window to the next/previous monitor (opening it there when it has no window yet,
  a no-op when there is only one monitor). Both work in Classic too. `keys.js:337`.
- **State the UI can trust.** `/api/control/windows` now answers `open_geometry` (each open
  window's live rect, the screen index and the screen's label) and `stranded` (ids needing rescue).
- **Docs in-app.** Guide gained a "Multiple monitors" section; the help topic `work.windows` was
  rewritten around send/snap/rescue and the new keys (searchable by "snap window", "unpin",
  "move window").

## 4. Scenario matrix (the sweep the directive asks for)

| Scenario | Status |
|---|---|
| One monitor, any resolution/scale | ✅ works; a "send to next monitor" is an honest no-op (F-3) |
| Two+ monitors, different DPI/scale | ✅ placement per screen, work-area clamp, DPI refit on arrival (`scale.js`); physical cross-DPI pass = owner's |
| Monitor to the LEFT of the primary (negative origin) | ✅ pinned (`test_a_preset_on_a_monitor_left_of_the_primary_keeps_its_negative_origin`) |
| Mixed sizes (4K + 1080p + portrait) | ✅ every shape is computed from the target screen, not the primary |
| Different taskbar heights/positions per monitor | ✅ work area = screen height − 56 px chrome; label carries the scale |
| Small display (1024×640, 1366×768@150%) | ✅ presets floor at the window minimums then clamp inside the work area |
| Panel moved from the TERMINAL board to any monitor | ✅ ⧉ button, menu, hotkey, dialog row |
| Panel windows on MANY monitors at once ("any combination") | ✅ up to 8 windows, each independently placed/snapped/pinned; open set restored on launch |
| Unpin (always-on-top off) | ✅ pin/unpin per window: menu row, dialog row, the aux window's own bar |
| Move an OPEN window between monitors | ✅ `move` action moves the real window now; store follows |
| Window on a monitor that is gone (unplug while running or since) | ✅ detected from the store AND the live rect; Bring them home |
| Unplugged monitor at next launch | ✅ `place_aux` re-places on the primary and writes the resolved rect back |
| Layouts per screen | ✅ §72 (`screen_key` = size@scale@origin) |
| Literal tear-out drag from the board to another monitor | ❌ impossible inside WebView2 — no OS drag can be started from the page; the commands above are the deliverable form (stated in §73 and here) |
| Windows' own Win+Shift+Arrow | ✅ mirrored as Ctrl+Alt+Shift+Arrow (Alt, so the OS shortcut is not stolen) |

## 5. Receipts (live) and gates

Live, sandboxed launcher (scratch `APPDATA`, 8094, CDP 9223, `EnumWindows`):
`⧉ Windows` in the terminal bar; the widget ⧉ menu rows; open → real window at (730, 312)
1100×760 with the store's `open_geometry` identical; the aux bar "⧉ Overview · window w9ef12e4 ·
Monitor 1 · 2560x1440 · ⇥ monitor · 📍 pin · × Close" with exactly 1 frame and 1 active section;
`fill` → OS window (0, 0, 2560, 1384) and `left` → (0, 0, 1280, 1384) — the work-area maths and the
real window agreeing; dialog open from the View menu in Terminal AND Classic; TAPE opened at the
left half from the dialog; both hotkeys recorded in `OFAPKEYS.recent`; the stranded banner and
Bring them home moving the real window back to (640, 0); the single-monitor send key changing
nothing; WM_CLOSE on the main window sweeping every aux window (§94); **0 `client error:` lines**
in the sandbox log.

Gates: pytest **1740 passed / 3 skipped** (1696 → +44: `test_aux_windows.py` 31 → 69 collected,
`test_windowing_ui.py` 4 → 10) · same counts under CI semantics (`PYTHONUTF8=0`) · `scripts/audit_ui_refs.py`
**AUDIT CLEAN** (123 modules) · ruff clean · **40/40 node selftests** (`windows-ui.selftest.js`
10 → 16 checks) · goldens untouched.

## 6. Limits of this audit (state these with any claim)

- One physical display on this host. Cross-monitor moves, a second monitor's work area, an unplug
  while running and mixed-DPI migration were exercised as (a) pinned maths over every screen shape
  and (b) real OS windows on the one screen; the physical two-monitor pass is the owner's.
- `EnumWindows` geometry was used as the OS-side truth for every "the window really moved" claim;
  the API's `open_geometry` was cross-checked against it in every case (they agreed exactly).
- CDP key events drove the hotkeys (real key events, as the harness requires); menu/dialog clicks
  were page-level `element.click()` on the visible panels (a first attempt hit a hidden menu panel
  — a probe artifact, recorded here so the next pass does not repeat it).
- Everything in this pass is on disk uncommitted; **nothing committed, nothing pushed**.
