# Contributing to ModFlow OrderFlow Analysis Suite

Thank you for your interest in contributing!

## Getting Started

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Run tests and the UI audit (see below)
5. Submit a pull request

## Development Setup

```bash
pip install -e ".[dev]"
```

## Tests, audit and UI selftests (the gates that must stay green)

Every change must leave these green — CI runs exactly the same commands on Python 3.11 and
3.12, plus the lint baseline and a dependency audit (`.github/workflows/ci.yml`):

```bash
python -m pytest orderflow_system -q                     # full suite (baseline: 881 passed / 2 skipped)
python scripts/audit_ui_refs.py                          # JS → FastAPI routes / DOM ids (baseline: AUDIT CLEAN)
for f in orderflow_system/desktop/ui/*.selftest.js; do node "$f"; done   # 23 selftests (needs Node)
```

There is also a lint baseline:

```bash
ruff check orderflow_system scripts                      # config lives in pyproject.toml
```

- Dependencies are locked in `uv.lock` (`uv sync` reproduces the environment) and audited in CI
  with `pip-audit` over the locked set.
- Run the audit after **any** edit under `orderflow_system/desktop/ui/` or `dashboard/` — it catches broken
  API paths, dead element ids and JS syntax errors without opening the app.
- The analytics engines are **stdlib-only** (`analytics/delta.py`, `analytics/volume_profile.py`): the
  frozen build excludes numpy, and `test_no_numpy.py` fails if a numpy import creeps back in. Their
  numbers are pinned by `test_analytics_golden.py` against `testdata/analytics_golden.json` — regenerate
  deliberately with `python scripts/regen_analytics_golden.py --write` and review the diff.
- `orderflow_system/test_integration.py` is the fast smoke for the analytics pipeline; `test_alpaca.py`
  covers the broker client with a stub transport (no live calls in CI).
- Behaviour changes need a test that failed before the change. Data endpoints must keep the demo payload
  shapes (`dashboard/demo_data.py` is the contract) — `test_payload_parity.py` guards that.
- Headless UI smoke while developing:
  `python -m orderflow_system.desktop --headless --port 8099` then hit
  `http://127.0.0.1:8099/api/...` (see the run flags in `desktop/launcher.py`). Point `APPDATA` at a
  scratch directory so a smoke run never touches your real config/DB.

## Areas for Contribution

- **New pattern detectors** — add to `patterns/` directory
- **Additional instruments** — add config in `config/settings.py`
- **Dashboard improvements** — frontend or API enhancements
- **Documentation** — guides, tutorials, API docs
- **Bug fixes** — check GitHub Issues

## Code Style

- Python 3.11+ (CI runs 3.11 and 3.12) with type hints
- `ruff check orderflow_system scripts` must stay clean (config in `pyproject.toml`)
- Dataclasses for data models
- Async/await for I/O operations
- Follow existing patterns in each module

## Reporting Issues

Use GitHub Issues to report:
- Bugs or unexpected behavior
- Feature requests
- Documentation errors
- Instrument configuration issues

**Security problems do not belong in a public issue** — see [SECURITY.md](SECURITY.md) for the
private channel and for the project's security model (loopback-only server, no execution,
credentials stay in your user config).

## Pull Request Process

1. Ensure tests pass
2. Add tests for new features
3. Update documentation if needed
4. Keep PRs focused — one feature or fix per PR
