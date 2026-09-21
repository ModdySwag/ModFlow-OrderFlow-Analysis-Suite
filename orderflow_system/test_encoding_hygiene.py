"""Housekeeping pin: text is decoded as UTF-8 everywhere the suite crosses a process or a file.

The suite went red on the CI runner (Python 3.11, Windows locale cp1252) because a process call in
text mode with no explicit encoding decodes node's UTF-8 output with the locale encoding — the em
dashes in refusal strings came back as mojibake, and four parity tests disagreed with the JS side.
The dev machines set PYTHONUTF8=1, which hid the whole class. This pin keeps it visible: it fails
if any process call in text mode, or any textual file open(), in the suite or the scripts loses its
explicit encoding.
"""
from __future__ import annotations

import ast
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCAN_DIRS = (ROOT / "orderflow_system", ROOT / "scripts")
SKIP_PARTS = (".venv", "build", "dist", "node_modules", ".git")
CALL = "subprocess" + r"\.(run|check_output|Popen|call)\s*\("
TEXT_MODE = ("text=True", "universal_newlines=True")


def _py_files():
    roots = list(SCAN_DIRS) + [ROOT]
    seen: set[pathlib.Path] = set()
    for base in roots:
        for p in base.glob("*.py") if base is ROOT else base.rglob("*.py"):
            if p in seen or any(part in SKIP_PARTS for part in p.parts):
                continue
            seen.add(p)
            yield p


def _call_block(src: str, start: int) -> str:
    """The full argument text of the call that opens at ``start`` (balanced parentheses)."""
    depth, j = 0, start
    while j < len(src):
        if src[j] == "(":
            depth += 1
        elif src[j] == ")":
            depth -= 1
            if depth == 0:
                break
        j += 1
    return src[start : j + 1]


def _process_text_calls(src: str):
    """Line numbers of process calls in text mode that carry no explicit encoding."""
    for m in re.finditer(CALL, src):
        block = _call_block(src, m.end() - 1)
        if any(flag in block for flag in TEXT_MODE) and "encoding=" not in block:
            yield src[: m.start()].count("\n") + 1


def _textual_open_calls(src: str):
    """Line numbers of ``open()`` calls in text mode that carry no explicit encoding."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open"):
            continue
        keywords = {k.arg for k in node.keywords}
        if "encoding" in keywords:
            continue
        mode = None
        if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
            mode = node.args[1].value
        for k in node.keywords:
            if k.arg == "mode" and isinstance(k.value, ast.Constant):
                mode = k.value.value
        if isinstance(mode, str) and "b" in mode:
            continue
        yield node.lineno


def test_the_scanner_catches_the_pattern_it_exists_for():
    """A pin that cannot fail is decoration: feed it the exact shapes it must catch."""
    planted_process = "subprocess" + '.run(["node", "x"], capture_output=True, text=True)\n'
    assert list(_process_text_calls(planted_process)) == [1]
    planted_open = "f = " + "open('a.txt')\n"
    assert list(_textual_open_calls(planted_open)) == [1]
    explicit_process = "subprocess" + '.run(["node", "x"], text=True, encoding="utf-8")'
    assert list(_process_text_calls(explicit_process)) == []
    binary_open = "data = " + "open('a.bin', 'rb')"
    assert list(_textual_open_calls(binary_open)) == []


def test_process_and_file_text_is_always_explicitly_utf8():
    offenders: list[str] = []
    for p in _py_files():
        src = p.read_text(encoding="utf-8", errors="replace")
        rel = p.relative_to(ROOT).as_posix()
        for line in _process_text_calls(src):
            offenders.append(f"{rel}:{line}: a process call in text mode with no encoding=")
        for line in _textual_open_calls(src):
            offenders.append(f"{rel}:{line}: open() in text mode with no encoding=")
    assert not offenders, (
        "text crossed a process or file boundary without an explicit encoding — the CI runner's "
        "locale is cp1252 and this bit the suite once already:\n" + "\n".join(offenders)
    )
