"""ICT strategy — in-memory setup history."""
from __future__ import annotations

from collections import deque
from typing import Any

_HISTORY: dict[str, deque] = {}
_MAX = 50


def record_ict_result(symbol: str, payload: dict[str, Any]) -> None:
    sym = (symbol or "XAUUSD").upper()
    if sym not in _HISTORY:
        _HISTORY[sym] = deque(maxlen=_MAX)
    sid = payload.get("setup_id") or ""
    for i, item in enumerate(_HISTORY[sym]):
        if item.get("setup_id") == sid and sid:
            _HISTORY[sym][i] = payload
            return
    _HISTORY[sym].appendleft(payload)


def list_ict_history(symbol: str, limit: int = 20) -> list[dict[str, Any]]:
    sym = (symbol or "XAUUSD").upper()
    items = list(_HISTORY.get(sym, []))
    return items[:limit]
