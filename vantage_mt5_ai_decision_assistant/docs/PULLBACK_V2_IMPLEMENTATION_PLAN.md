# Pullback Probability Desk V2 — Implementation Plan

**Status:** Milestone 7 complete — full V2 roadmap delivered  
**Date:** 2026-08-12  
**Principle:** V1 remains unchanged; V2 runs in parallel as experimental advisory module.

---

## 1. Current architecture summary

| Layer | V1 component | Role |
|-------|--------------|------|
| MQL5 engine | `VantagePullback.mqh` | Sole scorer; `Normalize4()` four-way partition |
| EA | `VantageMT5AIDecisionAssistant.mq5` | Inputs groups I–L, `MaybeEvalPullback`, heartbeat `"pullback"` |
| HUD | `VantageDashboard.mqh` | Rows `tpb0`–`tpb4` |
| Backend | `monitor_state.py`, `api.py` | Passthrough only |
| UI | `pullback.html` | Polls `/api/v1/pullback/status` every 11s |

V1 audit conclusion: rule-based confluence score labeled as probability; no OB/FVG/liquidity/OTE/premium-discount; BOS and CHoCH set together in V1 swing heuristic.

---

## 2. V2 goals (full roadmap)

V2 separates semantic questions instead of forcing Pullback / Continuation / Consolidation / Reversal to sum to 100%.

| Output | Milestone |
|--------|-----------|
| Objective pullback event definition + horizon | **M1** |
| Independent scores (no `Normalize4`) | **M1** |
| Corrected BOS vs CHoCH vs MSS | **M1** |
| Extension score reuse | **M1** |
| Structure state enum | **M1** |
| Displacement score | **M2** |
| Improved RSI momentum state | **M2** |
| Entry location score | **M2** |
| Premium / discount | **M2** |
| Liquidity integration (`VantageLiquidityGrab.mqh`) | **M3** |
| FVG integration (`VantageGoldSMCZones` / `VantageLiquidityGrab`) | **M4** |
| OB integration | **M4** |
| POI ranking engine | **M4** |
| Expected pullback depth | **M5** |
| OTE | **M5** |
| Continuation-after-pullback refinement | **M5** |
| Historical CSV logging | **M6** |
| Outcome labeler (offline only) | **M6** |
| V1 vs V2 shadow comparison | **M6** |
| Calibration buckets report | **M7** |

---

## 3. Reusable project components

### 3.1 Reuse in Milestone 1 (adapt in-place)

| Source | Reuse |
|--------|-------|
| `VantagePullback.mqh` | Extension formula, `FillTf` indicator pattern, trend vote, closed-bar cache, `Clamp`, session note pattern |
| `VantageTypes.mqh` | `JsonEscape`, `DoubleToJson` |
| V1 EA inputs groups J | Shared EMA/RSI/ATR/BB/ADX/swing params (V2 reads same inputs to avoid drift) |

### 3.2 Reuse in later milestones (do not duplicate)

| Source | Future use |
|--------|------------|
| `VantageGoldSMCCore.mqh` | External/internal swings, body-clears-level BOS, CHoCH/MSS with displacement gate |
| `VantageGoldSMCZones.mqh` | FVG/OB detection, mitigation, breaker |
| `VantageLiquidityGrab.mqh` | BSL/SSL, equal highs/lows, sweep/MSS, session liquidity |
| `VantageSwingStrategy.mqh` | Swing range, `pullback_pct` metric |
| `VantageIct.mqh` | M5 FVG, liquidity pools |
| Gold SMC heartbeat | Premium/discount, OTE, dealing range (if symbol is gold) |

### 3.3 Explicitly NOT reused in M1

- V1 `Normalize4()` and four competing outcome shares
- V1 combined BOS+CHoCH swing rule (L221–222 in V1)
- Gold SMC validator (V2 runs on any chart symbol like V1)

---

## 4. New files (Milestone 1)

| File | Purpose |
|------|---------|
| `MQL5/Include/VantageAI/VantagePullbackV2.mqh` | V2 engine |
| `docs/PULLBACK_V2_IMPLEMENTATION_PLAN.md` | This document |
| `docs/PULLBACK_V2_MILESTONE1_REPORT.md` | M1 delivery report |
| `backend/tests/test_pullback_v2_status.py` | Backend passthrough tests |

## 5. Modified files (Milestone 1, additive only)

| File | Change |
|------|--------|
| `VantageMT5AIDecisionAssistant.mq5` | Include V2, inputs M–N, eval + heartbeat |
| `VantageDashboard.mqh` | Optional V2 HUD rows `tpbv0`–`tpbv4` |
| `monitor_state.py` | `pullback_v2`, `pullback_v2_supported` |
| `schemas.py` | `HeartbeatRequest.pullback_v2` |
| `api.py` | Include `pullback_v2` in status response |
| `pullback.html` | Experimental V2 section |

**V1 files NOT modified:** `VantagePullback.mqh`

---

