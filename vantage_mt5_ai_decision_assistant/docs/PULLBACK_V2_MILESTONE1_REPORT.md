# Pullback Probability Desk V2 — Milestone 1 Report

**Date:** 2026-08-12  
**Scope:** Milestone 1 only (structure, horizon metadata, independent scores)  
**V1 modified:** No (`VantagePullback.mqh` untouched)

---

## Delivered

Milestone 1 adds an experimental **Pullback Desk V2** module running in parallel with V1. V2 uses **independent 0–100 scores** (no `Normalize4()`), **separate BOS vs CHoCH semantics**, **reused extension formula**, and **documented pullback event definition + prediction horizon** as calibration metadata.

---

## Files created

| File | Purpose |
|------|---------|
| `MQL5/Include/VantageAI/VantagePullbackV2.mqh` | V2 engine (~750 lines) |
| `docs/PULLBACK_V2_IMPLEMENTATION_PLAN.md` | Full roadmap + reuse map |
| `docs/PULLBACK_V2_MILESTONE1_REPORT.md` | This report |
| `backend/tests/test_pullback_v2_status.py` | Backend passthrough tests |

## Files modified (additive)

| File | Change |
|------|--------|
| `MQL5/Experts/VantageMT5AIDecisionAssistant.mq5` | V2 include, inputs L2/L3, eval, heartbeat `"pullback_v2"` |
| `MQL5/Include/VantageAI/VantageDashboard.mqh` | Experimental HUD rows `tpbv0`–`tpbv4` |
| `backend/app/monitor_state.py` | `pullback_v2`, `pullback_v2_supported` |
| `backend/app/schemas.py` | `HeartbeatRequest.pullback_v2` |
| `backend/app/routers/api.py` | V2 fields in `/api/v1/pullback/status` |
| `backend/app/static/pullback.html` | Experimental V2 section |

---

## V1 behavior preserved

- `VantagePullback.mqh` — **no edits**
- Heartbeat key `"pullback"` unchanged
- V1 dashboard rows `tpb0`–`tpb4` unchanged
- V1 tests — all passing

---

## Pullback event definition (research / calibration metadata)

Live scoring does **not** use future bars. The definition is exposed in JSON for Milestone 6 outcome labeling.

**Bullish dominant:**

```text
Within N closed horizon-TF bars, future_low <= reference_close - threshold_atr * ATR(M15)
without protected bullish low broken first
```

**Bearish:** symmetric with `future_high`.

**Defaults (EA inputs):**

| Input | Default |
|-------|---------|
| `InpPbV2PullbackAtrThreshold` | 0.50 |
| `InpPbV2PredictionBars` | 6 |
| `InpPbV2HorizonTF` | M15 (~90 min) |

---

## Structure algorithm (V2)

Swing pivots: reuse V1-style **3/3 closed-bar fractals**.

**BOS (separate from CHoCH):**

| Bias | Condition |
|------|-----------|
| Bullish BOS | HH+HL sequence AND close > previous confirmed swing high `sh[1]` |
| Bearish BOS | LH+LL sequence AND close < previous confirmed swing low `sl[1]` |

**Protected structure:**

| Bias | Protected level |
|------|-----------------|
| Bullish | Protected low = most recent HL `sl[0]` |
| Bearish | Protected high = most recent LH `sh[0]` |

**CHoCH / MSS (M1):**

| Bias | Condition |
|------|-----------|
| Bearish CHoCH/MSS | Bullish sequence AND close < protected low |
| Bullish CHoCH/MSS | Bearish sequence AND close > protected high |

**Note:** MSS currently equals CHoCH trigger (displacement gate deferred to Milestone 2).

**Structure states:** `PbV2StructureState` enum per TF (Continuation, Pullback, CHoCH, Range, Unknown).

**Reversal hierarchy:**

| Level | Reversal risk contribution |
|-------|----------------------------|
| H1 CHoCH | +45 |
| M15 CHoCH | +30 |
| M5 CHoCH only | +12 |
| RSI divergence against trend | +10 |

---

## Extension formula (reused from V1)

Per TF:

```text
d20 = |close - EMA20| / ATR
d50 = |close - EMA50| / ATR
dbb = |close - BB_mid| / ATR
ext_raw = (d20×0.45 + d50×0.25 + dbb×0.30) × 28
if close outside BB: ext_raw += 12
extension = clamp(ext_raw, 0, 100)
```

Combined: `extension_score = 0.55×M15 + 0.45×M5`

---

## Independent scores (Milestone 1 experimental)

Scores are **heuristic / uncalibrated**. Display as **X/100**, not statistical probability.

### Pullback score

```text
pullback_score =
    0.40 × extension_score
  + 0.25 × rsi_rollover_score
  + 0.20 × bb_reclaim_score
  + 0.15 × ltf_pullback_score
```

### Immediate continuation score

```text
immediate_continuation_score =
    0.30 × trend_align_score
  + 0.25 × (100 - extension_score)
  + 0.20 × adx_continuation_score
  + 0.15 × bos_continuation_score
  + 0.10 × rsi_healthy_score
```

### Continuation after pullback score

```text
continuation_after_pullback_score =
    0.40 × trend_strength
  + 0.35 × protected_structure_intact_score
  + 0.25 × trend_align_score
```

### Reversal risk score

Additive HTF/M15/M5 CHoCH weights + divergence; clamp 0–100.

**Scores do NOT sum to 100** — intentional.

---

## Expected depth (M1 placeholder)

Heuristic from pullback score (full depth engine in Milestone 5):

| Bucket | ATR range |
|--------|-----------|
| SHALLOW | < 0.5 |
| MODERATE | 0.5–1.0 |
| DEEP | 1.0–1.75 |
| STRUCTURAL_FAILURE | > 1.75 |

