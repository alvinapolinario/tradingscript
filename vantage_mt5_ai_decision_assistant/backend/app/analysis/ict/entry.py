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
