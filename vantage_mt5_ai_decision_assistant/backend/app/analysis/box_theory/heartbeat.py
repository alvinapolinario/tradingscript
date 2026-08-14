"""Process Box Theory closed candles from EA heartbeat through Python engine."""
from __future__ import annotations

from typing import Any

from app.analysis.box_theory.service import analyze_box_strategy
from app.market_structure import candles_from_payload


def candles_from_request(candles_raw: dict[str, Any]) -> dict[str, list]:
    by_tf: dict[str, list] = {}
    for key, rows in candles_raw.items():
        if isinstance(rows, list):
            by_tf[str(key).upper()] = candles_from_payload(rows)
    return by_tf


def process_box_heartbeat(payload: dict[str, Any]) -> dict[str, Any] | None:
    """
    Run canonical Box Theory analysis when heartbeat includes closed candle arrays.

    Expected keys:
      - symbol / broker_symbol
      - bid, spread_points (optional)
      - box_candles: { H1, M15, M5 }
      - box_theory (optional MQL5 legacy snapshot)
    """
    candles_raw = payload.get("box_candles")
    if not isinstance(candles_raw, dict):
        return None

    by_tf = candles_from_request(candles_raw)
    m15 = by_tf.get("M15") or []
    m5 = by_tf.get("M5") or []
    if not m15 and not m5:
        return None

    symbol = str(payload.get("symbol") or payload.get("broker_symbol") or "XAUUSD").upper()
    bid = float(payload.get("bid") or 0)

    result = analyze_box_strategy(
        symbol=symbol,
        candles_box=m15 or m5,
        candles_entry=m5 or m15,
        candles_structure=by_tf.get("H1") or m15,
        bid=bid,
    )
    result["source"] = "heartbeat"
    result["engine_source"] = "PYTHON_CANONICAL"

    legacy = payload.get("box_theory")
    if isinstance(legacy, dict):
        result["mql5_legacy"] = {
            "engine_source": "MQL5_LEGACY",
            "box_status": legacy.get("box_status") or legacy.get("status"),
            "signal": legacy.get("signal"),
            "confidence": legacy.get("confidence") or legacy.get("confidence_score"),
        }

    try:
        from app.box_discord_notify import maybe_box_theory_alert

        maybe_box_theory_alert({"box_theory": result})
    except Exception:
        pass

    return result
