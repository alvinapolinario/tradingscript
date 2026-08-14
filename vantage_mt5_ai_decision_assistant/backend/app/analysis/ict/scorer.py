"""Deterministic ICT confidence scoring — hard causal gates override score."""
from __future__ import annotations

from app.analysis.ict.types import IctConfig, IctDecision, IctSetupContext, IctSetupState, LiquiditySweepEvent


def _causality_gates(ctx: IctSetupContext) -> dict[str, bool]:
    sweep_ok = bool(ctx.sweep and ctx.sweep.detected)
    disp_ok = bool(ctx.displacement_event and ctx.displacement_score >= 0)
    mss_ok = bool(ctx.mss_event or (ctx.mss and ctx.mss.get("shift_detected")))
    fvg_ok = bool(ctx.fvg and ctx.execution_fvg_id)
    retrace_ok = ctx.state in (
        IctSetupState.FVG_TOUCHED,
        IctSetupState.ENTRY_ZONE_ACTIVE,
        IctSetupState.ENTRY_READY,
        IctSetupState.TRIGGERED,
    )
    not_invalid = ctx.state not in (IctSetupState.INVALIDATED, IctSetupState.EXPIRED)
    chronology_ok = not ctx.causality_errors
    return {
        "valid_sweep": sweep_ok,
        "valid_displacement": disp_ok,
        "valid_mss": mss_ok,
        "valid_execution_fvg": fvg_ok,
        "valid_retrace": retrace_ok,
        "not_invalidated": not_invalid,
        "causality_chronology": chronology_ok,
    }


def _requirements_met(ctx: IctSetupContext, cfg: IctConfig) -> dict[str, bool]:
    causal = _causality_gates(ctx)
    return {
        "liquidity_sweep": causal["valid_sweep"] or not cfg.require_liquidity_sweep,
        "displacement": (
            bool(ctx.displacement_event and ctx.displacement_score >= cfg.displacement_min_score)
            or not cfg.require_displacement
        ),
        "mss": causal["valid_mss"] or not cfg.require_mss,
        "fvg": causal["valid_execution_fvg"] or not cfg.require_fvg,
        "causality": causal["causality_chronology"],
    }


def _impulse_quality(ctx: IctSetupContext) -> float:
    parts: list[float] = []
    if ctx.displacement_event:
        parts.append(ctx.displacement_event.quality_score)
    if ctx.mss_event:
        parts.append(ctx.mss_event.quality_score)
    elif ctx.mss:
        parts.append(float(ctx.mss.get("quality_score") or 0))
    if ctx.fvg:
        parts.append(min(100.0, 50.0 + ctx.fvg.gap_atr * 100.0))
    if not parts:
        return 0.0
    return sum(parts) / len(parts)


