"""Breakout Structure — scoring helpers for deterministic tests."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BreakoutScoreInput:
    structure_pts: float = 14.0
    trendline_pts: float = 10.0
    breakout_pts: float = 12.0
    retest_pts: float = 0.0
    flip_pts: float = 0.0
    htf_pts: float = 5.0


def grade_from_score(score: float) -> str:
    if score >= 95:
        return "Institutional Grade"
    if score >= 90:
        return "A+"
    if score >= 85:
        return "A"
    if score >= 80:
        return "B+"
    if score >= 75:
        return "B"
    return "Reject"


def score_breakout(inp: BreakoutScoreInput) -> tuple[float, str]:
    total = inp.structure_pts + inp.trendline_pts + inp.breakout_pts + inp.retest_pts + inp.flip_pts + inp.htf_pts
    total = max(0.0, min(100.0, total))
    return total, grade_from_score(total)
