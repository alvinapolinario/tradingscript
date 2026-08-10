"""In-memory box strategy history (no DB required)."""
from __future__ import annotations

from collections import deque
from threading import Lock
from typing import Any

_lock = Lock()
_history: dict[str, deque[dict[str, Any]]] = {}
_MAX = 50


def record_box_result(symbol: str, result: dict[str, Any]) -> None:
    sym = (symbol or "XAUUSD").upper()
    snap = {
        "symbol": sym,
        "box_status": result.get("box_status"),
        "signal": result.get("signal"),
        "confidence": result.get("confidence_score") or result.get("confidence"),
        "box": result.get("box"),
        "eval_bar_time": result.get("eval_bar_time"),
        "signal_id": result.get("signal_id"),
        "recorded_at": result.get("eval_bar_time"),
    }
    with _lock:
        if sym not in _history:
            _history[sym] = deque(maxlen=_MAX)
        if _history[sym] and _history[sym][-1].get("signal_id") == snap.get("signal_id"):
            _history[sym][-1] = snap
        else:
            _history[sym].append(snap)


def list_box_history(symbol: str, limit: int = 20) -> list[dict[str, Any]]:
    sym = (symbol or "XAUUSD").upper()
    with _lock:
        items = list(_history.get(sym, deque()))
    return items[-limit:][::-1]
