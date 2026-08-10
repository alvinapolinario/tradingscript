"""Trading session context — timezone-aware (UTC default)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.analysis.ict.types import IctConfig
from app.market_structure.types import Candle

# Hour ranges in UTC (configurable later via cfg)
_SESSIONS_UTC: list[tuple[str, int, int]] = [
    ("ASIA", 0, 8),
    ("LONDON", 7, 16),
    ("NEW_YORK", 12, 21),
]


def _local_hour(broker_time_unix: int, tz_name: str) -> int:
    if tz_name.upper() in ("UTC", "GMT", "ETC/UTC"):
        return datetime.fromtimestamp(broker_time_unix, tz=timezone.utc).hour
    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(tz_name)
        return datetime.fromtimestamp(broker_time_unix, tz=timezone.utc).astimezone(tz).hour
    except Exception:
        return datetime.fromtimestamp(broker_time_unix, tz=timezone.utc).hour


def get_session_context(
    broker_time_unix: int,
    candles: list[Candle],
    cfg: IctConfig,
) -> dict[str, Any]:
    hour = _local_hour(broker_time_unix, cfg.session_timezone)
    session = "OFF_HOURS"
    for name, start, end in _SESSIONS_UTC:
        if start <= hour < end:
            session = name
            break

    session_candles = candles[-32:] if len(candles) >= 8 else candles
    sh = max(c.high for c in session_candles) if session_candles else 0.0
    sl = min(c.low for c in session_candles) if session_candles else 0.0
    return {
        "session": session,
        "session_high": sh,
        "session_low": sl,
        "session_range": sh - sl if sh > sl else 0.0,
        "local_hour": hour,
        "timezone": cfg.session_timezone,
    }
