# Contributing to OrderFlow Analysis Pro

Thank you for your interest in contributing!

## Getting Started

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Run tests: `pytest orderflow_system/test_integration.py`
5. Submit a pull request

## Development Setup

```bash
pip install -e ".[dev]"
```

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
