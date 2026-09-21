"""Paper trading for the Replay view: orders filled by the tape, and nothing the tape cannot show.

The Replay view plays a recorded session back so a user can study it as if it were live; this module
is the ledger that lets them put orders on it. The account is a **pure state machine** — the caller
feeds it prints (``on_trade``) and reads answers (``position``, ``mark``, ``stats``). It owns no
socket, no thread, no clock and no database. The Replay loop *is* the clock, which is what makes a
session reproducible: the same tape and the same orders give the same fills, every time.

The fill model, stated plainly, because a paper account that flatters its user teaches nothing:

* **A market order fills at the next print** — the first ``on_trade`` after ``submit``, at that
  print's price. Never at the quote that stood when the order was sent: that quote is gone.
* **A limit order fills when a print trades at or through its price**, and it fills *at its own
  limit price* — no better, no worse. It rests until that print arrives, however many don't. An
  order whose level the tape has already passed is refused at submit: filling it at its own
  price would book a price the tape never offered.
* **A stop order fills when a print trades at or through its trigger**, at the trigger price.
* **Stop-loss and take-profit are intents, not resting orders.** They are checked against every
  print while a position is open: a long stops out when a print touches its stop from above and
  takes profit when one touches the target from below (mirrored for a short). The exit is priced
  at the level it named, exactly as a limit is. A single print inside *both* triggers — only
  possible with an inverted pair, or a limit filled by a print beyond it — is resolved to the
  **stop**, in that fixed order. The tape holds one price and cannot say which side was reached
  first, so the account applies a rule instead of inventing a sequence of prints that would decide.
* **No queue position, no slippage, no partial fills, no liquidity cap** beyond the above. Fills are
  priced at the level the order named (or the print, for a market order); the print's size is
  recorded, not consumed, so an order fills whole against a print of any size. Read a paper session
  as a statement about the plan, never as a promise about real fills.

Everything the account reports in ticks is in the **instrument's tick units** — the unit the app's
journal already uses — and only the starting balance is cash (``mark`` converts it). Rebasing a
position and flipping it are the two arithmetic cases worth knowing: adding to a position averages
the entry, and an opposite order **reduces first, then flips the remainder** into a new position at
the fill price, booking the closed part as a journal row.

An **order template** (``desktop/atm.py``) rides along with an entry order and becomes a **plan** the
moment that order fills: the *fill* price fixes where the stop, the target and any partial sit,
because a limit that rested for an hour must be stopped eight ticks from its own fill rather than
from the click that placed it. A live plan then manages itself against every print — the stop moves
to break-even once the trade has gone its way far enough, trails behind the best price seen since,
and the position leaves at the print when the plan's clock runs out (``time_stop``). The legs are one
OCO group: when one of them is the reason the position leaves, every other working leg of the group
is cancelled with it, so nothing is left resting on a position that no longer exists. Setting the
exits by hand (``set_exits``) hands that job back to the user — a typed price always wins over
automation, and the plan says so in ``plan()["managed"]``.

The account is the device's own; the caller drives the tape:

    account = PaperAccount(symbol="ESZ6", tick_size=0.25, starting_balance=100_000.0)
    account.submit("buy", 2, stop_loss=4999.00, take_profit=5004.00, ts_ms=ms)
    for print in replay:            # whatever the Replay view hands over, in tape order
        for fill in account.on_trade(print.price, print.size, print.side, print.ts_ms):
            journal.append(fill)
"""

from __future__ import annotations

import logging
import math
from typing import Any, Optional

from orderflow_system.desktop import atm

logger = logging.getLogger(__name__)

#: Order kinds a caller can submit; anything else is rejected with a reason rather than raising.
ORDER_KINDS = ("market", "limit", "stop")
#: Sides, lower-case — the vocabulary of ``data.models.Side`` and of the journal.
SIDES = ("buy", "sell")
#: Why a fill happened: the order's own kind, the exit that closed the position, or its plan's clock.
FILL_REASONS = ("market", "limit", "stop", "stop_loss", "take_profit", "time_stop", "flatten")
#: Order lifecycle. ``cancelled`` is only ever reached through ``cancel``, never through ``submit``.
ORDER_STATUSES = ("working", "filled", "rejected", "cancelled")
#: The ``trade_journal`` columns a ``closed_trades`` row carries, in this order — so a session can
#: be handed to ``data.database.log_trade`` (or an INSERT) without a translation step.
JOURNAL_COLUMNS = ("instrument", "direction", "entry_time_ms", "exit_time_ms", "entry_price",
                   "exit_price", "stop_loss", "take_profit", "pnl_ticks", "rr_ratio",
                   "mae_ticks", "mfe_ticks")

#: Ticks are rounded here so float noise never reaches a journal row: a 0.05 tick, or a price that
#: travelled through a subtraction, can otherwise report 39.99999999999999 ticks of profit.
TICK_DECIMALS = 6


def _number(value: Any) -> Optional[float]:
    """``value`` as a finite float, or ``None`` when it is not one. Never raises."""
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _positive(value: Any) -> Optional[float]:
    """``value`` as a positive float, or ``None`` — the form the account stores its levels in."""
    out = _number(value)
    return out if out is not None and out > 0 else None


def _ms(value: Any) -> int:
    """A timestamp in milliseconds as an int; a junk stamp becomes 0 rather than raising."""
    out = _number(value)
    return int(out) if out is not None else 0


