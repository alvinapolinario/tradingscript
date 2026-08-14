"""Read-only Signal Center advisory cards from canonical Python ICT monitor state."""
from __future__ import annotations

from typing import Any


def _side_from_blob(blob: dict[str, Any]) -> str:
    decision = str(blob.get("decision") or "").upper()
    if decision in ("BUY", "SELL"):
        return decision
    direction = str(blob.get("direction") or "").upper()
    if direction in ("BULLISH", "LONG", "BUY"):
        return "BUY"
    if direction in ("BEARISH", "SHORT", "SELL"):
        return "SELL"
    return ""


def build_ict_advisory_cards(ea: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Build advisory cards when ICT is ENTRY_READY on the Python canonical engine."""
    if not isinstance(ea, dict):
        return []

    blob = ea.get("ict")
    if not isinstance(blob, dict) or not (blob.get("valid") or blob.get("analysis_active")):
        return []

    if str(blob.get("engine_source") or "").upper() == "MQL5_LEGACY":
        return []

    state = str(blob.get("state") or blob.get("setup_state") or blob.get("status") or "").upper()
    entry_ready = bool(blob.get("entry_ready")) or state in ("ENTRY_READY", "TRIGGERED")
    if not entry_ready:
        return []

    if blob.get("causality_valid") is False:
        return []

    side = _side_from_blob(blob)
    if not side:
        return []

    exec_fvg = blob.get("execution_fvg") if isinstance(blob.get("execution_fvg"), dict) else {}
    fvg = blob.get("fvg") if isinstance(blob.get("fvg"), dict) else {}
    zone = exec_fvg or fvg
    entry_low = float(zone.get("lower") or zone.get("low") or 0.0)
    entry_high = float(zone.get("upper") or zone.get("high") or 0.0)
    entry = blob.get("entry") if isinstance(blob.get("entry"), dict) else {}
    if entry_low <= 0 and entry:
        entry_low = float(entry.get("zone_low") or 0.0)
        entry_high = float(entry.get("zone_high") or 0.0)

    sl = blob.get("stop_loss") if isinstance(blob.get("stop_loss"), dict) else {}
    targets = blob.get("targets") if isinstance(blob.get("targets"), list) else []
    tp1 = float(targets[0].get("price") or 0.0) if targets else 0.0

    ote = blob.get("ote") if isinstance(blob.get("ote"), dict) else {}
    ob = blob.get("order_block") if isinstance(blob.get("order_block"), dict) else {}
    confluence_tags: list[str] = []
    if ote.get("price_in_ote") or ote.get("fvg_overlaps_ote"):
        confluence_tags.append("OTE")
    if ob.get("block_id"):
        confluence_tags.append("Breaker" if ob.get("is_breaker") else "OB")
    conf_suffix = f" · {'+'.join(confluence_tags)}" if confluence_tags else ""

    return [
        {
            "source": "ICT",
            "kind": "advisory",
            "advisory_only": True,
            "symbol": str(blob.get("symbol") or ea.get("symbol") or "—"),
            "side": side,
            "timeframe": f"{blob.get('timeframe') or 'M15'}→{blob.get('execution_timeframe') or 'M5'}",
            "mode": "ICT_CAUSAL",
            "state": state or "ENTRY_READY",
            "decision": str(blob.get("decision") or side),
            "score": blob.get("confidence_score") or blob.get("confidence"),
            "grade": blob.get("signal_quality"),
            "setup_id": blob.get("setup_id"),
            "entry_event_id": blob.get("entry_event_id"),
            "entry_low": entry_low,
            "entry_high": entry_high,
            "entry_price": entry.get("midpoint") or zone.get("midpoint"),
            "stop": sl.get("price"),
            "target": tp1 or None,
            "entry_ready_time": blob.get("entry_ready_time"),
            "engine_source": blob.get("engine_source") or "PYTHON_CANONICAL",
            "causality_valid": blob.get("causality_valid", True),
            "desk_path": "/ict",
            "summary": f"ICT {side} — ENTRY_READY (Python causal, analysis only){conf_suffix}",
        }
    ]