## 6. Milestone 1 — objective pullback event

Research definition (for calibration tooling; **not** evaluated with future bars in live scoring):

**Bullish dominant trend:**

```text
pullback_occurred = TRUE when
  future_low <= reference_price - threshold_atr * ATR(M15)
  within prediction_bars closed M15 bars
  without structural bullish invalidation (protected low broken first)
```

**Bearish dominant trend:** symmetric with `future_high`.

**Defaults (configurable EA inputs):**

| Input | Default |
|-------|---------|
| `InpPbV2PullbackAtrThreshold` | 0.50 |
| `InpPbV2PredictionBars` | 6 |
| `InpPbV2HorizonTF` | M15 (~90 minutes) |

Live V2 exposes this definition in JSON as metadata only until Milestone 6 outcome labeler exists.

---

## 7. Milestone 1 — structure semantics (V2)

Separate flags (never set BOS and CHoCH together):

**Bullish continuation sequence (HH + HL):**

- `bullish_bos` = close > previous confirmed swing high (`sh[1]`)
- `protected_low` = most recent HL (`sl[0]` when HL confirmed)
- `bearish_choch` / `bearish_mss` = close < `protected_low` (MSS = CHoCH + displacement gate in M2; M1 treats MSS identical to CHoCH with flag)

**Bearish continuation sequence (LH + LL):**

- `bearish_bos` = close < previous confirmed swing low (`sl[1]`)
- `protected_high` = most recent LH (`sh[0]`)
- `bullish_choch` / `bullish_mss` = close > `protected_high`

**Hierarchy for reversal risk:**

| Event | TF | M1 reversal contribution |
|-------|-----|--------------------------|
| HTF CHoCH/MSS | H1 | High |
| MTF CHoCH/MSS | M15 | Medium |
| LTF shift only | M5 | Low (local pullback) |

Swing detection: reuse V1 3/3 pivot scan on closed bars.

---

## 8. Milestone 1 — independent scores

No `Normalize4()`. Scores are 0–100, **not** required to sum to 100.

| Score | M1 formula (experimental) |
|-------|---------------------------|
| `extension_score` | Same as V1: `0.55×M15.ext + 0.45×M5.ext` |
| `pullback_score` | `0.40×ext + 0.25×rsi_rollover + 0.20×bb_reclaim + 0.15×ltf_pullback` |
| `immediate_continuation_score` | `0.30×align + 0.25×(100-ext) + 0.20×adx + 0.15×bos + 0.10×rsi_healthy` |
| `continuation_after_pullback_score` | `0.40×htf_strength + 0.35×protected_intact + 0.25×align` |
| `reversal_risk_score` | HTF/M15/M5 CHoCH weights + divergence; clamp 0–100 |

All weights documented in `VantagePullbackV2.mqh` and Milestone 1 report.

---

## 9. Heartbeat / API schema (M1)

New key: `"pullback_v2"` (V1 `"pullback"` unchanged).

```json
{
  "version": "pullback_v2",
  "experimental": true,
  "calibrated": false,
  "valid": true,
  "dominant_direction": 1,
  "dominant_trend": "Moderate Bullish",
  "extension_score": 78,
  "pullback_score": 68,
  "immediate_continuation_score": 51,
  "continuation_after_pullback_score": 72,
  "reversal_risk_score": 12,
  "trend_strength": 64,
  "prediction_horizon": { "timeframe": "M15", "bars": 6, "minutes": 90 },
  "pullback_event_definition": { "threshold_atr": 0.5, "description": "..." },
  "market_structure": { ... },
  "market_state": "TREND STRONG — WAIT FOR PULLBACK",
  "explanation": "...",
  "reasons_positive": "...",
  "reasons_negative": "..."
}
```

---

## 10. Testing strategy

| Layer | M1 tests |
|-------|----------|
| MQL5 compile | MetaEditor / CI if available — manual verify |
| Backend | `test_pullback_v2_status.py` passthrough + V1 regression unchanged |
| Conceptual | Cases A/B/F/G documented in Milestone 1 report (deterministic unit tests in MQL5 deferred) |

---

## 11. Risk controls

- Advisory-only invariant preserved
- Closed-bar `CopyRates(..., shift=1)` only
- M5 eval gate + same-bar cache (matches V1)
- No future-bar features in live scoring
- JSON fields additive — old consumers ignore `pullback_v2`

---

## 12. Milestone 1 exit criteria

- [ ] `VantagePullbackV2.mqh` compiles when included from EA
- [ ] V1 behavior and JSON unchanged
- [ ] V2 produces independent scores + structure flags + horizon metadata
- [ ] Heartbeat includes `pullback_v2` when enabled
- [ ] Web desk shows experimental V2 section
- [ ] Backend tests pass
- [ ] Milestone 1 report with CHATGPT REVIEW PACKAGE JSON

**Milestones 1–7 complete.** Validate CSV → label → calibrate workflow on demo data before treating scores as research-grade probabilities.
