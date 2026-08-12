"""Offline outcome labeler for Pullback Desk V2 calibration rows."""
from __future__ import annotations

from typing import Any


def _ohlc(c: dict[str, Any]) -> tuple[float, float, float, float]:
    return (
        float(c.get("open") or c.get("o") or 0),
        float(c.get("high") or c.get("h") or 0),
        float(c.get("low") or c.get("l") or 0),
        float(c.get("close") or c.get("c") or 0),
    )


def label_pullback_outcome(row: dict[str, Any], future_candles: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Apply the M1/M6 research pullback event definition using future closed candles only.

    Bullish: future low <= ref_close - threshold_atr * atr before protected_low broken.
    Bearish: symmetric with protected_high.
    """
    dom = int(row.get("dom_dir") or row.get("dominant_direction") or 0)
    ref = float(row.get("ref_close") or row.get("reference_close") or 0)
    atr = float(row.get("atr_m15") or 0)
    threshold = float(row.get("threshold_atr") or row.get("pullback_threshold_atr") or 0.5)
    prot_low = float(row.get("protected_low") or 0)
    prot_high = float(row.get("protected_high") or 0)

    if dom == 0 or ref <= 0 or atr <= 0 or not future_candles:
        return {
            "label_status": "insufficient",
            "pullback_occurred": False,
            "reversal_before_pullback": False,
            "bars_to_pullback": None,
            "threshold_price": None,
        }

    if dom > 0:
        threshold_price = ref - threshold * atr
    else:
        threshold_price = ref + threshold * atr

    pullback_occurred = False
    reversal_first = False
    bars_to_pullback: int | None = None

    for i, candle in enumerate(future_candles):
        _, high, low, close = _ohlc(candle)
        if dom > 0:
            if prot_low > 0 and close < prot_low:
                reversal_first = True
                break
            if low <= threshold_price:
                pullback_occurred = True
                bars_to_pullback = i + 1
                break
        else:
            if prot_high > 0 and close > prot_high:
                reversal_first = True
                break
            if high >= threshold_price:
                pullback_occurred = True
                bars_to_pullback = i + 1
                break

    return {
        "label_status": "ok",
        "pullback_occurred": pullback_occurred,
        "reversal_before_pullback": reversal_first,
        "bars_to_pullback": bars_to_pullback,
        "threshold_price": round(threshold_price, 8),
    }


def label_rows(
    rows: list[dict[str, Any]],
    *,
    candles_m15: list[dict[str, Any]] | None = None,
    horizon_bars: int | None = None,
) -> dict[str, Any]:
    """Label CSV/log rows when aligned M15 future candles are supplied."""
    labeled: list[dict[str, Any]] = []
    candles = candles_m15 or []
    hz_default = horizon_bars or 6

    for idx, row in enumerate(rows):
        hz = int(row.get("horizon_bars") or hz_default)
        future = candles[idx + 1 : idx + 1 + hz] if candles else []
        outcome = label_pullback_outcome(row, future)
        labeled.append({**row, "outcome": outcome})

    ok = [r for r in labeled if r.get("outcome", {}).get("label_status") == "ok"]
    pullbacks = sum(1 for r in ok if r["outcome"].get("pullback_occurred"))
    return {
        "module": "pullback_v2_labeler",
        "milestone": 6,
        "row_count": len(rows),
        "labeled_count": len(ok),
        "pullback_occurred_count": pullbacks,
        "rows": labeled,
    }
