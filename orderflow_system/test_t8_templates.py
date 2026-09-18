"""T8/B8 — the template gallery: every board must be a storable layout entry (grid bounds, real
views), every settings bundle must name REGISTERED paths (the /params gate refuses the rest), and
every entry must link a real help topic — the gallery is the Learn Center’s door."""

from __future__ import annotations

import re
from pathlib import Path

from orderflow_system.desktop import param_registry

UI = Path(__file__).parent / "desktop" / "ui"
INDEX = UI / "index.html"
TPL = UI / "templates.js"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_the_catalogue_is_whole():
    code = _text(TPL)
    ids = re.findall(r"\{ id: '([a-z0-9-]+)', kind: '", code)
    assert len(ids) == 6 and len(set(ids)) == 6, "the catalogue lost entries: " + repr(ids)
    assert code.count("kind: 'board'") == 3 and code.count("kind: 'settings'") == 3


def test_every_board_widget_fits_the_stored_grid():
    code = _text(TPL)
    rects = re.findall(r"\{ view: '([a-z0-9_-]+)', x: (\d+), y: (\d+), w: (\d+), h: (\d+) \}", code)
    assert len(rects) >= 12, "the boards lost their widgets"
    for view, x, y, w, h in rects:
        x, y, w, h = int(x), int(y), int(w), int(h)
        assert 1 <= w <= 12 and 1 <= h <= 8
        assert x + w <= 12 and y + h <= 8, f"{view} hangs off the 12x8 grid"
        assert re.match(r"^[a-z][a-z0-9_-]{0,23}$", view)


def test_every_board_view_exists_as_a_panel():
    html = _text(INDEX)
    code = _text(TPL)
    views = set(re.findall(r"\{ view: '([a-z0-9_-]+)'", code))
    for view in views:
        assert 'data-view="' + view + '"' in html, "no panel named " + view


def test_every_settings_path_is_registered():
    code = _text(TPL)
    blocks = re.findall(r"values: \{([^}]*)\}", code)
    assert len(blocks) == 3, "the settings bundles changed shape"
    seen = 0
    for block in blocks:
        for path in re.findall(r"'([a-z][a-z0-9_.]+)':", block):
            seen += 1
            assert path in param_registry.BY_PATH, ("unregistered path in a bundle (the /params "
                                                    "gate would refuse it): " + path)
    assert seen >= 6


def test_every_entry_links_a_real_topic_and_the_card_is_in_the_page():
    code = _text(TPL)
    topics = set(re.findall(r"topic: '([a-z0-9_.]+)'", code))
    assert topics, "no topics linked at all"
    corpus = _text(UI / "help-data.js")
    for topic in topics:
        assert "id: '" + topic + "'" in corpus, "a template links a topic that does not exist: " + topic
    html = _text(INDEX)
    assert '/desktop/templates.js' in html
    assert "Start from a template" in code and "nothing you already made is replaced" in code
    assert "activateLayout" in code, "boards must switch to the new layout through the shell"
    # the shell resolves ids against its own cache and focuses the CURRENT view on the way into
    # Terminal — so the load refreshes first, checks the result, and puts the board’s own view
    # on screen before switching (a foreign view gets appended and re-tiles the board).
    assert "refreshLayouts().then" in code and "res.ok === false" in code
    assert "showView(firstView)" in code, "the board must own the view Terminal focuses"