def score_ict_setup(
    ctx: IctSetupContext,
    *,
    htf_confidence: float,
    htf_aligned: bool,
    session_score: float,
    risk_reward: float,
    cfg: IctConfig,
) -> tuple[float, dict[str, float], dict[str, bool], list[str]]:
    """
    Returns (total_score, components, gates_passed, penalties_applied).
    Hard causal gates cap score when chronology invalid.
    """
    components: dict[str, float] = {}
    penalties: list[str] = []

    if htf_aligned:
        components["htf_alignment"] = min(
            cfg.weight_htf_alignment,
            cfg.weight_htf_alignment * (htf_confidence / 100.0),
        )
    else:
        components["htf_alignment"] = max(0.0, cfg.weight_htf_alignment * 0.25)
        if ctx.trade_bias in ("BULLISH", "BEARISH") and ctx.htf_bias not in ("NEUTRAL", ctx.trade_bias):
            components["htf_alignment"] = max(0.0, components["htf_alignment"] - cfg.countertrend_penalty * 0.5)
            penalties.append(f"HTF countertrend ({ctx.htf_bias} vs {ctx.trade_bias})")

    sweep: LiquiditySweepEvent | None = ctx.sweep
    if sweep and sweep.detected:
        components["liquidity_sweep"] = min(
            cfg.weight_liquidity_sweep,
            cfg.weight_liquidity_sweep * (sweep.quality_score / 100.0),
        )
    else:
        components["liquidity_sweep"] = 0.0

    impulse_q = _impulse_quality(ctx)
    if impulse_q > 0:
        components["impulse_quality"] = min(
            cfg.weight_impulse_quality,
            cfg.weight_impulse_quality * (impulse_q / 100.0),
        )
    else:
        components["impulse_quality"] = 0.0

    if cfg.use_premium_discount:
        pd = ctx.premium_discount_zone
        aligned_pd = (ctx.trade_bias == "BEARISH" and "PREMIUM" in pd) or (
            ctx.trade_bias == "BULLISH" and "DISCOUNT" in pd
        )
        components["premium_discount"] = (
            cfg.weight_premium_discount if aligned_pd else cfg.weight_premium_discount * 0.3
        )
        if not aligned_pd and ctx.trade_bias in ("BULLISH", "BEARISH"):
            penalties.append(f"Entry not in ideal PD zone ({pd})")
    else:
        components["premium_discount"] = cfg.weight_premium_discount * 0.5

    if cfg.use_session_filter:
        components["session"] = min(cfg.weight_session, cfg.weight_session * (session_score / 100.0))
    else:
        components["session"] = cfg.weight_session * 0.6

    rr_norm = min(1.0, risk_reward / max(cfg.minimum_rr, 0.1))
    components["risk_reward"] = cfg.weight_risk_reward * rr_norm
    if risk_reward < cfg.minimum_rr and ctx.state in (IctSetupState.ENTRY_READY, IctSetupState.TRIGGERED):
        penalties.append(f"R:R {risk_reward:.1f} below minimum {cfg.minimum_rr}")

    if cfg.enable_ote and ctx.ote_valid:
        if ctx.price_in_ote:
            components["ote"] = cfg.weight_ote
        elif ctx.fvg_overlaps_ote or ctx.poi_overlaps_ote:
            components["ote"] = cfg.weight_ote * 0.75
        else:
            components["ote"] = cfg.weight_ote * 0.25

    ob = ctx.order_block
    if cfg.enable_order_blocks and ob and ob.status not in ("INVALIDATED",):
        components["order_block"] = min(
            cfg.weight_order_block,
            cfg.weight_order_block * (ob.quality_score / 100.0),
        )
        if cfg.enable_breaker and ob.is_breaker:
            components["breaker"] = cfg.weight_breaker

    gates = _requirements_met(ctx, cfg)
    if ctx.causality_errors:
        penalties.extend(ctx.causality_errors)
        ctx.causality_valid = False
    else:
        ctx.causality_valid = all(_causality_gates(ctx).values()) or ctx.state not in (
            IctSetupState.ENTRY_READY,
            IctSetupState.TRIGGERED,
        )

    if not all(gates.values()):
        missing = [k for k, ok in gates.items() if not ok]
        penalties.append(f"Missing required: {', '.join(missing)}")

    raw = sum(components.values())
    if cfg.block_countertrend and not htf_aligned and ctx.trade_bias in ("BULLISH", "BEARISH"):
        raw *= 0.5
        penalties.append("Countertrend block active")

    # Hard gate: invalid chronology cannot produce high score
    if ctx.causality_errors:
        raw = min(raw, 45.0)

    if ctx.state in (
        IctSetupState.WAITING_FOR_LIQUIDITY,
        IctSetupState.LIQUIDITY_IDENTIFIED,
        IctSetupState.NO_SETUP,
    ):
        raw = min(raw, 35.0)
    elif ctx.state in (IctSetupState.LIQUIDITY_SWEPT, IctSetupState.WAITING_FOR_DISPLACEMENT):
        raw = min(raw, 55.0)
    elif ctx.state in (IctSetupState.WAITING_FOR_MSS, IctSetupState.DISPLACEMENT_CONFIRMED):
        raw = min(raw, 65.0)
    elif ctx.state in (
        IctSetupState.WAITING_FOR_RETRACE,
        IctSetupState.MSS_CONFIRMED,
        IctSetupState.WAITING_FOR_EXECUTION_FVG,
        IctSetupState.EXECUTION_FVG_FOUND,
    ):
        raw = min(raw, 75.0)

    total = round(min(100.0, max(0.0, raw)), 1)
    components = {k: round(v, 1) for k, v in components.items()}
    return total, components, gates, penalties


def quality_band(score: float) -> str:
    if score >= 85:
        return "VERY HIGH"
    if score >= 70:
        return "HIGH"
    if score >= 50:
        return "MODERATE"
    return "LOW"


def decide_from_score(
    *,
    state: IctSetupState,
    score: float,
    risk_reward: float,
    gates: dict[str, bool],
    htf_aligned: bool,
    trade_bias: str,
    cfg: IctConfig,
    causality_valid: bool = True,
) -> IctDecision:
    if state == IctSetupState.TARGET_REACHED:
        return IctDecision.NO_TRADE
    if state in (IctSetupState.INVALIDATED, IctSetupState.EXPIRED):
        return IctDecision.NO_TRADE
    if not causality_valid or not gates.get("causality", True):
        return IctDecision.WAIT if state != IctSetupState.NO_SETUP else IctDecision.NO_SETUP

    ready_states = (IctSetupState.ENTRY_READY, IctSetupState.TRIGGERED)
    if state in ready_states:
        if not all(gates.values()):
            return IctDecision.WAIT
        if cfg.block_countertrend and not htf_aligned and trade_bias in ("BULLISH", "BEARISH"):
            return IctDecision.WAIT
        if score >= cfg.min_confidence and risk_reward >= cfg.minimum_rr:
            return IctDecision.SELL if trade_bias == "BEARISH" else IctDecision.BUY
        return IctDecision.WAIT

    if state in (
        IctSetupState.ENTRY_ZONE_ACTIVE,
        IctSetupState.FVG_TOUCHED,
        IctSetupState.WAITING_FOR_RETRACE,
        IctSetupState.MSS_CONFIRMED,
        IctSetupState.EXECUTION_FVG_FOUND,
        IctSetupState.WAITING_FOR_EXECUTION_FVG,
    ):
        return IctDecision.WAIT
    if state == IctSetupState.NO_SETUP:
        return IctDecision.NO_SETUP
    return IctDecision.WAIT
