"""Every shipped instrument must be servable by the demo generator (v0.1b sweep finding).

`models_symbol()` correctly refuses to invent prices for unknown symbols — but six shipped
instruments (the four international indices NIKKEI225/CAC40/ASX200/HK50 and the two oils
USOIL/UKOIL) had no demo base price, so a demo-mode tour hit "no demo data" on them. Coverage
is now complete; this pins it so a new instrument cannot silently regress it again.
"""

from __future__ import annotations

from orderflow_system.config.settings import CRYPTO_MAJORS, INSTRUMENT_SPECS
from orderflow_system.dashboard import demo_data


def _shipped_symbols() -> set[str]:
    return {m.value for m in INSTRUMENT_SPECS} | set(CRYPTO_MAJORS)


def test_every_shipped_instrument_is_modelled_by_the_demo_generator():
    missing = sorted(s for s in _shipped_symbols() if not demo_data.models_symbol(s))
    assert missing == [], f"demo generator lacks base prices for: {missing}"


def test_unknown_symbols_still_serve_nothing():
    assert demo_data.models_symbol("UNKNOWNXYZ") is False
