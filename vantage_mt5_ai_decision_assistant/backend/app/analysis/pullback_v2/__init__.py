"""Pullback Desk V2 — offline calibration utilities (Milestones 6–7)."""

from app.analysis.pullback_v2.calibration_buckets import (
    build_calibration_report,
    build_score_buckets,
    lookup_calibrated_probability,
)
from app.analysis.pullback_v2.outcome_labeler import label_pullback_outcome, label_rows
from app.analysis.pullback_v2.shadow_compare import aggregate_shadow_metrics, live_shadow_compare

__all__ = [
    "build_calibration_report",
    "build_score_buckets",
    "lookup_calibrated_probability",
    "label_pullback_outcome",
    "label_rows",
    "aggregate_shadow_metrics",
    "live_shadow_compare",
]
