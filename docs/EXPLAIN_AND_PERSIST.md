# §83 — "explain it in the UI" and "why did I have to re-enter my keys?"

Owner's directive (one message, four asks — verbatim):

> *"could you build in a pop up window / hover over message or similar explaining this to the user if the right
> "click" conditions are made and pointers to how to fix/enable this funtionality. also ammend the help guide to
> reflect changes. also add any other menu options wherever they are needed to make this scenario easy to navigate
> and assist the user. one more thing the user reports "And how do i make sure my Alpaca api keys save i had to re
> enter when i restared it" so i think we need a sweep to ensure all relevant user cahnges inputs and any other
> relevany conditions where user input needs to be saved is saved and there is no "reinputting" of details config
> changesa etc necessary"*

So: (1) the app explains itself where the user is standing, (2) the help guide says the same thing, (3) the menus
lead there, and (4) **a sweep** of every user input for the "I had to type it again" class.

---

## 1. The reported bug: Alpaca keys did not survive a restart

**Root cause (found by reading every write path, then measured).** The Alpaca view's *Validate & save* button calls
`POST /api/control/alpaca/test` with `save:true`. That handler built `cfg = _alpaca_cfg()` — the **alpaca block**,
not the config — and then called `config_store.save_config(cfg)`. `save_config` merges its argument **over the
factory defaults**, so the write produced a config whose every other key was default and whose `key_id` / `secret` /
`paper` landed at the **top level** of the file, leaving `alpaca` itself empty. Consequences, both real:

* the key pair was not where the loader looks → next launch: "not configured" → **re-enter the keys** (the report);
* every other setting the user had — instruments, layouts, watchlist, thresholds, view prefs — silently reverted
  to defaults at the same moment.

**Fixes.**

| # | Change | Where |
|---|--------|-------|
| 1 | `alpaca_test(save=True)` now loads the whole config, updates the block, saves the whole config (no stray top-level keys) | `desktop/api.py` |
| 2 | `engine/start` / `engine/restart` with a body **merge** instead of replace (a partial body can no longer reset the rest) | `desktop/api.py` |
| 3 | Settings' collect/save reads the **on-disk** config before patching — a save built on a stale page copy rolled back anything written since boot | `ui/ui.js` |
| 4 | Alpaca's feed selector posts the one-field patch (`{alpaca:{feed}}`), not the page's whole config | `ui/alpaca-card.js` |
| 5 | **Dead control fixed:** the Settings *route order-flow alerts to Telegram* switch was read by nothing (the engine honours `telegram.enabled`), so the master switch could not be switched on from the UI and never saved. It is now restored and collected | `ui/ui.js` |
| 6 | View state the user sets by hand is persisted: `ui.chart {range, markers, vp}`, `ui.logs {auto, level}` — defaults + sanitiser clamps + saved on change + restored at boot | `config_store.py`, `ui/ui.js` |
| 7 | **Guard test for the whole class:** a static scan fails if any `save_config(X)` in the desktop package is handed a *block* rather than the whole config | `test_settings_persistence.py` |

**Live receipts (headless sandbox on 8099, scratch APPDATA, real restart in the middle).**

* key save → **process restart** → `GET /alpaca/status` → `configured: true`, `key_masked: "PK83…E2"`, secret present;
  a marker key, `data_source: bybit` and 51 instruments all intact; **no stray top-level keys**.
* a one-field patch (`{"alpaca":{"feed":"sip"}}`) left everything else intact (marker, source, instruments).
* re-saving the key id alone (`{"key_id": ...}`) kept the stored secret — an empty field never erases a stored one.
* `ui.chart` / `ui.logs` appear with defaults in a fresh config and survive the restart.

---

## 2. The app explains itself where the user stands

**New module: `ui/hint.js` (+ `hint.selftest.js`, 7 checks).** One popover for the whole app: **hover** shows it,
**right-click pins it**, and the card carries real buttons from a closed action set
(`lookup · engine · instruments · wizard · menu`). Hints declared in markup live in `data-hint-*` attributes and
are **re-read at show-time**, so a hint whose text the app updates (the Engine chip) always explains the *current*
state. `skippedNotice()` / `paintNotice()` turn an engine skip report into a banner that carries the button.

