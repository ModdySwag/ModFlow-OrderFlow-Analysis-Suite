"""The hover-info contract: what a user reads on hover must be true, findable and self-consistent.

Written for the owner's hover audit ("make sure the right details reach the user; some hover
information was anomalous"). Every rule here caught at least one real anomaly in the tree:

1. No internal case/ticket ids (paragraph marks, T14/B4, B2) in user-facing hover text - they are
   development traceability, not information for a user.
2. Every shortcut a hover mentions must exist in the shortcut registry (keys.js and the modules
   that bind through it), spelled the way the registry prints it.
3. Every menu path a hover mentions ("Settings > Data", "View > Full screen") must exist in the
   menubar spec.
4. A control whose shortcut keys.js annotates at runtime must not ALSO spell the shortcut out in
   its static text - the user saw the same key twice.
5. Hover text must carry information: sentence case, a floor on length, a ceiling so a title stays
   readable as a tooltip, and no dangling punctuation.
6. Every hint action must be in hint.js's closed action set - an unknown token is silently dropped,
   which reads to the user as a missing button rather than as a typo.
7. Every control the shortcut annotator targets must exist, or the shortcut never reaches it.
"""

from __future__ import annotations

import re
from pathlib import Path

UI = Path(__file__).parent / "desktop" / "ui"
HTML = UI / "index.html"

# quote characters, composed so this module needs no escaped quotes anywhere
DQ = chr(34)
SQ = chr(39)
SEP = "[ \n\r\t]"
VALUE = "(" + DQ + "([^" + DQ + "]*)" + DQ + "|" + SQ + "([^" + SQ + "]*)" + SQ + ")"
TAG = re.compile(r"<([a-zA-Z0-9]+)([^>]*)>", re.S)
MENU_ARROW = "\u25b8"

INTERNAL_ID = re.compile(r"\u00a7 ?\d|\bT\d{1,2}/B\d{1,2}\b|\bB\d{1,2} \u2014")
HOVER_ATTRS = ("title", "data-hint-title", "data-hint-body")
MAX_TITLE = 240
MIN_TITLE = 12


def _value(match) -> str:
    return (match.group(2) or match.group(3) or "") if match else ""


def _html_hovers():
    """(element-identity, attribute, text) for every static hover surface."""
    html = HTML.read_text(encoding="utf-8")
    out = []
    for m in TAG.finditer(html):
        tag, attrs = m.group(1), m.group(2)
        ident = _value(re.search(SEP + "id" + "=" + VALUE, attrs)) or tag
        for attr in HOVER_ATTRS:
            text = _value(re.search(SEP + attr + "=" + VALUE, attrs, re.S))
            if text:
                out.append((ident, attr, text))
    return out


BLOCK_COMMENT = re.compile(r"/\*[\s\S]*?\*/")


def _js_hover_lines():
    """(file:line, text) for hover machinery built in JS, with block comments removed first so a
    comment that merely talks about titles is not read as user-facing text."""
    out = []
    for path in sorted(UI.glob("*.js")):
        if path.name.endswith(".selftest.js"):
            continue
        src = BLOCK_COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), path.read_text(encoding="utf-8", errors="replace"))
        for i, line in enumerate(src.splitlines(), 1):
            if not re.search(r"title|hint-title|hint-body|hint-actions", line):
                continue
            if line.strip().startswith(("/*", "*", "//")):
                continue
            out.append((f"{path.name}:{i}", line))
    return out


def _element_tag(el_id: str) -> str:
    """The markup that declares this id: the shell's HTML, or a module that injects it (several
    controls — the menubar's hide button, the pause chip — are built in JS, not in index.html)."""
    html = HTML.read_text(encoding="utf-8")
    m = re.search(r"<[^>]*" + SEP + "id=" + DQ + re.escape(el_id) + DQ + r"[^>]*>", html)
    if m:
        return m.group(0)
    for path in sorted(UI.glob("*.js")):
        if path.name.endswith(".selftest.js"):
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if ('id="' + el_id + '"') in line or ("id='" + el_id + "'") in line:
                return line
    return ""


