"""Liquidity Grab — scoring helpers for deterministic scenario tests."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LiquidityGrabScoreInput:
    level_type: str = "SWING_HIGH"
    close_back_inside: bool = False
    wick_ratio: float = 0.0
    displacement: bool = False
    mss: bool = False
    mss_external: bool = False
    fvg: bool = False
    volume_elevated: bool = False
    htf_aligned: bool = False
    countertrend: bool = False
    session_boost: bool = False
    news_restricted: bool = False
    genuine_breakout: bool = False
    require_mss: bool = True
    confirmed_threshold: float = 70.0
    high_conf_threshold: float = 85.0


LEVEL_SCORES = {
    "PDH": 12,
    "PDL": 12,
    "PWH": 12,
    "PWL": 12,
    "ASIAN_HIGH": 10,
    "ASIAN_LOW": 10,
    "LONDON_HIGH": 10,
    "LONDON_LOW": 10,
    "NEW_YORK_HIGH": 10,
    "NEW_YORK_LOW": 10,
    "EQUAL_HIGHS": 10,
    "EQUAL_LOWS": 10,
    "SWING_HIGH": 8,
    "SWING_LOW": 8,
}


def score_liquidity_grab(inp: LiquidityGrabScoreInput) -> tuple[float, str]:
    """Mirror MQL5 scorer — returns (score, status)."""
    if inp.genuine_breakout:
        return 0.0, "GENUINE_BREAKOUT"

    score = float(LEVEL_SCORES.get(inp.level_type, 6))
    score += 8  # valid sweep placeholder
    if inp.close_back_inside:
        score += 12
    else:
        score -= 12
    if inp.wick_ratio >= 0.35:
        score += 6
    if inp.displacement:
        score += 12
    if inp.mss:
        score += 16
        if inp.mss_external:
            score += 8
    if inp.fvg:
        score += 5
    if inp.volume_elevated:
        score += 4
    if inp.htf_aligned:
        score += 8
    elif inp.countertrend:
        score -= 10
    if inp.session_boost:
        score += 5
    if inp.news_restricted:
        score -= 10

    if inp.require_mss and not inp.mss:
        score = min(score, 69.0)

    score = max(0.0, min(100.0, score))

    if score >= inp.high_conf_threshold and inp.mss:
        return score, "HIGH_CONFIDENCE_LIQUIDITY_GRAB"
    if score >= inp.confirmed_threshold and inp.mss:
        return score, "LIQUIDITY_GRAB_CONFIRMED"
    if score >= 55:
        return score, "LIQUIDITY_SWEEP_UNCONFIRMED"
    if score >= 40:
        return score, "LIQUIDITY_TEST"
    return score, "NO_VALID_SETUP"


def classify_mss_cap_without_mss() -> bool:
    """Wick-only path must not exceed 69."""
    inp = LiquidityGrabScoreInput(
        level_type="ASIAN_HIGH",
        close_back_inside=True,
        wick_ratio=0.48,
        displacement=True,
        mss=False,
        htf_aligned=True,
    )
    score, status = score_liquidity_grab(inp)
    return score <= 69 and status == "LIQUIDITY_SWEEP_UNCONFIRMED"
