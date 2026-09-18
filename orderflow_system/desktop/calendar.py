"""The economic calendar — this week's and next week's scheduled releases, keyless, from one host.

A footprint, a delta/CVD chart and a volume profile all read the same bars as though price moved only
because of what is inside them. It does not: at 14:30 the number a whole market was positioned for
lands, and the geometry of the book stops meaning what it meant a minute earlier — that delta flip is
a reaction to data, not to the order flow that preceded it. The panel this module feeds exists so an
analyst (and the alert path) knows when the clock is about to strike.

* **Keyless, deliberately.** ``FEED_URLS`` are the host's rolling weekly files — plain JSON, no API
  key, no account, no per-minute quota to babysit and no token that expires at 03:00 while the app is
  the only thing running. Two files are the whole calendar a desktop panel needs: fetch both, keep
  the union (the boundary week appears in both, which is why dedupe lives here and not in a caller).
* **One normalised shape, in UTC milliseconds.** The feed stamps carry an offset
  (``2026-09-18T08:30:00-04:00``) and its rows are loose: any field may be missing, empty or
  ``null``, a holiday is an ordinary row with an impact of ``Holiday``, and a date that cannot be
  parsed means *that row* is skipped — never that the feed is. Normalising to epoch milliseconds
  here means the engine, the alert line and the browser compare the same integer.
* **A cache that states its age.** The feed is a third party's server, and a desktop app polling it
  every few minutes is asking to be throttled — measured from this machine, a burst of requests is
  answered with HTTP 429. A cache younger than ``ttl_s`` (4 h by default) is served without touching
  the wire; when a fetch does run and fails, the last good calendar comes back with ``stale: True``
  and the failure in ``error`` — a calendar that was right four hours ago beats an empty panel, but
  it has to say so. Pass ``ttl_s=0`` to force a fetch.
* **A declared User-Agent on the default transport.** Measured here: the bare urllib agent is served
  HTTP 403 by this host, the declared one below is not. It lives in exactly one constant and every
  default request carries it — the same lesson ``desktop/edgar.py`` learned about sec.gov.
* **Pure where it can be.** ``impact_rank``, ``upcoming``, ``due_alerts`` and ``event_message`` are
  pure functions over normalised events, so window / impact / currency behaviour and the once-only
  alert key are pinned without a socket. The one impure seam is ``opener`` — ``opener(url, timeout)
  -> bytes``, :func:`_declared_urlopen` (``urllib.request.urlopen`` with ``APP_USER_AGENT``) by
  default — which is why this module's gate, ``orderflow_system/test_calendar.py``, never touches
  the wire.
* **Nothing raises out of here.** A timeout, an HTTP error, a body that is not JSON, a cache file
  full of half-written rubbish: each comes back as ``ok: False`` (or a stale payload) plus a sentence
  in ``error``, because a panel is a panel.

Headless use, for a smoke test or a log line:

    python -m orderflow_system.desktop.calendar --hours 48 --min-impact medium
"""

from __future__ import annotations

import argparse
import json
import logging
import tempfile
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence

logger = logging.getLogger(__name__)

#: The host's rolling weekly pair: this week and next week. Both are fetched and merged because the
#: same event appears in each file near the boundary — dedupe (below) is what makes the union exact.
FEED_URLS: tuple[str, str] = (
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
    "https://nfs.faireconomy.media/ff_calendar_nextweek.json",
)

#: The network seam: ``opener(url, timeout=...)`` returning a body (bytes, or a readable response).
Opener = Callable[..., Any]

#: What leaves this machine when no opener is injected. Measured: the bare urllib agent is served
#: 403 by the host above, the declared one is not — one constant, every default request carries it.
APP_USER_AGENT = "ModFlow OrderFlow Analysis Suite (+https://moddys.net)"

#: A clock: ``datetime``, epoch seconds, or a callable returning either. ``None`` means "now".
Clock = Any

DEFAULT_TIMEOUT_S = 10.0
DEFAULT_TTL_S = 14400.0

#: The five words the rest of the app speaks. The feed's own spellings plus the ones a lazy row
#: tends to use; anything else — including an empty cell — is ``unknown``, never a guess.
_IMPACT_ALIASES = {
    "high": "high",
    "medium": "medium",
    "moderate": "medium",
    "med": "medium",
    "low": "low",
    "holiday": "holiday",
    "holidays": "holiday",
    "bank holiday": "holiday",
    "holliday": "holiday",
}

