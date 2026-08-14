"""Process ICT closed candles from EA heartbeat through canonical Python engine."""
from __future__ import annotations

from typing import Any

from app.analysis.ict.service import analyze_ict_strategy
from app.market_structure import candles_from_payload


def candles_from_request(candles_raw: dict[str, Any]) -> dict[str, list]:
    """Parse heartbeat ``ict_candles`` object into timeframe → Candle lists."""
    by_tf: dict[str, list] = {}
    for key, rows in candles_raw.items():
        if isinstance(rows, list):
            by_tf[str(key).upper()] = candles_from_payload(rows)
    return by_tf


def process_ict_heartbeat(payload: dict[str, Any]) -> dict[str, Any] | None:
    """
    Run canonical ICT analysis when heartbeat includes closed candle arrays.

    Expected keys:
      - symbol / broker_symbol
      - bid, spread_points (optional)
      - ict_candles: { D1, H4, H1, M15, M5 }
      - ict (optional MQL5 legacy snapshot — preserved separately, not used for decisions)
    """
    candles_raw = payload.get("ict_candles")
    if not isinstance(candles_raw, dict):
        return None

    by_tf = candles_from_request(candles_raw)
    if not by_tf.get("M15") and not by_tf.get("M5"):
        return None

    symbol = str(payload.get("symbol") or payload.get("broker_symbol") or "XAUUSD").upper()
    bid = float(payload.get("bid") or 0)
    spread = float(payload.get("spread_points") or payload.get("spread") or 0)

    result = analyze_ict_strategy(
        symbol=symbol,
        candles_by_timeframe=by_tf,
        bid=bid,
        spread_points=spread,
    )
    result["source"] = "heartbeat"
    result["engine_source"] = "PYTHON_CANONICAL"

    legacy = payload.get("ict")
    if isinstance(legacy, dict):
        result["mql5_legacy"] = {
            "engine_source": "MQL5_LEGACY",
            "setup_state": legacy.get("setup_state") or legacy.get("status"),
            "decision": legacy.get("decision"),
            "confidence": legacy.get("confidence") or legacy.get("confidence_score"),
        }

    try:
        from app.ict_discord_notify import maybe_ict_alert

        maybe_ict_alert({"ict": result})
    except Exception:
        pass

    return result
