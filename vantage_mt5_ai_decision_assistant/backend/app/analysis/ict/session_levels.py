"""Previous-day high/low (PDH/PDL) from D1 or session-partitioned intraday bars."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.analysis.ict.types import IctConfig
from app.market_structure.types import Candle


def _trading_session_date(unix_ts: int, tz_name: str, reset_hour: int) -> str:
    """Map bar time to ICT-style trading session date (rolls at reset_hour local)."""
    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(tz_name)
    except Exception:
        tz = timezone.utc
    dt = datetime.fromtimestamp(unix_ts, tz=timezone.utc).astimezone(tz)
    if dt.hour < reset_hour:
        dt = dt - timedelta(days=1)
    return dt.strftime("%Y-%m-%d")


def previous_day_hl_from_d1(d1_candles: list[Candle]) -> tuple[float, float, int, str] | None:
    """Most recent closed D1 bar = previous completed trading day."""
    if not d1_candles:
        return None
    bar = d1_candles[-1]
    return float(bar.high), float(bar.low), int(bar.time), "D1_PREVIOUS_BAR"


def previous_day_hl_from_intraday(
    candles: list[Candle],
    eval_time: int,
    cfg: IctConfig,
) -> tuple[float, float, int, str] | None:
    """Partition intraday bars by session date; return prior session H/L."""
    if len(candles) < 8:
        return None
    tz = cfg.trading_day_timezone
    reset = cfg.trading_day_reset_hour
    current_day = _trading_session_date(eval_time, tz, reset)

    by_day: dict[str, list[Candle]] = {}
    for c in candles:
        if c.time > eval_time:
            continue
        day = _trading_session_date(c.time, tz, reset)
        by_day.setdefault(day, []).append(c)

    days = sorted(by_day.keys())
    prior_days = [d for d in days if d < current_day]
    if not prior_days:
        return None
    prev = prior_days[-1]
    group = by_day[prev]
    if not group:
        return None
    return (
        max(c.high for c in group),
        min(c.low for c in group),
        group[-1].time,
        f"SESSION_PARTITION_{tz}",
    )


def compute_previous_day_levels(
    setup_candles: list[Candle],
    d1_candles: list[Candle] | None,
    eval_time: int,
    cfg: IctConfig,
) -> tuple[float | None, float | None, int, str]:
    """
    Return (pdh, pdl, reference_time, source_label).
    Prefer closed D1; fall back to session-partitioned setup TF bars.
    """
    if d1_candles:
        d1 = previous_day_hl_from_d1(d1_candles)
        if d1:
            return d1[0], d1[1], d1[2], d1[3]

    intra = previous_day_hl_from_intraday(setup_candles, eval_time, cfg)
    if intra:
        return intra[0], intra[1], intra[2], intra[3]
    return None, None, 0, ""
