"""ICT setup state store — in-memory persistence per symbol/timeframe."""
from __future__ import annotations

import threading
from typing import Any

from app.analysis.ict.types import IctSetupRecord, IctSetupState

_lock = threading.Lock()
# symbol -> setup_id -> record
_STORE: dict[str, dict[str, IctSetupRecord]] = {}
# Track last notified state for dedupe (Discord later)
_LAST_STATE: dict[str, str] = {}
_MAX_PER_SYMBOL = 5


def get_active_setup(symbol: str, timeframe: str) -> IctSetupRecord | None:
    sym = (symbol or "").upper()
    with _lock:
        records = _STORE.get(sym, {})
        active = [
            r
            for r in records.values()
            if r.timeframe == timeframe
            and r.state
            not in (
                IctSetupState.INVALIDATED,
                IctSetupState.EXPIRED,
                IctSetupState.TARGET_REACHED,
                IctSetupState.NO_SETUP,
            )
        ]
        if not active:
            return None
        return max(active, key=lambda r: r.updated_time)


def save_setup(record: IctSetupRecord) -> None:
    sym = record.symbol.upper()
    with _lock:
        if sym not in _STORE:
            _STORE[sym] = {}
        _STORE[sym][record.setup_id] = record
        # Trim old terminal setups
        if len(_STORE[sym]) > _MAX_PER_SYMBOL * 3:
            terminal = [
                k
                for k, v in _STORE[sym].items()
                if v.state
                in (
                    IctSetupState.INVALIDATED,
                    IctSetupState.EXPIRED,
                    IctSetupState.TARGET_REACHED,
                )
            ]
            for k in terminal[: len(terminal) - _MAX_PER_SYMBOL]:
                del _STORE[sym][k]


def list_setups(symbol: str, limit: int = 20) -> list[IctSetupRecord]:
    sym = (symbol or "").upper()
    with _lock:
        records = list(_STORE.get(sym, {}).values())
    records.sort(key=lambda r: r.updated_time, reverse=True)
    return records[:limit]


def state_changed(setup_id: str, new_state: str) -> bool:
    prev = _LAST_STATE.get(setup_id)
    if prev == new_state:
        return False
    _LAST_STATE[setup_id] = new_state
    return True


def clear_store(symbol: str | None = None) -> None:
    """Test helper — clear in-memory store."""
    with _lock:
        if symbol:
            _STORE.pop(symbol.upper(), None)
        else:
            _STORE.clear()
            _LAST_STATE.clear()


def record_to_dict(record: IctSetupRecord) -> dict[str, Any]:
    return {
        "setup_id": record.setup_id,
        "symbol": record.symbol,
        "timeframe": record.timeframe,
        "trade_bias": record.trade_bias,
        "state": record.state.value,
        "sweep_time": record.sweep_time,
        "confidence": record.confidence,
        "created_time": record.created_time,
        "updated_time": record.updated_time,
        "age_candles": record.age_candles,
        "last_event": record.last_event,
    }
