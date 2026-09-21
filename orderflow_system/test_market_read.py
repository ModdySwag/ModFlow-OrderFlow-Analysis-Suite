
"""
Tests for the market read engine — pure functions, no network.
"""

from __future__ import annotations


from orderflow_system.atlas.market_read import (
    TapeSnapshot,
    FootprintSnapshot,
    HeatmapSnapshot,
    RadarSnapshot,
    VolumeProfileSnapshot,
    VWAPSnapshot,
    MarketState,
    MarketRead,
    Regime,
    read_market,
    classify_regime,
    compute_score,
    extract_levels,
    find_confluence,
    build_summary,
)


# ── helpers ──────────────────────────────────────────────────────────────────────

def _state(**kwargs) -> MarketState:
    return MarketState(**kwargs)


# ── regime classification ────────────────────────────────────────────────────────

class TestRegimeTrendingUp:
    def test_trending_up_when_delta_positive_and_slope_up(self):
        state = _state(
            spot=100.0,
            tape=TapeSnapshot(direction="up", delta=500.0, volume=10000.0,
                              big_prints=2, sweeps=1),
            footprint=FootprintSnapshot(delta_slope=0.20, delta_slope_ticks=100,
                                         imbalances_buy=2, imbalances_sell=1),
        )
        r = classify_regime(state)
        assert r.name == "trending_up"
        assert r.buyer_led is True
        assert r.seller_led is False

    def test_trending_down_when_delta_negative_and_slope_down(self):
        state = _state(
            spot=100.0,
            tape=TapeSnapshot(direction="down", delta=-800.0, volume=15000.0,
                              big_prints=3, sweeps=2),
            footprint=FootprintSnapshot(delta_slope=-0.25, delta_slope_ticks=100,
                                         imbalances_buy=1, imbalances_sell=3),
        )
        r = classify_regime(state)
        assert r.name == "trending_down"
        assert r.seller_led is True


class TestRegimeAbsorbing:
    def test_absorbing_when_many_imbalance_no_direction(self):
        state = _state(
            spot=100.0,
            tape=TapeSnapshot(direction="neutral", delta=0.0, volume=5000.0,
                              big_prints=1, sweeps=0),
            footprint=FootprintSnapshot(
                imbalances_buy=4, imbalances_sell=3,
                absorption_buy=2, absorption_sell=1,
                delta_slope=0.02, delta_slope_ticks=100),
        )
        r = classify_regime(state)
        assert r.name == "absorbing"
        assert r.absorbing is True


class TestRegimeChoppy:
    def test_choppy_when_many_prints_no_trend(self):
        state = _state(
            spot=100.0,
            tape=TapeSnapshot(direction="neutral", delta=50.0, volume=8000.0,
                              big_prints=8, sweeps=4),
            footprint=FootprintSnapshot(
                imbalances_buy=1, imbalances_sell=1,
                delta_slope=0.01, delta_slope_ticks=100),
        )
        r = classify_regime(state)
        assert r.name == "choppy"


class TestRegimeRanging:
    def test_ranging_default(self):
        state = _state(
            spot=100.0,
            tape=TapeSnapshot(direction="neutral", delta=10.0, volume=2000.0,
                              big_prints=0, sweeps=0),
            footprint=FootprintSnapshot(delta_slope=0.0, delta_slope_ticks=100),
        )
        r = classify_regime(state)
        assert r.name == "ranging"


# ── scoring ──────────────────────────────────────────────────────────────────────

class TestScoring:
    def test_score_is_0_to_100(self):
        state = _state(spot=100.0)
        regime = Regime(name="ranging", buyer_led=False, seller_led=False,
                        absorbing=False, absorbing_side=None,
                        description="Ranging.")
        score, breakdown = compute_score(state, regime)
        assert 0.0 <= score <= 100.0
        assert len(breakdown) == 7

    def test_high_trend_score(self):
        state = _state(
            spot=100.0,
            tape=TapeSnapshot(direction="up", delta=1000.0, volume=50000.0,
                              big_prints=5, sweeps=3),
            footprint=FootprintSnapshot(delta_slope=0.30, delta_slope_ticks=200,
                                         imbalances_buy=5, imbalances_sell=2),
            heatmap=HeatmapSnapshot(walls_above=3, walls_below=1, wall_refills=2),
            radar=RadarSnapshot(approaching_levels=2, held_levels=1),
            vwap=VWAPSnapshot(price=99.5, deviation=0.5, deviation_ticks=2.0),
        )
        regime = classify_regime(state)
        score, breakdown = compute_score(state, regime)
        assert score >= 60.0
        assert breakdown["trend"] >= 60.0

    def test_breakdown_sums_weighted(self):
        state = _state(spot=100.0)
        regime = Regime(name="ranging", buyer_led=False, seller_led=False,
                        absorbing=False, absorbing_side=None, description="")
        score, breakdown = compute_score(state, regime)
        weights = {"trend": 0.25, "imbalance": 0.20, "absorption": 0.15,
                   "liquidity": 0.15, "levels": 0.15, "profile": 0.05, "vwap": 0.05}
        weighted_sum = sum(weights[k] * breakdown[k] for k in weights)
        assert abs(weighted_sum - score) < 0.1


# ── levels ───────────────────────────────────────────────────────────────────────