---

## JSON schema (`pullback_v2`)

Key fields: `version`, `experimental`, `calibrated`, independent scores, `prediction_horizon`, `pullback_event_definition`, `market_structure`, `market_state`, reasons, explanation.

Heartbeat: `"pullback_v2": { ... }` alongside unchanged `"pullback"`.

---

## Dashboard

- **Chart HUD:** rows `tpbv0`–`tpbv4` when `InpPbV2ShowDash`
- **Web:** `/pullback` shows V2 section labeled **Experimental / Not historically calibrated**

---

## Tests

| Suite | Result |
|-------|--------|
| `test_pullback_status.py` (V1) | 5 passed |
| `test_pullback_v2_status.py` (V2) | 4 passed |
| **Total** | **9 passed** |

MQL5 compile: **not verified in CI** — requires MetaEditor recompile of `VantageMT5AIDecisionAssistant.mq5`.

---

## Known limitations (Milestone 1)

- No displacement score, entry location, premium/discount, liquidity, FVG, OB, POI ranking
- MSS identical to CHoCH trigger (no displacement gate)
- Expected depth is heuristic placeholder
- No historical CSV logging or outcome labeler yet
- No MQL5 unit tests (conceptual cases documented below)
- Scores uncalibrated — must not be read as true probabilities

---

## Conceptual test expectations (M1)

| Case | Expected V2 behavior |
|------|----------------------|
| A — Strong impulse, low extension | High immediate continuation, moderate/low pullback |
| B — Strong impulse, extreme extension | Bullish trend, high pullback, lower immediate continuation |
| F — Bullish H1/M15, bearish M5 CHoCH | M5 local pullback; low reversal risk unless M15/H1 CHoCH |
| G — M15 protected low broken | Reversal risk rises materially |
| H — Bullish deep premium | Not modeled until M2 (extension may partially proxy) |

---

## Deployment steps

1. Recompile `VantageMT5AIDecisionAssistant.mq5` in MetaEditor
2. Reload EA on chart; ensure `InpPullbackV2Enable = true`
3. Restart Python backend
4. Open `/pullback` — V2 section appears after heartbeat with `pullback_v2`

---

## Do not proceed to Milestone 2 until

- [ ] MetaEditor compile succeeds on your MT5 build
- [ ] Live heartbeat shows valid `pullback_v2` blob
- [ ] V1 and V2 outputs both visible for comparison

---

# CHATGPT REVIEW PACKAGE

```json
{
  "milestone": 1,
  "v1_modified": false,
  "v2_compiles": false,
  "tests_pass": true,
  "pullback_event_definition": "Within N closed horizon-TF bars, price retraces >= threshold_atr * M15 ATR against reference close without protected-structure invalidation first; bullish uses future_low, bearish uses future_high. Live eval exposes definition only — no future-bar features.",
  "prediction_horizon": "Default 6 M15 bars (~90 minutes); configurable via InpPbV2PredictionBars and InpPbV2HorizonTF",
  "bos_definition": "Bullish: HH+HL sequence and close > previous confirmed swing high sh[1]. Bearish: LH+LL and close < previous confirmed swing low sl[1]. BOS and CHoCH never set by the same rule.",
  "choch_definition": "Bullish CHoCH/MSS: bearish sequence and close > protected high (recent LH). Bearish CHoCH/MSS: bullish sequence and close < protected low (recent HL). MSS equals CHoCH in M1.",
  "extension_formula": "Per TF: (0.45*|c-EMA20| + 0.25*|c-EMA50| + 0.30*|c-BBmid|)/ATR*28 + outsideBB?12, clamp 0-100; combined 0.55*M15+0.45*M5",
  "pullback_score_formula": "0.40*extension + 0.25*rsi_rollover + 0.20*bb_reclaim + 0.15*ltf_pullback; clamp 0-100; independent",
  "immediate_continuation_formula": "0.30*trend_align + 0.25*(100-extension) + 0.20*adx_cont + 0.15*bos_cont + 0.10*rsi_healthy; clamp 0-100",
  "reversal_risk_formula": "H1 CHoCH +45, M15 CHoCH +30, M5 CHoCH +12, RSI div +10; clamp 0-100",
  "files_created": [
    "MQL5/Include/VantageAI/VantagePullbackV2.mqh",
    "docs/PULLBACK_V2_IMPLEMENTATION_PLAN.md",
    "docs/PULLBACK_V2_MILESTONE1_REPORT.md",
    "backend/tests/test_pullback_v2_status.py"
  ],
  "files_modified": [
    "MQL5/Experts/VantageMT5AIDecisionAssistant.mq5",
    "MQL5/Include/VantageAI/VantageDashboard.mqh",
    "backend/app/monitor_state.py",
    "backend/app/schemas.py",
    "backend/app/routers/api.py",
    "backend/app/static/pullback.html"
  ],
  "known_issues": [
    "MQL5 compile not verified in automated CI — requires MetaEditor",
    "MSS identical to CHoCH until Milestone 2 displacement gate",
    "Expected depth is heuristic placeholder",
    "No liquidity FVG OB premium discount POI engines yet",
    "Scores uncalibrated — labeled experimental in UI and JSON",
    "V2 reuses V1 indicator inputs (InpPb*) — intentional to avoid config drift"
  ],
  "questions_for_chatgpt": [
    "Is the M1 pullback_score weight split (40/25/20/15) reasonable before calibration data exists?",
    "Should protected_low for bullish BOS use sl[0] or the HL immediately before the BOS break bar?",
    "When should continuation_after_pullback_score be shown prominently vs immediate_continuation_score in UI?",
    "Is equating MSS to CHoCH acceptable for M1 or should MSS require displacement even at low sample cost?"
  ]
}
```
