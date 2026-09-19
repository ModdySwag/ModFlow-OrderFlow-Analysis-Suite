# Third-party notices

ModFlow OrderFlow Analysis Suite is released under the MIT licence (see `LICENSE`). The
components below remain under their own licences.

## Vendored in this repository

| Component | Version | Licence |
|---|---|---|
| TradingView Lightweight Charts™ | v4.1.3 | Apache License 2.0 |

`orderflow_system/desktop/ui/vendor/lightweight-charts.js` is a local copy of TradingView's
Lightweight Charts™ build; its `@license` banner is retained at the top of the file, and the
full licence text is at <https://www.apache.org/licenses/LICENSE-2.0>.

## Python dependencies

The Python dependencies (the direct set in `pyproject.toml` — FastAPI, Starlette, Uvicorn,
pywebview, pythonnet, websockets, aiohttp, aiosqlite, python-telegram-bot — and their
transitive dependencies) remain under their own licences as declared by their upstream
packages. A source install keeps each package's licence files in `site-packages`; the frozen
Windows build keeps the licence files it carries under `_internal/*.dist-info/licenses/`.

| Package | Licence |
|---|---|
| FastAPI | MIT |
| Starlette | BSD-3-Clause |
| Uvicorn | BSD-3-Clause |
| pywebview | BSD-3-Clause |
| pythonnet | MIT |
| websockets | BSD-3-Clause |
| aiohttp | Apache-2.0 |
| aiosqlite | MIT |
| python-telegram-bot | LGPL-3.0 |
| numpy (bundled so the MT5 bridge loads in the frozen app) | BSD-3-Clause |
| MetaTrader5 (optional `mt5` extra) | not an OSI licence — MetaQuotes' own terms |

### The frozen Windows build

The PyInstaller payload keeps the licence files of the packages whose metadata it carries, under
`_internal/*.dist-info/licenses/`. That set is **not yet complete** — the v0.1b audit found nine
licence directories against a much larger bundled set — so publishing a build requires checking
it first:

1. list what the payload carries: the `_internal/*.dist-info/licenses/` directories;
2. compare against the bundled packages (the table above plus transitive dependencies);
3. add any missing text to the build (`--add-data` in `scripts/build_exe.py`) before publishing.

`MetaTrader5` is bundled in the portable build under MetaQuotes' terms — review those terms before
redistributing beyond the project's own releases. The two committed bridge binaries
(`ofap-bridge.jar`, `ModFlowBridge.dll`) are covered in `docs/BINARY_PROVENANCE.md`.
