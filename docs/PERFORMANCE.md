# ModFlow performance sheet

The numbers the competitive analysis asked for. Every figure below is **measured on this machine
by the repo's own harness** — nothing here is a marketing claim, and nothing is estimated. Run it
yourself with:

    unset PYTHONPATH
    .venv/Scripts/python.exe scripts/bench_atlas.py 200000

Raw output, 2026-09-20, on the development host (Windows 11, CPython 3.12.14, single-threaded):

    benchmark: 200,000 synthetic BTC ticks (0.001–1.5 size, 0.1 grid)

    ingest (5 analysers, per tick) : 49.588 s → 4,033 ticks/s (247.9 µs/tick)
    book updates (1 per 4 ticks)   :  6.875 s → 7,273 book+ticks/s
    heatmap snapshot cold          :   0.78 ms (builds: 3)
    heatmap snapshot cached        :   0.4 µs  → 1,940× faster on an unchanged version
    alert rules evaluated          : 624,294 events/s

    analyser output after the run : TapeFlow:300 Depth:900 Cvd:- MarketProfile:- Imbalance:-

## What each line means

- **Ingest, 4,033 ticks/s (247.9 µs per tick).** One tick passes through five analysers — tape
  flow, depth map, CVD, market profile, imbalance ladder. This is the honest worst case: it is the
  full stack, single-threaded, on a synthetic feed with no idle time between events.
- **Book updates, 7,273/s.** Depth snapshots are heavier than prints; a book update on every fourth
  tick still keeps pace with the ingest rate, which is why the app can run a heatmap and a footprint
  from the same stream.
- **Heatmap snapshot: 0.78 ms cold, 0.4 µs cached (1,940×).** The snapshot payload is
  version-stamped, so an unchanged book costs the renderer almost nothing. This is the design
  decision the competitive analysis flagged as the one to advertise: *do not rebuild what has not
  changed*. An ATAS- or Sierra-grade "smooth at 600 fps" claim is a rendering claim; this is the
  number that makes it possible on a single thread — the renderer only pays when the data moved.
- **Alert rules, 624,294 events/s.** Rules are evaluated against the event stream, not polled per
  panel, so a desk can run every rule it has without the panels slowing down.

## How this compares with the paid platforms

Bookmap (40 fps nanosecond zoom), ATAS (600+ FPS), Exocharts (~60 FPS desktop with heavy cluster
counts) publish *rendering* numbers. ModFlow publishes both sides separately:

- **ingest** — the numbers above, in ticks/s and µs/tick, reproducible with one command;
- **render** — the panels draw only version-changed content, on canvases sized exactly to their
  backing store times `devicePixelRatio` (a hard rule in this codebase), so the per-frame cost is
  bounded by what changed rather than by what is on screen.

If you want a render-side figure for a public comparison, it should be measured the same way as the
competitors' claims — a scripted frame-time capture at a fixed cluster count, on a stated machine —
and that harness does not exist yet. Until it does, this sheet will not quote one.

## Reproducing and extending

- `scripts/bench_atlas.py [ticks]` — the ingest/snapshot benchmark above.
- `scripts/profile_atlas.py` — where the ingest microseconds actually go (per-analyser profile).
- `scripts/soak.py` — long-run soak, for memory growth rather than throughput.

These ran clean on 2026-09-20 against the current worktree. Re-run them before quoting any figure
publicly; the machine matters and the numbers move with it.