def _registry_keys():
    """Every shortcut the app binds, printed roughly the way keys.js prints it."""
    found = set()
    for path in sorted(UI.glob("*.js")):
        if path.name.endswith(".selftest.js"):
            continue
        src = path.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"bind\(\{(.{0,700}?)\}\)", src, re.S):
            km = re.search(r"keys:\s*\[([^\]]*)\]", m.group(1))
            if not km:
                continue
            for raw in re.findall(SQ + "([^" + SQ + "]+)" + SQ, km.group(1)):
                parts = raw.split("+")
                rendered = []
                for idx, part in enumerate(parts):
                    if idx < len(parts) - 1:
                        rendered.append({"ctrl": "Ctrl", "alt": "Alt", "meta": "Win",
                                         "shift": "Shift"}.get(part, part))
                    else:
                        names = {"escape": "Escape", "pagedown": "PageDown", "pageup": "PageUp",
                                 "space": "Space", "enter": "Enter", "tab": "Tab", "f1": "F1"}
                        rendered.append(names.get(part, part.upper() if len(part) == 1 else part.capitalize()))
                found.add("+".join(rendered))
    return found


def _menubar_paths():
    """(group label, item label) pairs from the menubar spec, one level of submenus deep."""
    src = (UI / "menubar.js").read_text(encoding="utf-8")
    paths = set()
    for g in re.findall(r"\{\s*id:\s*'[a-z]+',\s*label:\s*'([^']+)',\s*items:\s*\[", src):
        start = src.find("label: '" + g + "', items: [")
        chunk = src[start:start + 30000]
        for label in re.findall(r"label:\s*'([^']+)'", chunk):
            paths.add((g, label))
    return paths


# ── 1. internal ids ─────────────────────────────────────────────────────────────────────────

def test_no_internal_ticket_ids_reach_the_user():
    bad = [f"{ident} [{attr}]: {text[:80]}" for ident, attr, text in _html_hovers()
           if INTERNAL_ID.search(text)]
    for where, line in _js_hover_lines():
        if INTERNAL_ID.search(line):
            bad.append(f"{where}: {line.strip()[:80]}")
    assert not bad, ("internal case/ticket ids in hover text (traceability, not user information):\n"
                     + "\n".join(bad))


# ── 2/3. cross-references resolve ───────────────────────────────────────────────────────────

# one modifier chain, then a key; the single-char repetition form \bCtrl\+A\b never matched a
# two-part chord like Ctrl+Alt+T, which is how a real title slipped through as a bare "Alt+T"
SHORTCUT = re.compile(r"((?:Ctrl|Alt|Shift|Win)(?:\+[A-Za-z0-9=+\-_]+)+|\bF\d{1,2}\b|\bEsc\b)")


def test_every_shortcut_a_hover_mentions_is_really_bound():
    registry = _registry_keys()
    aliases = {"Esc": "Escape"}
    bad = []
    for ident, attr, text in _html_hovers():
        for m in SHORTCUT.finditer(text):
            token = aliases.get(m.group(1), m.group(1))
            if token not in registry:
                bad.append(f"{ident} [{attr}]: {token}")
    assert not bad, ("hover text promises a shortcut that is not bound "
                     f"(registry: {sorted(registry)}):\n" + "\n".join(sorted(set(bad))))


def test_every_menu_path_a_hover_mentions_exists():
    paths = _menubar_paths()
    groups = {g for g, _ in paths}
    bad = []
    rows = _html_hovers() + [(where, "js", line) for where, line in _js_hover_lines()]
    for ident, _attr, text in rows:
        for group, phrase in re.findall(r"([A-Z][A-Za-z ]{2,12})\s*" + MENU_ARROW + r"\s*([A-Za-z][A-Za-z ]{2,40})", text):
            group, phrase = group.strip(), phrase.strip()
            # the prose continues after the path ("Data > Source still lists..."), so the menubar
            # item must be a PREFIX of the captured phrase - not the other way round
            if group in groups and not any(g == group and phrase.startswith(it) for g, it in paths):
                bad.append(f"{ident}: {group} {MENU_ARROW} {phrase}")
    assert not bad, ("hover text points at a menu path that does not exist:\n"
                     + "\n".join(sorted(set(bad))))


# ── 4. the shortcut is not said twice ───────────────────────────────────────────────────────

