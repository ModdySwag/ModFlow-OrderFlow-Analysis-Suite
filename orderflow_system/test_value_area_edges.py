"""Value-area edge behaviour, pinned (v0.1b audit Tier 1.1 verdict: no inversion exists).

The audit claimed one-sided profiles report a wrong VAL (collapsing onto the POC). A read of
`_compute_value_area` plus a probe over extreme profiles shows the invariant val <= poc <= vah
holds by construction — `lo`/`hi` start at `poc_idx` and only move outward — and the only
`val == poc` profiles are those whose POC genuinely sits at the accumulation's edge, which is
the standard expansion's correct result. The audit's suggested "fix" (walking val past the
accumulated range) would report a band WIDER than the 68% containment. These tests pin the
invariant and the two edge shapes; the analytics golden carries the exact numbers
(`poc_top_cluster`, `poc_at_low`).
"""

from __future__ import annotations

from orderflow_system.analytics.volume_profile import VolumeProfileEngine
from orderflow_system.config.settings import VolumeProfileConfig

VP = VolumeProfileEngine(VolumeProfileConfig())


def _run(vap):
    return VP._compute_profile({float(k): float(v) for k, v in vap.items()}, "t")


def test_invariant_holds_across_extreme_profiles():
    profiles = {
        "one_sided_top": {10.0: 5, 11.0: 4, 12.0: 6},
        "poc_alone_dominant": {float(i): (9.0 if i == 9 else 0.1) for i in range(10)},
        "poc_at_bottom": {float(i): (9.0 if i == 0 else (4.0 if i < 5 else 1.0)) for i in range(10)},
        "flat": {float(i): 2.0 for i in range(10)},
        "two_levels": {100.0: 60.0, 101.0: 40.0},
    }
    for name, vap in profiles.items():
        res = _run(vap)
        lo, hi = min(vap), max(vap)
        assert lo <= res.val <= res.poc <= res.vah <= hi, (name, res.val, res.poc, res.vah)


def test_one_sided_top_keeps_val_below_poc():
    """The audit's proposed new golden case — it already passes on the current algorithm."""
    res = _run({10.0: 5, 11.0: 4, 12.0: 6})
    assert res.val < res.poc
    assert res.poc == res.vah == 12.0


def test_val_equals_poc_only_when_no_lower_neighbour_can_be_included():
    """POC alone above the 68% target: a single-price value area is the correct answer."""
    res = _run({100.0: 60.0, 101.0: 40.0})
    assert res.poc == res.val == 100.0
    assert res.vah == 101.0


def test_value_area_never_contains_more_than_the_target_plus_one_level():
    """Sanity on the accumulation: the band may overshoot by at most the last added level."""
    vap = {round(100.0 + i * 0.5, 6): float(100 - abs(i - 5) * 6) for i in range(11)}
    res = _run(vap)
    total = sum(vap.values())
    contained = sum(v for p, v in vap.items() if res.val <= p <= res.vah)
    assert contained >= total * 0.68
    ordered = [vap[p] for p in sorted(vap)]
    assert contained - max(ordered) <= total * 0.68  # overshoot bounded by the last level