class TestLevels:
    def test_profile_levels(self):
        state = _state(
            spot=100.0,
            profile=VolumeProfileSnapshot(poc=100.0, vah=102.0, val=98.0, poc_volume_pct=0.12),
        )
        levels = extract_levels(state)
        poc = [l for l in levels if l.kind == "poc"]
        vah = [l for l in levels if l.kind == "vah"]
        val = [l for l in levels if l.kind == "val"]
        assert len(poc) == 1
        assert poc[0].price == 100.0
        assert len(vah) == 1
        assert len(val) == 1

    def test_levels_sorted_by_strength(self):
        state = _state(
            spot=100.0,
            profile=VolumeProfileSnapshot(poc=100.0, vah=102.0, val=98.0, poc_volume_pct=0.12),
            radar=RadarSnapshot(held_levels=1),
            heatmap=HeatmapSnapshot(walls_above=2, walls_below=2),
        )
        levels = extract_levels(state)
        strengths = [l.strength for l in levels]
        assert strengths == sorted(strengths, reverse=True)

    def test_no_duplicate_prices(self):
        state = _state(
            spot=100.0,
            profile=VolumeProfileSnapshot(poc=100.0, vah=100.5, val=99.5, poc_volume_pct=0.12),
            radar=RadarSnapshot(held_levels=1),  # adds another level near 100
        )
        levels = extract_levels(state)
        prices = [l.price for l in levels]
        assert len(prices) == len(set(prices))


# ── confluence ───────────────────────────────────────────────────────────────────

class TestConfluence:
    def test_two_levels_near_each_other(self):
        levels = [
            MarketRead.__annotations__  # can't instantiate easily; use KeyLevel directly
        ]
        from orderflow_system.atlas.market_read import KeyLevel
        levels = [
            KeyLevel(price=100.0, kind="poc", source="volume_profile", strength=0.9),
            KeyLevel(price=100.1, kind="wall_above", source="heatmap", strength=0.7),
            KeyLevel(price=98.0, kind="val", source="volume_profile", strength=0.6),
        ]
        conf = find_confluence(levels, spot=100.0, tolerance_pct=0.002)
        assert len(conf) == 1
        assert conf[0].price == 100.0
        assert len(conf[0].signals) == 2
        assert conf[0].strength >= 0.3

    def test_isolated_levels_no_confluence(self):
        from orderflow_system.atlas.market_read import KeyLevel
        levels = [
            KeyLevel(price=100.0, kind="poc", source="volume_profile", strength=0.9),
            KeyLevel(price=110.0, kind="wall_above", source="heatmap", strength=0.7),
            KeyLevel(price=90.0, kind="val", source="volume_profile", strength=0.6),
        ]
        conf = find_confluence(levels, spot=100.0, tolerance_pct=0.002)
        assert len(conf) == 0

    def test_empty_levels(self):
        assert find_confluence([], spot=100.0) == []


# ── summary ─────────────────────────────────────────────────────────────────────

class TestSummary:
    def test_summary_is_string(self):
        read = MarketRead(
            regime=Regime(name="trending_up", buyer_led=True, seller_led=False,
                           absorbing=False, absorbing_side=None,
                           description="Buyers are in control."),
            composite_score=75.0,
            score_breakdown={},
            key_levels=[],
            confluence_points=[],
            summary="",
            timestamp_ms=0,
            n_levels=0,
            n_confluence=0,
        )
        s = build_summary(read)
        assert isinstance(s, str)
        assert len(s) > 0
        assert "Conviction is high" in s

    def test_summary_includes_levels(self):
        from orderflow_system.atlas.market_read import KeyLevel
        read = MarketRead(
            regime=Regime(name="ranging", buyer_led=False, seller_led=False,
                           absorbing=False, absorbing_side=None,
                           description="Ranging."),
            composite_score=50.0,
            score_breakdown={},
            key_levels=[
                KeyLevel(price=100.0, kind="poc", source="volume_profile", strength=0.9),
                KeyLevel(price=102.0, kind="vah", source="volume_profile", strength=0.6),
            ],
            confluence_points=[],
            summary="",
            timestamp_ms=0,
            n_levels=2,
            n_confluence=0,
        )
        s = build_summary(read)
        assert "Key levels:" in s
        assert "100.0" in s


# ── full read ────────────────────────────────────────────────────────────────────

class TestFullRead:
    def test_full_read_produces_all_fields(self):
        state = _state(
            symbol="BTCUSDT",
            spot=64100.0,
            tape=TapeSnapshot(direction="up", delta=1200.0, volume=50000.0,
                              big_prints=3, sweeps=2, timestamp_ms=1700000000000),
            footprint=FootprintSnapshot(
                imbalances_buy=4, imbalances_sell=2,
                absorption_buy=1, absorption_sell=0,
                delta_slope=0.22, delta_slope_ticks=200,
                poc_price=64050.0),
            heatmap=HeatmapSnapshot(walls_above=2, walls_below=3, wall_refills=1,
                                    wall_pulls=0, absorption_zones=2, pinned_levels=1),
            radar=RadarSnapshot(armed_levels=3, approaching_levels=2, held_levels=1,
                                 spent_levels=0),
            profile=VolumeProfileSnapshot(poc=64050.0, vah=64200.0, val=63900.0,
                                          poc_volume_pct=0.11),
            vwap=VWAPSnapshot(price=64080.0, deviation=20.0, deviation_ticks=1.0),
            timestamp_ms=1700000000000,
        )
        read = read_market(state)
        assert read.regime.name in ("trending_up", "ranging", "absorbing")
        assert 0.0 <= read.composite_score <= 100.0
        assert len(read.key_levels) > 0
        assert isinstance(read.summary, str) and len(read.summary) > 0
        assert read.n_levels == len(read.key_levels)
        assert read.n_confluence == len(read.confluence_points)

    def test_empty_state(self):
        state = _state(spot=0.0, symbol="")
        read = read_market(state)
        assert read.regime.name == "ranging"
        assert read.composite_score >= 0.0
        assert read.key_levels == []
        assert read.confluence_points == []
        assert read.n_levels == 0
        assert read.n_confluence == 0
