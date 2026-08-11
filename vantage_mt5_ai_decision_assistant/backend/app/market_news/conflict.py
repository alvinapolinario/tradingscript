"""Macro vs technical direction conflict detection."""
from __future__ import annotations

from app.market_news.types import MacroBiasDirection, MacroConflictResult, MacroConflictStatus, normalize_bias

_BULLISH = {
    MacroBiasDirection.STRONGLY_BULLISH,
    MacroBiasDirection.BULLISH,
    MacroBiasDirection.MILD_BULLISH,
}
_BEARISH = {
    MacroBiasDirection.STRONGLY_BEARISH,
    MacroBiasDirection.BEARISH,
    MacroBiasDirection.MILD_BEARISH,
}


def _side(direction: MacroBiasDirection) -> str:
    if direction in _BULLISH:
        return "BULLISH"
    if direction in _BEARISH:
        return "BEARISH"
    return "NEUTRAL"


def macro_technical_conflict(
    macro_direction: MacroBiasDirection | str,
    technical_direction: MacroBiasDirection | str,
) -> MacroConflictResult:
    macro = normalize_bias(macro_direction.value if hasattr(macro_direction, "value") else str(macro_direction))
    technical = normalize_bias(
        technical_direction.value if hasattr(technical_direction, "value") else str(technical_direction)
    )
    macro_side = _side(macro)
    tech_side = _side(technical)

    if macro_side == "NEUTRAL" or tech_side == "NEUTRAL":
        return MacroConflictResult(
            status=MacroConflictStatus.NEUTRAL,
            recommendation="MONITOR",
            reason="Macro or technical bias is neutral",
            technical_direction=tech_side,
            macro_direction=macro_side,
        )
    if macro_side == tech_side:
        return MacroConflictResult(
            status=MacroConflictStatus.ALIGNED,
            recommendation="CONFIRM",
            reason=f"Macro {macro_side.lower()} aligns with technical {tech_side.lower()}",
            technical_direction=tech_side,
            macro_direction=macro_side,
        )

    return MacroConflictResult(
        status=MacroConflictStatus.CONFLICT,
        recommendation="WAIT",
        reason=f"Macro {macro_side.lower()} vs technical {tech_side.lower()} momentum",
        technical_direction=tech_side,
        macro_direction=macro_side,
    )
