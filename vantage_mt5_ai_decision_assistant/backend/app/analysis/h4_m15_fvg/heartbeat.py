"""Process H4/M15 closed candles from EA heartbeat into Python engine output."""
from __future__ import annotations

from typing import Any

from app.analysis.h4_m15_fvg.service import analyze_h4_m15_fvg, candles_from_request


def process_h4_m15_fvg_heartbeat(payload: dict[str, Any]) -> dict[str, Any] | None:
    """
    Run canonical H4→M15 analysis when heartbeat includes closed candle arrays.

    Expected payload keys:
      - symbol / broker_symbol
      - h4_m15_fvg_candles: { "H4": [...], "M15": [...] }
    """
    candles_raw = payload.get("h4_m15_fvg_candles")
    if not isinstance(candles_raw, dict):
        return None

    symbol = str(payload.get("symbol") or payload.get("broker_symbol") or "XAUUSD").upper()
    by_tf = candles_from_request(candles_raw)
    if not by_tf.get("H4") and not by_tf.get("M15"):
        return None

    result = analyze_h4_m15_fvg(
        symbol=symbol,
        candles_by_timeframe=by_tf,
        persist=True,
    )
    result["source"] = "heartbeat"
    result["engine"] = "python"
    return result
