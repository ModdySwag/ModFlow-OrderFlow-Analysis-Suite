# Security policy

ModFlow OrderFlow Analysis Suite is a local desktop application (v0.1.0-beta).

## Supported versions

Pre-1.0: only the latest beta gets fixes. There are no backports.

## Reporting a vulnerability

Please report privately — not as a public issue.

- **Preferred:** GitHub's private vulnerability reporting on this repository
  (**Security → Report a vulnerability**). The whole discussion stays in one place and you
  get credit for a confirmed report.
- If you cannot use that, open a minimal issue that asks for a private channel and post
  **no** vulnerability details in it.

What helps: the build you ran (version / installer or `dist` you used), what you did, what
happened, and the smallest proof you have — a request, a crafted file or feed message, a
recording. A precise "this request against this endpoint does that" is worth more than a
long report.

## What to expect

- Acknowledgement within a few days, and an honest assessment: exploitable or not, and why.
- A fix in the beta; credit (name or handle, your choice) once the fix is out.
- No bug bounty — this is a free, single-maintainer project.

## Scope

**In scope:** this repository's code — the desktop shell and its local HTTP/WebSocket server,
the analytics engines, the data feeds (Bybit, MetaTrader 5, Alpaca), the config store, the
frozen Windows build and the installer.

**Out of scope:** the venues and their data (report those to the provider — Bybit, Alpaca,
Deribit, CoinGecko, SEC EDGAR, ntfy, Telegram); anything that requires an attacker who can
already run code as your Windows user (that attacker can read your config file directly, and
this app does not pretend to defend against it); trading decisions.

## The security model, so a report lands in the right bucket

The design is a single-user desktop app. Some things are deliberate and documented:

- **Loopback only.** The API binds `127.0.0.1` and a request guard refuses non-loopback
  `Host` headers and cross-site mutations (DNS-rebinding / CSRF). It is never exposed to the
  LAN or the internet.
- **No login, on purpose.** Anyone who can already reach `127.0.0.1` as your user can call
  the API; a password would not add a boundary at that same privilege level.
- **Market data, no execution.** The app places no orders on any venue. The Alpaca
  integration is read-only (account state, positions, order *history*) plus market data. A
  defect that could trade for you would be critical — please report it immediately.
- **Credentials stay local, and are write-only over the API.** Keys and tokens live in your
  per-user config file (`%APPDATA%\OrderFlowAnalysisPro\config.json`), are never written to logs,
  never committed, and are only ever sent to the provider you configured. The control API never
  hands a stored credential back: `GET /config` and `/bootstrap` return a mask in place of every
  non-empty secret, a masked value posted back means "unchanged", and pressing Test with an
  untouched field tests the stored credential rather than the mask.
- **No telemetry.** No analytics, no crash reporting, no usage reporting. One release check
  does run: while the app is open it asks GitHub (`api.github.com`) for the newest published
  release, no more often than the interval you set in Updates (6 h by default) — that request
  carries nothing about you or your data, and there is no other unrequested traffic. Everything
  else that leaves the machine is a feed or a notification channel you enabled.
- **The study engine runs JavaScript you paste yourself** ("Studies" view). Treat a pasted
  module as code you chose to run, exactly like a browser console snippet.
- The bundled chart library is a local copy of TradingView's *Lightweight Charts* v4.1.3
  (Apache-2.0 — see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)); report library issues
  upstream, tell us as well and we will bump the vendored copy.

## Disclosure

We fix first, then publish a short advisory with credit once a fixed build is out. Reports
about a dependency are forwarded upstream, with you in the loop.
