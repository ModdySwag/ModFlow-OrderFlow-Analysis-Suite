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

logger = logging.getLogger(__name__)

#: Order kinds a caller can submit; anything else is rejected with a reason rather than raising.
ORDER_KINDS = ("market", "limit", "stop")
#: Sides, lower-case — the vocabulary of ``data.models.Side`` and of the journal.
SIDES = ("buy", "sell")
#: Why a fill happened: the order's own kind, or the exit that closed the position.
FILL_REASONS = ("market", "limit", "stop", "stop_loss", "take_profit", "flatten")
#: Order lifecycle. ``cancelled`` is only ever reached through ``cancel``, never through ``submit``.
ORDER_STATUSES = ("working", "filled", "rejected", "cancelled")
#: The ``trade_journal`` columns a ``closed_trades`` row carries, in this order — so a session can
#: be handed to ``data.database.log_trade`` (or an INSERT) without a translation step.
JOURNAL_COLUMNS = ("instrument", "direction", "entry_time_ms", "exit_time_ms", "entry_price",
                   "exit_price", "stop_loss", "take_profit", "pnl_ticks", "rr_ratio")

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
        self._realised = 0.0       # banked PnL in price × size; turned into ticks on the way out
        self._closed: list[dict[str, Any]] = []
        self._last_price: Optional[float] = None
        self._last_print: Optional[dict[str, Any]] = None

    # ══════════════════════════════════════════════════════════════
    # Orders
    # ══════════════════════════════════════════════════════════════

    def submit(self, side: str, size: float, *, kind: str = "market", price: Optional[float] = None,
               stop_loss: Optional[float] = None, take_profit: Optional[float] = None,
               ts_ms: int = 0) -> dict[str, Any]:
        """Put an order on the book. Always returns an order row; a refusal is a row, not an error.

        A market order comes back ``working`` and fills on the next print; a limit or stop waits
        for a print at or through ``price``. ``stop_loss`` / ``take_profit`` ride along and become
        the position's exits if this order opens one. ``price`` on a market order is meaningless
        and stored as ``None``.

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
        if reason:
            order["status"] = "rejected"
            order["reason"] = reason
            logger.debug("paper %s: refused %s %s — %s",
                         self.symbol or "account", order["side"], order["kind"], reason)
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

    def cancel(self, order_id: str) -> bool:
        """Take a working order off the book. ``False`` when it never was (filled/cancelled/unknown)."""
        for order in self._orders:
            if order["id"] == order_id and order["status"] == "working":
                order["status"] = "cancelled"
                order["reason"] = "cancelled by the user"
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
        fills: list[dict[str, Any]] = []
        for order in list(self._working()):
            if order["kind"] == "market":
                fills.append(self._fill(order, mark_price, ts_ms, "market"))
        for order in list(self._working()):
            if order["kind"] == "limit" and _level_reached(order, mark_price):
                fills.append(self._fill(order, order["price"], ts_ms, "limit"))
            elif order["kind"] == "stop" and _level_reached(order, mark_price):
                fills.append(self._fill(order, order["price"], ts_ms, "stop"))
        exit_fill = self._exit_on_print(mark_price, ts_ms)
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
        return [self._exit("flatten", px, ts_ms)]

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
            self._entry_price = ((self._entry_price * abs(self._net)) + (price * size)) / total
            if self._net == 0:                       # a fresh position takes its order's exits
                self._entry_ms = _ms(fill["ts_ms"])
                self._adopt_exits(order)
            self._net = net
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
            "stop_loss": self._stop_loss if self._stop_loss is not None else 0.0,
            "take_profit": self._take_profit if self._take_profit is not None else 0.0,
            "pnl_ticks": self._ticks(leg),
            "rr_ratio": self._rr(),
        })
        self._net = net
        if net == 0:                                 # flat: the position's levels go with it
            self._entry_price = 0.0
            self._entry_ms = 0
            self._stop_loss = None
            self._take_profit = None
        elif (net > 0) == (direction > 0):
            return                                   # reduced only: entry, age and exits survive
        else:                                        # flipped: the remainder opened at this fill
            self._entry_price = price
            self._entry_ms = _ms(fill["ts_ms"])
            self._adopt_exits(order)

    def _adopt_exits(self, order: Optional[dict[str, Any]]) -> None:
        """A new position inherits the exits of the order that opened it (``None`` clears them)."""
        self._stop_loss = _positive(order.get("stop_loss")) if order else None
        self._take_profit = _positive(order.get("take_profit")) if order else None

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
                         "take_profit": self._take_profit},
            "realised": self._realised,
            "closed_trades": [dict(row) for row in self._closed],
            "last_price": self._last_price,
            "last_print": dict(self._last_print) if self._last_print else None,
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
        account._take_profit = _positive(held.get("take_profit"))
        account._realised = _number(data.get("realised")) or 0.0
        account._closed = [dict(row) for row in data.get("closed_trades") or []
                           if isinstance(row, dict)]
        account._last_price = _number(data.get("last_price"))
        last = data.get("last_print")
        account._last_print = dict(last) if isinstance(last, dict) else None
        return account
