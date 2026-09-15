# Use cases — what to actually do with ModFlow OrderFlow Analysis Suite

Nine scenarios, each with the setup, what you watch, and what would make the read
wrong. Everything here works with public data and no account; nothing in this
program places an order.

**Before any of them:** start the engine (two or three instruments you actually
watch), give the heatmap a minute to build, and make sure the tape is live. A
scenario read on a stale screen is a guess.

---

## 1. Absorption at a level that matters — "who is eating the sellers?"

**Setup** — Heatmap on, overlays: bubbles + walls. Order Flow view beside it. Alerts:
*Stacked imbalance ≥3 levels* and *Big trade* routed to ntfy.

**Watch** — price arrives at a large resting bid wall, prints keep hammering it, and
the wall does not fall. Footprint shows one price level with heavy volume and almost
no downward progress; CVD flattens while price stops falling.

**Read** — a passive buyer is absorbing aggression. The level is the reference: a
reaction is expected while it holds, and a break of it (wall pulled, price through)
invalidates the whole idea.

**Invalidation** — the wall disappears from the heatmap (pulled) or price closes
through it with rising sell volume.

---

## 2. Stop run — "the move that ends the move"

**Setup** — Trackers view (stop runs + liquidations), Stop run alert routed to phone.

**Watch** — a fast, wide move with a burst of prints and rising volume z-score, often
with liquidation prints on the same side. The detector reports *direction*,
*ticks moved*, *volume* and *prints*.

**Read** — forced exits tend to exhaust: the tape is dominated by panic rather than
by new positioning. This is a fade scenario — price often reverts to the origin of
the run once the burst stops.

**Invalidation** — volume keeps *rising* after the burst, or the run continues into
fresh prices on follow-through volume. Then it is repricing, not a stop run.

---

## 3. Sweep and reclaim — liquidity grab at an obvious level

**Setup** — Heatmap with the wall table; Trackers with sweeps.

**Watch** — price sweeps several levels in under a second, then stalls inside
30–60 seconds without holding the swept extreme.

**Read** — liquidity was taken, not repriced. If CVD does not follow the sweep
direction, the sweep was buy-side/sell-side noise rather than a real break.

**Invalidation** — price holds beyond the swept level and the heatmap shows new
resting size building there (acceptance, not a grab).

---

## 4. Block trade at the session open — institutional print detection

**Setup** — Alerts: *Block trade* (critical) to ntfy/Telegram; Overview open.

**Watch** — a single print several times the big-trade threshold, or fragmented
prints reassembled into one (the tape reports `reassembled` / `fragments`).

**Read** — in the first minutes of a session, size prints are usually execution of
intent, not noise. Direction (buy/sell aggressor) at a level that then holds is the
check.

**Invalidation** — the print sits in the middle of a range with no reaction and no
follow-through; size alone is not information.

---

## 5. Delta divergence — price lies, delta does not

**Setup** — CVD view (with the Market pressure panel), *CVD divergence* alert.

**Watch** — price makes a new high while CVD makes a lower high (bearish), or a new
low while CVD makes a higher low (bullish). The divergence list timestamps each one.

**Read** — buyers are not behind the new high: participation is thinning.

**Invalidation** — divergence appears *during* a fast trend without any loss of
speed in the tape; trends can diverge for a long time before they turn.

---

## 6. Reading the book before it moves — stack vs pull

**Setup** — Heatmap with stack/pull events; wall table sorted by size.

**Watch** — *stack*: resting size grows quickly at a level near price. *pull*: size
vanishes. Both are reported with size and distance from price.

**Read** — a stack near price is a magnet/target; a pull near price removes the
brake, so expect travel in the direction of least resistance.

**Invalidation** — stacking that price then walks straight through (spoofed or
absorbed), or a pull that reappears within seconds.

---

## 7. Session review by replay — "re-run my worst hour"

**Setup** — Replay view: instrument, source *recorded ticks* (this app's own
history) or *exchange tape*, window of minutes-ago, speed 0.5×–10×.

**Watch** — the heatmap, trackers, CVD and profile rebuild exactly as they did
live, and you can pause and scrub.

**Read** — compare what the screen said at the moment you acted with what the
detectors say now. The journal in Performance shows your logged signals.

**Notes** — recorded replay needs the engine to have been running; the exchange-tape
source works on any machine with no local history.

---

## 8. Only the instruments that deserve attention — alerts that page you

**Setup** — Alerts: per-rule channel ticks (ntfy for the fast stuff, email for the
daily stuff, webhook for automation). Global on/off in Settings.

**Watch** — ntfy arrives with severity-coded priority (urgent for block/stop runs,
high for sweeps), sound in-app, everything logged in Alerts with durable history.

