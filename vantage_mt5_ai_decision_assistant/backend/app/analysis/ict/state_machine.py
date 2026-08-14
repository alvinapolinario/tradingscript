"""ICT setup state machine — transitions, invalidation, expiration."""
from __future__ import annotations

from app.analysis.ict.types import (
    IctConfig,
    IctSetupContext,
    IctSetupRecord,
    IctSetupState,
    LiquiditySweepEvent,
)
from app.market_structure.types import Candle

STATE_RANK: dict[IctSetupState, int] = {
    IctSetupState.NO_SETUP: -1,
    IctSetupState.WAITING_FOR_LIQUIDITY: 0,
    IctSetupState.LIQUIDITY_IDENTIFIED: 1,
    IctSetupState.LIQUIDITY_SWEPT: 2,
    IctSetupState.WAITING_FOR_DISPLACEMENT: 3,
    IctSetupState.DISPLACEMENT_CONFIRMED: 4,
    IctSetupState.WAITING_FOR_MSS: 5,
    IctSetupState.MSS_CONFIRMED: 6,
    IctSetupState.WAITING_FOR_EXECUTION_FVG: 6,
    IctSetupState.EXECUTION_FVG_FOUND: 7,
    IctSetupState.WAITING_FOR_RETRACE: 8,
    IctSetupState.FVG_TOUCHED: 9,
    IctSetupState.ENTRY_ZONE_ACTIVE: 9,
    IctSetupState.ENTRY_READY: 10,
    IctSetupState.TRIGGERED: 10,
    IctSetupState.TARGET_REACHED: 11,
    IctSetupState.INVALIDATED: 99,
    IctSetupState.EXPIRED: 99,
}

_ADVISORY_READY = (
    IctSetupState.ENTRY_READY,
    IctSetupState.TRIGGERED,
    IctSetupState.ENTRY_ZONE_ACTIVE,
    IctSetupState.FVG_TOUCHED,
)


def make_setup_id(symbol: str, timeframe: str, sweep: LiquiditySweepEvent | None, bias: str) -> str:
    """Stable setup ID anchored to sweep event — does not change each bar."""
    sym = (symbol or "XAUUSD").upper()
    tf = timeframe or "M15"
    if sweep and sweep.detected:
        b = "B" if bias == "BULLISH" else "S" if bias == "BEARISH" else "N"
        return f"ICT-{sym}-{tf}-{sweep.sweep_time}-{b}"
    return f"ICT-{sym}-{tf}-SCAN"


def merge_state(stored: IctSetupState | None, computed: IctSetupState) -> IctSetupState:
    """Never regress lifecycle state unless terminal."""
    if stored is None:
        return computed
    if stored in (IctSetupState.INVALIDATED, IctSetupState.EXPIRED, IctSetupState.TARGET_REACHED):
        return stored
    if computed in (IctSetupState.INVALIDATED, IctSetupState.EXPIRED, IctSetupState.TARGET_REACHED):
        return computed
    # Legacy TRIGGERED ↔ ENTRY_READY equivalence
    if stored == IctSetupState.TRIGGERED and computed == IctSetupState.ENTRY_READY:
        return IctSetupState.ENTRY_READY
    if stored == IctSetupState.ENTRY_READY and computed == IctSetupState.TRIGGERED:
        return IctSetupState.ENTRY_READY
    s_rank = STATE_RANK.get(stored, 0)
    c_rank = STATE_RANK.get(computed, 0)
    return computed if c_rank >= s_rank else stored


def setup_age_candles(setup_candles: list[Candle], sweep_time: int) -> int:
    if not sweep_time or not setup_candles:
        return 0
    after = [c for c in setup_candles if c.time >= sweep_time]
    return len(after)


def check_expiration(
    ctx: IctSetupContext,
    setup_candles: list[Candle],
    cfg: IctConfig,
) -> bool:
    if not ctx.sweep or not ctx.sweep.detected:
        return False
    age = setup_age_candles(setup_candles, ctx.sweep.sweep_time)
    if age > cfg.max_setup_age_candles:
        ctx.state = IctSetupState.EXPIRED
        ctx.reasons.append(f"Setup expired after {age} candles (max {cfg.max_setup_age_candles}).")
        ctx.invalidations.append("Setup age limit exceeded")
        return True
    return False


def _opposite_sweep_invalidates(
    ctx: IctSetupContext,
    setup_candles: list[Candle],
    cfg: IctConfig,
) -> bool:
    """Symmetric invalidation when opposite-side liquidity is swept after entry sweep."""
    if not ctx.sweep:
        return False
    sweep = ctx.sweep
    min_pen = cfg.sweep_min_penetration_atr
    for c in setup_candles:
        if c.time <= sweep.sweep_time:
            continue
        if sweep.sweep_type == "BUY_SIDE" and ctx.trade_bias == "BEARISH":
            pen = sweep.level - c.low
            if pen >= min_pen and c.close > sweep.level:
                ctx.state = IctSetupState.INVALIDATED
                ctx.reasons.append("Invalidated by opposite SSL sweep after BSL sweep.")
                return True
        if sweep.sweep_type == "SELL_SIDE" and ctx.trade_bias == "BULLISH":
            pen = c.high - sweep.level
            if pen >= min_pen and c.close < sweep.level:
                ctx.state = IctSetupState.INVALIDATED
                ctx.reasons.append("Invalidated by opposite BSL sweep after SSL sweep.")
                return True
    return False


