"""Candle utilities — ATR, validation, payload parsing, body metrics."""
from __future__ import annotations

from typing import Any

from app.market_structure.types import Candle


def atr(candles: list[Candle], period: int = 14) -> float:
    if len(candles) < period + 1:
        return max((candles[-1].high - candles[-1].low), 1e-9) if candles else 1e-9
    trs: list[float] = []
    for i in range(-period, 0):
        c = candles[i]
        p = candles[i - 1]
        tr = max(c.high - c.low, abs(c.high - p.close), abs(c.low - p.close))
        trs.append(tr)
    return sum(trs) / len(trs) if trs else 1e-9


def validate_candles(candles: list[Candle]) -> str | None:
    if len(candles) < 3:
        return "Insufficient candles"
    seen: set[int] = set()
    prev_t = -1
    for c in candles:
        if c.high < c.low or c.open <= 0 or c.close <= 0:
            return "Invalid OHLC"
        if c.time in seen:
            return "Duplicate timestamps"
        seen.add(c.time)
        if prev_t >= 0 and c.time <= prev_t:
            return "Unsorted candles"
        prev_t = c.time
    return None


def candles_from_payload(rows: list[dict[str, Any]] | None) -> list[Candle]:
    out: list[Candle] = []
    for row in rows or []:
        out.append(
            Candle(
                time=int(row.get("time") or row.get("t") or 0),
                open=float(row.get("open") or row.get("o") or 0),
                high=float(row.get("high") or row.get("h") or 0),
                low=float(row.get("low") or row.get("l") or 0),
                close=float(row.get("close") or row.get("c") or 0),
                volume=float(row.get("volume") or row.get("tick_volume") or row.get("v") or 0),
            )
        )
    return out


def body_ratio(c: Candle) -> float:
    rng = max(c.high - c.low, 1e-9)
    return abs(c.close - c.open) / rng


def is_bullish(c: Candle) -> bool:
    return c.close > c.open


def is_bearish(c: Candle) -> bool:
    return c.close < c.open
