# Golden features

Three reads set this suite apart from the usual indicator rack. None of them is a single study
sitting on a chart — each is a piece of machinery that watches the whole board, keeps score, and
says what it sees in plain words. They run on every instrument the app streams, over the free
public feeds, with no account required.

If you read one file in this repository, read this one: it explains what the rest of the program
is arranged around.

---

## 1. The level radar — every level, tracked from armed to spent

Most order-flow tools alert you to *events*: a big trade, a sweep, an absorption print. This suite
goes one level up. **It treats every level as an object with a lifecycle**, and tracks it across
the whole watchlist at once:

- **Armed** — the level is registered: a point of control, a double or triple node, an
  unfinished-auction extreme, a virgin POC, a weekly or monthly POC, a VWAP band, a
  stacked-imbalance zone, or a level you boxed on the Engine and watched yourself.
- **Approaching** — price comes into range; the level is live now.
- **Defended** — price tests it and turns away. When it is the level's first test, the alert says
  so: *"held — first test"*.
- **Confirmed** — a level two or more independent sources agree on, held. The strongest version
  of the read.
- **Spent** — price traded straight through without holding. The level is done; it dims and
  expires instead of calling you back.
- **Failed** — it held once and broke later. The classic second-test break, named for what it is.

The state lives in the **Scanner's Radar column**, so "what is arming where" is one glance across
your instruments — the question most tools make you answer nine windows at a time. Transitions
arrive as sentences in the alerts, through the same machinery every rule uses:

> `BTCUSDT: node level 76950.0 held — first test`
> `BTCUSDT: unfinished level 76930.5 spent — traded through`

![The Radar column on the Scanner](screenshots/level-radar.png)

## 2. The area volume profile — box anything, profile it, watch it

Classic volume profiles are fixed to a session. Here, **any region you drag on the Engine becomes
a profile**: volume-at-price over exactly that window, with its POC, VAH and VAL drawn on the
chart, a histogram and the headline numbers in the selection strip, and the full rows exported to
CSV alongside the raw bars.

The part no chart study closes: press **Watch this level** and the profile's point of control
becomes a tracked level — radar state, alerts, the lot. Box the trend leg and watch its cluster.
Box the rotation and watch its heavy line. The gesture-to-alert loop is one button.

![An area volume profile boxed on the Engine](screenshots/area-volume-profile.png)

## 3. Unfinished business and node persistence — the precision reads

Two reads borrowed from the professional numbers-bar toolchains, computed live on every feed this
program carries:

- **Unfinished business.** A high that never finished its auction — nothing traded on the bid at
  the extreme — is an imperfection the market tends to revisit. The suite detects these
  automatically, draws them as magnets, and clears each line the moment price returns and fixes
  it. It is a futures-grade read, rare outside paid toolchains.
- **Node persistence.** When consecutive bars agree on the same high-volume price — a double,
  then a triple node — that is repeat acceptance, and it is drawn as a band rather than a line.
  Alert rules can watch for a run to form at all.

Both feed the radar, so an unfinished magnet is just another lifecycle to track.

---

## How the pieces fit together

The reading order the program is built around:

**Profile first** (the session's shape and heavy prices — the bias), **then choose one level**
(POC, node, magnet, band), **then wait for order flow at that level** (absorption, a wall
holding, a failed break), and **trade a level once** — the first test carries the edge, and the
radar keeps that count for you.

That order is not folklore sprinkled through the UI; it is the education layer. The Help Centre
ships a whole group on it — the reading order, the confirmations and the side convention,
first-test discipline, the level sources, the radar states, and the VWAP band playbook — and the
setup guide points at each surface when setup is done.

## Under it all

The engines behind these reads are pure and deterministic, pinned by the test suite: the same
radar maths that runs live also runs over recorded data in tests, so the states you see are the
states that were verified. Everything computes locally from public market data — no cloud, no
account, no vendor data subscription.
