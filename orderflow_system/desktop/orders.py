"""Where an order goes: one door, a risk gate in front of it, and no way to reach a broker by accident.

The desktop app has one order surface (the Replay view's paper account) and, one day, a broker
behind a bridge. Everything that wants to trade goes through :class:`OrderRouter`, which does three
things in one place:

* **picks the account driver** — ``paper`` sends the order to :class:`~orderflow_system.desktop.paper.PaperAccount`,
  ``bridge`` is the live path, and :class:`BridgeDriver` refuses it with one plain sentence: this
  build has no broker connection, and a refusal is the only honest answer. The bridge never invents
  a fill, never reports ``ok`` and never returns an order row.
* **runs the risk gates first** — a daily loss cap, a maximum order size and a maximum number of
  concurrent positions, each measured against the account the order would actually hit.
* **says which route it used** — the driver's route table (:data:`ROUTES`) names the HTTP path the
  UI should send the order to, so a panel can be driver-agnostic without guessing.

Live routing is off twice over and both locks are inspected before anything else: ``live_disabled``
defaults to **True**, and there is no live counterparty in this build at all. Turning the switch off
in a config file therefore still cannot place a live order — the driver refuses — which is the point
of having two locks rather than one.

Pure by construction: the router owns no socket, no thread, no clock and no file handle. It is
handed a paper account (or nothing) and answers with plain dicts.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Optional

from fastapi import APIRouter, Body

from orderflow_system.desktop import atm

logger = logging.getLogger(__name__)

#: The accounts an order can be sent to. Unknown names are refused rather than guessed.
DRIVERS = ("paper", "bridge")

#: The feature's settings block. Every cap at 0 means "no cap configured". ``max_positions``
#: counts the positions **open across the attached accounts** — never the entries resting on
#: one of them, and a single paper account holds at most one position at a time. With this
#: build's one trading account the cap therefore cannot refuse anything: it ships at 1 as the
#: guard for a caller that has attached more than one account (the control API), which is
#: exactly when a second position could otherwise open. §148 T1-D3: the old sentence here
#: promised a refusal the shipped single-account app cannot reach.
DEFAULTS: dict[str, Any] = {
    "driver": "paper",
    "live_disabled": True,
    "max_size": 0.0,
    "max_positions": 1,
    "daily_loss_cap_ticks": 0.0,
}

#: The route each driver's orders already travel in this build. A UI reads these instead of hard-coding.
ROUTES: dict[str, dict[str, str]] = {
    "paper": {
        "order": "/api/atlas/replay/paper/order",
        "cancel": "/api/atlas/replay/paper/cancel",
        "flatten": "/api/atlas/replay/paper/flatten",
        "state": "/api/atlas/replay/paper/state",
    },
    "bridge": {},
}

#: The four sentences a user can meet. Each one says what happened and what would change it.
LIVE_REFUSAL = ("live routing is off — this build has no broker connection, so orders only ever "
                "reach the paper account")
BRIDGE_REFUSAL = ("no live account is configured in this build — a live order is refused here "
                  "rather than filled")
NO_ACCOUNT_REFUSAL = "no paper session is open — start one on the Replay view first"
NO_SESSION_REFUSAL = "no trading session is bound here yet — open a paper session on the Replay view first"
UNKNOWN_DRIVER = "that account is not one this build can route to — orders go to the paper account"
SIZE_REFUSAL = "order refused: size must be a positive number"


def _number(value: Any) -> Optional[float]:
    """``value`` as a finite float, or ``None``. Never raises."""
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _cap(value: Any) -> float:
    """A cap: a non-negative number, or 0.0 meaning "no cap configured"."""
    out = _number(value)
    return max(0.0, out) if out is not None else 0.0


def clean(patch: Any) -> dict[str, Any]:
    """Coerce an incoming settings patch onto :data:`DEFAULTS`. Never raises; returns only the block.

    ``live_disabled`` is *not* cleared by a patch that omits it, and a patch that hands it a junk
    value leaves it **on** — the safe reading of "I am not sure" is "live is off".
    """
    out = dict(DEFAULTS)
    if not isinstance(patch, dict):
        return out
    driver = str(patch.get("driver") or "").strip().lower()
    if driver in DRIVERS:
        out["driver"] = driver
    if "live_disabled" in patch:
        out["live_disabled"] = bool(patch.get("live_disabled")) if isinstance(
            patch.get("live_disabled"), bool) else True
    for key in ("max_size", "daily_loss_cap_ticks"):
        if key in patch:
            out[key] = _cap(patch.get(key))
    if "max_positions" in patch:
        out["max_positions"] = int(min(100, _cap(patch.get("max_positions"))))
    return out


# ══════════════════════════════════════════════════════════════
# Drivers: the paper account today, the bridge when there is one
# ══════════════════════════════════════════════════════════════

class AccountDriver:
    """What a driver must answer. The router never asks a driver for anything else."""

    name = ""

    def submit(self, side: str, size: float, **kwargs: Any) -> dict[str, Any]:   # pragma: no cover
        raise NotImplementedError

    def cancel(self, order_id: Any) -> bool:                                     # pragma: no cover
        raise NotImplementedError

    def cancel_all(self) -> list[str]:                                           # pragma: no cover
        raise NotImplementedError

    def flatten(self, price: Any, ts_ms: int = 0) -> list[dict[str, Any]]:       # pragma: no cover
        raise NotImplementedError

    def position(self) -> dict[str, Any]:                                        # pragma: no cover
        raise NotImplementedError

    def state(self) -> dict[str, Any]:                                           # pragma: no cover
        raise NotImplementedError


class PaperDriver(AccountDriver):
    """The simulated account, behind the driver interface.

    Nothing is added to the fill model here — the order is handed straight to ``PaperAccount``, which
    stays the one place a fill can happen.
    """

    name = "paper"

    def __init__(self, account: Any = None) -> None:
        self.account = account

    def _refuse(self) -> dict[str, Any]:
        return {"ok": False, "status": "rejected", "reason": NO_ACCOUNT_REFUSAL, "order": None}

    def submit(self, side: str, size: float, **kwargs: Any) -> dict[str, Any]:
        if self.account is None:
            return self._refuse()
        order = self.account.submit(side, size, **kwargs)
        return {"ok": order.get("status") != "rejected", "status": order.get("status") or "",
                "reason": str(order.get("reason") or ""), "order": order}

    def cancel(self, order_id: Any) -> bool:
        return bool(self.account is not None and order_id and self.account.cancel(str(order_id)))

    def cancel_all(self) -> list[str]:
        if self.account is None:
            return []
        return [order["id"] for order in self.account.open_orders() if self.account.cancel(order["id"])]

    def flatten(self, price: Any, ts_ms: int = 0) -> list[dict[str, Any]]:
        return list(self.account.flatten(price, ts_ms)) if self.account is not None else []

    def position(self) -> dict[str, Any]:
        if self.account is None:
            return {"side": "flat", "size": 0.0, "entry_price": 0.0, "entry_ms": 0}
        return dict(self.account.position())

    def stats(self) -> dict[str, Any]:
        return dict(self.account.stats()) if self.account is not None else {}

    def state(self) -> dict[str, Any]:
        if self.account is None:
            return {"ok": False, "reason": NO_ACCOUNT_REFUSAL}
        out = dict(self.account.to_dict())
        out["ok"] = True
        out["stats"] = self.account.stats()
        return out


class BridgeDriver(AccountDriver):
    """The live path, which this build does not have. Every method refuses; none of them fills.

    There is deliberately no ``_account`` attribute to fall back on: a driver that answers ``ok``
    without a counterparty would be a simulated live trade, which is worse than a refusal.
    """

    name = "bridge"
    #: One sentence, used by every method — the same words wherever a user meets it.
    reason = BRIDGE_REFUSAL

    def submit(self, side: str, size: float, **kwargs: Any) -> dict[str, Any]:
        logger.debug("bridge: refused %s %s — %s", side, size, self.reason)
        return {"ok": False, "status": "refused", "reason": self.reason, "order": None}

    def cancel(self, order_id: Any) -> bool:
        return False

    def cancel_all(self) -> list[str]:
        return []

    def flatten(self, price: Any, ts_ms: int = 0) -> list[dict[str, Any]]:
        return []

    def position(self) -> dict[str, Any]:
        return {"side": "flat", "size": 0.0, "entry_price": 0.0, "entry_ms": 0}

    def state(self) -> dict[str, Any]:
        return {"ok": False, "reason": self.reason, "driver": self.name}


# ══════════════════════════════════════════════════════════════
# The router
# ══════════════════════════════════════════════════════════════

class OrderRouter:
    """Validates an order against the risk gates, then hands it to the driver for the account.

    The router holds whatever paper accounts the app has opened (the Replay view's session, and any
    other account a caller attaches), because two of the gates are properties of the *account*, not
    of the order: the day's PnL, and how many positions are already open.
    """

    def __init__(self, account: Any = None, *, settings: Any = None) -> None:
        self.settings = clean(settings)
        self._accounts: list[Any] = []
        self._day_baseline: Optional[float] = None
        self._day_stamp = ""
        self._bridge = BridgeDriver()
        if account is not None:
            self.attach(account)

    # ── accounts and drivers ─────────────────────────────────────────────────────────────

    def attach(self, account: Any) -> Any:
        """Register a paper account the gates must count. Returns the account for chaining."""
        if account is not None and account not in self._accounts:
            self._accounts.append(account)
            # §148 T1-D10: attaching does NOT rebase the day. It used to clear the baseline, so a
            # caller that had just rebased with `start_day` saw the loss cap fire again against the
            # PnL they had written off — `set_account` is the one that starts a fresh day.
        return account

    def set_account(self, account: Any) -> Any:
        """Replace the trading account (a new session on a new instrument)."""
        self._accounts = []
        self._day_baseline = None
        return self.attach(account)

    @property
    def account(self) -> Any:
        """The account orders are sent to: the first attached, or ``None``."""
        return self._accounts[0] if self._accounts else None

    def driver(self) -> AccountDriver:
        """The driver the settings name. ``bridge`` is always the refusing one."""
        return self._bridge if self.settings.get("driver") == "bridge" else PaperDriver(self.account)

    def route_for(self, what: str = "order") -> Optional[str]:
        """The HTTP path this driver's orders travel, from :data:`ROUTES`. ``None`` when there is none."""
        return ROUTES.get(str(self.settings.get("driver") or "paper"), {}).get(what)

    # ── the day ──────────────────────────────────────────────────────────────────────────

    def start_day(self, stamp: str, *, ticks_now: Any = 0.0) -> dict[str, Any]:
        """Start (or restart) the day the loss cap is measured against.

        The router owns no clock — the app hands it the day it means, and the PnL standing at that
        moment becomes the baseline everything afterwards is measured from.
        """
        self._day_stamp = str(stamp or "")
        self._day_baseline = float(_number(ticks_now) or 0.0)
        return {"ok": True, "day": self._day_stamp, "baseline_ticks": self._day_baseline}

    def session_ticks(self) -> float:
        """Realised plus open PnL, in ticks, over every attached account."""
        total = 0.0
        for account in self._accounts:
            try:
                stats = account.stats()
            except Exception:                                   # a driver must never break the gate
                continue
            total += float(_number(stats.get("realised_ticks")) or 0.0)
            total += float(_number(stats.get("unrealised_ticks")) or 0.0)
        return round(total, 6)

    def day_ticks(self) -> float:
        """The day's PnL in ticks, measured from the baseline ``start_day`` set."""
        baseline = self._day_baseline if self._day_baseline is not None else 0.0
        return round(self.session_ticks() - baseline, 6)

    def open_positions(self) -> int:
        """How many attached accounts are holding a position right now."""
        count = 0
        for account in self._accounts:
            try:
                held = account.position()
            except Exception:
                continue
            if str(held.get("side") or "flat") != "flat" and float(_number(held.get("size")) or 0) > 0:
                count += 1
        return count

    # ── the gates ────────────────────────────────────────────────────────────────────────

    def _position_of(self, account: Any) -> dict[str, Any]:
        """An account's position, or flat — a gate must never fail because an account is missing."""
        target = account if account is not None else self.account
        if target is None:
            return {"side": "flat", "size": 0.0, "entry_price": 0.0, "entry_ms": 0}
        try:
            return dict(target.position())
        except Exception:
            return {"side": "flat", "size": 0.0, "entry_price": 0.0, "entry_ms": 0}

    def gates(self, side: Any, size: Any, *, account: Any = None) -> list[dict[str, Any]]:
        """Every gate's verdict for this order, in the order they are checked — the UI's read-out.

        A gate that passes carries an empty ``detail``; a gate that refuses carries the sentence a
        user would see, so a panel can show why an order never left.
        """
        cfgs = clean(self.settings)
        amount = _number(size)
        verdicts: list[dict[str, Any]] = []

        def add(name: str, ok: bool, detail: str = "") -> None:
            verdicts.append({"gate": name, "ok": bool(ok), "detail": detail if not ok else ""})

        add("driver", cfgs["driver"] in DRIVERS, UNKNOWN_DRIVER)
        add("size", amount is not None and amount > 0, SIZE_REFUSAL)
        cap = float(cfgs["max_size"])
        add("max_size", not (cap > 0 and amount is not None and amount > cap),
            f"order refused: size {amount:g} is past the max size {cap:g} in Risk settings"
            if cap > 0 and amount is not None else "")
        loss_cap = float(cfgs["daily_loss_cap_ticks"])
        day = self.day_ticks()
        add("daily_loss_cap", not (loss_cap > 0 and day <= -loss_cap),
            f"order refused: the daily loss cap of {loss_cap:g} ticks has been reached "
            f"(the day stands at {day:g})" if loss_cap > 0 else "")
        held = self.open_positions()
        limit = int(cfgs["max_positions"])
        opening = str(self._position_of(account).get("side") or "flat") == "flat"
        # §148 T1-D3: both halves are needed for the cap to bite — the order must be *opening* and
        # the attached accounts must already hold `limit` of them. Entries resting on an account are
        # not positions, and one account holds at most one, so with this build's single trading
        # account `opening` implies `held == 0` and this refuses only a caller that attached more
        # than one (see DEFAULTS). Adds and reduces on a held position pass, unchanged.
        add("max_positions", not (limit > 0 and opening and held >= limit),
            f"order refused: {held} position is open and max concurrent positions is {limit}"
            if limit > 0 and held else "")
        return verdicts

    def check(self, side: Any, size: Any, *, account: Any = None) -> dict[str, Any]:
        """The first gate that refuses, as ``{"gate", "reason"}``; ``{"gate": "", "reason": ""}`` when clear."""
        for verdict in self.gates(side, size, account=account):
            if not verdict["ok"]:
                return {"gate": verdict["gate"], "reason": verdict["detail"] or UNKNOWN_DRIVER}
        return {"gate": "", "reason": ""}

    # ── the door ─────────────────────────────────────────────────────────────────────────

    def route(self, side: Any, size: Any, *, kind: str = "market", price: Any = None,
              stop_loss: Any = None, take_profit: Any = None, template: Any = None,
              ts_ms: int = 0, account: Any = None) -> dict[str, Any]:
        """Send one order through the gates to the driver. Returns a receipt, never an exception.

        The receipt answers the same questions whatever the outcome: ``ok``, the ``driver`` and
        ``route`` that were used, ``body`` (the exact payload to send if the caller prefers to walk
        the route itself), the ``gates``, and — on a refusal — the ``gate`` that refused and the
        ``reason`` a user reads.
        """
        cfgs = clean(self.settings)
        driver = self._bridge if cfgs["driver"] == "bridge" else PaperDriver(account or self.account)
        side_name = atm.side_of(side)
        amount = _number(size)
        body: dict[str, Any] = {"side": side_name, "size": amount, "kind": str(kind or "market").lower(),
                               "price": _number(price)}
        if stop_loss not in (None, ""):
            body["stop_loss"] = _number(stop_loss)
        if take_profit not in (None, ""):
            body["take_profit"] = _number(take_profit)
        if template not in (None, "", {}):
            body["template"] = template

        receipt: dict[str, Any] = {"ok": False, "driver": driver.name, "route": self.route_for("order"),
                                   "reason": "", "gate": "", "order": None, "body": body,
                                   "gates": self.gates(side_name, size, account=account or self.account)}
        if not side_name:
            receipt["reason"], receipt["gate"] = "an order needs a side — 'buy' or 'sell'", "side"
            return receipt
        if driver.name == "bridge":
            # Two locks, both inspected here: the switch, then the counterparty that does not exist.
            receipt["reason"] = LIVE_REFUSAL if cfgs["live_disabled"] else BRIDGE_REFUSAL
            receipt["gate"] = "live_disabled" if cfgs["live_disabled"] else "live_account"
            logger.info("router: refused a %s %s on the bridge — %s", side_name, amount, receipt["reason"])
            return receipt
        if driver.account is None:
            receipt["reason"], receipt["gate"] = NO_ACCOUNT_REFUSAL, "account"
            return receipt
        failed = self.check(side_name, size, account=account or self.account)
        if failed["gate"]:
            receipt["reason"], receipt["gate"] = failed["reason"], failed["gate"]
            logger.info("router: refused a %s %s at the %s gate — %s", side_name, amount,
                        failed["gate"], failed["reason"])
            return receipt
        result = driver.submit(side_name, amount, kind=body["kind"], price=body["price"],
                               stop_loss=body.get("stop_loss"), take_profit=body.get("take_profit"),
                               template=template, ts_ms=int(ts_ms or 0))
        receipt.update({"ok": bool(result.get("ok")), "order": result.get("order"),
                        "reason": "" if result.get("ok") else str(result.get("reason") or SIZE_REFUSAL),
                        "gate": "" if result.get("ok") else "account"})
        return receipt

    def cancel(self, order_id: Any = None) -> dict[str, Any]:
        """Cancel one order by id, or every working order when none is named."""
        driver = self.driver()
        if driver.name == "bridge":
            return {"ok": False, "driver": driver.name, "route": self.route_for("cancel"),
                    "reason": LIVE_REFUSAL if clean(self.settings)["live_disabled"] else BRIDGE_REFUSAL,
                    "cancelled": []}
        if driver.account is None:
            return {"ok": False, "driver": driver.name, "route": self.route_for("cancel"),
                    "reason": NO_ACCOUNT_REFUSAL, "cancelled": []}
        if order_id:
            done = driver.cancel(order_id)
            return {"ok": done, "driver": driver.name, "route": self.route_for("cancel"),
                    "reason": "" if done else "that order is not working — it filled, was cancelled, or never existed",
                    "cancelled": [str(order_id)] if done else []}
        done = driver.cancel_all()
        return {"ok": True, "driver": driver.name, "route": self.route_for("cancel"),
                "reason": "", "cancelled": done}

    def flatten(self, price: Any, ts_ms: int = 0) -> dict[str, Any]:
        """Close the position at ``price`` — the caller's print, not a guess at one."""
        driver = self.driver()
        if driver.name == "bridge":
            return {"ok": False, "driver": driver.name, "route": self.route_for("flatten"),
                    "reason": LIVE_REFUSAL if clean(self.settings)["live_disabled"] else BRIDGE_REFUSAL,
                    "fills": []}
        if driver.account is None:
            return {"ok": False, "driver": driver.name, "route": self.route_for("flatten"),
                    "reason": NO_ACCOUNT_REFUSAL, "fills": []}
        fills = driver.flatten(price, int(ts_ms or 0))
        return {"ok": bool(fills), "driver": driver.name, "route": self.route_for("flatten"),
                "reason": "" if fills else "nothing to flatten — the position is already flat",
                "fills": fills}

    def status(self) -> dict[str, Any]:
        """The router as a panel reads it: the driver, its route, the gates and the day so far."""
        cfgs = clean(self.settings)
        account = self.account
        held = account.position() if account is not None else {"side": "flat", "size": 0.0}
        return {
            "ok": True,
            "driver": cfgs["driver"],
            "live_disabled": bool(cfgs["live_disabled"]),
            "routes": dict(ROUTES.get(cfgs["driver"], {})),
            "settings": cfgs,
            "gates": self.gates("buy", 1, account=account),
            "positions_open": self.open_positions(),
            "session_ticks": self.session_ticks(),
            "day_ticks": self.day_ticks(),
            "day": self._day_stamp,
            "position": dict(held),
            "refusals": {"live": LIVE_REFUSAL, "bridge": BRIDGE_REFUSAL, "account": NO_ACCOUNT_REFUSAL},
        }


