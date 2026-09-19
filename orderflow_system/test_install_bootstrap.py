"""The source-install bootstrap: install.cmd / run.cmd and the README's activation guidance.

Why this file exists: users hit `'.venv' is not recognized as an internal or external command`
following the README's old quick start — a POSIX-style activation path (forward slashes) typed in
`cmd.exe`, which then reads `.venv` as the program name. The fix is threefold and each part is
pinned here:

1. `install.cmd` / `run.cmd` do the whole job without an activation step (they call the venv's
   python.exe by full path), so the failing step does not exist on the documented happy path.
2. The README gives a per-shell activation table for anyone doing it by hand — cmd.exe gets the
   backslash path, PowerShell gets its policy note, bash gets the POSIX source line.
3. The README names the exact error and both fixes, so a search for the message lands on it.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"


def test_install_cmd_creates_the_venv_and_installs_without_activation() -> None:
    text = (ROOT / "install.cmd").read_text(encoding="utf-8")
    assert "%PYEXE% -m venv .venv" in text, "the script must create the venv itself"
    assert '".venv\\Scripts\\python.exe" -m pip install -e ".[dev]"' in text, (
        "the install must call the venv's python by full path — the step users get wrong")
    assert "activate" not in text.lower(), (
        "install.cmd must never need activation: that is the failure mode it exists to close")
    assert "py -3" in text and "python -c" in text, "both the py launcher and python are probed"
    assert "python.org/downloads" in text, "the no-Python branch must point somewhere useful"
    assert "ModFlow-beta-builds/releases" in text, "the no-Python branch offers the ready-built installer"


def test_run_cmd_uses_the_venv_and_forwards_arguments() -> None:
    text = (ROOT / "run.cmd").read_text(encoding="utf-8")
    assert '".venv\\Scripts\\python.exe" -m orderflow_system.desktop %*' in text, (
        "run.cmd starts the app through the venv and passes arguments through")
    assert "install.cmd" in text, "run.cmd explains what to do when the venv is missing"


def test_both_scripts_are_crlf_batch_files() -> None:
    for name in ("install.cmd", "run.cmd"):
        data = (ROOT / name).read_bytes()
        assert b"\r\n" in data, f"{name} must be a CRLF batch file"
        assert data.count(b"\n") == data.count(b"\r\n"), f"{name} must not mix line endings"
        assert data.startswith(b"@echo off"), f"{name} must run quietly from a double-click"


def test_the_readme_explains_the_classic_activation_error() -> None:
    readme = README.read_text(encoding="utf-8")
    assert "'.venv' is not recognized as an internal or external command" in readme, (
        "the exact error users report must be findable in the README")
    assert "Command Prompt (`cmd.exe`) | `.venv\\Scripts\\activate.bat`" in readme, "cmd.exe row"
    assert "`.\\.venv\\Scripts\\Activate.ps1`" in readme, "PowerShell row"
    assert "source .venv/Scripts/activate" in readme, "Git Bash row"
    assert "\n.venv/Scripts/activate\n" not in readme, (
        "the bare POSIX activation line must never appear as a Windows instruction again")
    assert "Set-ExecutionPolicy -Scope Process Bypass" in readme, "the PowerShell policy note"


def test_the_readme_puts_the_installer_first_and_keeps_the_paths_honest() -> None:
    readme = README.read_text(encoding="utf-8")
    installer = readme.index("### Easiest — the ready-built installer")
    source = readme.index("### From source — clone, one command, run")
    manual = readme.index("Manual step-by-step")
    assert installer < source < manual, "the no-Python path must come first"
    assert "install.cmd" in readme and "run.cmd" in readme, "the one-command path is documented"
    assert "ModFlow-beta-builds/releases/tag/v0.1.0-beta" in readme, "the download link is live text"
