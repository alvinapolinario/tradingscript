"""Fair Value Gap detection, mitigation, and inversion (iFVG)."""
from __future__ import annotations

from typing import Any, Protocol

from app.market_structure.types import Candle, FvgStatus, FvgZone


class FvgSettings(Protocol):
    fvg_min_gap_atr: float
    ifvg_min_break_atr: float
    ifvg_require_body_close: bool


def detect_fvgs(
    candles: list[Candle],
    *,
    timeframe: str,
    atr: float,
    cfg: FvgSettings,
    start_idx: int = 2,
) -> list[FvgZone]:
    """Three-candle FVG model on closed bars (indices 0=oldest)."""
    out: list[FvgZone] = []
    min_gap = cfg.fvg_min_gap_atr * atr
    for i in range(max(start_idx, 2), len(candles)):
        c1, c2, c3 = candles[i - 2], candles[i - 1], candles[i]
        body = abs(c2.close - c2.open)
        body_atr = body / atr if atr else 0.0
        disp = min(100.0, body_atr * 50.0)
        if c3.low > c1.high:
            gap = c3.low - c1.high
            if gap >= min_gap:
                out.append(
                    FvgZone(
                        fvg_id=f"FVG-B-{timeframe}-{c3.time}",
                        direction="BULLISH",
                        timeframe=timeframe,
                        created_time=c3.time,
                        lower=c1.high,
                        upper=c3.low,
                        gap_size=gap,
                        gap_atr=gap / atr if atr else 0.0,
                        displacement_score=disp,
                    )
                )
        if c3.high < c1.low:
            gap = c1.low - c3.high
            if gap >= min_gap:
                out.append(
                    FvgZone(
                        fvg_id=f"FVG-S-{timeframe}-{c3.time}",
                        direction="BEARISH",
                        timeframe=timeframe,
                        created_time=c3.time,
                        lower=c3.high,
                        upper=c1.low,
                        gap_size=gap,
                        gap_atr=gap / atr if atr else 0.0,
                        displacement_score=disp,
                    )
                )
    return out


def update_fvg_mitigation(fvg: FvgZone, price: float) -> None:
    if fvg.status in (FvgStatus.INVERTED, FvgStatus.INVALIDATED, FvgStatus.EXPIRED):
        return
    width = fvg.upper - fvg.lower
    if width <= 0:
        return
    if fvg.direction == "BULLISH":
        if price <= fvg.lower:
            fvg.mitigation_pct = 100.0
            fvg.status = FvgStatus.FULLY_MITIGATED
        elif price < fvg.upper:
            fvg.mitigation_pct = max(fvg.mitigation_pct, (fvg.upper - price) / width * 100.0)
            if fvg.mitigation_pct >= 50:
                fvg.status = FvgStatus.PARTIALLY_MITIGATED
    else:
        if price >= fvg.upper:
            fvg.mitigation_pct = 100.0
            fvg.status = FvgStatus.FULLY_MITIGATED
        elif price > fvg.lower:
            fvg.mitigation_pct = max(fvg.mitigation_pct, (price - fvg.lower) / width * 100.0)
            if fvg.mitigation_pct >= 50:
                fvg.status = FvgStatus.PARTIALLY_MITIGATED


def try_invert_fvg(
    fvg: FvgZone,
    candle: Candle,
    atr: float,
    cfg: FvgSettings,
) -> bool:
    """Decisive body close beyond FVG → iFVG."""
    if fvg.inverted or fvg.status == FvgStatus.EXPIRED:
        return False
    min_break = cfg.ifvg_min_break_atr * atr
    if fvg.direction == "BULLISH":
        if cfg.ifvg_require_body_close and candle.close >= fvg.lower:
            return False
        if candle.close < fvg.lower - min_break:
            fvg.original_direction = fvg.direction
            fvg.direction = "BEARISH"
            fvg.inverted = True
            fvg.inversion_time = candle.time
            fvg.status = FvgStatus.INVERTED
            return True
    elif fvg.direction == "BEARISH":
        if cfg.ifvg_require_body_close and candle.close <= fvg.upper:
            return False
        if candle.close > fvg.upper + min_break:
            fvg.original_direction = fvg.direction
            fvg.direction = "BULLISH"
            fvg.inverted = True
            fvg.inversion_time = candle.time
            fvg.status = FvgStatus.INVERTED
            return True
    return False