# ══════════════════════════════════════════════════════════════
# The app's own router: /api/control/trading/*
# ══════════════════════════════════════════════════════════════

#: The session's router. The app binds it when a paper session opens; without one every trading
#: route refuses with the sentence below rather than inventing an account.
_SESSION: dict[str, Any] = {"router": None}


def bind_account(account: Any, *, settings: Any = None) -> OrderRouter:
    """Build the session's router around ``account`` and make it the one the routes answer with."""
    router = _SESSION.get("router")
    if isinstance(router, OrderRouter):
        router.set_account(account)
        if settings is not None:
            router.settings = clean(settings)
        return router
    router = OrderRouter(account, settings=settings)
    _SESSION["router"] = router
    return router


def session_router() -> Optional[OrderRouter]:
    """The bound router, or ``None`` when no session has opened one."""
    router = _SESSION.get("router")
    return router if isinstance(router, OrderRouter) else None


def unbind_account() -> None:
    """Stand the session's router down — the trading routes refuse again until one is bound.

    §148: the paper session calls this when it closes, so a closed session leaves no router
    pointing at a dead account.
    """
    _SESSION["router"] = None


def _stored(key: str) -> Any:
    """The stored settings block for this feature, or ``None`` — read-only, never a write."""
    try:
        from orderflow_system.desktop import config_store

        return (config_store.load_config() or {}).get(key)
    except Exception:                                          # a missing config is not an error
        return None


