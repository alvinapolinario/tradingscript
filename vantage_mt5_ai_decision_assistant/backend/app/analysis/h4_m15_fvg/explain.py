"""Human-readable and JSON explanations for H4→M15 setups."""
from __future__ import annotations

from typing import Any

from app.analysis.h4_m15_fvg.types import H4M15Setup, H4M15SetupState


def setup_to_json(setup: H4M15Setup) -> dict[str, Any]:
    z = setup.htf_fvg
    ef = setup.entry_fvg
    sw = setup.sweep
    decision = "NO ENTRY YET"
    if setup.state == H4M15SetupState.ENTRY_READY:
        decision = "ENTRY_READY"
    elif setup.state == H4M15SetupState.SETUP_INVALIDATED:
        decision = "INVALIDATED"
    elif setup.state == H4M15SetupState.SETUP_EXPIRED:
        decision = "EXPIRED"

    return {
        "symbol": setup.symbol,
        "direction": setup.direction,
        "state": setup.state.value,
        "setup_id": setup.setup_id,
        "htf_location": {
            "timeframe": z.timeframe,
            "fvg_id": z.fvg_id,
            "lower": z.lower,
            "upper": z.upper,
            "mitigation_percent": round(z.mitigation_pct, 2),
            "pd_location": setup.pd_location,
            "first_touch_time": setup.htf_first_touch_time,
        },
        "liquidity": {
            "sweep_detected": bool(sw and sw.detected),
            "type": sw.sweep_type if sw else "",
            "time": sw.sweep_time if sw else 0,
            "price": sw.sweep_price if sw else 0.0,
            "quality": sw.quality_score if sw else 0.0,
        },
        "displacement": {
            "confirmed": setup.displacement_time > 0,
            "time": setup.displacement_time,
            "score": setup.displacement_score,
        },
        "structure": {
            "mss_confirmed": setup.mss_time > 0,
            "broken_level": setup.mss_price,
            "time": setup.mss_time,
        },
        "entry_fvg": {
            "timeframe": ef.timeframe if ef else "",
            "fvg_id": ef.fvg_id if ef else "",
            "lower": ef.lower if ef else 0.0,
            "upper": ef.upper if ef else 0.0,
            "parent_fvg_id": ef.parent_fvg_id if ef else "",
        },
        "entry_ready_time": setup.entry_ready_time,
        "entry_price": setup.entry_price,
        "structural_stop": setup.structural_stop,
        "score": setup.setup_score,
        "grade": setup.setup_grade,
        "decision": decision,
        "reasons": list(setup.reasons[-12:]),
        "rejections": list(setup.rejections),
        "invalidation_reason": setup.invalidation_reason,
        "expiration_reason": setup.expiration_reason,
        "transition_log": [
            {
                "timestamp": t.timestamp,
                "old_state": t.old_state,
                "new_state": t.new_state,
                "reason": t.reason,
            }
            for t in setup.transition_log[-20:]
        ],
    }


def setup_to_text(setup: H4M15Setup) -> str:
    z = setup.htf_fvg
    lines = [
        f"{setup.symbol} — {setup.direction} FVG CANDIDATE",
        "",
        "HTF Location:",
        f"H4 {setup.direction.title()} FVG",
        f"{z.lower:.5f} – {z.upper:.5f}",
        "",
        f"Mitigation: {z.mitigation_pct:.0f}%",
        f"HTF PD Location: {setup.pd_location}",
        "",
    ]
    if setup.sweep and setup.sweep.detected:
        lines.extend(
            [
                "Liquidity:",
                f"M15 {setup.sweep.sweep_type} Sweep CONFIRMED",
                "",
            ]
        )
    if setup.displacement_time:
        lines.extend(
            [
                "Displacement:",
                f"{setup.direction.title()} / score {setup.displacement_score:.0f}",
                "",
            ]
        )
    if setup.mss_time:
        lines.extend(
            [
                "Structure:",
                f"{setup.direction.title()} MSS CONFIRMED @ {setup.mss_price:.5f}",
                "",
            ]
        )
    if setup.entry_fvg:
        ef = setup.entry_fvg
        lines.extend(
            [
                "Execution POI:",
                f"M15 {setup.direction.title()} FVG",
                f"{ef.lower:.5f} – {ef.upper:.5f}",
                "",
            ]
        )
    lines.extend(
        [
            f"Current State: {setup.state.value}",
            f"Setup Score: {setup.setup_score:.0f} / 100",
            f"{setup.setup_grade.replace('_', ' ')}",
            "",
        ]
    )
    if setup.state == H4M15SetupState.ENTRY_READY:
        lines.append("Decision: ENTRY_READY (analysis only — no auto trade)")
    elif setup.state == H4M15SetupState.SETUP_INVALIDATED:
        lines.extend(["SETUP INVALIDATED", f"Reason: {setup.invalidation_reason}"])
    elif setup.state == H4M15SetupState.SETUP_EXPIRED:
        lines.extend(["SETUP EXPIRED", f"Reason: {setup.expiration_reason}"])
    else:
        lines.append("Decision: NO ENTRY YET")
    if setup.rejections:
        lines.extend(["", "Rejections:"] + setup.rejections)
    return "\n".join(lines)
