"""Edge statistics, confidence calibration and the per-strategy verdict."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from statistics import median, pstdev
from typing import Any, Iterable

from app.research.simulate import Trade

MIN_TRADES = 30
BUCKET_WIDTH = 10
TRAIN_FRACTION = 0.7
MIN_THRESHOLD_TRADES = 20

# UTC session windows (start hour inclusive, end hour exclusive)
SESSIONS = (("ASIA", 0, 7), ("LONDON", 7, 12), ("NY_OVERLAP", 12, 16), ("NEW_YORK", 16, 21), ("LATE", 21, 24))


def basic_stats(trades: Iterable[Trade]) -> dict[str, Any]:
    rs = [t.r for t in trades if t.status == "CLOSED"]
    n = len(rs)
    if n == 0:
        return {"n": 0}
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r <= 0]
    gross_loss = -sum(losses)
    sd = pstdev(rs) if n > 1 else 0.0
    equity = peak = dd = 0.0
    for r in rs:
        equity += r
        peak = max(peak, equity)
        dd = max(dd, peak - equity)
    avg = sum(rs) / n
    return {
        "n": n,
        "win_rate": round(len(wins) / n, 4),
        "avg_r": round(avg, 4),
        "median_r": round(median(rs), 4),
        "total_r": round(sum(rs), 2),
        "profit_factor": round(sum(wins) / gross_loss, 3) if gross_loss > 0 else None,
        "max_drawdown_r": round(dd, 2),
        "t_stat": _t_stat(avg, sd, n),
    }


def _t_stat(avg: float, sd: float, n: int, cap: float = 99.0) -> float:
    """t of the mean R; capped (JSON has no infinity) when every trade has the same R."""
    if sd > 0:
        return round(max(-cap, min(cap, avg / (sd / math.sqrt(n)))), 2)
    return cap if avg > 0 else -cap if avg < 0 else 0.0


def session_of(ts: int, utc_offset_hours: float = 0.0) -> str:
    hour = datetime.fromtimestamp(ts - utc_offset_hours * 3600, tz=timezone.utc).hour
    for name, lo, hi in SESSIONS:
        if lo <= hour < hi:
            return name
    return "LATE"


def _group(trades: list[Trade], key) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[Trade]] = {}
    for t in trades:
        groups.setdefault(str(key(t)), []).append(t)
    return {k: basic_stats(v) for k, v in sorted(groups.items())}


def confidence_buckets(trades: list[Trade], width: int = BUCKET_WIDTH) -> list[dict[str, Any]]:
    out = []
    for lo in range(0, 100, width):
        hi = lo + width
        sel = [t for t in trades if lo <= t.confidence < hi or (hi == 100 and t.confidence >= 100)]
        if sel:
            out.append({"lo": lo, "hi": hi, **basic_stats(sel)})
    return out


def fit_threshold(train: list[Trade]) -> float | None:
    """Lowest-risk confidence floor: best t-stat on the training slice with enough trades."""
    best: tuple[float, float] | None = None
    for floor in range(0, 100, 5):
        st = basic_stats([t for t in train if t.confidence >= floor])
        if st.get("n", 0) < MIN_THRESHOLD_TRADES or st["avg_r"] <= 0:
            continue
        if best is None or st["t_stat"] > best[1]:
            best = (float(floor), st["t_stat"])
    return best[0] if best else None


def verdict(stats: dict[str, Any], folds: list[dict[str, Any]]) -> str:
    n = stats.get("n", 0)
    if n < MIN_TRADES:
        return "INSUFFICIENT_DATA"
    if stats["avg_r"] <= 0 or stats["t_stat"] < 1.0:
        return "NO_EDGE"
    positive = sum(1 for f in folds if f.get("n", 0) and f["avg_r"] > 0)
    if stats["t_stat"] >= 2.0 and positive >= math.ceil(0.75 * len(folds)):
        return "EDGE"
    return "INCONCLUSIVE"


def evaluate_strategy(trades: list[Trade], *, utc_offset_hours: float = 0.0, folds: int = 4) -> dict[str, Any]:
    closed = sorted((t for t in trades if t.status == "CLOSED"), key=lambda t: t.signal_time)
    status_counts: dict[str, int] = {}
    for t in trades:
        status_counts[t.status] = status_counts.get(t.status, 0) + 1

    overall = basic_stats(closed)
    fold_stats = []
    if closed:
        size = math.ceil(len(closed) / folds)
        for k in range(folds):
            part = closed[k * size:(k + 1) * size]
            if part:
                fold_stats.append(
                    {"fold": k + 1, "from": part[0].signal_time, "to": part[-1].signal_time, **basic_stats(part)}
                )

    cut = int(len(closed) * TRAIN_FRACTION)
    train, test = closed[:cut], closed[cut:]
    floor = fit_threshold(train)
    oos = basic_stats([t for t in test if floor is None or t.confidence >= floor])
    oos_unfiltered = basic_stats(test)

    return {
        "verdict": verdict(overall, fold_stats),
        "overall": overall,
        "signals": status_counts,
        "exit_reasons": _count(t.exit_reason for t in closed),
        "by_side": _group(closed, lambda t: t.side),
        "by_session": _group(closed, lambda t: session_of(t.signal_time, utc_offset_hours)),
        "by_year": _group(closed, lambda t: datetime.fromtimestamp(t.signal_time, tz=timezone.utc).year),
        "folds": fold_stats,
        "confidence_buckets": confidence_buckets(closed),
        "threshold": {
            "fitted_on": "first 70% of trades (time-ordered)",
            "min_confidence": floor,
            "out_of_sample_filtered": oos,
            "out_of_sample_unfiltered": oos_unfiltered,
            "confirmed": bool(floor is not None and oos.get("n", 0) >= 10 and oos.get("avg_r", 0) > 0),
        },
    }


def _count(values: Iterable[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return out