router = APIRouter(prefix="/api/control", tags=["trading"])


@router.get("/trading/status")
async def trading_status() -> dict[str, Any]:
    """The active driver, its route, the risk gates and the day's PnL — nothing writes here."""
    bound = session_router()
    settings = _stored("orders")
    if bound is None:
        return {"ok": True, "bound": False, "settings": clean(settings),
                "routes": dict(ROUTES.get(clean(settings)["driver"], {})),
                "live_disabled": bool(clean(settings)["live_disabled"]),
                "refusals": {"live": LIVE_REFUSAL, "bridge": BRIDGE_REFUSAL,
                             "account": NO_ACCOUNT_REFUSAL}}
    return dict(bound.status(), bound=True)


@router.get("/trading/templates")
async def trading_templates() -> dict[str, Any]:
    """The order templates the ladder offers: the stored block, coerced onto the shipped defaults."""
    return {"ok": True, "atm": atm.clean(_stored("atm"))}


@router.post("/trading/route")
async def trading_route(payload: dict = Body(default={})) -> dict[str, Any]:
    """Send one order through the router's gates. Refuses, with its words, when nothing is bound."""
    body = dict(payload or {})
    bound = session_router()
    if bound is None:
        return {"ok": False, "bound": False, "reason": NO_SESSION_REFUSAL, "driver": "",
                "route": "", "order": None}
    result = bound.route(body.get("side"), body.get("size"), kind=str(body.get("kind") or "market"),
                         price=body.get("price"), stop_loss=body.get("stop_loss"),
                         take_profit=body.get("take_profit"), template=body.get("template"),
                         ts_ms=int(_number(body.get("ts_ms")) or 0))
    out = dict(result)
    out["bound"] = True
    out["error"] = result.get("reason") or ""
    account = bound.account
    if account is not None:
        out["state"] = {"position": account.position(), "orders": account.open_orders(),
                        "exits": account.exits()}
    return out


@router.post("/trading/cancel")
async def trading_cancel(payload: dict = Body(default={})) -> dict[str, Any]:
    """Cancel one working order by id, or every working order when none is named."""
    bound = session_router()
    if bound is None:
        return {"ok": False, "bound": False, "reason": NO_SESSION_REFUSAL, "cancelled": []}
    result = bound.cancel((payload or {}).get("order_id"))
    out = dict(result)
    out["bound"] = True
    out["error"] = result.get("reason") or ""
    return out
