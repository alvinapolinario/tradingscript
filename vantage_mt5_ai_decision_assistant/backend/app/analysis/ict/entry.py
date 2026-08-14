"""ICT entry zone from FVG retrace."""
from __future__ import annotations

from app.analysis.ict.types import EntryZone
from app.market_structure.types import FvgZone


def build_entry_zone(fvg: FvgZone, trade_bias: str) -> EntryZone:
    direction = "BUY" if trade_bias == "BULLISH" else "SELL"
    return EntryZone(
        type="FVG_RETRACE",
        direction=direction,
        zone_high=fvg.upper,
        zone_low=fvg.lower,
        midpoint=fvg.midpoint,
        status="ACTIVE",
    )


def update_mitigation(fvg: FvgZone, price: float) -> None:
    """Track CE / mitigation depth for explainability."""
    if fvg.upper <= fvg.lower:
        return
    span = fvg.upper - fvg.lower
    if fvg.direction == "BULLISH":
        depth = (fvg.upper - price) / span
    else:
        depth = (price - fvg.lower) / span
    depth = max(0.0, min(1.0, depth))
    fvg.mitigation_pct = round(depth * 100.0, 1)