_IMPACT_RANKS = {"high": 3, "medium": 2, "low": 1, "holiday": 0, "unknown": 0}

#: What a cache file actually holds — the good fetch, without the transport-shaped extras.
_CACHE_KEYS = ("ok", "events", "error", "fetched_at_ms")

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_MS_PER_HOUR = 3_600_000
_MS_PER_MINUTE = 60_000


# ══════════════════════════════════════════════════════════════
# Values as the app wants them
# ══════════════════════════════════════════════════════════════

def _text(value: Any) -> str:
    """A feed value as the trimmed string the panel shows; ``None``, absent and blank all give ``""``."""
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _int_ms(value: Any) -> Optional[int]:
    """A value that should already be epoch milliseconds, or ``None`` if it is not one."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value.strip():
        try:
            return int(float(value.strip()))
        except ValueError:
            return None
    return None


def parse_at_ms(value: Any) -> Optional[int]:
    """A feed stamp as UTC epoch milliseconds, or ``None`` when it cannot be read.

    Accepts ISO 8601 with an offset (what the feed sends), a ``Z`` suffix, a bare stamp (read as
    UTC — the feed is a UTC-facing file), and plain epoch seconds or milliseconds.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return int(number if abs(number) >= 1e11 else number * 1000.0)
    text = _text(value)
    if not text:
        return None
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        try:
            return parse_at_ms(float(text))
        except ValueError:
            return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    delta = stamp.astimezone(timezone.utc) - _EPOCH
    return (delta.days * 86400 + delta.seconds) * 1000 + delta.microseconds // 1000


def normalise_impact(value: Any) -> str:
    """The feed's impact cell in the app's vocabulary: high | medium | low | holiday | unknown."""
    text = _text(value).lower()
    if text in _IMPACT_ALIASES:
        return _IMPACT_ALIASES[text]
    if "holiday" in text or "holliday" in text:
        return "holiday"
    return "unknown"


def impact_rank(impact: Any) -> int:
    """Ordering for ``min_impact`` filters: high 3, medium 2, low 1, holiday and unknown 0."""
    return _IMPACT_RANKS[normalise_impact(impact)]


def normalise_event(raw: Mapping[str, Any]) -> Optional[dict[str, Any]]:
    """One feed row in the app's shape, or ``None`` when its date cannot be read.

    The feed's ``country`` cell is the currency code; it is kept verbatim as ``country`` and
    upper-cased as ``currency`` (the field filters and display use).
    """
    at_ms = parse_at_ms(raw.get("date"))
    if at_ms is None:
        return None
    country = _text(raw.get("country"))
    return {
        "at_ms": at_ms,
        "currency": country.upper(),
        "impact": normalise_impact(raw.get("impact")),
        "title": _text(raw.get("title")),
        "country": country,
        "forecast": _text(raw.get("forecast")),
        "previous": _text(raw.get("previous")),
        "actual": _text(raw.get("actual")),
    }


def event_key(event: Mapping[str, Any]) -> str:
    """Stable identity of an event — ``currency|title|at_ms`` — the token ``alerted_keys`` holds."""
    at_ms = _int_ms(event.get("at_ms"))
    return f"{_text(event.get('currency')).upper()}|{_text(event.get('title'))}|{at_ms if at_ms is not None else 0}"


def _sort_key(event: Mapping[str, Any]) -> tuple[int, str, str]:
    """Time first (the documented order), then code and title so equal stamps are deterministic."""
    at_ms = _int_ms(event.get("at_ms"))
    return (
        at_ms if at_ms is not None else 0,
        _text(event.get("currency")).upper(),
        _text(event.get("title")).lower(),
    )


def _now_s(now: Clock) -> float:
    """Epoch seconds from the injected clock — ``None`` means now, a number is taken as seconds."""
    if now is None:
        return time.time()
    value = now() if callable(now) else now
    if isinstance(value, datetime):
        return value.timestamp()
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(
            f"now must be a datetime, epoch seconds, or a callable returning either, not {type(value).__name__}"
        )
    return float(value)


# ══════════════════════════════════════════════════════════════
# The fetch
# ══════════════════════════════════════════════════════════════

