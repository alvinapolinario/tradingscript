"""Offline calibration bucket report for Pullback Desk V2 (Milestone 7)."""
from __future__ import annotations

from typing import Any


def _f(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _bucket_bounds(score: float, width: int) -> tuple[int, int]:
    width = max(1, min(int(width), 50))
    clamped = max(0.0, min(_f(score), 100.0))
    lo = int(clamped // width) * width
    hi = min(lo + width, 100)
    if lo >= 100:
        lo = max(0, 100 - width)
        hi = 100
    return lo, hi


def _ok_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rows if r.get("outcome", {}).get("label_status") == "ok"]


def build_score_buckets(
    rows: list[dict[str, Any]],
    score_field: str,
    *,
    outcome_field: str = "pullback_occurred",
    bucket_width: int = 10,
    min_samples: int = 5,
) -> dict[str, Any]:
    """Bin a score column against a labeled binary outcome."""
    ok = _ok_rows(rows)
    accum: dict[tuple[int, int], dict[str, Any]] = {}

    preds: list[float] = []
    actuals: list[int] = []

    for row in ok:
        if row.get(score_field) is None:
            continue
        score = _f(row.get(score_field))
        actual = bool(row["outcome"].get(outcome_field))
        lo, hi = _bucket_bounds(score, bucket_width)
        key = (lo, hi)
        if key not in accum:
            accum[key] = {"lo": lo, "hi": hi, "n": 0, "occurred": 0, "score_sum": 0.0}
        accum[key]["n"] += 1
        accum[key]["occurred"] += int(actual)
        accum[key]["score_sum"] += score
        preds.append(score / 100.0)
        actuals.append(int(actual))

    buckets: list[dict[str, Any]] = []
    for key in sorted(accum.keys()):
        b = accum[key]
        n = int(b["n"])
        occurred = int(b["occurred"])
        rate = round(occurred / n, 4) if n else None
        avg_score = round(b["score_sum"] / n, 2) if n else None
        buckets.append(
            {
                "lo": b["lo"],
                "hi": b["hi"],
                "label": f"{b['lo']}-{b['hi']}",
                "n": n,
                "occurred": occurred,
                "rate": rate,
                "avg_score": avg_score,
                "reliable": n >= min_samples,
            }
        )

    labeled_with_score = len(preds)
    brier = None
    ece = None
    if labeled_with_score:
        brier = round(sum((p - a) ** 2 for p, a in zip(preds, actuals)) / labeled_with_score, 4)
        total_n = sum(b["n"] for b in buckets)
        if total_n:
            ece = round(
                sum(abs((b["rate"] or 0.0) - ((b["lo"] + b["hi"]) / 200.0)) * b["n"] for b in buckets)
                / total_n,
                4,
            )

    recommended_threshold = _recommend_threshold(ok, score_field, outcome_field)

    return {
        "score_field": score_field,
        "outcome_field": outcome_field,
        "bucket_width": bucket_width,
        "labeled_count": labeled_with_score,
        "buckets": buckets,
        "brier_score": brier,
        "ece": ece,
        "recommended_threshold": recommended_threshold,
    }


def _recommend_threshold(
    rows: list[dict[str, Any]],
    score_field: str,
    outcome_field: str,
) -> float | None:
    pairs = [
        (_f(r.get(score_field)), bool(r["outcome"].get(outcome_field)))
        for r in rows
        if r.get(score_field) is not None
    ]
    if len(pairs) < 10:
        return None

    best_thr: float | None = None
    best_f1 = -1.0
    for thr in range(10, 96, 5):
        tp = fp = fn = 0
        for score, actual in pairs:
            pred = score >= thr
            if pred and actual:
                tp += 1
            elif pred and not actual:
                fp += 1
            elif not pred and actual:
                fn += 1
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        if f1 > best_f1:
            best_f1 = f1
            best_thr = float(thr)
    return best_thr


def lookup_calibrated_probability(score: float, buckets: list[dict[str, Any]]) -> float | None:
    """Map a raw score to empirical outcome rate from its bucket."""
    clamped = max(0.0, min(_f(score), 100.0))
    ordered = sorted(buckets, key=lambda b: (b["lo"], b["hi"]))
    for i, b in enumerate(ordered):
        lo, hi = int(b["lo"]), int(b["hi"])
        last = i == len(ordered) - 1
        in_bucket = lo <= clamped < hi or (last and lo <= clamped <= hi)
        if in_bucket and b.get("rate") is not None and b.get("n", 0) > 0:
            return float(b["rate"])
    return None


def build_calibration_report(
    labeled_rows: list[dict[str, Any]],
    *,
    bucket_width: int = 10,
    min_samples: int = 5,
) -> dict[str, Any]:
    """Full offline calibration report for labeled CSV/log rows."""
    ok = _ok_rows(labeled_rows)
    base_rate = round(
        sum(1 for r in ok if r["outcome"].get("pullback_occurred")) / len(ok), 4
    ) if ok else None

    score_specs = [
        ("v2_pullback_score", "pullback_occurred"),
        ("v1_pullback_prob", "pullback_occurred"),
        ("v2_reversal_risk_score", "reversal_before_pullback"),
    ]

    scores: dict[str, Any] = {}
    for field, outcome in score_specs:
        part = build_score_buckets(
            labeled_rows,
            field,
            outcome_field=outcome,
            bucket_width=bucket_width,
            min_samples=min_samples,
        )
        if part["labeled_count"] > 0:
            scores[field] = part

    reliable_buckets = sum(
        1 for s in scores.values() for b in s.get("buckets", []) if b.get("reliable")
    )
    calibrated = bool(ok) and len(ok) >= max(min_samples * 4, 20) and reliable_buckets >= 3

    v2_pull = scores.get("v2_pullback_score", {})
    lookup_example = None
    if v2_pull.get("buckets"):
        lookup_example = lookup_calibrated_probability(68.0, v2_pull["buckets"])

    return {
        "module": "pullback_v2_calibration",
        "milestone": 7,
        "row_count": len(labeled_rows),
        "labeled_count": len(ok),
        "pullback_base_rate": base_rate,
        "bucket_width": bucket_width,
        "min_samples": min_samples,
        "calibrated": calibrated,
        "calibrated_note": (
            "Offline report only — live EA scores remain raw until calibration artifact is applied."
            if calibrated
            else "Insufficient labeled samples for reliable calibration buckets."
        ),
        "scores": scores,
        "lookup_example": {
            "v2_pullback_score": 68.0,
            "empirical_pullback_rate": lookup_example,
        },
    }
