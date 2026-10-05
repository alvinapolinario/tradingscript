"""
Bar-by-bar trade simulation on M5 bid bars with real spread.

Conventions (conservative on purpose):
  * MARKET entries fill at the open of the first M5 bar after the decision —
    BUY at ask (open + spread), SELL at bid.
  * LIMIT entries fill when the touching side reaches the price before
    ``limit_expiry_bars``; unfilled limits are recorded as NOT_FILLED.
  * Bars are bid prices, so a SELL's stop/target trigger on ask = bid + spread.
  * If stop and target are both inside one bar, the stop wins.
  * Open trades are closed at the bar close after ``max_hold_bars``.
  * One open trade per strategy — signals arriving while in a trade are SKIPPED_BUSY
    (same rule as the executor's InpMaxOpenPositions = 1).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from app.research.data import History
from app.research.signals import Signal


@dataclass
class SimConfig:
    max_hold_bars: int = 48  # 4 hours of M5
    limit_expiry_bars: int = 12
    default_rr: float = 2.0  # target when an engine publishes none
    commission: float = 0.0  # round-trip cost in price units per unit volume
    one_position_per_strategy: bool = True


@dataclass
class Trade:
    strategy: str
    signal_time: int
    side: str
    confidence: float
    setup_id: str
    status: str  # CLOSED | NOT_FILLED | INVALID_LEVELS | SKIPPED_BUSY | NO_DATA
    entry_time: int = 0
    entry: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    exit_time: int = 0
    exit: float = 0.0
    exit_reason: str = ""  # TP | SL | TIME
    r: float = 0.0
    bars_held: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def _levels_ok(side: str, entry: float, sl: float, tp: float) -> bool:
    if side == "BUY":
        return sl < entry < tp
    return tp < entry < sl


def simulate_signal(hist: History, sig: Signal, cfg: SimConfig) -> Trade:
    base = dict(
        strategy=sig.strategy,
        signal_time=sig.time,
        side=sig.side,
        confidence=sig.confidence,
        setup_id=sig.setup_id,
    )
    bars, spreads = hist.m5, hist.spread
    i = hist.index_after(sig.time)
    if i >= len(bars):
        return Trade(**base, status="NO_DATA")

    is_buy = sig.side == "BUY"
    # --- entry ---------------------------------------------------------
    if sig.entry_type == "LIMIT" and sig.entry_price > 0:
        fill_i = -1
        for k in range(i, min(i + cfg.limit_expiry_bars, len(bars))):
            b, s = bars[k], spreads[k]
            if (is_buy and b.low + s <= sig.entry_price) or (not is_buy and b.high >= sig.entry_price):
                fill_i = k
                break
        if fill_i < 0:
            return Trade(**base, status="NOT_FILLED")
        entry = sig.entry_price
        entry_i = fill_i
    else:
        entry_i = i
        entry = bars[i].open + (spreads[i] if is_buy else 0.0)

    sl = sig.stop_loss
    risk = abs(entry - sl)
    tp = sig.take_profit
    if tp <= 0 and risk > 0:
        tp = entry + cfg.default_rr * risk if is_buy else entry - cfg.default_rr * risk
    if sl <= 0 or risk <= 0 or not _levels_ok(sig.side, entry, sl, tp):
        return Trade(**base, status="INVALID_LEVELS", entry=entry, stop_loss=sl, take_profit=tp)

    # --- exit ----------------------------------------------------------
    last_i = min(entry_i + cfg.max_hold_bars, len(bars) - 1)
    exit_px, reason, exit_i = 0.0, "", last_i
    for k in range(entry_i, last_i + 1):
        b, s = bars[k], spreads[k]
        # A limit fill bar only counts the part of the bar after the fill: skip TP on that bar.
        same_bar_limit = sig.entry_type == "LIMIT" and k == entry_i
        if is_buy:
            hit_sl, hit_tp = b.low <= sl, b.high >= tp and not same_bar_limit
        else:
            hit_sl, hit_tp = b.high + s >= sl, b.low + s <= tp and not same_bar_limit
        if hit_sl:
            exit_px, reason, exit_i = sl, "SL", k
            break
        if hit_tp:
            exit_px, reason, exit_i = tp, "TP", k
            break
    if not reason:
        b, s = bars[last_i], spreads[last_i]
        exit_px, reason = (b.close if is_buy else b.close + s), "TIME"

    pnl = (exit_px - entry) if is_buy else (entry - exit_px)
    pnl -= cfg.commission
    return Trade(
        **base,
        status="CLOSED",
        entry_time=bars[entry_i].time,
        entry=round(entry, 5),
        stop_loss=sl,
        take_profit=round(tp, 5),
        exit_time=bars[exit_i].time + 300,
        exit=round(exit_px, 5),
        exit_reason=reason,
        r=round(pnl / risk, 4),
        bars_held=exit_i - entry_i + 1,
    )


def simulate(hist: History, signals: list[Signal], cfg: SimConfig | None = None) -> list[Trade]:
    cfg = cfg or SimConfig()
    busy_until: dict[str, int] = {}
    trades: list[Trade] = []
    for sig in sorted(signals, key=lambda s: s.time):
        if cfg.one_position_per_strategy and sig.time < busy_until.get(sig.strategy, 0):
            trades.append(
                Trade(sig.strategy, sig.time, sig.side, sig.confidence, sig.setup_id, status="SKIPPED_BUSY")
            )
            continue
        t = simulate_signal(hist, sig, cfg)
        if t.status == "CLOSED":
            busy_until[sig.strategy] = t.exit_time
        trades.append(t)
    return trades
