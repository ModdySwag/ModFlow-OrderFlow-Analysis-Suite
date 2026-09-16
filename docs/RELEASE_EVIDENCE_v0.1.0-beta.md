# Release evidence — v0.1.0-beta

One page of receipts for the release review (auditor / owner). Everything here was **re-measured on
2026-09-17**, on the **third same-day rebuild**: the §79 Help Centre close-out build, the MT5-fix
rebuild (bridge excluded), and now the **MT5-ships pass** — the owner's call, implemented and
verified against a **real MetaTrader 5 terminal**: numpy and the MetaTrader5 bridge are **bundled**
in the portable build again, and the "run from source" messaging is gone. The MT5-fix rebuild this
supersedes kept the Help Centre intact; the §78 release-assurance audit
(`docs/FINAL_RELEASE_ASSURANCE_AUDIT_v0.1.0-beta.md`) remains the reference for the packaged-UI
defect fix it landed; §77's send-back judgement (`docs/AUDIT_SENDBACK_RESPONSE_v0.1b.md`) is
unchanged.

## Artefacts (release candidates — rebuilt 2026-09-17, MT5-ships pass)

| Artefact | Bytes | sha256 (first 16) |
|---|---|---|
| `dist/ModFlowOrderFlowAnalysisSuite/ModFlowOrderFlowAnalysisSuite.exe` | 15,020,151 | `d6287ef292c281d5…` |
| `dist/ModFlowOrderFlowAnalysisSuite-win64.zip` | 39,884,552 | `2dc1817d20c62947…` |
| `dist/ModFlowOrderFlowAnalysisSuite-Setup-0.1.0.exe` | 40,826,742 | `1a1a9f49d59fe9cb…` |
| `dist/ModFlowOrderFlowAnalysisSuite-win64.sbom.cdx.json` | 448,822 | `28811a2dd41a66ef…` |

Full hashes:

```
d6287ef292c281d59c60c898b7c761d83747b5c97c13145cd9b5ce9930ca9478  ModFlowOrderFlowAnalysisSuite.exe
2dc1817d20c62947327c39d90b24c781426aa8a9c2846b8a7b7c49fb40fa1144  ModFlowOrderFlowAnalysisSuite-win64.zip
1a1a9f49d59fe9cb9ab0965c0f3ecf493d0531abf46771684faae9a2c31e62dc  ModFlowOrderFlowAnalysisSuite-Setup-0.1.0.exe
28811a2dd41a66efdc76f7454060e69cc8cf6d19fba81769dda63b5ef9773a87  ModFlowOrderFlowAnalysisSuite-win64.sbom.cdx.json
```

