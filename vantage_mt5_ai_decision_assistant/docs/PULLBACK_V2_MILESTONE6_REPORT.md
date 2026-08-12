# Pullback Probability Desk V2 — Milestone 6 Report

**Date:** 2026-08-12  
**Scope:** Historical CSV logging, offline outcome labeler, V1 vs V2 shadow comparison  
**V1 modified:** No

---

## Delivered

Milestone 6 adds the calibration toolchain promised since M1: log snapshots to CSV, label outcomes offline with future bars only, and compare V1 normalized probabilities against V2 independent scores.

1. **CSV historical logger** (`VantagePullbackV2Logger.mqh`) — one row per closed M5 eval  
2. **V1 shadow columns** — optional V1 probability shares in the same CSV row  
3. **Offline outcome labeler** (Python) — applies M1 pullback event definition to logged rows + future M15 candles  
4. **Shadow comparison** — live heartbeat compare + offline precision/agreement metrics  
5. **API + UI** — `/api/v1/pullback/v2/shadow`, `/label`, `/shadow/analyze`; web desk shadow panel  

---

## Files created / modified

| File | Change |
|------|--------|
| `MQL5/Include/VantageAI/VantagePullbackV2Logger.mqh` | **New** CSV logger |
| `MQL5/Include/VantageAI/VantagePullbackV2.mqh` | `reference_close`, `atr_m15`, `calibration` JSON, milestone 6 |
| `MQL5/Experts/VantageMT5AIDecisionAssistant.mq5` | L8 inputs, logger init/write/release |
| `backend/app/analysis/pullback_v2/outcome_labeler.py` | **New** offline labeler |
| `backend/app/analysis/pullback_v2/shadow_compare.py` | **New** live + aggregate shadow |
| `backend/app/routers/api.py` | Shadow + label endpoints |
| `backend/app/static/pullback.html` | Live shadow panel |
| `backend/tests/test_pullback_v2_m6.py` | **New** M6 tests |
| `backend/tests/test_pullback_v2_status.py` | Milestone 6 + calibration fields |

---

## CSV format

**Path:** `MQL5/Files/{prefix}_{symbol}.csv` (default `pullback_v2_shadow_XAUUSD.csv`)

**Columns:** eval_time, symbol, dom_dir, ref_close, atr_m15, protected_low/high, horizon_tf, horizon_bars, threshold_atr, v1_* probs, v2_* scores, expected_depth, market_state, depth_source

**When:** once per new closed M5 bar after successful V2 eval (`InpPbV2CsvLogEnable`, default true)

---

## Outcome labeler (offline only)

```text
POST /api/v1/pullback/v2/label
{
  "rows": [ { CSV row fields... } ],
  "candles_m15": [ {open, high, low, close}, ... ],
  "horizon_bars": 6
}
```

**Bullish pullback occurred** when future low ≤ ref_close − threshold×ATR before protected_low close break.

Returns per-row `outcome`: `pullback_occurred`, `reversal_before_pullback`, `bars_to_pullback`, `threshold_price`.

Live scoring never uses future bars — labeler is for backtest/CSV calibration only.

---

## Shadow comparison

### Live (`GET /api/v1/pullback/v2/shadow`)

Compares:
- V1 dominant outcome (max of four normalized shares)
- V2 posture (pullback / continuation / reversal_risk / resumption / neutral)
- Alignment flag + gap notes

### Offline (`POST /api/v1/pullback/v2/shadow/analyze`)

After labeling, reports:
- `v1_pullback_precision` (V1 prob ≥ 50 vs actual)
- `v2_pullback_precision` (V2 score ≥ 55 vs actual)
- `v1_v2_prediction_agreement`
- `pullback_base_rate`

---

## EA inputs (group L8)

| Input | Default |
|-------|---------|
| `InpPbV2CsvLogEnable` | true |
| `InpPbV2CsvLogV1Shadow` | true |
| `InpPbV2CsvFilePrefix` | `pullback_v2_shadow` |

---

## JSON additions

```json
"reference_close": 3335.0,
"atr_m15": 4.2,
"calibration": {
  "csv_logging_enabled": true,
  "outcome_labeler": "offline_python_only",
  "shadow_compare": "v1_vs_v2"
},
"milestone": 6
```

---

## Tests

| Suite | Result |
|-------|--------|
| V1 + V2 status + M6 labeler/shadow | **15 passed** |

---

## Known limitations (post-M6)

- CSV rows are not auto-uploaded to backend — copy from `MQL5/Files/` for offline analyze  
- Labeler expects caller-supplied aligned M15 candle array (no broker fetch in API yet)  
- Shadow precision uses fixed thresholds (V1 50%, V2 55) — Milestone 7 calibration buckets  
- Scores remain uncalibrated until M7 bucket report  

---

## Do not start Milestone 7 until

- [ ] MetaEditor compile succeeds  
- [ ] CSV file grows on live/demo EA (one row per M5 bar)  
- [ ] Offline label + shadow/analyze tested on a real CSV export  
- [ ] Live shadow panel shows alignment on `/pullback`  

---

# CHATGPT REVIEW PACKAGE

```json
{
  "milestone": 6,
  "v1_modified": false,
  "v2_compiles": false,
  "tests_pass": true,
  "csv_logger": "VantagePullbackV2Logger.mqh",
  "csv_default_prefix": "pullback_v2_shadow",
  "outcome_labeler": "offline_python_only — POST /api/v1/pullback/v2/label",
  "shadow_endpoints": [
    "GET /api/v1/pullback/v2/shadow",
    "POST /api/v1/pullback/v2/shadow/analyze"
  ],
  "live_scoring_uses_future_bars": false,
  "files_created": [
    "MQL5/Include/VantageAI/VantagePullbackV2Logger.mqh",
    "backend/app/analysis/pullback_v2/outcome_labeler.py",
    "backend/app/analysis/pullback_v2/shadow_compare.py",
    "backend/tests/test_pullback_v2_m6.py"
  ]
}
```