def _text(value: Any) -> str:
    """A vocabulary word, lower-cased — accepts the app's ``Side`` enum as well as a string."""
    return str(getattr(value, "value", value)).strip().lower()


def _plan_outcome(reason: str) -> str:
    """The plan's word for why the position left, read off the fill's own reason.

    ``stop_loss``, ``take_profit`` and ``time_stop`` are the plan's own exits; a limit or market
    fill that closed the position was a hand on the button (``flatten``), and a flip is a flip.
    """
    word = _text(reason)
    if word in ("stop_loss", "take_profit", "time_stop", "flip"):
        return word
    return "flatten" if word in ("limit", "market", "stop", "flatten") else "unknown"


def _level_reached(order: dict[str, Any], price: float) -> bool:
    """Has ``price`` reached this limit or stop order's trigger?

    A buy limit (and a sell stop) is reached from above; a sell limit (and a buy stop) from below.
    """
    level = float(order["price"])
    if order["kind"] == "limit":
        return price <= level if order["side"] == "buy" else price >= level
    return price >= level if order["side"] == "buy" else price <= level


class PaperAccount:
    """One instrument's paper account, filled print by print. Pure: no IO, no timers, no asyncio.

    ``max_position`` caps the position one order could create: it is checked when the order is
    submitted, against the position open at that moment (a reducing order always fits). It is a
    per-order guard, not a risk engine — two resting orders are not netted against each other.
    """

    def __init__(self, *, symbol: str = "", tick_size: float = 0.01,
                 starting_balance: float = 100_000.0, max_position: Optional[float] = None) -> None:
        self.symbol = str(symbol)
        tick = _number(tick_size)
        self.tick_size = tick if tick and tick > 0 else 0.01      # a tick size of 0 divides nowhere
        self.starting_balance = _number(starting_balance) or 0.0
        cap = _positive(max_position)
        self.max_position = cap                                    # None = unlimited
        self._orders: list[dict[str, Any]] = []                    # every order, in id order
        self._next_id = 1
        self._net = 0.0            # signed position: positive long, negative short, 0 flat
        self._entry_price = 0.0
        self._entry_ms = 0
        self._stop_loss: Optional[float] = None
        self._take_profit: Optional[float] = None
        #: §148: the stop the position was OPENED with — the risk its trades are measured against.
        #: ``_stop_loss`` moves with break-even and the trail, so it cannot be the R basis.
        self._entry_stop: Optional[float] = None
        #: §148: the open position's worst and best print prices — the journal's MAE/MFE. Prices
        #: while the position lives; ticks off the row's own entry price when a leg closes.
        self._excursion_worst: Optional[float] = None
        self._excursion_best: Optional[float] = None
        self._realised = 0.0       # banked PnL in price × size; turned into ticks on the way out
        self._closed: list[dict[str, Any]] = []
        self._last_price: Optional[float] = None
        self._last_print: Optional[dict[str, Any]] = None
        self._plan: Optional[dict[str, Any]] = None   # the template bracket, once an order armed one
        self._plan_seq = 0                            # names the OCO group: oc1, oc2, ...

    # ══════════════════════════════════════════════════════════════
    # Orders
    # ══════════════════════════════════════════════════════════════

    def submit(self, side: str, size: float, *, kind: str = "market", price: Optional[float] = None,
               stop_loss: Optional[float] = None, take_profit: Optional[float] = None,
               template: Any = None, ts_ms: int = 0) -> dict[str, Any]:
        """Put an order on the book. Always returns an order row; a refusal is a row, not an error.

        A market order comes back ``working`` and fills on the next print; a limit or stop waits
        for a print at or through ``price``. ``stop_loss`` / ``take_profit`` ride along and become
        the position's exits if this order opens one. ``price`` on a market order is meaningless
        and stored as ``None``.

        ``template`` is an ATM plan (``desktop/atm.py``) — either the template dict the ladder sends
        or a shipped template's id. It is stored on the order and built into a bracket at the fill
        price, so the plan is measured from the price that actually traded. A template and a typed
        stop-loss are refused together: one position, one stop. A template on an order that would
        ADD to a position already open is refused too — the bracket belongs to the order that OPENS
        the position. (The one path that can still carry a template onto an adding fill is a race:
        two orders posted while flat, the second arriving after the first has opened. That one is
        dropped at the fill and the row records ``plan_template_note`` saying so.) An order that fills **against a
        position already open** (an add, a scale-out, a reduce) keeps that position's plan and
        cannot arm its template; the row records ``plan_template_note`` saying so (§148 T1-D4).

        The returned dict *is* the account's own row for this order: it flips to ``filled`` (with
        ``filled_ms`` and ``fill_price``) when the tape catches it, so a UI can keep hold of it.
        """
        order: dict[str, Any] = {
            "id": f"o{self._next_id}",
            "side": _text(side),
            "kind": _text(kind),
            "size": 0.0,
            "price": None,
            "stop_loss": None,
            "take_profit": None,
            "status": "working",
            "reason": "",
            "created_ms": _ms(ts_ms),
            "filled_ms": None,
            "fill_price": None,
        }
        self._next_id += 1
        reason = self._validate(order, size, price, stop_loss, take_profit)
        if not reason:
            reason = self._resolve_template(order, template, stop_loss, take_profit)
        if reason:
            order["status"] = "rejected"
            order["reason"] = reason
            logger.debug("paper %s: refused %s %s — %s",
                         self.symbol or "account", order["side"], order["kind"], reason)
        self._orders.append(order)
        return order

    def refuse(self, side: Any, size: Any, reason: Any, *, kind: Any = "market",
               price: Any = None, ts_ms: int = 0) -> dict[str, Any]:
        """A refused order as a ledger row — the id and the trace of a click that placed nothing.

        Used when the refusal happened *before* the account (a risk gate in `orders.OrderRouter`):
        the row keeps the shape one the account refused itself would have, so the session's ledger
        and its ``orders_rejected`` count read the same whichever door said no.
        """
        amount = _number(size)
        order: dict[str, Any] = {
            "id": f"o{self._next_id}",
            "side": _text(side),
            "kind": _text(kind),
            "size": amount if amount is not None and amount > 0 else 0.0,
            "price": _number(price),
            "stop_loss": None,
            "take_profit": None,
            "status": "rejected",
            "reason": str(reason or ""),
            "created_ms": _ms(ts_ms),
            "filled_ms": None,
            "fill_price": None,
        }
        self._next_id += 1
        self._orders.append(order)
        return order

    def _validate(self, order: dict[str, Any], size: Any, price: Any,
                  stop_loss: Any, take_profit: Any) -> str:
        """The refusal reason for this order, or ``""`` when it is good. Fills the row in as it goes."""
        if order["side"] not in SIDES:
            return "side must be 'buy' or 'sell'"
        if order["kind"] not in ORDER_KINDS:
            return "kind must be 'market', 'limit' or 'stop'"
        amount = _number(size)
        if amount is None or amount <= 0:
            return "size must be a positive number"
        order["size"] = amount
        if order["kind"] in ("limit", "stop"):
            trigger = _number(price)
            if trigger is None or trigger <= 0:
                return f"a {order['kind']} order needs a price above 0"
            order["price"] = trigger
            # An order the tape has already passed would fill the moment it is placed — at its
            # own price, which the tape never offered (measured 2026-09-18: a sell limit at 1.0 on
            # a 2,450 tape stayed "working", then filled at 1.0 and booked a -244,699-tick journal
            # loss). Refuse it with the sentence instead; a refusal is a row, not an error.
            printed = float(self._last_price or 0.0)
            if printed > 0 and _level_reached(order, printed):
                return (f"a {order['side']} {order['kind']} at {trigger:g} would fill the moment "
                        f"it is placed — at a price the tape never traded (last {printed:g})")
        order["stop_loss"] = _positive(stop_loss)
        order["take_profit"] = _positive(take_profit)
        if self.max_position is not None:
            signed = amount if order["side"] == "buy" else -amount
            projected = self._net + signed
            if abs(projected) > self.max_position:
                return (f"a fill of {amount:g} would put the position at {abs(projected):g}, "
                        f"past max_position {self.max_position:g}")
        return ""

    def _resolve_template(self, order: dict[str, Any], template: Any,
                          stop_loss: Any, take_profit: Any) -> str:
        """Store the order's ATM template, or the reason it cannot be used. ``""`` when there is none.

        An id is looked up in the shipped templates; a dict is coerced field by field. A template
        that names nothing (`clean_template` leaves it empty) is refused rather than silently
        treated as no plan at all, and a template sent with a typed stop is refused outright: a
        position with two stops is the mistake this whole feature exists to prevent.
        """
        if template is None or template == "" or template == {}:
            return ""
        if isinstance(template, dict):
            cleaned = atm.clean_template(template)
            if not (cleaned["stop_ticks"] or cleaned["target_ticks"] or cleaned["trail_ticks"]
                    or cleaned["time_stop_min"]):
                return "that plan names no stop, target, trail or clock — there is no plan in it"
        else:
            cleaned = atm.template_of(atm.DEFAULTS, template)
            if cleaned is None:
                return (f"'{str(template)[:24]}' is not a template this build ships — "
                        f"pick one from the ladder")
        if _positive(stop_loss) is not None or _positive(take_profit) is not None:
            return "a plan and a typed stop or target are two exits for one position — send one or the other"
        # §148 T1-D4: a template arms only the order that OPENS the position, so an order that would
        # ADD to one already open is refused here rather than dropped at the fill. The old build
        # stored the template, never built a plan from it, and left the row advertising a bracket
        # that did not exist (§148 measured: 3 of 3 adds);
        # the ladder shows this sentence under the order button, so the trader is told at the click.
        if self._net != 0 and (self._net > 0) == (order["side"] == "buy"):
            return ("this order would add to a position that is already open, and a template is armed "
                    "by the order that opens one — send it without a template, or set the exits by hand")
        order["plan_template"] = cleaned
        return ""

    def cancel(self, order_id: str) -> bool:
        """Take a working order off the book. ``False`` when it never was (filled/cancelled/unknown).

        A cancelled leg the plan was still counting is dropped from the plan and ``partial_note``
        says what happened (§148 T1-D5): the row used to keep advertising a scale-out that would
        never fill, so the ladder read "half resting" over an empty book.
        """
        for order in self._orders:
            if order["id"] == order_id and order["status"] == "working":
                order["status"] = "cancelled"
                order["reason"] = "cancelled by the user"
                if str(order.get("plan_leg") or "") == "partial" and self._plan is not None:
                    self._plan["partial"] = None
                    self._plan["partial_note"] = "cancelled — the partial was taken off the book"
                return True
        return False

    def open_orders(self) -> list[dict[str, Any]]:
        """The working orders, in submission order, as copies — safe to hand to a UI."""
        return [dict(order) for order in self._working()]

    def _working(self) -> list[dict[str, Any]]:
        """The live working-order rows (the ones ``on_trade`` fills)."""
        return [order for order in self._orders if order["status"] == "working"]

    # ══════════════════════════════════════════════════════════════
    # The tape
    # ══════════════════════════════════════════════════════════════

    def on_trade(self, price: float, size: float, side: str, ts_ms: int) -> list[dict[str, Any]]:
        """Feed one print — the tape's trade. Returns the fills it produced, in the order they fired.

        That order is the whole trading model in one place: working **market orders first** (the
        next print *is* this one), then **limit and stop entries** whose price this print reached,
        then the open position's **stop-loss / take-profit** against the print. An exit does not
        cancel working orders — that stays the caller's decision.
        """
        mark_price = _number(price)
        if mark_price is None:
            logger.debug("paper %s: ignored a print with no usable price (%r)", self.symbol, price)
            return []
        self._last_price = mark_price
        self._last_print = {"price": mark_price, "size": _number(size) or 0.0,
                            "side": _text(side), "ts_ms": _ms(ts_ms)}
        if self._net != 0:
            self._note_excursion(mark_price)   # §148: the print is part of the position's own path
        fills: list[dict[str, Any]] = []
        for order in list(self._working()):
            if order["kind"] == "market":
                fills.append(self._fill(order, mark_price, ts_ms, "market"))
        for order in list(self._working()):
            if order["kind"] == "limit" and _level_reached(order, mark_price):
                fills.append(self._fill(order, order["price"], ts_ms, "limit"))
            elif order["kind"] == "stop" and _level_reached(order, mark_price):
                fills.append(self._fill(order, order["price"], ts_ms, "stop"))
        # The plan moves the stop *before* the print is measured against it: a break-even or trailing
        # stop this print armed is the stop this print is judged by, which is what "move to break-even
        # as soon as it pays" has to mean to be worth having.
        step = self._advance_plan(mark_price, ts_ms)
        exit_fill = self._exit_on_print(mark_price, ts_ms)
        if exit_fill is None and step.get("exit"):
            exit_fill = self._exit(str(step["exit"]["reason"]), float(step["exit"]["price"]), ts_ms)
        if exit_fill is not None:
            fills.append(exit_fill)
        return fills

    def flatten(self, price: float, ts_ms: int) -> list[dict[str, Any]]:
        """Close whatever is open at ``price`` — the caller's own print, reason ``flatten``.

        Returns the one fill that closed the position, or ``[]`` when there was nothing to close
        (including when ``price`` is unusable: a flatten that cannot be priced is not a fill).
        """
        px = _number(price)
        if px is None:
            logger.debug("paper %s: flatten ignored, price %r is unusable", self.symbol, price)
            return []
        self._last_price = px
        if self._net == 0:
            return []
        self._note_excursion(px)                     # §148: the flatten price is part of the path
        return [self._exit("flatten", px, ts_ms)]

    # ── the bracket, edited as a pair ────────────────────────────────────────────────────

    def set_exits(self, *, stop_loss: Any = None, take_profit: Any = None,
                  ts_ms: int = 0) -> dict[str, Any]:
        """Replace the open position's exits — a bracket is one intent pair, edited in one call.

        Both fields mean "what the position carries afterwards": a positive price sets it,
        ``None`` clears it, and anything else is refused with the sentence (junk must never
        silently clear a stop). Refused while flat: an exit without a position is a resting
        order, and this account models those separately. Whether either level ever fills stays
        the tape's call, exactly as at submission.

        Editing a plan's exits by hand releases the plan from managing them: the levels become the
        user's, the break-even move and the trail stop, and the plan says so in ``managed``. The
        plan's clock is not a level and keeps running: a nudged stop does not cancel a time exit.
        """
        if self._net == 0:
            return {"ok": False, "reason": "no open position — exits belong to a position, not to the book"}
        clean: dict[str, Any] = {}
        for field, value in (("stop_loss", stop_loss), ("take_profit", take_profit)):
            if value is None or value == "":
                clean[field] = None
                continue
            out = _number(value)
            if out is None or out <= 0:
                return {"ok": False,
                        "reason": f"{field} must be a positive price, or empty to clear it"}
            clean[field] = out
        changed = (clean["stop_loss"] != self._stop_loss) or (clean["take_profit"] != self._take_profit)
        self._stop_loss = clean["stop_loss"]
        self._take_profit = clean["take_profit"]
        released = False
        if self._plan is not None and str(self._plan.get("status") or "live") == "live":
            # A typed price beats a template: the plan keeps the levels it was edited to and stops
            # managing them, so nothing moves a stop out from under the user's own hand.
            self._plan["managed"] = False
            self._plan["stop_loss"] = self._stop_loss
            self._plan["take_profit"] = self._take_profit
            released = True
        return {"ok": True, "changed": changed, "stop_loss": self._stop_loss,
                "take_profit": self._take_profit, "plan_released": released, "ts_ms": _ms(ts_ms)}

    def exits(self) -> dict[str, Any]:
        """The open position's exits as the UI edits them: a price, or ``None`` when unset."""
        return {"stop_loss": self._stop_loss, "take_profit": self._take_profit}

    # ── the plan: a template's bracket, live on the position ─────────────────────────────

    def plan(self) -> Optional[dict[str, Any]]:
        """The position's plan — or the last one, marked ``done`` — as a copy. ``None`` when there is none.

        This is what the ladder draws: the legs, where the stop has travelled to, whether the
        break-even move has happened, how far the trade ever got, and how it ended.
        """
        return dict(self._plan) if self._plan else None

    def set_plan(self, template: Any, *, ts_ms: int = 0, price: Any = None) -> dict[str, Any]:
        """Attach a template's bracket to the open position — for the fill you took before planning.

        §148 T1-D9: nothing in the app calls this yet. The Replay view reaches a bracket the way the
        ladder sends it, on the order that OPENS the position; a route for attaching one to a
        position that is already open has not landed, so today this is a tested API a caller (a test,
        a future route) reaches directly — not a control any user surface offers.

        The levels are measured from ``price`` (the position's own entry by default) and applied at
        once. Refused while flat, exactly as ``set_exits`` is: a plan belongs to a position, not to
        the book. An older plan on the same position is retired, and its resting orders with it.
        """
        if self._net == 0:
            return {"ok": False, "reason": "no open position — a plan belongs to a position, not to the book"}
        if isinstance(template, dict):
            cleaned = atm.clean_template(template)
            if not (cleaned["stop_ticks"] or cleaned["target_ticks"] or cleaned["trail_ticks"]
                    or cleaned["time_stop_min"]):
                return {"ok": False,
                        "reason": "that plan names no stop, target, trail or clock — there is no plan in it"}
        else:
            cleaned = atm.template_of(atm.DEFAULTS, template)
            if cleaned is None:
                return {"ok": False, "reason": (f"'{str(template)[:24]}' is not a template this build "
                                                f"ships — pick one from the ladder")}
        if self._plan is not None:
            self._cancel_group(str(self._plan.get("group") or ""), "cancelled — its plan was replaced")
        base = _positive(price) or self._entry_price
        self._plan_seq += 1
        p = atm.plan("buy" if self._net > 0 else "sell", abs(self._net), base, cleaned,
                     tick_size=self.tick_size, ts_ms=ts_ms, group=f"oc{self._plan_seq}")
        if not p.get("ok"):
            return {"ok": False, "reason": str(p.get("reason") or "that plan could not be built")}
        self._plan = p
        self._stop_loss = _positive(p.get("stop_loss"))
        self._take_profit = _positive(p.get("take_profit"))
        self._place_partial(p, _ms(ts_ms))
        return {"ok": True, "changed": True, "plan": dict(p), "text": str(p.get("text") or ""),
                "stop_loss": self._stop_loss, "take_profit": self._take_profit, "ts_ms": _ms(ts_ms)}

    def _note_unarmed_template(self, order: Optional[dict[str, Any]]) -> None:
        """Say on the row that the template it carried was not built into a plan (§148 T1-D4).

        A template arms only when the order opens a position — ``_arm_plan`` runs on a fresh fill or
        on a flip. An order that fills against a position already open (an add, a scale-out, a
        reduce) keeps the plan the position has, so its template is dropped. Dropping it silently
        left the row advertising a bracket that was never built; the row keeps both facts now: the
        template that was sent, and this note saying it was not used.
        """
        if order is not None and order.get("plan_template"):
            order["plan_template_note"] = (
                "not armed — a template is built into a plan by the order that opens the position; "
                "this order filled against one that was already open")

    def _arm_plan(self, order: Optional[dict[str, Any]], price: float, ts_ms: int) -> Optional[dict[str, Any]]:
        """Build the plan the filling order carried and put its legs on the position just opened."""
        template = (order or {}).get("plan_template")
        if not template:
            # §148 T1-D8: the order that opens the position decides its plan. With no template there
            # is none — so a settled plan from the position before this one is dropped here, instead
            # of leaving ``plan()`` describing a closed trade while a new position runs on.
            self._plan = None
            return None
        self._plan_seq += 1
        p = atm.plan("buy" if self._net > 0 else "sell", abs(self._net), price, template,
                     tick_size=self.tick_size, kind=str((order or {}).get("kind") or "market"),
                     ts_ms=ts_ms, group=f"oc{self._plan_seq}")
        if not p.get("ok"):
            logger.debug("paper %s: the order's plan was refused — %s", self.symbol, p.get("reason"))
            return None
        self._plan = p
        if order is not None:
            order["plan"] = p["group"]
        self._stop_loss = _positive(p.get("stop_loss"))
        self._take_profit = _positive(p.get("take_profit"))
        self._place_partial(p, ts_ms)
        return p

    def _place_partial(self, plan: dict[str, Any], ts_ms: int) -> Optional[dict[str, Any]]:
        """Rest the plan's partial as a reduce-only limit, so the tape decides when it is taken.

        The order carries the plan's group and its leg name, which is what makes the OCO sibling
        cancel real: when the position leaves, the group's working orders leave with it. If the tape
        has already passed the level the account refuses it — the same rule every other limit obeys —
        and the plan carries on without a partial rather than inventing one.
        """
        part = (plan or {}).get("partial")
        if not part or self._net == 0:
            return None
        order = self.submit("sell" if self._net > 0 else "buy", float(part["size"]), kind="limit",
                            price=float(part["price"]), ts_ms=ts_ms)
        order["plan_leg"] = "partial"
        order["group"] = str(plan.get("group") or "")
        if order["status"] == "rejected":
            plan["partial"] = None
            plan["partial_note"] = str(order.get("reason") or "")
            return order
        plan["partial_order"] = order["id"]
        return order

    def _advance_plan(self, price: float, ts_ms: int) -> dict[str, Any]:
        """One print's worth of plan management: break-even, the trail, the clock.

        Returns the pure module's step (``actions``, ``exit``) so a caller can see what the print
        moved. A plan whose exits the user has since edited by hand keeps them: ``managed`` is False
        from that moment, so the break-even move and the trail are not touched. Its clock is not a
        level, though, and it still runs (§148 T1-D7 — a nudged stop used to take the time stop with
        it, silently, because the whole step was skipped).
        """
        if self._plan is None or self._net == 0:
            return {}
        step = atm.advance(self._plan, price=price, ts_ms=ts_ms, tick_size=self.tick_size,
                           levels=self._plan.get("managed") is not False)
        if not step.get("ok"):
            return step
        self._plan.update({"stop_loss": step["stop_loss"], "take_profit": step["take_profit"],
                           "trail_stop": step["trail_stop"], "peak": step["peak"],
                           "breakeven_done": step["breakeven_done"]})
        if step["changed"]:
            self._stop_loss = _positive(step.get("stop_loss"))
            self._take_profit = _positive(step.get("take_profit"))
        return step

    def _settle_plan(self, reason: str, ts_ms: int) -> Optional[dict[str, Any]]:
        """The position has left: settle the plan, and cancel whatever it still had resting.

        This is the OCO half that matters in practice. A bracket's legs are siblings, so the moment
        one of them is the reason the position is gone the others stop existing — a partial limit
        left resting on a closed position would open a new one nobody asked for.
        """
        if self._plan is None:
            return None
        cancelled = self._cancel_group(str(self._plan.get("group") or ""),
                                       "cancelled — the position closed")
        self._plan = atm.finish(self._plan, _plan_outcome(reason), ts_ms=ts_ms)
        self._plan["cancelled"] = cancelled
        return self._plan

    def _cancel_group(self, group: str, reason: str) -> list[str]:
        """Cancel every working order of an OCO group — the siblings of the leg that filled."""
        if not group:
            return []
        out: list[str] = []
        for order in self._working():
            if str(order.get("group") or "") == group:
                order["status"] = "cancelled"
                order["reason"] = reason
                out.append(order["id"])
        return out

    def _mark_partial_done(self) -> None:
        """Record that the plan's scale-out filled, so the ladder can stop drawing it as pending."""
        if self._plan is not None and str(self._plan.get("status") or "live") == "live":
            self._plan["partial_done"] = True

    def _fill(self, order: dict[str, Any], price: float, ts_ms: int, reason: str) -> dict[str, Any]:
        """Fill one order at ``price`` — the level it named, or the print for a market order."""
        order["status"] = "filled"
        order["filled_ms"] = _ms(ts_ms)
        order["fill_price"] = float(price)
        order["reason"] = reason
        fill = {"order_id": order["id"], "side": order["side"], "size": order["size"],
                "price": float(price), "ts_ms": _ms(ts_ms), "kind": order["kind"], "reason": reason}
        self._apply(fill, order)
        return fill

    def _exit_on_print(self, price: float, ts_ms: int) -> Optional[dict[str, Any]]:
        """Close the position if this print touched its stop or its target (stop checked first)."""
        if self._net == 0:
            return None
        long = self._net > 0
        stop, target = self._stop_loss, self._take_profit
        if stop is not None and (price <= stop if long else price >= stop):
            return self._exit("stop_loss", stop, ts_ms)
        if target is not None and (price >= target if long else price <= target):
            return self._exit("take_profit", target, ts_ms)
        return None

    def _exit(self, reason: str, level: float, ts_ms: int) -> dict[str, Any]:
        """Close the whole position at ``level`` — a plan's exit, or a flatten. No order behind it."""
        fill = {"order_id": None, "side": "sell" if self._net > 0 else "buy", "size": abs(self._net),
                "price": float(level), "ts_ms": _ms(ts_ms), "kind": reason, "reason": reason}
        self._apply(fill, None)
        return fill

    def _apply(self, fill: dict[str, Any], order: Optional[dict[str, Any]]) -> None:
        """Move the position, bank the PnL, journal the leg — the one place a fill changes state.

        Same direction as the open position: the entry becomes the size-weighted average and the
        position keeps the age and the exits it already had. Opposite direction: the position is
        **reduced first** (that leg lands in ``closed_trades``), and any remainder **flips** into a
        new position at the fill price, adopting the exits of the order that did the flipping.
        """
        size = float(fill["size"])
        price = float(fill["price"])
        signed = size if fill["side"] == "buy" else -size
        net = self._net + signed
        if self._net == 0 or (self._net > 0) == (signed > 0):
            total = abs(self._net) + size
            fresh = self._net == 0
            self._entry_price = ((self._entry_price * abs(self._net)) + (price * size)) / total
            if fresh:                                # a fresh position takes its order's exits
                self._entry_ms = _ms(fill["ts_ms"])
                self._adopt_exits(order)
            self._net = net
            if fresh:                                # ...and the bracket its order carried
                self._arm_plan(order, price, _ms(fill["ts_ms"]))
                # §148: captured AFTER the plan arms — an order-level stop and a template-armed one
                # both land in `_stop_loss`, and this is the level BE/trail later move.
                self._entry_stop = self._stop_loss
                self._excursion_worst = self._excursion_best = price   # the price path starts here
            else:                                    # §148 T1-D4: an add cannot arm a template
                self._note_unarmed_template(order)
            if order is not None and str(order.get("plan_leg") or "") == "partial":
                self._mark_partial_done()
            return

        direction = 1 if self._net > 0 else -1
        closed = min(abs(self._net), size)
        leg = (price - self._entry_price) * direction * closed
        self._realised += leg
        self._closed.append({
            "instrument": self.symbol,
            "direction": "long" if direction > 0 else "short",
            "entry_time_ms": self._entry_ms,
            "exit_time_ms": _ms(fill["ts_ms"]),
            "entry_price": self._entry_price,
            "exit_price": price,
            "stop_loss": self._entry_stop if self._entry_stop is not None else 0.0,   # §148: the R basis
            "take_profit": self._take_profit if self._take_profit is not None else 0.0,
            "pnl_ticks": self._ticks(leg),
            "rr_ratio": self._rr(),
            "mae_ticks": self._excursion_ticks(adverse=True),
            "mfe_ticks": self._excursion_ticks(adverse=False),
        })
        self._net = net
        if net == 0:                                 # flat: the position's levels go with it
            self._entry_price = 0.0
            self._entry_ms = 0
            self._entry_stop = None
            self._excursion_worst = self._excursion_best = None
            self._stop_loss = None
            self._take_profit = None
            self._settle_plan(str(fill.get("reason") or ""), _ms(fill["ts_ms"]))
        elif (net > 0) == (direction > 0):
            # reduced only: entry, age and exits survive — and so does the plan. §148 T1-D4: a
            # template on a reducing order never arms either, and the row now says so.
            self._note_unarmed_template(order)
        else:                                        # flipped: the remainder opened at this fill
            self._settle_plan("flip", _ms(fill["ts_ms"]))   # the old plan left with the old position
            self._entry_price = price
            self._entry_ms = _ms(fill["ts_ms"])
            self._adopt_exits(order)
            self._arm_plan(order, price, _ms(fill["ts_ms"]))   # and the new position takes its bracket
            self._entry_stop = self._stop_loss       # §148: the flipped position's own risk basis
            self._excursion_worst = self._excursion_best = price
        if order is not None and str(order.get("plan_leg") or "") == "partial":
            self._mark_partial_done()

    def _adopt_exits(self, order: Optional[dict[str, Any]]) -> None:
        """A new position inherits the exits of the order that opened it (``None`` clears them)."""
        self._stop_loss = _positive(order.get("stop_loss")) if order else None
        self._take_profit = _positive(order.get("take_profit")) if order else None

    def _note_excursion(self, price: float) -> None:
        """Fold one print into the open position's worst/best excursion (the journal's MAE/MFE).

        Direction-aware at the source: ``_excursion_worst`` is the print most against the trade and
        ``_excursion_best`` the print most for it, so a short's adverse side is the HIGHER price.
        (Measured before this shape: the note kept long-perspective min/max, the ticks helper then
        applied the direction again, and a short's excursions both read 0.)
        """
        px = float(price)
        if self._excursion_worst is None or self._excursion_best is None:
            self._excursion_worst = self._excursion_best = px
            return
        if self._net > 0:                            # long: a lower print is the adverse one
            self._excursion_worst = min(self._excursion_worst, px)
            self._excursion_best = max(self._excursion_best, px)
        else:                                        # short: a higher print is the adverse one
            self._excursion_worst = max(self._excursion_worst, px)
            self._excursion_best = min(self._excursion_best, px)

    def _excursion_ticks(self, *, adverse: bool) -> float:
        """One side of the excursion as ticks against the row's own entry: MAE or MFE.

        MAE is the worst move against the trade and MFE the best for it, both positive by
        convention. The excursion is position-level, so every leg of a scale-out carries the same
        pair; a row with no excursion recorded (an old session, a position that never printed
        while it was open) answers 0.0, which the analytics read as "not recorded".
        """
        if self._excursion_worst is None or self._excursion_best is None or self._net == 0:
            return 0.0
        entry = float(self._entry_price)
        long = self._net > 0
        if adverse:                                  # worst is already on the adverse side
            move = (entry - self._excursion_worst) if long else (self._excursion_worst - entry)
        else:
            move = (self._excursion_best - entry) if long else (entry - self._excursion_best)
        return round(max(0.0, move) / self.tick_size, TICK_DECIMALS)

    # ══════════════════════════════════════════════════════════════
    # What the account looks like now
    # ══════════════════════════════════════════════════════════════

    def position(self) -> dict[str, Any]:
        """The open position as the Replay view shows it: side, size, entry price and age."""
        if self._net == 0:
            return {"side": "flat", "size": 0.0, "entry_price": 0.0, "entry_ms": 0}
        return {"side": "long" if self._net > 0 else "short", "size": abs(self._net),
                "entry_price": self._entry_price, "entry_ms": self._entry_ms}

    def mark(self, price: float) -> dict[str, float]:
        """The account valued at ``price``, in ticks — the journal's unit.

        ``balance_ticks`` is the funded balance in ticks plus what has been realised;
        ``equity_ticks`` adds the open position. A mark is a valuation, never a fill: it also sets
        the last price ``stats`` values against, but only ``on_trade`` moves the position.
        """
        px = _number(price)
        if px is not None:
            self._last_price = px
        unrealised = self._unrealised_ticks()
        balance = self._balance_ticks()
        return {"unrealised_ticks": unrealised, "equity_ticks": balance + unrealised,
                "balance_ticks": balance}

    def stats(self) -> dict[str, Any]:
        """The session in numbers: order counts, closed trades, wins/losses and PnL in ticks."""
        realised = self._ticks(self._realised)
        unrealised = self._unrealised_ticks()
        return {
            "orders_submitted": len(self._orders),     # every submit(), refusals included
            "orders_filled": sum(1 for o in self._orders if o["status"] == "filled"),
            "orders_rejected": sum(1 for o in self._orders if o["status"] == "rejected"),
            "closed": len(self._closed),
            "wins": sum(1 for row in self._closed if row["pnl_ticks"] > 0),
            "losses": sum(1 for row in self._closed if row["pnl_ticks"] < 0),
            "realised_ticks": realised,
            "unrealised_ticks": unrealised,
            "equity_ticks": self._balance_ticks() + unrealised,
        }

    def closed_trades(self) -> list[dict[str, Any]]:
        """Every closed leg, oldest first, as rows shaped like the app's ``trade_journal`` columns."""
        return [dict(row) for row in self._closed]

    # ══════════════════════════════════════════════════════════════
    # Ticks, the journal's unit
    # ══════════════════════════════════════════════════════════════

    def _ticks(self, price_delta: float) -> float:
        """A price move × size as ticks, rounded so float noise never reaches a journal row."""
        return round(price_delta / self.tick_size, TICK_DECIMALS)

    def _rr(self) -> float:
        """The reward:risk the position was opened with, the way ``data.models.TradeState`` reads it."""
        stop, target = self._stop_loss, self._take_profit
        if stop is None or target is None:
            return 0.0
        risk = abs(self._entry_price - stop)
        return abs(target - self._entry_price) / risk if risk > 0 else 0.0

    def _unrealised_ticks(self) -> float:
        """The open position's PnL at the last price seen (a print or a mark), in ticks."""
        if self._net == 0 or self._last_price is None:
            return 0.0
        direction = 1 if self._net > 0 else -1
        return self._ticks((self._last_price - self._entry_price) * direction * abs(self._net))

    def _balance_ticks(self) -> float:
        """The funded balance expressed in ticks, plus everything realised so far."""
        return round(self.starting_balance / self.tick_size, TICK_DECIMALS) + self._ticks(self._realised)

    # ══════════════════════════════════════════════════════════════
    # Sessions: store and restore
    # ══════════════════════════════════════════════════════════════

    def to_dict(self) -> dict[str, Any]:
        """The whole account as JSON-ready data — no objects inside, so a session can be stored."""
        return {
            "symbol": self.symbol,
            "tick_size": self.tick_size,
            "starting_balance": self.starting_balance,
            "max_position": self.max_position,
            "next_id": self._next_id,
            "orders": [dict(order) for order in self._orders],
            "position": {"net": self._net, "entry_price": self._entry_price,
                         "entry_ms": self._entry_ms, "stop_loss": self._stop_loss,
                         "entry_stop": self._entry_stop,
                         "excursion_worst": self._excursion_worst,
                         "excursion_best": self._excursion_best,
                         "take_profit": self._take_profit},
            "realised": self._realised,
            "closed_trades": [dict(row) for row in self._closed],
            "last_price": self._last_price,
            "last_print": dict(self._last_print) if self._last_print else None,
            "plan": dict(self._plan) if self._plan else None,
            "plan_seq": self._plan_seq,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PaperAccount":
        """Rebuild an account from ``to_dict`` output, including the order log and the next id.

        Tolerant by design — a hand-edited or older file restores what it can and defaults the
        rest, rather than refusing to open a session the user saved.
        """
        data = data or {}
        account = cls(
            symbol=str(data.get("symbol") or ""),
            tick_size=_number(data.get("tick_size")) or 0.01,
            starting_balance=_number(data.get("starting_balance")) or 0.0,
            max_position=data.get("max_position"),
        )
        account._orders = [dict(order) for order in data.get("orders") or []
                           if isinstance(order, dict)]
        account._next_id = int(_number(data.get("next_id")) or (len(account._orders) + 1))
        held = data.get("position") or {}
        account._net = _number(held.get("net")) or 0.0
        account._entry_price = _number(held.get("entry_price")) or 0.0
        account._entry_ms = _ms(held.get("entry_ms"))
        account._stop_loss = _positive(held.get("stop_loss"))
        # §148: older files have no entry_stop; the level the stop is at now is the best estimate
        # available for the risk basis, and it is only consulted for trades that close from here.
        account._entry_stop = _positive(held.get("entry_stop")) or account._stop_loss
        account._excursion_worst = _number(held.get("excursion_worst"))
        account._excursion_best = _number(held.get("excursion_best"))
        account._take_profit = _positive(held.get("take_profit"))
        account._realised = _number(data.get("realised")) or 0.0
        account._closed = [dict(row) for row in data.get("closed_trades") or []
                           if isinstance(row, dict)]
        account._last_price = _number(data.get("last_price"))
        last = data.get("last_print")
        account._last_print = dict(last) if isinstance(last, dict) else None
        held_plan = data.get("plan")
        account._plan = dict(held_plan) if isinstance(held_plan, dict) else None
        account._plan_seq = int(_number(data.get("plan_seq")) or 0)
        return account