Provenance: **rebuilt from the current tree** (exe → zip → Setup, all from the same frozen folder).
The zip grew to **565 entries** (525 before): numpy (+27 MB payload, the MT5 bridge's dependency) and
a new test module. The **SBOM was regenerated** — it was a base-only lockfile export and therefore
never listed the `mt5` extra; it now covers what the build actually ships
(`uv export --frozen --format cyclonedx1.5 --extra mt5`; 45 components, including
`metatrader5 5.0.6180` and `numpy` 2.4.6/2.5.3 for the 3.11/3.12 forks), and the same
`--extra mt5` was added to the CI dependency-audit and SBOM steps (`.github/workflows/ci.yml`).

Checked: **no source file newer than the build**; the loose-file payload check is **120/120
byte-identical** (covering `desktop/ui`, `dashboard/static` *and* the Bookmap add-on); the zip
`namelist()` is 565 entries and `testzip()` reports OK; the served `/desktop` is byte-identical to
**both** the packaged and the tree `index.html` (`eceebf07bab273b3…`) and carries the CSP; the
frozen `_internal` now **holds numpy and the MetaTrader5 bridge** (asserted by the smoke battery).
Dist raw: 565 files / 83,423,024 bytes (79.6 MB) → 39,884,552 bytes (38.0 MB) zipped.

## Gates (this pass, on the current content)

- pytest **881 passed / 2 skipped** — Python 3.12 (25.6 s) **and** 3.11 (26.9 s; the parity venv
  carries the `mt5` extra so the two MT5-import pins run there too).
- `scripts/audit_ui_refs.py` — **AUDIT CLEAN**: 78 modules parse, 123 routes discovered,
  275 HTML ids + 256 created, 0 missing, 0 duplicate ids.
- `ruff check orderflow_system scripts` — clean (ruff 0.16.7, the CI pin).
- Analytics golden **0.000e+00** (40 cases, 2,196 numeric leaves); config golden **31/18/49**;
  **23/23 UI selftests** (help-search's 26 checks included).
- `pip-audit` over the lockfile **including the `mt5` extra** — **no known vulnerabilities**
  (135 requirement lines; metatrader5 + both numpy forks covered); `uv lock --check` consistent;
  bandit / CI / lockfile posture unchanged from §78 (the single High is the non-security SHA1
  mutex digest; disposition in the audit doc §F-08).

## Security boundary (observed live on the rebuilt exe — §79 battery, 31/31)

Hostile `Host` header → **403**; cross-origin POST → **403**; `Sec-Fetch-Site: cross-site` POST →
**403**; loopback POST → **200**; native WS handshake + ping/pong; cross-origin WS refused (403);
`/desktop` byte-identical to the packaged **and** the tree `index.html`, CSP present; unknown
symbols → **`[]`** (candles + markers); `/api/control/sources` advertises binance / hyperliquid /
okx; **0 `client error:` / 0 ERROR / 0 Traceback** in the sandbox log; the exe's captured stdout
is **empty**. Three checks in this pass are new/changed: `bootstrap.capabilities.mt5` is
**available: true** (bridge + numpy shipped — the two "portable build" checks are gone), and the
`_internal` payload is asserted to **ship numpy and the MetaTrader5 bridge**. Source-level pins
unchanged: `test_request_guard.py`, `test_feed_value_guards.py`, `test_context_hardening.py`,
`test_client_error_log.py`, `test_demo_symbol_guards.py`, the asset-root pin in `test_wiring.py` —
plus the new MT5 feed pins (`test_mt5_feed.py`, five).

## The MT5-ships pass (owner's directive — what changed, and what it caught)

**Why:** the owner's call, verbatim: *"i want the packaged app to ship MT5 … bundle numpy (+27 MB)
and verify against a real MT5 terminal."*

**What changed in the source:**
- `scripts/build_exe.py` — numpy and MetaTrader5 are **bundled** again (numpy rides with the bridge;
  the analytics engines themselves stay stdlib-only, pinned by `test_no_numpy.py` + the golden).
- `engine.mt5_status()` / `engine.mt5_probe()` / `data/mt5_feed.py` — the frozen "portable build"
  branches are **deleted**; frozen behaves exactly like a source install (import → available).
- Guide + Help Centre MT5 topics — the install step now reads *"the portable Windows build already
  includes the bridge — nothing to install there"* for the packaged case, with the source-install
  line kept.
- Pins replaced: the two portable-build tests and the exclusion test are gone; in their place,
  `test_atlas_v2.py` pins that frozen is **not** special-cased (importable bridge → available) and
  `test_platforms.py` pins that **the build ships** the bridge and numpy.

**What the real-terminal verification caught — a live defect, fixed:**
`data/mt5_feed.py`'s DOM polling read `entry.volume_real` off `BookInfo` objects. On a real
terminal (MetaQuotes-Demo, package 5.0.6180, measured) `BookInfo` is a structseq with fields
**`type, price, volume, volume_dbl`** — `volume_real` exists on neither that build nor the current
docs' namedtuple shape, so **every DOM poll raised** (one ERROR + traceback per symbol per 100 ms —
1,558 in the first minutes) and the order book was silently dead. The fix is a version-tolerant
`_book_quantity()` helper (volume_dbl → volume_real → volume), an honest warning when
`market_book_add` fails (it had logged a false "Market book enabled" for a symbol that doesn't
exist), and a **new `orderflow_system/test_mt5_feed.py`** (5 pins) — the feed previously had **zero
unit coverage**, which is exactly why the defect survived test-only review. The style pin
constructs the real `mt5.BookInfo` so a future package rename fails loudly.

**The verification — three levels, against a live terminal:**
- Host: official MetaTrader 5 terminal installed silently to `C:\Program Files\MetaTrader 5`
  (build **6199**), one-time first-run completed (see root cause below), logged in to a
  **MetaQuotes-Demo** account (login 112751745, balance 100,000 USD virtual).
- Root cause found while wiring it: a freshly installed official terminal refuses
  `mt5.initialize()` with **`(-10005, 'IPC timeout')`** until an account login has completed once
  (`config/accounts.dat` absent = never logged in; the mql5 forums' standing answer matches). After
  the wizard's demo registration, `initialize()` works in every process, path-optional.
- **Tree feed:** engine on `source=mt5`: NAS100USDT 20,953 · XAUUSDT 20,871 · EURUSD 19,933 ticks in
  25 s. Symbol resolution through the feed's alternatives: `USTECm→USTEC`, `XAUUSDm→XAUUSD`,
  `EURUSDm→EURUSD`; `BTCUSDm` genuinely absent on this demo server (honest "Could not find any
  matching symbol for BTCUSDT" — the demo carries no BTC instruments).
- **Feed driver (20 s):** EURUSD 32,686 ticks / **192 DOM snapshots** / 10×10 book (top bid
  3,000,000 @ 1.15115); XAUUSD 72,939 ticks / 192 snapshots / 7×7 book; NAS100USDT 37,267 ticks
  (no DOM from this server for USTEC; none arrives — no errors). **0 book errors** after the fix.
- **Frozen exe (the star receipt):** the rebuilt portable exe, headless, `source=mt5` against the
  running terminal — NAS100USDT **30,940** · XAUUSDT **30,842** · EURUSD **30,817** ticks in 32 s,
  same alternative-symbol resolutions, DOM enabled for the three, **0 `Error polling` lines**.

## §79 payload receipts (frozen exe and the packaged shell — unchanged)

- Help assets served by the exe **byte-identical to the tree**: `help.css`, `help-data.js`,
  `help-search.js`, `help.js` + **9/9** `ui/help/*.png` screenshots.
- **Asset parity: 50/50** — every local `src`/`href` of `index.html` fetched from the running exe
  and sha256-compared to the tree.
- `GET /api/control/help` in the packaged app: facts (`frozen: true`, version present) plus a
  well-formed system check (`counts.total == len(checks)`).
- Driven in a real browser against the packaged shell: `OFAPHELP` + `OFAPHELPSEARCH` boot, the
  status-bar dock renders, **68 topics** in the corpus, a live search for "heatmap" returns ranked
  suggestions — **0 page errors**.

## §78 zero-leak / live soak receipts (unchanged — §78 measurements, same code path)

8 full cycles × 28 views + ~96 s live on the busy views: WebInterval count 24 **flat**, observers 13
**flat**, canvases 19 **flat**, DOM stabilised, JS heap a 5.7–22 MB **GC sawtooth with no upward
trend**, **0 page errors**; engine live throughout (ticks 5,840). Frame timing on the Engine view with
a live feed: **median 16.7 ms, p95 16.7, p99 16.8, max 16.8** (both tree and exe). The raw JSON was
captured under `%LOCALAPPDATA%\Temp\ofap_secaudit\` — that folder was later swept by the host's
nightly Storage Sense temp cleanup (2026-09-17); the measurements above are as recorded.

## §76 receipts (the fold-in, driven through the app — unchanged)

- **Four venues, one switch:** binance / okx / hyperliquid / bybit each switched via
  `/api/control/source` (`ok=True`), engine `running`, BTCUSDT ticks flowing on every venue.
- **Archive backfill, round trip:** `POST /api/control/backfill` BTCUSDT `2026-09-13` → **512,737
  ticks / 6,390,912 B** downloaded, job `done`; read back through `/api/control/trades`.
- **Trade audio, param round trip:** the **eight** `audio.*` variables set through
  `/api/control/params` and read back from the registry **and** `config.json`.

## Frozen-build acceptance (installer journey — re-run on the MT5-ships Setup)

- **Silent install** (`/s /v"/qn"`) → **565 files** under
  `%LOCALAPPDATA%\Programs\ModFlowOrderFlowAnalysisSuite`; installed exe sha256 **== dist exe**
  (`d6287ef2…`); desktop shortcut targeting the installed exe (the settle loop's msiexec-exit wait
  timed out at 240 s on this 40 MB build; the file count and the matching hash confirm the install
  completed — subsequent steps ran against the installed copy).
- **Installed smoke** (8098): healthz 200; BTCUSDT candles 200 (173,389 B); unknown symbol `[]`;
  hostile `Host` refused; **0 client errors**.
- **Silent uninstall** → msiexec exit 0; install dir, shortcut and the Add/Remove entry all gone;
  this run's product code `{820D9A42-F2D4-4CFA-B28D-AB629F5CFB5E}` was found in **both** the HKCU
  and the HKLM WOW6432Node views (the journey script now scans all three hives, so the uninstall
  completed without the manual step the earlier runs needed); `%APPDATA%` untouched; the machine's
  pre-existing development desktop shortcut was backed up and restored (target verified:
  `.venv\Scripts\pythonw.exe -m orderflow_system.desktop`).
- **Double-launch (N-1) acceptance:** as measured in §75 (windowed; second launch exits 0; one
  process, one window, one port).

## Known limits (honest scope)

- MT5 **ships and is verified**, but the verification ran against a **MetaQuotes-Demo** account
  (plain EURUSD/XAUUSD/index symbols; **no BTC instruments on that server** — the feed reports the
  miss honestly and the exchange feeds cover crypto). A broker terminal with `m`-suffix symbol
  naming exercises the alternatives path the same way.
- The physical multi-monitor pass is the **owner's** (this host has one display).
- Cosmetic carry-overs (next source-changing pass): the client-abort `ConnectionResetError` log
  filter and the bandit SHA1 note.

## Where to look

- `docs/SESSION_HANDOFF.md` §79 (+ its close-out, and the two same-day addenda: the MT5-fix record
  — superseded — and the MT5-ships pass) — the Help Centre, the counts, and the rebuild receipts.
- `docs/FINAL_RELEASE_ASSURANCE_AUDIT_v0.1.0-beta.md` — the §78 audit: the artefacts defect and its
  fix, the soak/validation receipts.
- `docs/AUDIT_SENDBACK_RESPONSE_v0.1b.md` — the send-back value judgement + plan.
- `docs/SECURITY_SWEEP_v0.1b.md` — the pre-release security sweep (14 findings; SS-8 closed in §74).
- `docs/DISPLAY_MULTIMONITOR_AUDIT_v0.1b.md` — the display audit the §72 hardening answers.
- `docs/AUDIT_RETURN_v0.1b.md` — the audit-return pass (§66–§68).
