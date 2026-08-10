"""Human-readable ICT decision trace."""
from __future__ import annotations

from app.analysis.ict.types import IctDecision, IctSetupContext


def build_explanation(ctx: IctSetupContext, decision: IctDecision, score: float, rr: float) -> str:
    lines = [
        f"ICT bias = {ctx.trade_bias}",
        f"HTF bias = {ctx.htf_bias}",
        f"State = {ctx.state.value}",
    ]
    if ctx.sweep and ctx.sweep.detected:
        lines.append(f"Sweep = {ctx.sweep.sweep_type} @ {ctx.sweep.sweep_price:.2f}")
    if ctx.displacement_score:
        lines.append(f"Displacement = {ctx.displacement_score:.0f}")
    if ctx.mss:
        lines.append(f"MSS = {ctx.mss.get('direction', '—')}")
    if ctx.fvg:
        lines.append(f"FVG = {ctx.fvg.lower:.2f}–{ctx.fvg.upper:.2f}")
    lines.append(f"Premium/Discount = {ctx.premium_discount_zone}")
    lines.append(f"R:R = {rr:.1f}")
    lines.append(f"Score = {score:.0f}")
    lines.append(f"Decision = {decision.value}")
    return "\n".join(lines)
