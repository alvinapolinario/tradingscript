# Pullback Probability Desk V2 — Milestone 7 Report

**Date:** 2026-08-12  
**Scope:** Offline calibration bucket report (score deciles → empirical outcome rates)  
**V1 modified:** No

---

## Delivered

Milestone 7 completes the V2 calibration toolchain started in M6. Labeled CSV rows are binned by score; each bucket reports sample count and empirical pullback (or reversal) rate. Shadow analyze can reuse bucket-derived thresholds instead of fixed V1 50% / V2 55.

1. **Calibration bucket engine** (`calibration_buckets.py`) — decile bins, Brier/ECE, recommended threshold, lookup helper  
2. **API** — `POST /api/v1/pullback/v2/calibrate`; `shadow/analyze` accepts `include_calibration: true`  
3. **Shadow metrics** — optional data-driven thresholds from bucket F1 scan  
4. **MQL5 metadata** — milestone 7, `calibration.bucket_report: offline_python_only`  
5. **UI** — M7 banner + offline calibration API hints on `/pullback`  

Live EA JSON still sets `"calibrated": false` — calibration is offline-only until an artifact is explicitly applied in a future build.

---

## Files created / modified

| File | Change |
|------|---------|
| `backend/app/analysis/pullback_v2/calibration_buckets.py` | **New** bucket report |
| `backend/app/analysis/pullback_v2/shadow_compare.py` | Configurable thresholds |
| `backend/app/routers/api.py` | `/calibrate` + extended `/shadow/analyze` |
| `backend/tests/test_pullback_v2_m7.py` | **New** M7 tests |
| `backend/tests/test_pullback_v2_status.py` | Milestone 7 + `bucket_report` |
| `MQL5/Include/VantageAI/VantagePullbackV2.mqh` | M7 JSON metadata |
| `backend/app/static/pullback.html` | M7 banner + API hints |

---

## Bucket report shape

```json
POST /api/v1/pullback/v2/calibrate
{
  "rows": [ /* CSV rows */ ],
  "candles_m15": [ /* aligned future bars */ ],
  "bucket_width": 10,
  "min_samples": 5
}
```

Response highlights:

| Field | Meaning |
|-------|---------|
| `scores.v2_pullback_score.buckets[]` | Decile bins with `n`, `occurred`, `rate` |
| `scores.v1_pullback_prob.buckets[]` | V1 normalized share vs actual pullback |
| `scores.v2_reversal_risk_score.buckets[]` | Reversal-risk score vs `reversal_before_pullback` |
| `recommended_threshold` | F1-max threshold per score column |
| `brier_score` / `ece` | Calibration quality metrics |
| `calibrated` | `true` when enough reliable buckets exist (offline report flag) |

---

## Lookup helper

`lookup_calibrated_probability(score, buckets)` maps a raw V2 pullback score to the empirical rate in its decile — for research dashboards, not live EA scoring.

---

## JSON additions (heartbeat metadata)

```json
"milestone": 7,
"calibrated": false,
"calibration": {
  "csv_logging_enabled": true,
  "outcome_labeler": "offline_python_only",
  "shadow_compare": "v1_vs_v2",
  "bucket_report": "offline_python_only"
}
```

---

## Tests

| Suite | Result |
|-------|--------|
| V1 + V2 status + M6 + M7 | **21 passed** (expected after run) |

---

## Known limitations (post-M7)

- Calibration artifact is not auto-loaded into MT5 — export CSV, run `/calibrate`, review buckets manually  
- Live heartbeat scores remain raw (`calibrated: false`)  
- Minimum sample guidance: ≥20 labeled rows, ≥3 reliable deciles  
- No broker candle fetch in API — caller supplies aligned M15 array  

---

## Roadmap status

**Milestones 1–7 complete.** Full V2 experimental architecture delivered per implementation plan.

---

# CHATGPT REVIEW PACKAGE

```json
{
  "milestone": 7,
  "v1_modified": false,
  "v2_compiles": false,
  "tests_pass": true,
  "calibration_mode": "offline_bucket_report_only",
  "live_calibrated_flag": false,
  "endpoints": [
    "POST /api/v1/pullback/v2/calibrate",
    "POST /api/v1/pullback/v2/shadow/analyze?include_calibration=true"
  ],
  "bucket_scores": [
    "v2_pullback_score",
    "v1_pullback_prob",
    "v2_reversal_risk_score"
  ],
  "files_created": [
    "backend/app/analysis/pullback_v2/calibration_buckets.py",
    "backend/tests/test_pullback_v2_m7.py",
    "docs/PULLBACK_V2_MILESTONE7_REPORT.md"
  ]
}
```