def test_an_annotated_control_does_not_spell_its_shortcut_in_its_static_title():
    keys_js = (UI / "keys.js").read_text(encoding="utf-8")
    block = re.search(r"\[\['#ofapPause'[\s\S]*?\]\.forEach", keys_js)
    assert block, "the annotate() table moved - update this contract"
    annotated = re.findall(r"\['(#[^']+)',\s*'([^']+)'\]", block.group(0))
    assert annotated, "annotate() has no targets - update this contract"
    bad = []
    for sel, _kid in annotated:
        tag = _element_tag(sel[1:])
        if not tag:
            bad.append(f"{sel}: annotated but no element declares it")
            continue
        text = _value(re.search(SEP + "title" + "=" + VALUE, tag))
        if text and ("Shortcut" in text or re.search(r"\((?:Ctrl\+)?[A-Za-z0-9=+\-]+\)", text)):
            bad.append(f"{sel}: static title also spells the shortcut ({text[-60:]})")
    assert not bad, "the shortcut arrives twice on hover:\n" + "\n".join(bad)


# ── 5. the text carries information ────────────────────────────────────────────────────────

def test_hover_text_is_informative_and_readable():
    bad = []
    for ident, attr, text in _html_hovers():
        if attr != "title":
            continue                      # hint cards carry their detail in data-hint-body
        stripped = text.strip()
        if len(stripped) < MIN_TITLE:
            bad.append(f"{ident}: too short ({stripped})")
        if len(stripped) > MAX_TITLE:
            bad.append(f"{ident}: {len(stripped)} chars, over the {MAX_TITLE} ceiling")
        if stripped[:1].islower():
            bad.append(f"{ident}: starts lowercase ({stripped[:48]})")
        if stripped.endswith((" \u2014", " \u00b7", ",")):
            bad.append(f"{ident}: ends mid-sentence ({stripped[-24:]})")
    assert not bad, "hover text that does not inform:\n" + "\n".join(bad)


# ── 5b. the shortcut annotation is idempotent and speaks the digits ───────────────────────

def test_the_shortcut_annotation_re_derives_instead_of_appending():
    """A control whose shortcut changes (any rail digit after a view is added or removed) must be
    RE-DERIVED from its pristine text — the append-only shape produced "Shortcut 8 · Shortcut 9"
    on eight rail items the moment the view list shifted."""
    keys_js = (UI / "keys.js").read_text(encoding="utf-8")
    annotate = keys_js[keys_js.index("function annotate()"):]
    annotate = annotate[:annotate.index("\n    }")]
    assert "data-base-title" in annotate, "annotate() no longer re-derives from a base title"
    assert "shortcutPhrase" in annotate, "annotate() does not use the phrase helper"
    # every rail item is visited, so an item that loses its digit gets its base title back
    assert ".rail .nav-item[data-view]" in annotate, "the rail loop moved"
    assert "i < 9 ? String(i + 1) : ''" in annotate, "an out-of-range rail item keeps a stale digit"
    # digits are spoken as an instruction, never as a bare key
    phrase = keys_js[keys_js.index("function shortcutPhrase("):]
    phrase = phrase[:phrase.index("\n    }")]
    assert "'Press '" in phrase, "digits are not phrased as a press instruction"
    assert "/^[1-9]$/" in phrase, "the digit test moved out of the phrase helper"
    # and the hover card reads the phrase, not the raw attribute
    hint = (UI / "hint.js").read_text(encoding="utf-8")
    assert "data-shortcut-phrase" in hint, "the card line no longer reads the published phrase"


# ── 6. the hint machinery's own contract ───────────────────────────────────────────────────

def test_hint_actions_are_in_the_closed_set():
    hint = (UI / "hint.js").read_text(encoding="utf-8")
    actions = set(re.search(r"var ACTIONS = \[([^\]]*)\]", hint).group(1).replace(SQ, "").split(", "))
    bad = []
    for ident, attr, text in _html_hovers():
        if attr != "data-hint-actions":
            continue
        for token in re.split(r"[\s,]+", text.strip()):
            if token and token not in actions:
                bad.append(f"{ident}: {token} (valid: {sorted(actions)})")
    assert not bad, "a hint action typo drops the card's button silently:\n" + "\n".join(bad)
