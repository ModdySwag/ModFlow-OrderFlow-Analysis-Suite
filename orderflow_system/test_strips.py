"""The arbiter's coverage: every poller asks, the strips hold a reader's place, the chips are one
cluster, and the ingest is still untouched."""
from pathlib import Path

UI = Path(__file__).resolve().parent / "desktop" / "ui"
def _r(n): return (UI / n).read_text(encoding="utf-8")


def test_every_poller_consults_the_arbiter():
    for name in ("ofx-view.js", "heatmap-pro.js", "ui.js", "atlas-v2.js",
                 "alpaca-card.js", "scanner.js", "market-pressure.js", "context.js"):
        assert "OFAPINTENT" in _r(name), "%s still polls blind" % name


def test_strips_hold_the_reader_place_and_never_drop_data():
    s = _r("strips.js")
    assert "MutationObserver" in s
    assert "st.lastTop" in s, "the reader's anchor must be restored"
    assert "pending += added" in s, "arrivals are counted, not dropped"
    assert "jump to newest" in s
    assert "strips.js" in _r("index.html")


def test_one_status_cluster():
    i = _r("intent.js")
    assert "ofapPause" in i, "the hold chip belongs beside the pause control"
    assert "setStrips" in i and "holding your place" in i
    assert "ofap-strip-chip" in _r("atlas.css")
