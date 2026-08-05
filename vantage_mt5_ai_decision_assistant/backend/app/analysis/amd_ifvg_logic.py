"""AMD + iFVG strategy — Python detection engine (Gold / XAUUSD).

Advisory-only. Used for offline analyze/backtest mirrors and deterministic tests.
Live path: EA computes on MT5 closed bars → heartbeat passthrough.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.analysis.gold_symbol_validator import is_approved_gold_symbol


class AmdPhase(str, Enum):
    SEARCHING = "SEARCHING"
    ACCUMULATION = "ACCUMULATION"
    MANIPULATION = "MANIPULATION"
    DISTRIBUTION = "DISTRIBUTION"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"


class SetupState(str, Enum):
    SEARCHING_FOR_ACCUMULATION = "SEARCHING_FOR_ACCUMULATION"
    ACCUMULATION_DETECTED = "ACCUMULATION_DETECTED"
    WAITING_FOR_LIQUIDITY_SWEEP = "WAITING_FOR_LIQUIDITY_SWEEP"
    MANIPULATION_DETECTED = "MANIPULATION_DETECTED"
    WAITING_FOR_DISPLACEMENT = "WAITING_FOR_DISPLACEMENT"
    WAITING_FOR_MSS = "WAITING_FOR_MSS"
    WAITING_FOR_IFVG_INVERSION = "WAITING_FOR_IFVG_INVERSION"
    WAITING_FOR_RETRACE = "WAITING_FOR_RETRACE"
    ENTRY_ZONE_ACTIVE = "ENTRY_ZONE_ACTIVE"
    ENTRY_TRIGGERED = "ENTRY_TRIGGERED"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"
    NO_TRADE = "NO_TRADE"


class Decision(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"
    NO_TRADE = "NO_TRADE"


class FvgStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PARTIALLY_MITIGATED = "PARTIALLY_MITIGATED"
    FULLY_MITIGATED = "FULLY_MITIGATED"
    INVALIDATED = "INVALIDATED"
    INVERTED = "INVERTED"
    EXPIRED = "EXPIRED"


@dataclass
class Candle:
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class AmdIfvgConfig:
    enabled: bool = True
    allowed_symbols: tuple[str, ...] = ("XAUUSD", "GOLD")
    min_candles: int = 80
    pivot_left: int = 2
    pivot_right: int = 2
    accumulation_min_candles: int = 8
    accumulation_max_candles: int = 40
    accumulation_max_width_atr: float = 1.5
    accumulation_min_touches: int = 2
    sweep_min_penetration_atr: float = 0.05
    sweep_max_penetration_atr: float = 0.75
    sweep_require_reentry: bool = True
    displacement_min_body_atr: float = 0.8
    displacement_min_body_range: float = 0.65
    fvg_min_gap_atr: float = 0.05
    fvg_max_age_candles: int = 100
    ifvg_min_break_atr: float = 0.1
    ifvg_require_body_close: bool = True
    ifvg_max_retests: int = 2
    ifvg_use_midpoint_entry: bool = True
    minimum_rr: float = 2.0
    minimum_trade_score: float = 75.0
    high_quality_score: float = 85.0
    risk_percent: float = 0.5
    max_spread_points: float = 80.0
    entry_mode: str = "CONSERVATIVE"
    chase_max_atr: float = 0.35


DEFAULT_AMD_IFVG_CONFIG = AmdIfvgConfig()


@dataclass
class FvgZone:
    fvg_id: str
    direction: str  # BULLISH | BEARISH
    timeframe: str
    created_time: int
    lower: float
    upper: float
    gap_size: float
    gap_atr: float
    displacement_score: float
    mitigation_pct: float = 0.0
    status: FvgStatus = FvgStatus.ACTIVE
    inverted: bool = False
    inversion_time: int = 0
    retest_count: int = 0
    original_direction: str = ""

    @property
    def midpoint(self) -> float:
        return (self.lower + self.upper) / 2.0


@dataclass
class AccumulationRange:
    start_time: int
    end_time: int
    range_high: float
    range_low: float
    candle_count: int
    touches_high: int
    touches_low: int
    quality_score: float

    @property
    def midpoint(self) -> float:
        return (self.range_high + self.range_low) / 2.0

    @property
    def width(self) -> float:
        return self.range_high - self.range_low


@dataclass
class NewsRiskService:
    """Placeholder — integrate calendar API later. Never hardcode events."""

    enabled: bool = False

    def is_blocked(self, broker_time_unix: int) -> tuple[bool, str]:
        if not self.enabled:
            return False, ""
        return False, ""


def _atr(candles: list[Candle], period: int = 14) -> float:
    if len(candles) < period + 1:
        return max(candles[-1].high - candles[-1].low, 1e-9) if candles else 1e-9
    trs: list[float] = []
    for i in range(-period, 0):
        c = candles[i]
        p = candles[i - 1]
        tr = max(c.high - c.low, abs(c.high - p.close), abs(c.low - p.close))
        trs.append(tr)
    return sum(trs) / len(trs) if trs else 1e-9


def _validate_candles(candles: list[Candle]) -> str | None:
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


def detect_fvgs(
    candles: list[Candle],
    *,
    timeframe: str,
    atr: float,
    cfg: AmdIfvgConfig,
    start_idx: int = 2,
) -> list[FvgZone]:
    """Three-candle FVG model on closed bars (indices 0=oldest)."""
    out: list[FvgZone] = []
    min_gap = cfg.fvg_min_gap_atr * atr
    for i in range(max(start_idx, 2), len(candles)):
        c1, c2, c3 = candles[i - 2], candles[i - 1], candles[i]
        body = abs(c2.close - c2.open)
        body_atr = body / atr if atr else 0.0
        disp = min(100.0, body_atr * 50.0)
        if c3.low > c1.high:
            gap = c3.low - c1.high
            if gap >= min_gap:
                out.append(
                    FvgZone(
                        fvg_id=f"FVG-B-{timeframe}-{c3.time}",
                        direction="BULLISH",
                        timeframe=timeframe,
                        created_time=c3.time,
                        lower=c1.high,
                        upper=c3.low,
                        gap_size=gap,
                        gap_atr=gap / atr if atr else 0.0,
                        displacement_score=disp,
                    )
                )
        if c3.high < c1.low:
            gap = c1.low - c3.high
            if gap >= min_gap:
                out.append(
                    FvgZone(
                        fvg_id=f"FVG-S-{timeframe}-{c3.time}",
                        direction="BEARISH",
                        timeframe=timeframe,
                        created_time=c3.time,
                        lower=c3.high,
                        upper=c1.low,
                        gap_size=gap,
                        gap_atr=gap / atr if atr else 0.0,
                        displacement_score=disp,
                    )
                )
    return out


def update_fvg_mitigation(fvg: FvgZone, price: float) -> None:
    if fvg.status in (FvgStatus.INVERTED, FvgStatus.INVALIDATED, FvgStatus.EXPIRED):
        return
    width = fvg.upper - fvg.lower
    if width <= 0:
        return
    if fvg.direction == "BULLISH":
        if price <= fvg.lower:
            fvg.mitigation_pct = 100.0
            fvg.status = FvgStatus.FULLY_MITIGATED
        elif price < fvg.upper:
            fvg.mitigation_pct = max(fvg.mitigation_pct, (fvg.upper - price) / width * 100.0)
            if fvg.mitigation_pct >= 50:
                fvg.status = FvgStatus.PARTIALLY_MITIGATED
    else:
        if price >= fvg.upper:
            fvg.mitigation_pct = 100.0
            fvg.status = FvgStatus.FULLY_MITIGATED
        elif price > fvg.lower:
            fvg.mitigation_pct = max(fvg.mitigation_pct, (price - fvg.lower) / width * 100.0)
            if fvg.mitigation_pct >= 50:
                fvg.status = FvgStatus.PARTIALLY_MITIGATED


def try_invert_fvg(
    fvg: FvgZone,
    candle: Candle,
    atr: float,
    cfg: AmdIfvgConfig,
) -> bool:
    """Decisive body close beyond FVG → iFVG."""
    if fvg.inverted or fvg.status == FvgStatus.EXPIRED:
        return False
    min_break = cfg.ifvg_min_break_atr * atr
    if fvg.direction == "BULLISH":
        if cfg.ifvg_require_body_close and candle.close >= fvg.lower:
            return False
        if candle.close < fvg.lower - min_break:
            fvg.original_direction = fvg.direction
            fvg.direction = "BEARISH"
            fvg.inverted = True
            fvg.inversion_time = candle.time
            fvg.status = FvgStatus.INVERTED
            return True
    elif fvg.direction == "BEARISH":
        if cfg.ifvg_require_body_close and candle.close <= fvg.upper:
            return False
        if candle.close > fvg.upper + min_break:
            fvg.original_direction = fvg.direction
            fvg.direction = "BULLISH"
            fvg.inverted = True
            fvg.inversion_time = candle.time
            fvg.status = FvgStatus.INVERTED
            return True
    return False


def detect_accumulation(
    candles: list[Candle],
    atr: float,
    cfg: AmdIfvgConfig,
) -> AccumulationRange | None:
    """Detect narrow range with liquidity touches — not every consolidation."""
    if len(candles) < cfg.accumulation_min_candles + 2:
        return None
    window = candles[-cfg.accumulation_max_candles :]
    if len(window) < cfg.accumulation_min_candles:
        return None
    rh = max(c.high for c in window)
    rl = min(c.low for c in window)
    width = rh - rl
    if width <= 0 or width > cfg.accumulation_max_width_atr * atr:
        return None
    touch_tol = width * 0.15
    touches_h = sum(1 for c in window if c.high >= rh - touch_tol)
    touches_l = sum(1 for c in window if c.low <= rl + touch_tol)
    if touches_h < cfg.accumulation_min_touches or touches_l < cfg.accumulation_min_touches:
        return None
    inside = sum(1 for c in window if rl <= c.close <= rh)
    if inside / len(window) < 0.65:
        return None
    quality = min(
        100.0,
        40.0
        + min(30.0, (cfg.accumulation_max_width_atr * atr - width) / atr * 20.0)
        + min(20.0, (touches_h + touches_l) * 3.0)
        + min(10.0, inside / len(window) * 10.0),
    )
    return AccumulationRange(
        start_time=window[0].time,
        end_time=window[-1].time,
        range_high=rh,
        range_low=rl,
        candle_count=len(window),
        touches_high=touches_h,
        touches_low=touches_l,
        quality_score=round(quality, 1),
    )


def detect_manipulation(
    acc: AccumulationRange,
    candles: list[Candle],
    atr: float,
    cfg: AmdIfvgConfig,
) -> dict[str, Any] | None:
    """Liquidity sweep outside accumulation with rejection."""
    if len(candles) < 3:
        return None
    recent = candles[-5:]
    min_pen = cfg.sweep_min_penetration_atr * atr
    max_pen = cfg.sweep_max_penetration_atr * atr
    for c in recent:
        sweep_up = c.high - acc.range_high
        if min_pen <= sweep_up <= max_pen and c.close < acc.range_high:
            reentry = cfg.sweep_require_reentry is False or c.close <= acc.range_high
            if reentry:
                wick = c.high - max(c.open, c.close)
                body = abs(c.close - c.open) or 1e-9
                return {
                    "detected": True,
                    "direction": "BUY_SIDE_SWEEP",
                    "trade_bias": "BEARISH",
                    "sweep_price": c.high,
                    "sweep_time": c.time,
                    "reentered_range": c.close <= acc.range_high,
                    "quality_score": min(100.0, 55.0 + (wick / body) * 15.0 + sweep_up / atr * 20.0),
                }
        sweep_dn = acc.range_low - c.low
        if min_pen <= sweep_dn <= max_pen and c.close > acc.range_low:
            reentry = cfg.sweep_require_reentry is False or c.close >= acc.range_low
            if reentry:
                wick = min(c.open, c.close) - c.low
                body = abs(c.close - c.open) or 1e-9
                return {
                    "detected": True,
                    "direction": "SELL_SIDE_SWEEP",
                    "trade_bias": "BULLISH",
                    "sweep_price": c.low,
                    "sweep_time": c.time,
                    "reentered_range": c.close >= acc.range_low,
                    "quality_score": min(100.0, 55.0 + (wick / body) * 15.0 + sweep_dn / atr * 20.0),
                }
    return None


def find_swings(candles: list[Candle], left: int, right: int, atr: float, min_atr: float = 0.3) -> list[dict[str, Any]]:
    swings: list[dict[str, Any]] = []
    for i in range(left, len(candles) - right):
        hi = candles[i].high
        lo = candles[i].low
        is_hi = all(hi >= candles[i - j].high for j in range(1, left + 1)) and all(
            hi >= candles[i + j].high for j in range(1, right + 1)
        )
        is_lo = all(lo <= candles[i - j].low for j in range(1, left + 1)) and all(
            lo <= candles[i + j].low for j in range(1, right + 1)
        )
        if is_hi and hi - lo >= min_atr * atr:
            swings.append({"type": "HIGH", "price": hi, "time": candles[i].time, "index": i})
        if is_lo and hi - lo >= min_atr * atr:
            swings.append({"type": "LOW", "price": lo, "time": candles[i].time, "index": i})
    return swings


def detect_mss(
    candles: list[Candle],
    swings: list[dict[str, Any]],
    bias: str,
    atr: float,
    cfg: AmdIfvgConfig,
) -> dict[str, Any] | None:
    if len(candles) < 3:
        return None
    last = candles[-1]
    body = abs(last.close - last.open)
    if body / atr < cfg.displacement_min_body_atr * 0.5:
        return None
    body_lo = min(last.open, last.close)
    body_hi = max(last.open, last.close)
    if bias == "BEARISH":
        lows = [s for s in swings if s["type"] == "LOW"]
        if not lows:
            return None
        level = lows[-1]["price"]
        if body_lo < level:
            return {
                "shift_detected": True,
                "direction": "BEARISH",
                "broken_level": level,
                "confirmation_type": "BODY_CLOSE",
                "quality_score": min(100.0, 60.0 + body / atr * 25.0),
            }
    if bias == "BULLISH":
        highs = [s for s in swings if s["type"] == "HIGH"]
        if not highs:
            return None
        level = highs[-1]["price"]
        if body_hi > level:
            return {
                "shift_detected": True,
                "direction": "BULLISH",
                "broken_level": level,
                "confirmation_type": "BODY_CLOSE",
                "quality_score": min(100.0, 60.0 + body / atr * 25.0),
            }
    return None


def premium_discount(dealing_high: float, dealing_low: float, price: float) -> str:
    if dealing_high <= dealing_low:
        return "NEUTRAL"
    eq = (dealing_high + dealing_low) / 2.0
    if price >= eq + (dealing_high - eq) * 0.5:
        return "DEEP_PREMIUM"
    if price >= eq:
        return "PREMIUM"
    if price <= eq - (eq - dealing_low) * 0.5:
        return "DEEP_DISCOUNT"
    if price <= eq:
        return "DISCOUNT"
    return "NEUTRAL"


def score_displacement(candle: Candle, atr: float, structure_break: bool, fvg_created: bool) -> float:
    body = abs(candle.close - candle.open)
    rng = candle.high - candle.low or 1e-9
    score = 0.0
    score += min(25.0, (body / atr) * 25.0) if atr else 0.0
    score += min(15.0, (body / rng) * 15.0)
    if structure_break:
        score += 25.0
    if fvg_created:
        score += 15.0
    if candle.close > candle.open and candle.close >= candle.high - rng * 0.25:
        score += 10.0
    if candle.close < candle.open and candle.close <= candle.low + rng * 0.25:
        score += 10.0
    return min(100.0, score)


def compute_confidence(
    *,
    htf_alignment: float,
    acc_quality: float,
    sweep_quality: float,
    disp_quality: float,
    mss_quality: float,
    ifvg_quality: float,
    pd_alignment: float,
    rr_quality: float,
    penalties: float,
) -> float:
    raw = (
        htf_alignment * 0.15
        + acc_quality * 0.10
        + sweep_quality * 0.15
        + disp_quality * 0.15
        + mss_quality * 0.15
        + ifvg_quality * 0.15
        + pd_alignment * 0.05
        + rr_quality * 0.05
        + 5.0  # session placeholder
    )
    return max(0.0, min(100.0, raw - penalties))


def _htf_bias(candles: list[Candle]) -> str:
    if len(candles) < 20:
        return "NEUTRAL"
    closes = [c.close for c in candles[-20:]]
    if closes[-1] > closes[0] * 1.002:
        return "BULLISH"
    if closes[-1] < closes[0] * 0.998:
        return "BEARISH"
    return "NEUTRAL"


def analyze_amd_ifvg(
    *,
    symbol: str,
    candles_setup: list[Candle],
    candles_entry: list[Candle] | None = None,
    candles_bias: list[Candle] | None = None,
    bid: float = 0.0,
    ask: float = 0.0,
    spread_points: float = 0.0,
    cfg: AmdIfvgConfig | None = None,
    news: NewsRiskService | None = None,
) -> dict[str, Any]:
    """Main analyzer — closed-bar only, no look-ahead."""
    st = cfg or DEFAULT_AMD_IFVG_CONFIG
    sym = (symbol or "").upper()
    base = sym.split(".")[0].split("+")[0]
    gold_ok, _ = is_approved_gold_symbol(sym)
    if not gold_ok and base not in st.allowed_symbols:
        return _disabled_blob(sym, "AMD + iFVG supports XAUUSD/Gold only.")

    err = _validate_candles(candles_setup)
    if err:
        return _empty_blob(sym, f"Rejected: {err}")

    if len(candles_setup) < st.min_candles:
        return _empty_blob(sym, f"Rejected: need at least {st.min_candles} setup candles.")

    entry = candles_entry or candles_setup
    bias_c = candles_bias or candles_setup
    atr_setup = _atr(candles_setup)
    atr_entry = _atr(entry)
    price = bid or candles_setup[-1].close
    reasoning: list[str] = []
    warnings: list[str] = []

    news_svc = news or NewsRiskService()
    blocked, news_reason = news_svc.is_blocked(candles_setup[-1].time)
    if blocked:
        warnings.append(news_reason or "News block active")

    if spread_points > st.max_spread_points:
        warnings.append(f"Spread {spread_points} exceeds max {st.max_spread_points}")

    htf = _htf_bias(bias_c)
    acc = detect_accumulation(candles_setup, atr_setup, st)
    setup_state = SetupState.SEARCHING_FOR_ACCUMULATION
    amd_phase = AmdPhase.SEARCHING
    manip: dict[str, Any] | None = None
    mss: dict[str, Any] | None = None
    active_ifvg: FvgZone | None = None
    trade_bias = "NEUTRAL"

    if acc:
        setup_state = SetupState.ACCUMULATION_DETECTED
        amd_phase = AmdPhase.ACCUMULATION
        reasoning.append(
            f"Accumulation range {acc.range_low:.2f}–{acc.range_high:.2f} "
            f"({acc.candle_count} bars, quality {acc.quality_score:.0f})."
        )
        setup_state = SetupState.WAITING_FOR_LIQUIDITY_SWEEP
        manip = detect_manipulation(acc, candles_setup, atr_setup, st)
        if manip and manip.get("detected"):
            setup_state = SetupState.MANIPULATION_DETECTED
            amd_phase = AmdPhase.MANIPULATION
            trade_bias = str(manip.get("trade_bias", "NEUTRAL"))
            reasoning.append(
                f"{manip['direction']} at {manip['sweep_price']:.2f} with range re-entry."
            )
            setup_state = SetupState.WAITING_FOR_DISPLACEMENT

    fvgs = detect_fvgs(entry, timeframe="M5", atr=atr_entry, cfg=st)
    for f in fvgs:
        update_fvg_mitigation(f, price)
    for i, c in enumerate(entry):
        for f in fvgs:
            try_invert_fvg(f, c, atr_entry, st)

    inverted = [f for f in fvgs if f.inverted]
    swings = find_swings(entry, st.pivot_left, st.pivot_right, atr_entry)

    if manip and manip.get("detected") and trade_bias != "NEUTRAL":
        last = entry[-1]
        disp_q = score_displacement(last, atr_entry, False, bool(inverted))
        if disp_q >= 50:
            setup_state = SetupState.WAITING_FOR_MSS
            amd_phase = AmdPhase.DISTRIBUTION
            reasoning.append(f"Displacement score {disp_q:.0f} after manipulation.")
        mss = detect_mss(entry, swings, trade_bias, atr_entry, st)
        if mss and mss.get("shift_detected"):
            reasoning.append(
                f"{mss['direction']} MSS — broke {mss['broken_level']:.2f} by body close."
            )
            setup_state = SetupState.WAITING_FOR_IFVG_INVERSION

    if inverted:
        active_ifvg = inverted[-1]
        setup_state = SetupState.WAITING_FOR_RETRACE
        reasoning.append(
            f"iFVG {active_ifvg.direction} from inverted {active_ifvg.original_direction} FVG "
            f"({active_ifvg.lower:.2f}–{active_ifvg.upper:.2f})."
        )
        if active_ifvg.lower <= price <= active_ifvg.upper:
            active_ifvg.retest_count += 1
            setup_state = SetupState.ENTRY_ZONE_ACTIVE
            reasoning.append("Price inside iFVG entry zone.")
        elif price > active_ifvg.upper + st.chase_max_atr * atr_entry and active_ifvg.direction == "BEARISH":
            warnings.append("Missed entry: price chased below iFVG.")
            setup_state = SetupState.EXPIRED
        elif price < active_ifvg.lower - st.chase_max_atr * atr_entry and active_ifvg.direction == "BULLISH":
            warnings.append("Missed entry: price chased above iFVG.")
            setup_state = SetupState.EXPIRED

    pd_zone = premium_discount(
        acc.range_high if acc else candles_setup[-1].high,
        acc.range_low if acc else candles_setup[-1].low,
        price,
    )
    pd_score = 80.0 if (trade_bias == "BEARISH" and "PREMIUM" in pd_zone) or (
        trade_bias == "BULLISH" and "DISCOUNT" in pd_zone
    ) else 40.0

    penalties = len(warnings) * 8.0
    if htf == "BULLISH" and trade_bias == "BEARISH":
        penalties += 12.0
    if htf == "BEARISH" and trade_bias == "BULLISH":
        penalties += 12.0

    confidence = compute_confidence(
        htf_alignment=70.0 if htf in ("BULLISH", "BEARISH") else 40.0,
        acc_quality=acc.quality_score if acc else 0.0,
        sweep_quality=float(manip.get("quality_score", 0)) if manip else 0.0,
        disp_quality=score_displacement(entry[-1], atr_entry, bool(mss), bool(inverted)),
        mss_quality=float(mss.get("quality_score", 0)) if mss else 0.0,
        ifvg_quality=75.0 if active_ifvg else 0.0,
        pd_alignment=pd_score,
        rr_quality=80.0 if st.minimum_rr >= 2 else 50.0,
        penalties=penalties,
    )

    decision = Decision.NO_TRADE
    if confidence >= st.minimum_trade_score and active_ifvg and setup_state == SetupState.ENTRY_ZONE_ACTIVE:
        if active_ifvg.direction == "BULLISH" and trade_bias == "BULLISH":
            decision = Decision.BUY
        elif active_ifvg.direction == "BEARISH" and trade_bias == "BEARISH":
            decision = Decision.SELL
        else:
            decision = Decision.WAIT
    elif confidence >= 55 or (manip and manip.get("detected")):
        decision = Decision.WAIT

    entry_low = entry_high = preferred = 0.0
    sl = inv = 0.0
    tps: list[dict[str, Any]] = []
    if active_ifvg:
        entry_low, entry_high = active_ifvg.lower, active_ifvg.upper
        preferred = active_ifvg.midpoint if st.ifvg_use_midpoint_entry else (
            active_ifvg.upper if active_ifvg.direction == "BEARISH" else active_ifvg.lower
        )
        if decision == Decision.SELL and manip:
            sl = float(manip.get("sweep_price", active_ifvg.upper)) + 0.2 * atr_entry
            inv = sl
            risk = sl - preferred
            if risk > 0:
                tps = [
                    {"name": "TP1", "price": preferred - risk, "reason": "1R internal", "rr": 1.0},
                    {"name": "TP2", "price": acc.range_low if acc else preferred - 2 * risk, "reason": "Range low", "rr": 2.0},
                ]
        if decision == Decision.BUY and manip:
            sl = float(manip.get("sweep_price", active_ifvg.lower)) - 0.2 * atr_entry
            inv = sl
            risk = preferred - sl
            if risk > 0:
                tps = [
                    {"name": "TP1", "price": preferred + risk, "reason": "1R internal", "rr": 1.0},
                    {"name": "TP2", "price": acc.range_high if acc else preferred + 2 * risk, "reason": "Range high", "rr": 2.0},
                ]

    return {
        "module": "amd_ifvg",
        "version": "1.0",
        "valid": True,
        "gold_symbol_valid": True,
        "engine_enabled": st.enabled,
        "analysis_active": True,
        "symbol": sym,
        "base_symbol": "XAUUSD",
        "strategy": "AMD_IFVG",
        "timestamp": candles_setup[-1].time,
        "decision": decision.value,
        "setup_state": setup_state.value,
        "confidence": round(confidence, 1),
        "higher_timeframe_bias": htf,
        "amd_phase": amd_phase.value,
        "accumulation": {
            "detected": acc is not None,
            "start_time": acc.start_time if acc else 0,
            "end_time": acc.end_time if acc else 0,
            "range_high": acc.range_high if acc else 0.0,
            "range_low": acc.range_low if acc else 0.0,
            "midpoint": acc.midpoint if acc else 0.0,
            "quality_score": acc.quality_score if acc else 0.0,
        },
        "manipulation": manip or {"detected": False},
        "market_structure": mss or {"shift_detected": False},
        "ifvg": {
            "detected": active_ifvg is not None,
            "direction": active_ifvg.direction if active_ifvg else "",
            "original_fvg_direction": active_ifvg.original_direction if active_ifvg else "",
            "lower_boundary": active_ifvg.lower if active_ifvg else 0.0,
            "upper_boundary": active_ifvg.upper if active_ifvg else 0.0,
            "midpoint": active_ifvg.midpoint if active_ifvg else 0.0,
            "retest_count": active_ifvg.retest_count if active_ifvg else 0,
            "quality_score": 75.0 if active_ifvg else 0.0,
        },
        "entry": {
            "entry_type": "LIMIT",
            "entry_low": entry_low,
            "entry_high": entry_high,
            "preferred_entry": preferred,
            "current_price_inside_zone": bool(
                active_ifvg and active_ifvg.lower <= price <= active_ifvg.upper
            ),
        },
        "risk": {
            "stop_loss": sl,
            "stop_distance_points": abs(preferred - sl) if sl and preferred else 0.0,
            "risk_percentage": st.risk_percent,
            "recommended_lot_size": 0.0,
        },
        "targets": tps,
        "invalidation": {"price": inv, "reason": "Beyond manipulation extreme / iFVG distal"},
        "warnings": warnings,
        "reasoning": reasoning or ["No AMD + iFVG sequence detected on closed bars."],
        "status_line": decision.value,
        "recommendation": decision.value,
        "technical_narrative": "; ".join(reasoning[:4]) if reasoning else "Scanning.",
        "action_guidance": "Advisory only — confirm on closed candles before manual entry.",
        "premium_discount_zone": pd_zone,
        "spread_points": spread_points,
        "eval_bar_m5": entry[-1].time if entry else 0,
        "engine_phase": 1,
    }


def _disabled_blob(symbol: str, reason: str) -> dict[str, Any]:
    return {
        "module": "amd_ifvg",
        "version": "1.0",
        "valid": False,
        "gold_symbol_valid": False,
        "engine_enabled": False,
        "analysis_active": False,
        "symbol": symbol,
        "disable_reason": reason,
        "decision": Decision.NO_TRADE.value,
        "setup_state": SetupState.NO_TRADE.value,
        "confidence": 0.0,
        "reasoning": [reason],
    }


def _empty_blob(symbol: str, reason: str) -> dict[str, Any]:
    return {
        "module": "amd_ifvg",
        "version": "1.0",
        "valid": True,
        "gold_symbol_valid": True,
        "engine_enabled": True,
        "analysis_active": False,
        "symbol": symbol,
        "decision": Decision.NO_TRADE.value,
        "setup_state": SetupState.SEARCHING_FOR_ACCUMULATION.value,
        "confidence": 0.0,
        "reasoning": [reason],
    }


def candles_from_payload(rows: list[dict[str, Any]] | None) -> list[Candle]:
    """Parse OHLC rows from API / offline analyze payloads."""
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