def fetch_events(
    *,
    opener: Optional[Opener] = None,
    now: Clock = None,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> dict[str, Any]:
    """Both weekly feeds, normalised, merged, deduped and sorted by time.

    Returns ``{"ok": bool, "events": [...], "error": str, "fetched_at_ms": int}``. ``ok`` is True as
    soon as one feed parsed — a single dead URL is reported in ``error`` without losing the other —
    and ``ok`` is False, with the exception text in ``error``, when nothing could be had.
    """
    try:
        return _fetch_events(opener=opener, now=now, timeout=timeout)
    except Exception as exc:  # the panel never sees a raise, whatever the opener or clock did
        logger.warning("calendar fetch failed: %s", exc)
        return _failure(exc)


def _fetch_events(*, opener: Optional[Opener], now: Clock, timeout: float) -> dict[str, Any]:
    fetched_at_ms = int(_now_s(now) * 1000.0)
    transport = opener if opener is not None else _declared_urlopen
    problems: list[str] = []
    merged: dict[str, dict[str, Any]] = {}
    for url in FEED_URLS:
        try:
            rows = _load_rows(transport, url, timeout)
        except Exception as exc:
            problems.append(f"{url}: {type(exc).__name__}: {exc}")
            logger.warning("calendar feed %s failed: %s", url, exc)
            continue
        for event in rows:
            key = event_key(event)
            kept = merged.get(key)
            if kept is None:
                merged[key] = event
            else:
                _fill_blanks(kept, event)
    events = sorted(merged.values(), key=_sort_key)
    error = " | ".join(problems)
    if problems and not events:
        return {"ok": False, "events": [], "error": error, "fetched_at_ms": fetched_at_ms}
    return {"ok": True, "events": events, "error": error, "fetched_at_ms": fetched_at_ms}


def _failure(exc: BaseException) -> dict[str, Any]:
    """The guaranteed-safe envelope: nothing parsed, the exception's own text as the reason."""
    return {
        "ok": False,
        "events": [],
        "error": f"{type(exc).__name__}: {exc}",
        "fetched_at_ms": int(time.time() * 1000.0),
    }


def _load_rows(opener: Opener, url: str, timeout: float) -> list[dict[str, Any]]:
    """One feed as normalised events; anything wrong is raised for the caller to report."""
    payload = json.loads(_read_body(opener(url, timeout=timeout)))
    if not isinstance(payload, list):
        raise ValueError(f"expected a JSON list of rows, got {type(payload).__name__}")
    rows: list[dict[str, Any]] = []
    skipped = 0
    for item in payload:
        event = normalise_event(item) if isinstance(item, dict) else None
        if event is None:
            skipped += 1
            continue
        rows.append(event)
    if skipped:
        logger.info("%s: skipped %d row(s) that were not events with a readable date", url, skipped)
    return rows


def _declared_urlopen(url: str, timeout: Optional[float] = None) -> Any:
    """The default transport: ``urlopen`` carrying :data:`APP_USER_AGENT` — a bare agent gets 403."""
    request = urllib.request.Request(
        url,
        headers={"User-Agent": APP_USER_AGENT, "Accept": "application/json"},
    )
    return urllib.request.urlopen(request, timeout=timeout)


def _read_body(response: Any) -> bytes:
    """Bytes out of whatever the opener handed back — ``urlopen``'s response, or bytes already."""
    if isinstance(response, (bytes, bytearray)):
        return bytes(response)
    reader = getattr(response, "read", None)
    if reader is None:
        raise TypeError(f"opener returned {type(response).__name__}, not bytes or a readable response")
    try:
        body = reader()
    finally:
        closer = getattr(response, "close", None)
        if callable(closer):
            closer()
    if isinstance(body, str):
        return body.encode("utf-8")
    if body is None:
        raise TypeError("opener response read() returned nothing")
    return bytes(body)


def _fill_blanks(kept: dict[str, Any], extra: Mapping[str, Any]) -> None:
    """A duplicate from the other weekly file may carry a value the first copy had not published."""
    for field in ("forecast", "previous", "actual"):
        if not _text(kept.get(field)) and _text(extra.get(field)):
            kept[field] = _text(extra.get(field))
    if kept.get("impact") in ("unknown", "") and extra.get("impact") not in (None, "unknown", ""):
        kept["impact"] = extra.get("impact")


# ══════════════════════════════════════════════════════════════
# The cache
# ══════════════════════════════════════════════════════════════

def fetch_events_cached(
    cache_path: str | Path,
    *,
    opener: Optional[Opener] = None,
    now: Clock = None,
    ttl_s: float = DEFAULT_TTL_S,
) -> dict[str, Any]:
    """``fetch_events`` with the last good result kept as JSON at ``cache_path``.

    A cache younger than ``ttl_s`` is served as-is (``stale: False``, no request sent); otherwise the
    feeds are fetched, and a successful fetch replaces the cache. When the fetch fails the last good
    calendar is returned with ``stale: True``, the failure in ``error`` and its age in
    ``cache_age_s`` — or, if there is no usable cache, an honest failure. Never raises.
    """
    path = Path(cache_path)
    try:
        return _fetch_cached(path, opener=opener, now=now, ttl_s=ttl_s)
    except Exception as exc:
        logger.warning("calendar cache path %s failed: %s", path, exc)
        return {**_failure(exc), "stale": False, "cache_age_s": None}


def _fetch_cached(path: Path, *, opener: Optional[Opener], now: Clock, ttl_s: float) -> dict[str, Any]:
    now_ms = int(_now_s(now) * 1000.0)
    cached = _read_cache(path)
    age_s = _cache_age_s(cached, now_ms)
    if cached is not None and age_s is not None and float(ttl_s) > 0 and age_s < float(ttl_s):
        logger.debug("calendar cache hit at %s (%.0f s old)", path, age_s)
        return {**cached, "ok": True, "stale": False, "cache_age_s": age_s}
    result = fetch_events(opener=opener, now=now)
    if result.get("ok"):
        _write_cache(path, result)
        return {**result, "stale": False, "cache_age_s": 0.0}
    if cached is not None:
        logger.warning("calendar fetch failed (%s); serving the cache at %s", result.get("error"), path)
        return {**cached, "stale": True, "error": result.get("error", ""), "cache_age_s": age_s}
    return {**result, "stale": False, "cache_age_s": None}


def _read_cache(path: Path) -> Optional[dict[str, Any]]:
    """The stored payload, or ``None`` for anything that is not a calendar result."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        payload = json.loads(text)
    except ValueError:
        logger.warning("calendar cache at %s is not JSON; ignoring it", path)
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        logger.warning("calendar cache at %s carries no event list; ignoring it", path)
        return None
    return payload


def _cache_age_s(cached: Optional[Mapping[str, Any]], now_ms: int) -> Optional[float]:
    """Seconds since the cached fetch, or ``None`` when the cache is absent or undated."""
    if cached is None:
        return None
    fetched_at_ms = _int_ms(cached.get("fetched_at_ms"))
    if fetched_at_ms is None:
        return None
    return max(0.0, (now_ms - fetched_at_ms) / 1000.0)


def _write_cache(path: Path, payload: Mapping[str, Any]) -> None:
    """Best-effort and atomic-ish: the caller already holds the events, so a bad disk is a log line."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        body = {key: payload.get(key) for key in _CACHE_KEYS}
        tmp.write_text(json.dumps(body, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        logger.warning("could not write the calendar cache at %s: %s", path, exc)


# ══════════════════════════════════════════════════════════════
# The pure filters the panel and the alert path call
# ══════════════════════════════════════════════════════════════

def _currency_filter(currencies: Optional[Iterable[str] | str]) -> set[str]:
    """Upper-case codes to match; an empty or ``None`` selection means 'every currency'."""
    if currencies is None:
        return set()
    if isinstance(currencies, str):
        currencies = (currencies,)
    return {_text(code).upper() for code in currencies if _text(code)}


def upcoming(
    events: Iterable[dict[str, Any]],
    *,
    now_ms: int,
    within_hours: float = 24.0,
    currencies: Optional[Iterable[str] | str] = None,
    min_impact: Any = "high",
) -> list[dict[str, Any]]:
    """Events landing in ``[now_ms, now_ms + within_hours]`` at or above ``min_impact``, ascending.

    Both window ends are inclusive; ``currencies`` (case-insensitive) filters when given and is
    ignored when empty. Pure: the input list is not modified, the event dicts are returned as they
    came in.
    """
    start_ms = int(now_ms)
    end_ms = start_ms + int(round(float(within_hours) * _MS_PER_HOUR))
    wanted = _currency_filter(currencies)
    floor = impact_rank(min_impact)
    picked: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        at_ms = _int_ms(event.get("at_ms"))
        if at_ms is None or at_ms < start_ms or at_ms > end_ms:
            continue
        if wanted and _text(event.get("currency")).upper() not in wanted:
            continue
        if impact_rank(event.get("impact")) < floor:
            continue
        picked.append(event)
    return sorted(picked, key=_sort_key)


def due_alerts(
    events: Iterable[dict[str, Any]],
    *,
    now_ms: int,
    lead_minutes: float,
    alerted_keys: Iterable[str] = (),
) -> list[dict[str, Any]]:
    """Events starting within ``lead_minutes`` ahead that have not been alerted yet, ascending.

    An event that has already started is not due; neither is one whose :func:`event_key` is in
    ``alerted_keys`` (the caller adds the key once an alert has gone out, so nothing fires twice).
    Impact is deliberately not filtered here — pass ``upcoming``'s output to choose what to alert on.
    """
    start_ms = int(now_ms)
    end_ms = start_ms + int(round(float(lead_minutes) * _MS_PER_MINUTE))
    alerted = {_text(key) for key in alerted_keys}
    due: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        at_ms = _int_ms(event.get("at_ms"))
        if at_ms is None or at_ms < start_ms or at_ms > end_ms:
            continue
        if event_key(event) in alerted:
            continue
        due.append(event)
    return sorted(due, key=_sort_key)


def event_message(event: Mapping[str, Any]) -> str:
    """One plain alert line for the alert path, e.g.::

        USD · Federal Funds Rate — high impact at 12:30 UTC (forecast 4.25%, previous 4.50%)
    """
    at_ms = _int_ms(event.get("at_ms"))
    when = f"{_utc_hm(at_ms)} UTC" if at_ms is not None else "an unknown time"
    currency = _text(event.get("currency")).upper() or "—"
    title = _text(event.get("title")) or "Unnamed event"
    impact = normalise_impact(event.get("impact"))
    line = f"{currency} · {title} — {impact} impact at {when}"
    details = [f"{label} {value}" for label, value in _detail_cells(event)]
    return f"{line} ({', '.join(details)})" if details else line


def _detail_cells(event: Mapping[str, Any]) -> list[tuple[str, str]]:
    """The figure pairs worth showing, in the order an alert reads them: actual, forecast, previous."""
    cells = []
    for field in ("actual", "forecast", "previous"):
        value = _text(event.get(field))
        if value:
            cells.append((field, value))
    return cells


def _utc_hm(at_ms: int) -> str:
    """``12:30`` for a UTC instant — the alert line's clock is always UTC, whatever the host's zone."""
    return (_EPOCH + timedelta(milliseconds=int(at_ms))).strftime("%H:%M")


# ══════════════════════════════════════════════════════════════
# Headless entry point (smoke test / log line)
# ══════════════════════════════════════════════════════════════

def _default_cache_path() -> Path:
    return Path(tempfile.gettempdir()) / "modflow-calendar.json"


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Print the releases coming up, so a human can check the panel's data without the panel."""
    parser = argparse.ArgumentParser(description="Show the economic calendar ModFlow watches.")
    parser.add_argument("--cache", default=None, help="cache file (default: <temp>/modflow-calendar.json)")
    parser.add_argument("--hours", type=float, default=24.0, help="window ahead, in hours")
    parser.add_argument("--min-impact", default="high", choices=("high", "medium", "low", "holiday", "unknown"))
    parser.add_argument("--ttl", type=float, default=DEFAULT_TTL_S, help="cache ttl in seconds (0 = always fetch)")
    args = parser.parse_args(argv)

    cache = Path(args.cache) if args.cache else _default_cache_path()
    payload = fetch_events_cached(cache, ttl_s=args.ttl)
    if not payload.get("ok"):
        print(f"calendar unavailable: {payload.get('error')}")
        return 1
    if payload.get("stale"):
        print(f"(stale calendar — {payload.get('error')})")
    events = upcoming(
        payload.get("events") or [],
        now_ms=int(time.time() * 1000.0),
        within_hours=args.hours,
        min_impact=args.min_impact,
    )
    for event in events:
        print(event_message(event))
    if not events:
        print(f"no {args.min_impact}-impact events in the next {args.hours:g} h")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised by hand, not by the gate
    raise SystemExit(main())
