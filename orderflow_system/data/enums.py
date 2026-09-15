"""Enum ↔ string boundary helpers.

The codebase historically tolerated enums and raw strings in the same paths with
``x.value if hasattr(x, 'value') else str(x)`` scattered across the hot code and the
REST layer (audit finding P5/P6). This module declares that boundary **once**:

    rule:  enums stay enums inside the engines and detectors;
           everything that crosses into JSON / WS / string logs goes through as_value().

Nothing else should do ad-hoc ``hasattr(x, "value")`` probing.
"""

from __future__ import annotations

from typing import Any


def as_value(value: Any, default: Any = None) -> Any:
    """Normalise an enum-or-string to its plain form.

    - an Enum (or anything carrying a ``value`` attribute) → that ``value``
    - an already-plain string → unchanged
    - ``None`` → *default*
    - anything else → ``str(value)``

    Matches the historical ``x.value if hasattr(x, "value") else str(x)`` idiom
    exactly, so replacing it is behaviour-preserving.
    """
    attr = getattr(value, "value", None)
    if attr is not None:
        return attr
    if value is None:
        return default
    if isinstance(value, str):
        return value
    return str(value)


def as_name(value: Any, default: Any = None) -> Any:
    """Like :func:`as_value` but prefers ``name`` (e.g. ``Side.BUY`` → ``"BUY"``)."""
    attr = getattr(value, "name", None)
    if attr is not None:
        return attr
    return as_value(value, default)
