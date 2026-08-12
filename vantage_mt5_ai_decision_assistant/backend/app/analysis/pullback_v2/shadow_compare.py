"""V1 vs V2 shadow comparison — live and offline aggregate metrics."""
from __future__ import annotations

from typing import Any


def _f(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _v1_dominant_outcome(v1: dict[str, Any]) -> str:
    probs = {
        "pullback": _f(v1.get("pullback_probability")),
        "continuation": _f(v1.get("continuation_probability")),
        "consolidation": _f(v1.get("consolidation_probability")),
        "reversal": _f(v1.get("reversal_probability")),
    }
    return max(probs, key=probs.get)


def _v2_posture(v2: dict[str, Any]) -> str:
    pb = _f(v2.get("pullback_score"))
    imm = _f(v2.get("immediate_continuation_score"))
    rev = _f(v2.get("reversal_risk_score"))
    if rev >= 55:
        return "reversal_risk"
    if pb >= 55 and pb >= imm:
        return "pullback"
    if imm >= 55 and imm > pb:
        return "continuation"
    if _f(v2.get("continuation_after_pullback_score")) >= 70:
        return "resumption"
    return "neutral"


def live_shadow_compare(v1: dict[str, Any] | None, v2: dict[str, Any] | None) -> dict[str, Any]:
    """Compare current heartbeat V1 normalized shares vs V2 independent scores."""
    if not v1 or not v2:
        return {
            "module": "pullback_v2_shadow",
            "milestone": 6,
            "available": False,
            "reason": "Requires both pullback and pullback_v2 heartbeat blobs.",
        }

    v1_out = _v1_dominant_outcome(v1)
    v2_out = _v2_posture(v2)
    aligned = (
        (v1_out == "pullback" and v2_out in {"pullback", "resumption"})
        or (v1_out == "continuation" and v2_out in {"continuation", "neutral"})
        or (v1_out == "reversal" and v2_out == "reversal_risk")
        or (v1_out == "consolidation" and v2_out == "neutral")
    )

    gap_notes: list[str] = []
    if v1_out == "pullback" and v2_out == "continuation":
        gap_notes.append("V1 favors pullback share; V2 immediate continuation is higher.")
    if v1_out == "continuation" and v2_out == "pullback":
        gap_notes.append("V1 favors continuation share; V2 pullback score is elevated.")
    if _f(v1.get("pullback_probability")) >= 55 and _f(v2.get("pullback_score")) < 45:
        gap_notes.append("V1 pullback probability high; V2 pullback score low.")
    if _f(v2.get("reversal_risk_score")) >= 45 and _f(v1.get("reversal_probability")) < 20:
        gap_notes.append("V2 reversal risk elevated vs low V1 reversal share.")

    return {
        "module": "pullback_v2_shadow",
        "milestone": 6,
        "available": True,
        "aligned": aligned,
        "v1_dominant_outcome": v1_out,
        "v2_posture": v2_out,
        "v1_probs": {
            "pullback": _f(v1.get("pullback_probability")),
            "continuation": _f(v1.get("continuation_probability")),
            "consolidation": _f(v1.get("consolidation_probability")),
            "reversal": _f(v1.get("reversal_probability")),
        },
        "v2_scores": {
            "pullback": _f(v2.get("pullback_score")),
            "immediate_continuation": _f(v2.get("immediate_continuation_score")),
            "continuation_after_pullback": _f(v2.get("continuation_after_pullback_score")),
            "reversal_risk": _f(v2.get("reversal_risk_score")),
        },
        "gap_notes": gap_notes,
        "csv_logging_enabled": bool((v2.get("calibration") or {}).get("csv_logging_enabled")),
    }


def aggregate_shadow_metrics(
    labeled_rows: list[dict[str, Any]],
    *,
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Offline precision-style summary for labeled CSV rows with V1/V2 shadow columns."""
    thr = thresholds or {}
    v1_thr = float(thr.get("v1_pullback_prob", 50.0))
    v2_thr = float(thr.get("v2_pullback_score", 55.0))
    ok = [r for r in labeled_rows if r.get("outcome", {}).get("label_status") == "ok"]
    if not ok:
        return {"module": "pullback_v2_shadow", "milestone": 6, "labeled_count": 0}

    v1_hits = v1_total = v2_hits = v2_total = agree = 0
    for row in ok:
        actual = bool(row["outcome"].get("pullback_occurred"))
        v1_pred = _f(row.get("v1_pullback_prob")) >= v1_thr
        v2_pred = _f(row.get("v2_pullback_score")) >= v2_thr
        if row.get("v1_pullback_prob") is not None:
            v1_total += 1
            if v1_pred == actual:
                v1_hits += 1
        if row.get("v2_pullback_score") is not None:
            v2_total += 1
            if v2_pred == actual:
                v2_hits += 1
        if row.get("v1_pullback_prob") is not None and row.get("v2_pullback_score") is not None:
            if v1_pred == v2_pred:
                agree += 1

    pair_total = min(v1_total, v2_total)
    return {
        "module": "pullback_v2_shadow",
        "milestone": 6,
        "labeled_count": len(ok),
        "pullback_base_rate": round(
            sum(1 for r in ok if r["outcome"].get("pullback_occurred")) / len(ok), 4
        ),
        "v1_pullback_precision": round(v1_hits / v1_total, 4) if v1_total else None,
        "v2_pullback_precision": round(v2_hits / v2_total, 4) if v2_total else None,
        "v1_v2_prediction_agreement": round(agree / pair_total, 4) if pair_total else None,
        "thresholds": {"v1_pullback_prob": v1_thr, "v2_pullback_score": v2_thr},
    }