Where it is wired:

* **Engine view** — the symbol chip's card is the live verdict. Measured in the browser, on the exchange feed with
  `NQ1!` typed: *"⚠ not on this source | NQ1! → NAS100USDT — Bybit perps list crypto only — switch to MT5 (Windows)
  for this instrument · switch the data source to MetaTrader 5 for indices, metals and FX (☰ ▸ sources, or the setup
  assistant) and map the broker symbol | Open the instrument look-up | Open Instruments"*. Right-clicking the chip
  pins the same card; the `find` box explains what the box accepts.
* **Top-bar pills** — source, data state (live/warming/demo) and the engine each explain themselves, with the way out
  (data-sources menu, instrument look-up, Instruments).
* **Instruments view** — a **Look up an instrument…** button in the header, and **right-click any row** for the same
  verdict from the look-up endpoint without leaving the table. Measured on the `NAS100USDT` row of a 51-row table:
  *"NAS100USDT — unsupported | Bybit perps list crypto only — switch to MT5 (Windows) for this instrument · switch the
  data source to MetaTrader 5 … and map the broker symbol | Open the instrument look-up | Open Instruments"*.
* **The engine's skip banner** — was a sentence, now a sentence **and** the button. Measured:
  *"NAS100USDT: Bybit perps list crypto only — switch to MT5 (Windows) for this instrument (+3 more) | Open the
  instrument look-up"* → clicking it opened the Engine view with the look-up panel showing that same verdict.
* **Menus** — Data ▸ **Instrument look-up…** (measured: navigates to the Engine view and opens the panel), and a
  command-palette entry *"Instrument look-up — why won't my symbol stream?"* whose keywords include `crypto only`,
  `nq`, `broker symbol`, `mt5`.

**Pins:** `test_hint_ui.py` (module parses, selftest ≥ 7, the closed action vocabulary, the shell ships the module
and declares the hints, the audit registers it, the skip banner carries the button, the start path announces skips).

---

## 3. Help guide amendments

| Topic | What it now says |
|-------|------------------|
| `start.sources` | *An exchange feed is crypto-only — by nature*: no keyless venue carries indices/FX/metals/CFDs; NQ1!/US100 need MT5; US equities need Alpaca; the look-up turns the refusal into the next step |
| `connect.mt5_map` | broker names are **case-sensitive** and differ per broker; the look-up offers your broker's spelling and **Add & restart** writes it |
| `view.instruments` | summary + a three-step *Look a name up before you tick it* block + the look-up action |
| `view.alpaca` | *Your keys stay saved — nothing to re-enter*: masked key id after restart, empty fields change nothing, **Test saved keys** needs no typing, saving keeps every other setting, **Remove stored keys** is the only wipe |
| `fix.no_data` | new row: *the market itself needs another source* — type it into the symbol box, press **find** |
| `fix.skipped_symbols` | a start that skips something now **says so** with a button; the look-up answers the name you typed |
| `view.settings` | the Telegram master switch is stored with the token/chat, and the pill says when it is off |

`test_help.py` still passes (30 checks).

---

## 4. Gates at the end of this pass

* pytest **962 passed / 2 skipped** (944 → 962; new pins: `test_settings_persistence.py` 10, `test_hint_ui.py` 8; the 2 skips are the opt-in live Alpaca tests, unchanged).
* AUDIT CLEAN — no broken calls or dead element references (**82 JS modules** parse, `hint.js` registered).
* ruff clean (run via `uvx ruff check`; the venv has no ruff module).
* goldens OK (config 31 factories / 18 crypto majors / 49 instruments; analytics `0.000e+00`, 40 cases).
* Node selftests: **25** modules (24 `*.selftest.js` + `search-ops` which prints its own wording), incl. the new
  `hint.selftest.js` (7 checks).
* OpenAPI unchanged: **140 operations**.

## 5. Owed (not in this pass)

* `dist/` · zip · SBOM · the installer are **not rebuilt** — the payload changed again, so the next packaging pass
  rebuilds and re-runs payload parity + the installer journey.
* README/CONTRIBUTING counts re-derivation (pytest total moved; new files added).
* Nothing committed — HEAD is still `110c568`.
