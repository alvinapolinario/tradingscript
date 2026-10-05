"""M5 history loading + closed-bar higher-timeframe views (no look-ahead)."""
from __future__ import annotations

import bisect
import csv
from dataclasses import dataclass, field
from pathlib import Path

from app.analysis.h4_m15_fvg.replay import _norm_col, _parse_time
from app.market_structure.types import Candle

TF_SECONDS: dict[str, int] = {
    "M5": 300,
    "M15": 900,
    "M30": 1800,
    "H1": 3600,
    "H4": 14400,
    "D1": 86400,
}


@dataclass
class History:
    """M5 bars (oldest first) with per-bar spread in price units."""

    symbol: str
    m5: list[Candle]
    spread: list[float]
    _tf: dict[str, list[Candle]] = field(default_factory=dict, repr=False)
    _tf_close: dict[str, list[int]] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self._m5_open = [c.time for c in self.m5]
        self._m5_close = [t + TF_SECONDS["M5"] for t in self._m5_open]

    def timeframe(self, tf: str) -> list[Candle]:
        if tf == "M5":
            return self.m5
        if tf not in self._tf:
            self._tf[tf] = resample(self.m5, TF_SECONDS[tf])
            self._tf_close[tf] = [c.time + TF_SECONDS[tf] for c in self._tf[tf]]
        return self._tf[tf]

    def closed(self, tf: str, at: int, count: int) -> list[Candle]:
        """Last ``count`` bars of ``tf`` that had fully closed by time ``at``."""
        bars = self.timeframe(tf)
        closes = self._m5_close if tf == "M5" else self._tf_close[tf]
        end = bisect.bisect_right(closes, at)
        return bars[max(0, end - count):end]

    def index_after(self, at: int) -> int:
        """Index of the first M5 bar that opens at or after ``at``."""
        return bisect.bisect_left(self._m5_open, at)


def resample(m5: list[Candle], tf_seconds: int) -> list[Candle]:
    """Aggregate M5 bars into ``tf_seconds`` buckets aligned to epoch multiples."""
    out: list[Candle] = []
    cur: Candle | None = None
    for c in m5:
        bucket = c.time - (c.time % tf_seconds)
        if cur is None or cur.time != bucket:
            if cur is not None:
                out.append(cur)
            cur = Candle(time=bucket, open=c.open, high=c.high, low=c.low, close=c.close, volume=c.volume)
        else:
            cur.high = max(cur.high, c.high)
            cur.low = min(cur.low, c.low)
            cur.close = c.close
            cur.volume += c.volume
    if cur is not None:
        out.append(cur)
    return out


def load_m5_csv(
    path: str | Path,
    *,
    symbol: str = "XAUUSD",
    point: float = 0.01,
    default_spread: float = 0.30,
) -> History:
    """
    Load an M5 export (oldest or newest first).

    Spread columns, first match wins:
      ``spread_price`` — already in price units (VantageExportHistory.mq5 writes this)
      ``spread``       — MT5 points, converted with ``point``
    Missing / zero spread falls back to ``default_spread``.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(p))
    rows: list[tuple[Candle, float]] = []
    with p.open(newline="", encoding="utf-8-sig") as fh:
        for raw in csv.DictReader(fh):
            row = {_norm_col(k): (v or "").strip() for k, v in raw.items() if k}
            t = _parse_time(row.get("time") or row.get("timestamp") or row.get("datetime") or "")
            try:
                o, h, l, c = (float(row[k]) for k in ("open", "high", "low", "close"))
            except (KeyError, ValueError):
                continue
            if t <= 0 or min(o, h, l, c) <= 0:
                continue
            vol = float(row.get("tick_volume") or row.get("volume") or 0)
            if row.get("spread_price"):
                spr = float(row["spread_price"])
            elif row.get("spread"):
                spr = float(row["spread"]) * point
            else:
                spr = 0.0
            rows.append((Candle(time=t, open=o, high=h, low=l, close=c, volume=vol), spr if spr > 0 else default_spread))
    if not rows:
        raise ValueError(f"{p.name}: no usable OHLC rows")
    rows.sort(key=lambda r: r[0].time)
    dedup: dict[int, tuple[Candle, float]] = {r[0].time: r for r in rows}
    ordered = [dedup[t] for t in sorted(dedup)]
    return History(symbol=symbol.upper(), m5=[r[0] for r in ordered], spread=[r[1] for r in ordered])
