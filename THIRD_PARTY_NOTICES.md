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