def check_invalidation(
    ctx: IctSetupContext,
    price: float,
    setup_candles: list[Candle],
    cfg: IctConfig,
    invalidation_price: float,
) -> bool:
    if not ctx.sweep or invalidation_price <= 0:
        return False

    last = setup_candles[-1] if setup_candles else None
    if ctx.trade_bias == "BEARISH":
        if price > invalidation_price or (last and last.close > invalidation_price):
            ctx.state = IctSetupState.INVALIDATED
            ctx.reasons.append(f"Bearish setup invalidated — close above {invalidation_price:.2f}.")
            ctx.invalidations.append(f"{cfg.primary_setup_timeframe} close above {invalidation_price:.2f}")
            return True
    elif ctx.trade_bias == "BULLISH":
        if price < invalidation_price or (last and last.close < invalidation_price):
            ctx.state = IctSetupState.INVALIDATED
            ctx.reasons.append(f"Bullish setup invalidated — close below {invalidation_price:.2f}.")
            ctx.invalidations.append(f"{cfg.primary_setup_timeframe} close below {invalidation_price:.2f}")
            return True

    if _opposite_sweep_invalidates(ctx, setup_candles, cfg):
        return True

    return False


def check_target_reached(
    ctx: IctSetupContext,
    price: float,
    targets: list[dict],
) -> bool:
    if not targets or ctx.state not in _ADVISORY_READY:
        return False
    tp1 = float(targets[0].get("price") or 0)
    if tp1 <= 0:
        return False
    if ctx.trade_bias == "BEARISH" and price <= tp1:
        ctx.state = IctSetupState.TARGET_REACHED
        ctx.reasons.append(f"TP1 reached at {tp1:.2f}.")
        return True
    if ctx.trade_bias == "BULLISH" and price >= tp1:
        ctx.state = IctSetupState.TARGET_REACHED
        ctx.reasons.append(f"TP1 reached at {tp1:.2f}.")
        return True
    return False


def context_to_record(
    ctx: IctSetupContext,
    *,
    symbol: str,
    timeframe: str,
    setup_id: str,
    confidence: float,
    setup_candles: list[Candle],
    stop_loss: float,
    tp1: float,
    eval_time: int,
) -> IctSetupRecord:
    sweep = ctx.sweep
    age = setup_age_candles(setup_candles, sweep.sweep_time if sweep else 0)
    return IctSetupRecord(
        setup_id=setup_id,
        symbol=symbol.upper(),
        timeframe=timeframe,
        trade_bias=ctx.trade_bias,
        state=ctx.state,
        sweep_time=sweep.sweep_time if sweep else 0,
        sweep_type=sweep.sweep_type if sweep else "",
        sweep_level=sweep.level if sweep else 0.0,
        sweep_price=sweep.sweep_price if sweep else 0.0,
        displacement_score=ctx.displacement_score,
        mss_direction=str((ctx.mss or {}).get("direction") or ""),
        fvg_id=ctx.fvg.fvg_id if ctx.fvg else "",
        fvg_high=ctx.fvg.upper if ctx.fvg else 0.0,
        fvg_low=ctx.fvg.lower if ctx.fvg else 0.0,
        entry_zone_high=ctx.entry.zone_high if ctx.entry else 0.0,
        entry_zone_low=ctx.entry.zone_low if ctx.entry else 0.0,
        stop_loss=stop_loss,
        invalidation_price=stop_loss,
        tp1_price=tp1,
        confidence=confidence,
        created_time=sweep.sweep_time if sweep else eval_time,
        updated_time=eval_time,
        age_candles=age,
        last_event=ctx.state.value,
    )


def build_timeline(ctx: IctSetupContext) -> list[dict[str, str]]:
    rank = STATE_RANK.get(ctx.state, 0)
    terminal = ctx.state in (
        IctSetupState.INVALIDATED,
        IctSetupState.EXPIRED,
        IctSetupState.TARGET_REACHED,
    )

    def _status(step_rank: int, *, active_state: IctSetupState | None = None) -> str:
        if terminal and ctx.state == IctSetupState.TARGET_REACHED and step_rank <= STATE_RANK[IctSetupState.ENTRY_READY]:
            return "done"
        if terminal and ctx.state in (IctSetupState.INVALIDATED, IctSetupState.EXPIRED):
            if step_rank <= rank:
                return "done"
            return "pending"
        if active_state and ctx.state == active_state:
            return "active"
        return "done" if rank >= step_rank else "pending"

    return [
        {"step": "HTF_BIAS", "status": "done" if ctx.htf_bias != "NEUTRAL" else "pending"},
        {"step": "LIQUIDITY", "status": "done" if ctx.bsl_levels or ctx.ssl_levels else "pending"},
        {"step": "SWEEP", "status": "done" if ctx.sweep and ctx.sweep.detected else "pending"},
        {"step": "DISPLACEMENT", "status": _status(STATE_RANK[IctSetupState.DISPLACEMENT_CONFIRMED])},
        {"step": "MSS", "status": "done" if ctx.mss_event or ctx.mss else "pending"},
        {"step": "FVG", "status": "done" if ctx.fvg else "pending"},
        {
            "step": "RETRACE",
            "status": _status(
                STATE_RANK[IctSetupState.FVG_TOUCHED],
                active_state=IctSetupState.WAITING_FOR_RETRACE,
            ),
        },
        {"step": "ENTRY", "status": _status(STATE_RANK[IctSetupState.ENTRY_READY])},
        {"step": "TP", "status": "done" if ctx.state == IctSetupState.TARGET_REACHED else "pending"},
    ]