**Read** — anything that is not worth waking up for stays `ui`-only. A rule that
fires more often than you act on it is a rule you should tune (cooldown, threshold)
or switch off.

**Verification** — the Test button in Setup/Alerts sends a real message; if the phone
stays silent, the channel is the problem, not the rule.

---

## 9. Cross-instrument context — "is it BTC or is it the market?"

**Setup** — stream three majors; Overview with the Market context card; switch
instruments with the selector.

**Watch** — funding rate and open interest on the instrument you are trading,
long/short account ratio (crowd positioning), Fear & Greed, plus headlines.

**Read** — a move that is broad (all three instruments, funding flipping, OI rising)
is a market move; one instrument with flat funding and falling OI is more likely
local flow. Extreme long/short with rising OI is crowded positioning — the fuel for
scenario 1 or 2 in the opposite direction.

**Invalidation** — headlines and sentiment lag; they explain context, they do not
time entries.

---

## Where each scenario lives in the app

| Scenario | Views | Rules that matter |
|---|---|---|
| 1 Absorption | Heatmap, Order Flow, CVD | Stacked imbalance, Big trade |
| 2 Stop run | Trackers, CVD | Stop run, Liquidation |
| 3 Sweep & reclaim | Heatmap, Trackers, CVD | Sweep ≥5 levels |
| 4 Block trade | Alerts, Overview, Time & Sales | Block trade |
| 5 Delta divergence | CVD | CVD divergence |
| 6 Stack vs pull | Heatmap | Liquidity stacking / pulled |
| 7 Replay | Replay, Performance | — (manual review) |
| 8 Alerting | Alerts, Settings, Guide | all, per-rule channels |
| 9 Cross-instrument | Overview (Market context) | — (context only) |

## Keeping score

The Performance view is where a scenario earns or loses its keep: signals are
journaled with entry/stop/targets and outcome. A scenario that keeps showing up in
the journal without a follow-through is a scenario to stop acting on — or a
threshold to tighten. Nothing here is advice; the journal is the only evidence that
matters, and it is yours.


## 10. Reading intent: what the book shows before the chart moves

The chart tells you what happened. The book tells you what the people who are about
to move have already committed to. The Participants' intent card on the Overview is
that read, assembled from four book facts that are true before the move appears.

**Setup.** Engine running on one instrument. The card needs about five minutes of
book history before its percentages mean anything — that is the reference layout's own training
period, and the card counts it down for you. Nothing it says during training is
worth acting on, which is why it says "training" out loud.

**What to watch.**

| Panel | The read |
|-------|----------|
| Book pressure | Weighted liquidity within the top levels, expressed as a percentage of *this instrument's own recent normal*. 80%+ means somebody has committed size at the touch. During training the number is meaningless. |
| Absorption | Aggression that fails to move price. Buyers hammering and price not rising = sellers absorbing. Buyers hammering and price *falling* is the strongest version of the same read. |
| Depth change | Whether size near price is being added or withdrawn, per side. Rising bids with flat price is support being built; bids thinning under price is a floor being removed. |
| Tape quality | How prints arrived: at the bid, at the ask, inside the spread, or through the touch. Prints that trade through the ladder ("slippage") mean the passive side was not there to meet them. |
| Pulled size | Large orders that appeared near price and disappeared without being traded. One is noise; a cluster on the same side is information. |
| Trapped side | A level that gave way, then was reclaimed. Whoever chased the break is now on the wrong side of it. |

**Reading it as a sentence.** The verdict line states, in plain words, what the four
facts add up to, and names the level that matters — for example: *"book pressure
favours buyers (93% vs 73% of normal); buyers absorbing sellers (score 15.1); last
pull 0.526 on the bid 6.5 ticks away; shorts trapped at 78656.2 (10s ago)"*.

**What would make the read wrong.** Thin books lie: on a quiet Sunday evening a
five-order wall is a real wall, and during a data burst it is nothing. Public feeds
give no order identities, so "pulled size" and "trapped" are *inferences from
behaviour*, not confirmed participants — the card labels them as such. Deep-book
updates arrive at 100 ms, so tape classification against a book older than 1.5 s is
discarded rather than guessed at. And any read built on the top ten levels is a
statement about the top ten levels: liquidity can be hiding behind them.

**Alerting.** `intent_pressure`, `pulled_size` and `trapped_traders` are off for
external channels by default and on for the in-app log — the card is a context
panel, not an entry signal. Route them to Telegram/ntfy/email if you want to be told
when they fire; the cooldowns on those rules are what keep a busy tape from becoming
a pager.
