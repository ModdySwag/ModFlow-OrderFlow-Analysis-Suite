"""The display-variable registry — one table describing every knob the UI may show.

Why this file exists: the app already stores ~80 display variables in `config.json`, but *what they
are* lives only in `config_store.default_config()` (values) and in the UI code that happens to touch
them. That is why the reference programs (the reference platform's studies panel, the conventional Chart Settings) can offer
a hundred controls and we offer a handful: they have a registry, we have a habit. This is the registry.

Rules that keep it honest:

* **Values are not duplicated here.** `default`/`current` are read from the config store at call time,
  so a schema change cannot leave the registry pointing at a stale default. The test asserts every
  path resolves and every display-relevant leaf in the config is registered.
* **Presentation only**: label, group (dialog/tab), owning view (whose Chart menu shows it), kind,
  bounds, unit, meaning, and whether a change applies live or needs an engine restart.
* `kind` is `number | bool | enum | list`; enums carry their choices, numbers carry their bounds, and
  the UI renders from this — never hand-writes a control again.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

# Roots of the config that hold display variables. A leaf under these roots that is not registered
# fails the test suite, so nothing display-relevant can be forgotten.
DISPLAY_ROOTS: tuple[str, ...] = ("ofx", "atlas", "risk", "audio", "studies.data_box", "search.default_view")

# Keys under those roots that are deliberately not display variables.
NOT_DISPLAY: frozenset[str] = frozenset({
    "ofx.symbol",              # a selector (the instrument picker owns it), not a variable
    "atlas.webhook_url",       # an endpoint, needs its own field with validation
    "atlas.alert_rules",       # edited by the Alerts view, has its own contract
    "atlas.telegram.enabled",  # channel routing, sits with the other notification settings
    "atlas.history.enabled",   # a storage switch, not a display variable
})


@dataclass(frozen=True)
class Param:
    """One display variable: where it lives, what it does, and how a UI should edit it."""

    path: str
    label: str
    group: str
    view: str
    kind: str = "number"
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    unit: str = ""
    meaning: str = ""
    applies: str = "live"                      # live | restart
    choices: tuple[str, ...] = ()

    def as_dict(self, value: Any = None, default: Any = None) -> dict[str, Any]:
        """The entry as the UI consumes it. `value` is live, `default` is what Restore returns to."""
        out: dict[str, Any] = {
            "path": self.path, "label": self.label, "group": self.group, "view": self.view,
            "kind": self.kind, "unit": self.unit, "meaning": self.meaning, "applies": self.applies,
        }
        if default is not None:
            out["default"] = default
        if self.kind == "number":
            out.update({"min": self.minimum, "max": self.maximum, "step": self.step})
        if self.kind == "enum":
            out["choices"] = list(self.choices)
        if value is not None:
            out["value"] = value
        return out


def P(path: str, label: str, group: str, view: str, kind: str = "number",
      minimum: float | None = None, maximum: float | None = None, step: float | None = None,
      unit: str = "", meaning: str = "", applies: str = "live",
      choices: Iterable[str] = ()) -> Param:
    return Param(path=path, label=label, group=group, view=view, kind=kind, minimum=minimum,
                 maximum=maximum, step=step, unit=unit, meaning=meaning, applies=applies,
                 choices=tuple(choices))


# ── the table ─────────────────────────────────────────────────────────────────────────────
# Order matters: it is the order the dialogs render in.

PARAMS: tuple[Param, ...] = (
    # Engine — footprint matrix (the view this whole system grew out of)
    P("ofx.R", "Imbalance ratio (R)", "Footprint", "ofx", minimum=1.0, maximum=20.0, step=0.5,
      unit="x", meaning="Bid must exceed ask by this multiple one row up (and the reverse) before a "
                        "diagonal imbalance is flagged."),
    P("ofx.stack", "Stacked run (levels)", "Footprint", "ofx", minimum=2, maximum=12, step=1,
      meaning="How many consecutive imbalanced rows make a stacked zone worth banding."),
    P("ofx.va_pct", "Value area", "Footprint", "ofx", minimum=0.5, maximum=0.95, step=0.05,
      meaning="Share of the bar's volume treated as the value area around its POC."),
    P("ofx.text_px", "Cell text threshold", "Footprint", "ofx", minimum=8, maximum=60, step=1,
      unit="px", meaning="Row height at which numbers are drawn instead of colours alone."),
    P("ofx.min_block", "Min block to draw", "Footprint", "ofx", minimum=0.0, maximum=1000.0,
      step=0.01, meaning="Blocks smaller than this are not bubbled on the flow layer."),
    P("ofx.sweep_c", "Sweep bubble scale", "Footprint", "ofx", minimum=0.2, maximum=5.0, step=0.05,
      meaning="Radius curve for execution bubbles; higher spreads the same size wider."),
    P("ofx.lambda_ms", "Liquidity decay", "Depth heat", "ofx", minimum=50, maximum=5000, step=50,
      unit="ms", meaning="Half-life used to fade resting liquidity that was pulled."),
    # Bar expression (P1-8). Two surfaces draw bars and each keeps its own mode + palette; the words
    # for whatever is chosen come from `desktop/ui/expression.js`, which the renderers also paint
    # from. Registered as enums so a Chart menu can never offer a value the store would clamp.
    P("expression.engine.mode", "Engine bar mode", "Expression", "ofx", kind="enum",
      choices=("default", "delta", "split", "heat", "wick"),
      meaning="How the Engine view expresses each bar: the footprint default, a delta-tinted body, "
              "a split candle, a heat-gradient body, or wick + footprint only."),
    P("expression.engine.palette", "Engine palette", "Expression", "ofx", kind="enum",
      choices=("theme", "deutan", "protan", "tritan"),
      meaning="Colour vocabulary of the Engine view. The colour-blind palettes are two-hue sets "
              "measured for separation under each dichromacy (expression.selftest)."),
    P("ofx.ramp", "Depth heat ramp", "Depth heat", "ofx", kind="enum",
      choices=("classic", "thermal"),
      meaning="Ramp behind the matrix. Magnitude reads from luminance, so both ramps stay readable "
              "without colour vision — a property the engine's selftest measures."),
    P("expression.chart.mode", "Chart bar mode", "Expression", "chart", kind="enum",
      choices=("default", "delta", "split", "heat", "wick"),
      meaning="How the Chart view expresses each bar. Split candles have no vendor equivalent and "
              "the Chart view says so in its legend rather than drawing something else."),
    P("expression.chart.palette", "Chart palette", "Expression", "chart", kind="enum",
      choices=("theme", "deutan", "protan", "tritan"),
      meaning="Colour vocabulary of the Chart view (candles, delta lane), independent of the shell "
              "theme."),
    # Depth heat behind the matrix
    P("atlas.heatmap.bucket_ms", "Bucket width", "Depth heat", "heatmap", minimum=100, maximum=10000,
      step=100, unit="ms", meaning="How much book time each depth column represents."),
    P("atlas.heatmap.max_columns", "History columns", "Depth heat", "heatmap", minimum=60,
      maximum=4000, step=20, meaning="Hard cap on depth columns the backend keeps for replay."),
    P("atlas.heatmap.upper_cutoff_pct", "Colour saturation", "Depth heat", "heatmap", minimum=0.5,
      maximum=25.0, step=0.5, unit="%", meaning="Top share of the visible book at which the ramp "
                                               "reaches full colour (the exchange convention)."),
    P("atlas.heatmap.wall_quantile", "Wall threshold", "Depth heat", "heatmap", minimum=0.5,
      maximum=1.0, step=0.01, meaning="Quantile of resting size that counts as a wall."),
    P("atlas.heatmap.stack_pct", "Stack detection", "Depth heat", "heatmap", minimum=1.0,
      maximum=10.0, step=0.1, unit="x", meaning="Growth over the level's own average that counts as "
                                                "liquidity stacking."),
    P("atlas.heatmap.pull_pct", "Pull threshold", "Depth heat", "heatmap", minimum=0.1, maximum=1.0,
      step=0.05, meaning="Fraction of a level that must disappear to count as a pull."),
    P("atlas.heatmap.pull_window_ms", "Pull window", "Depth heat", "heatmap", minimum=200,
      maximum=20000, step=100, unit="ms", meaning="Time window the pull is measured over."),
    # Tape and sweeps
    P("atlas.tape.big_quantile", "Big-print quantile", "Tape", "tape", minimum=0.5, maximum=1.0,
      step=0.01, meaning="Size quantile that marks a print as big in the tape colouring."),
    P("atlas.tape.big_min_size", "Big-print floor", "Tape", "tape", minimum=0.0, maximum=1000.0,
      step=0.001, meaning="Absolute floor so thin instruments do not mark everything big."),
    P("atlas.tape.block_multiple", "Block multiple", "Tape", "tape", minimum=1.0, maximum=50.0,
      step=0.5, unit="x", meaning="Multiple of the median print size that marks a block trade."),
    P("atlas.tape.sweep_levels", "Sweep levels", "Sweeps", "tape", minimum=2, maximum=50, step=1,
      meaning="Levels a single burst must cross to count as a sweep."),
    P("atlas.tape.sweep_max_ms", "Sweep window", "Sweeps", "tape", minimum=10, maximum=2000, step=10,
      unit="ms", meaning="Maximum time for those levels to be crossed."),
    P("atlas.tape.sweep_min_size", "Sweep size floor", "Sweeps", "tape", minimum=0.0, maximum=1000.0,
      step=0.001, meaning="Total size a burst needs before it is reported."),
    P("atlas.tape.sweep_min_aggressors", "Sweep aggressors", "Sweeps", "tape", minimum=1, maximum=20,
      step=1, meaning="Distinct aggressive prints required — 1 accepts a single large order."),
    P("atlas.tape.sweep_min_range_ticks", "Sweep range", "Sweeps", "tape", minimum=0.0,
      maximum=200.0, step=0.5, unit="ticks", meaning="Price distance the burst must cover."),
    P("atlas.tape.iceberg_min_fills", "Iceberg fills", "Sweeps", "tape", minimum=2, maximum=100,
      step=1, meaning="Refills at one price that suggest a hidden order."),
    P("atlas.tape.iceberg_min_total", "Iceberg total", "Sweeps", "tape", minimum=0.0, maximum=10000.0,
      step=0.01, meaning="Cumulative size those refills must reach."),
    P("atlas.tape.iceberg_min_duration_s", "Iceberg duration", "Sweeps", "tape", minimum=0.0,
      maximum=3600.0, step=1.0, unit="s", meaning="How long the refills must persist."),
    P("atlas.tape.stoprun_ticks", "Stop-run distance", "Sweeps", "tape", minimum=1.0, maximum=500.0,
      step=1.0, unit="ticks", meaning="Move against the book that marks a stop run rather than a sweep."),
    P("atlas.tape.stoprun_ms", "Stop-run window", "Sweeps", "tape", minimum=100, maximum=20000,
      step=100, unit="ms", meaning="Time window for that move."),
    P("atlas.tape.stoprun_min_volume", "Stop-run volume", "Sweeps", "tape", minimum=0.0,
      maximum=10000.0, step=0.01, meaning="Volume the run must carry."),
    P("atlas.tape.stoprun_min_prints", "Stop-run prints", "Sweeps", "tape", minimum=1, maximum=200,
      step=1, meaning="Prints the run must contain."),
    P("atlas.tape.reassembly_ms", "Out-of-order window", "Tape", "tape", minimum=0, maximum=2000,
      step=10, unit="ms", meaning="How long trades may be buffered to reassemble venue ordering."),
    P("atlas.tape.zone_ticks", "Zone width", "Tape", "tape", minimum=1.0, maximum=5000.0, step=1.0,
      unit="ticks", meaning="Price band used to group prints into a zone."),
    # CVD
    P("atlas.cvd.bucket_ms", "CVD bucket", "CVD", "cvd", minimum=500, maximum=60000, step=500,
      unit="ms", meaning="Time bucket for the CVD series."),
    P("atlas.cvd.divergence_lookback", "Divergence lookback", "CVD", "cvd", minimum=4, maximum=200,
      step=1, unit="bars", meaning="Bars compared when looking for price/flow disagreement."),
    P("atlas.cvd.divergence_min_ticks", "Divergence distance", "CVD", "cvd", minimum=0.0,
      maximum=500.0, step=0.5, unit="ticks", meaning="Minimum price distance for a divergence to count."),
    P("atlas.cvd.pro_min_size", "CVD Pro band from", "CVD", "cvd", minimum=0.0, maximum=10000.0,
      step=0.001, meaning="Lower size of the CVD Pro band (0 disables the band)."),
    P("atlas.cvd.pro_max_size", "CVD Pro band to", "CVD", "cvd", minimum=0.0, maximum=10000.0,
      step=0.001, meaning="Upper size of the CVD Pro band; equal to the floor means no band."),
    P("atlas.cvd.pro_bands", "CVD Pro bands", "CVD", "cvd", kind="list",
      meaning="Up to five size buckets tracked side by side in the Pro view."),
    # Profile / value area
    P("atlas.market_profile.bracket_minutes", "Profile bracket", "Profile", "profile", minimum=5,
      maximum=1440, step=5, unit="min", meaning="Trades per profile bracket for the market profile view."),
    P("atlas.market_profile.value_area_pct", "Profile value area", "Profile", "profile", minimum=0.5,
      maximum=0.95, step=0.05, meaning="Value-area share used by the profile view (separate from the "
                                       "engine's own VA)."),
    # Imbalance detector
    P("atlas.imbalance.rate_pct", "Imbalance rate", "Imbalance", "orderflow", minimum=100.0,
      maximum=1000.0, step=10.0, unit="%", meaning="Bid/ask ratio that flags a book imbalance."),
    P("atlas.imbalance.window_s", "Imbalance window", "Imbalance", "orderflow", minimum=10, maximum=3600,
      step=10, unit="s", meaning="Rolling window the ratio is measured over."),
    P("atlas.imbalance.min_volume", "Imbalance volume", "Imbalance", "orderflow", minimum=0.0,
      maximum=10000.0, step=0.001, meaning="Minimum resting size before an imbalance is reported."),
    P("atlas.imbalance.min_levels", "Imbalance levels", "Imbalance", "orderflow", minimum=1, maximum=50,
      step=1, meaning="Levels that must be imbalanced together."),
    # VWAP
    P("atlas.vwap.window_s", "VWAP window", "VWAP", "vwap", minimum=300, maximum=604800, step=300,
      unit="s", meaning="Window for the rolling VWAP."),
    P("atlas.vwap.bands", "VWAP sigma bands", "VWAP", "vwap", kind="list",
      meaning="Standard-deviation bands drawn either side of VWAP."),
    P("atlas.vwap.cross_min_ticks", "Cross distance", "VWAP", "vwap", minimum=0.0, maximum=100.0,
      step=0.5, unit="ticks", meaning="Distance from VWAP that counts as a decisive cross."),
    # Footprint (Numbers-Bars pack)
    P("atlas.footprint.min_print_size", "Min print size", "Footprint", "ofx", minimum=0.0,
      maximum=1000.0, step=0.001, meaning="Prints below this are ignored while building bars (0 keeps "
                                          "every print)."),
    P("atlas.footprint.imbalance_mode", "Imbalance mode", "Footprint", "ofx", kind="enum",
      choices=("same_price", "diagonal", "both"),
      meaning="Which comparison flags an imbalance: the same price across bars, the diagonal inside "
              "the bar, or both."),
    P("atlas.footprint.imbalance_threshold", "Imbalance threshold", "Footprint", "ofx", minimum=0.0,
      maximum=50.0, step=0.5, unit="x", meaning="Ratio used by the Numbers-Bars pack."),
    P("atlas.footprint.equal_tolerance", "Equal tolerance", "Footprint", "ofx", minimum=0.0,
      maximum=10.0, step=0.1, meaning="Difference treated as equal when the tolerance itself is shown."),
    P("atlas.footprint.show_equal", "Show equal ticks", "Footprint", "ofx", kind="bool",
      meaning="Mark rows where bid and ask are within tolerance."),
    P("atlas.footprint.show_extremes", "Show extremes", "Footprint", "ofx", kind="bool",
      meaning="Mark the bar's extreme bid/ask rows."),
    # Dots
    P("atlas.dots.window_ms", "Dots window", "Dots", "chart", minimum=10000, maximum=3600000, step=10000,
      unit="ms", meaning="Time span the dot layer covers."),
    P("atlas.dots.cluster_ms", "Dots clustering", "Dots", "chart", minimum=50, maximum=5000, step=50,
      unit="ms", meaning="Prints within this span merge into one dot (the 'smart' clustering knob)."),
    P("atlas.dots.min_size", "Dots size floor", "Dots", "chart", minimum=0.0, maximum=1000.0,
      step=0.001, meaning="Smallest aggregate that still draws a dot."),
    # Trackers
    P("atlas.correlation.bucket_ms", "Correlation bucket", "Correlation", "trackers", minimum=1000,
      maximum=3600000, step=1000, unit="ms", meaning="Bucket width for return correlation."),
    P("atlas.correlation.window", "Correlation window", "Correlation", "trackers", minimum=10,
      maximum=2000, step=10, unit="buckets", meaning="How many buckets of returns the correlation is "
                                                     "measured over."),
    P("atlas.correlation.min_samples", "Correlation samples", "Correlation", "trackers", minimum=3,
      maximum=500, step=1, meaning="Minimum overlapping buckets before a pair is ranked."),
    P("atlas.correlation.top", "Correlation rows", "Correlation", "trackers", minimum=1, maximum=50,
      step=1, meaning="How many pairs the tracker shows."),
    P("atlas.detector.min_share", "Detector share", "Trade detector", "trackers", minimum=0.0,
      maximum=1.0, step=0.05, meaning="Share of a level that must be eaten to flag an execution."),
    P("atlas.detector.size_mult", "Detector size", "Trade detector", "trackers", minimum=1.0,
      maximum=100.0, step=0.5, unit="x", meaning="Size multiple of the median print."),
    P("atlas.detector.resting_mult", "Detector resting", "Trade detector", "trackers", minimum=1.0,
      maximum=100.0, step=0.5, unit="x", meaning="Resting multiple the level must have held."),
    P("atlas.detector.refill_pct", "Refill threshold", "Trade detector", "trackers", minimum=0.1,
      maximum=1.0, step=0.05, meaning="Fraction of the eaten level that must come back to count a refill."),
    P("atlas.detector.refill_ms", "Refill window", "Trade detector", "trackers", minimum=100,
      maximum=60000, step=100, unit="ms", meaning="Time allowed for that refill."),
    P("atlas.intent.levels", "Intent levels", "Intent", "trackers", minimum=1, maximum=50, step=1,
      meaning="Book levels weighed when reading participants' intent."),
    P("atlas.intent.decay", "Intent decay", "Intent", "trackers", minimum=0.5, maximum=20.0, step=0.5,
      meaning="Distance weighting across those levels."),
    P("atlas.intent.threshold_pct", "Intent threshold", "Intent", "trackers", minimum=50.0,
      maximum=100.0, step=1.0, unit="%", meaning="Confidence needed before an intent reading is shown."),
    P("atlas.intent.training_min", "Intent training", "Intent", "trackers", minimum=1, maximum=120,
      step=1, unit="min", meaning="Minutes of book behaviour used to calibrate the weighting."),
    P("atlas.intent.absorb_window_s", "Absorption window", "Intent", "trackers", minimum=1.0,
      maximum=300.0, step=1.0, unit="s", meaning="Window for absorption detection."),
    P("atlas.intent.absorb_ref_ticks", "Absorption depth", "Intent", "trackers", minimum=1.0,
      maximum=200.0, step=1.0, unit="ticks", meaning="How deep an absorbed level must be."),
    P("atlas.intent.spoof_near_ticks", "Spoof distance", "Intent", "trackers", minimum=1.0,
      maximum=200.0, step=1.0, unit="ticks", meaning="Distance from the touch that counts as 'near'."),
    P("atlas.intent.spoof_size_mult", "Spoof size", "Intent", "trackers", minimum=1.0, maximum=100.0,
      step=0.5, unit="x", meaning="Size multiple that marks a suspect order."),
    P("atlas.intent.trap_ticks", "Trap distance", "Intent", "trackers", minimum=0.5, maximum=100.0,
      step=0.5, unit="ticks", meaning="Move that traps the side that chased."),
    P("atlas.intent.trap_window_s", "Trap window", "Intent", "trackers", minimum=5.0, maximum=3600.0,
      step=5.0, unit="s", meaning="Time window for the trap."),
    P("atlas.intent.trap_reclaim_s", "Trap reclaim", "Intent", "trackers", minimum=1.0, maximum=600.0,
      step=1.0, unit="s", meaning="Time allowed to reclaim the level before the trap is confirmed."),
    # Scanner and risk
    P("atlas.scanner_window_s", "Scanner window", "Scanner", "scanner", minimum=60, maximum=86400,
      step=60, unit="s", meaning="Rolling window the cross-instrument ranking is computed over."),
    P("risk.signal_cooldown_seconds", "Signal cooldown", "Signals", "signals", minimum=0.0,
      maximum=3600.0, step=5.0, unit="s", meaning="Minimum time between two signals from one detector."),
    P("risk.min_composite_score", "Minimum score", "Signals", "signals", minimum=0.0, maximum=100.0,
      step=1.0, meaning="Composite strength a signal needs before it is surfaced."),
    # Non-atlas display switches
    P("atlas.extras_enabled", "Extra Bybit streams", "Data", "instruments", kind="bool",
      applies="restart", meaning="200-level book, liquidations and block-trade flags. Turning these off "
                                 "cuts bandwidth and memory."),
    P("studies.data_box", "Study data box", "Studies", "studies", kind="bool",
      meaning="Show the values box on the chart for active studies."),
    P("search.default_view", "Enter lands on", "Search", "overview", kind="enum",
      choices=("overview", "chart", "heatmap", "orderflow", "ofx", "depth", "tape", "cvd", "profile",
               "frames", "scanner", "trackers", "signals"),
      meaning="Where the command palette takes you when you press Enter on a symbol."),
    # Trade audio — the tape you can hear. The Tape view owns these because prints are what they
    # speak about; the master switch is off until it is turned on here.
    P("audio.enabled", "Trade audio", "Audio", "tape", kind="bool",
      meaning="Play a sound for qualifying prints on the active instrument. Off by default."),
    P("audio.volume", "Volume", "Audio", "tape", minimum=0.0, maximum=1.0, step=0.05,
      meaning="Master gain, applied on top of the overlap attenuation."),
    P("audio.min_size", "Min print size", "Audio", "tape", minimum=0.0, maximum=1_000_000.0,
      step=0.001, unit="base", meaning="Prints smaller than this stay silent. 0 = every print the "
                                       "feed publishes (the tick channel is throttled to 5/s)."),
    P("audio.hard_multiple", "Hard alert at", "Audio", "tape", minimum=1.0, maximum=50.0, step=0.5,
      unit="x", meaning="A print at least this multiple of the minimum plays the two-tone alert "
                        "instead of the single blip."),
    P("audio.hard_enabled", "Two-tone alert", "Audio", "tape", kind="bool",
      meaning="Use the loud sample for oversized prints at all."),
    P("audio.active_symbol_only", "Symbol box only", "Audio", "tape", kind="bool",
      meaning="Follow the selected instrument rather than every enabled one — the desk hears what "
              "it is looking at."),
    P("audio.overlap_window_ms", "Overlap window", "Audio", "tape", minimum=0, maximum=5000, step=5,
      unit="ms", meaning="A retrigger inside this window is attenuated rather than stacked."),
    P("audio.overlap_floor", "Overlap floor", "Audio", "tape", minimum=0.01, maximum=1.0, step=0.01,
      meaning="Quietest share of full gain the attenuation can reach."),
)

BY_PATH: dict[str, Param] = {p.path: p for p in PARAMS}


# ── reading values out of a config ────────────────────────────────────────────────────────


def _walk(cfg: dict[str, Any], path: str) -> tuple[bool, Any]:
    node: Any = cfg
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return False, None
        node = node[part]
    return True, node


def current(cfg: dict[str, Any], param: Param) -> Any:
    """The live value of a registered variable, or None when the config does not carry it."""
    found, value = _walk(cfg, param.path)
    return value if found else None


def groups() -> dict[str, list[Param]]:
    """The table grouped the way dialogs render it: {group: [params in table order]}."""
    out: dict[str, list[Param]] = {}
    for param in PARAMS:
        out.setdefault(param.group, []).append(param)
    return out


def for_view(view: str) -> list[Param]:
    """The variables whose owning view is this one (an empty list is a valid answer)."""
    return [p for p in PARAMS if p.view == view]


def tree() -> dict[str, list[str]]:
    """Group → paths, for menus that only need structure."""
    return {group: [p.path for p in params] for group, params in groups().items()}


def dump(cfg: dict[str, Any], defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    """The whole registry with live values (and defaults when a default config is supplied)."""
    defaults = defaults or {}
    return {
        "ok": True,
        "count": len(PARAMS),
        "groups": {group: [p.as_dict(current(cfg, p), current(defaults, p)) for p in params]
                   for group, params in groups().items()},
        "views": sorted({p.view for p in PARAMS}),
    }
