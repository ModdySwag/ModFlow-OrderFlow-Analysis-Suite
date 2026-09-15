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

## Tests & UI audit (the two commands that must stay green)

Every change must leave these green — CI runs exactly the same two commands
(`.github/workflows/ci.yml`):

```bash
.venv/Scripts/python.exe -m pytest orderflow_system -q   # full suite (baseline: 130 passed)
.venv/Scripts/python.exe scripts/audit_ui_refs.py        # JS → FastAPI routes / DOM ids (baseline: AUDIT CLEAN)
```

- Run the audit after **any** edit under `orderflow_system/desktop/ui/` or `dashboard/` — it catches broken
  API paths, dead element ids and JS syntax errors without opening the app.
- `orderflow_system/test_integration.py` is the fast smoke for the analytics pipeline; `test_alpaca.py`
  covers the broker client with a stub transport (no live calls in CI).
- Behaviour changes need a test that failed before the change. Data endpoints must keep the demo payload
  shapes (`dashboard/demo_data.py` is the contract) — `test_payload_parity.py` guards that.
- Headless UI smoke while developing:
  `.venv/Scripts/python.exe -m orderflow_system.desktop --headless --port 8099` then hit
  `http://127.0.0.1:8099/api/...` (see the run flags in `desktop/launcher.py`).

## Areas for Contribution

- **New pattern detectors** — add to `patterns/` directory
- **Additional instruments** — add config in `config/settings.py`
- **Dashboard improvements** — frontend or API enhancements
- **Documentation** — guides, tutorials, API docs
- **Bug fixes** — check GitHub Issues

## Code Style

- Python 3.10+ with type hints
- Dataclasses for data models
- Async/await for I/O operations
- Follow existing patterns in each module

## Reporting Issues

Use GitHub Issues to report:
- Bugs or unexpected behavior
- Feature requests
- Documentation errors
- Instrument configuration issues

## Pull Request Process

1. Ensure tests pass
2. Add tests for new features
3. Update documentation if needed
4. Keep PRs focused — one feature or fix per PR
