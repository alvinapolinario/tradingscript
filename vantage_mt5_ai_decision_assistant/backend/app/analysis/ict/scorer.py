"""Deterministic ICT confidence scoring — AI must not invent these values."""
from __future__ import annotations

from app.analysis.ict.types import IctConfig, IctDecision, IctSetupContext, IctSetupState, LiquiditySweepEvent


def _requirements_met(ctx: IctSetupContext, cfg: IctConfig) -> dict[str, bool]:
    return {
        "liquidity_sweep": bool(ctx.sweep and ctx.sweep.detected) or not cfg.require_liquidity_sweep,
        "displacement": ctx.displacement_score >= cfg.displacement_min_score or not cfg.require_displacement,
        "mss": bool(ctx.mss and ctx.mss.get("shift_detected")) or not cfg.require_mss,
        "fvg": bool(ctx.fvg) or not cfg.require_fvg,
    }


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
    Weights sum to 100 by default.
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

    if ctx.displacement_score >= cfg.displacement_min_score:
        components["displacement"] = min(
            cfg.weight_displacement,
            cfg.weight_displacement * (ctx.displacement_score / 100.0),
        )
    else:
        components["displacement"] = 0.0

    mss_q = float((ctx.mss or {}).get("quality_score") or 0)
    components["mss"] = min(cfg.weight_mss, cfg.weight_mss * (mss_q / 100.0)) if ctx.mss else 0.0

    if ctx.fvg:
        fvg_q = min(100.0, 50.0 + ctx.fvg.gap_atr * 100.0)
        components["fvg"] = min(cfg.weight_fvg, cfg.weight_fvg * (fvg_q / 100.0))
    else:
        components["fvg"] = 0.0

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
    if risk_reward < cfg.minimum_rr:
        penalties.append(f"R:R {risk_reward:.1f} below minimum {cfg.minimum_rr}")

    gates = _requirements_met(ctx, cfg)
    if not all(gates.values()):
        missing = [k for k, ok in gates.items() if not ok]
        penalties.append(f"Missing required: {', '.join(missing)}")

    raw = sum(components.values())
    if cfg.block_countertrend and not htf_aligned and ctx.trade_bias in ("BULLISH", "BEARISH"):
        raw *= 0.5
        penalties.append("Countertrend block active")

    # Cap score when setup not far enough in lifecycle
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
    elif ctx.state in (IctSetupState.WAITING_FOR_RETRACE, IctSetupState.MSS_CONFIRMED):
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
) -> IctDecision:
    if state == IctSetupState.TARGET_REACHED:
        return IctDecision.NO_TRADE
    if state in (IctSetupState.INVALIDATED, IctSetupState.EXPIRED):
        return IctDecision.NO_TRADE
    if state == IctSetupState.TRIGGERED:
        if not all(gates.values()):
            return IctDecision.WAIT
        if cfg.block_countertrend and not htf_aligned and trade_bias in ("BULLISH", "BEARISH"):
            return IctDecision.WAIT
        if score >= cfg.min_confidence and risk_reward >= cfg.minimum_rr:
            return IctDecision.SELL if trade_bias == "BEARISH" else IctDecision.BUY
        return IctDecision.WAIT
    if state in (
        IctSetupState.ENTRY_ZONE_ACTIVE,
        IctSetupState.WAITING_FOR_RETRACE,
        IctSetupState.MSS_CONFIRMED,
    ):
        return IctDecision.WAIT
    if state == IctSetupState.NO_SETUP:
        return IctDecision.NO_SETUP
    return IctDecision.WAIT
