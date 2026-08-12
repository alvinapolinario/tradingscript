# Pullback Probability Desk V2 — Milestone 2 Report

**Date:** 2026-08-12  
**Scope:** Displacement, RSI momentum state, premium/discount, entry location  
**V1 modified:** No

---

## Delivered

Milestone 2 extends V2 with four new analytical layers that were explicitly deferred from M1:

1. **Displacement score** (0–100) with exposed component breakdown  
2. **RSI momentum state machine** (NEUTRAL / CONTINUATION / STRONG / EXTENDED / ROLLOVER / DIVERGENCE)  
3. **Premium / discount** from M15 structural dealing range  
4. **Entry location score** (0–100) — separate from trend strength  
5. **MSS displacement gate** — MSS requires CHoCH + displacement ≥ threshold  

Pullback score weights updated for M2. Market states now consider entry location and displacement exhaustion.

---

## Files modified

| File | Change |
|------|--------|
| `MQL5/Include/VantageAI/VantagePullbackV2.mqh` | M2 engines, scoring, JSON |
| `MQL5/Experts/VantageMT5AIDecisionAssistant.mq5` | Inputs L4 (MSS threshold, PD bands) |
| `MQL5/Include/VantageAI/VantageDashboard.mqh` | HUD shows Disp, Entry, PD, Momentum |
| `backend/app/static/pullback.html` | M2 KPI rows + dealing range |
| `backend/tests/test_pullback_v2_status.py` | M2 field assertions |
| `docs/PULLBACK_V2_IMPLEMENTATION_PLAN.md` | Status updated |

---

## Displacement score

**Formula (experimental weights):**

```text
displacement_score =
    0.25 × body_strength
  + 0.20 × range_expansion
  + 0.15 × directional_persistence
  + 0.10 × close_quality
  + 0.10 × ema_acceleration
  + 0.10 × bos_component
  + 0.10 × fvg_component
```

| Component | Calculation |
|-----------|-------------|
| body | `\|close-open\| / ATR` normalized to 0–100 |
| range | `(high-low) / ATR` normalized |
| persistence | consecutive M5 bars in trend direction (max 4 → 100) |
| close_quality | CLV toward trend side of candle |
| ema_accel | EMA20 slope / ATR |
| bos | 100 if M15 BOS in trend; 60 if M5 only |
| fvg | 100 if M15 ICT gap in trend; 75 if M5 only |

All components exported in JSON under `"displacement": { ... }`.

---

## RSI momentum state

| State | Bullish condition (mirror for bear) |
|-------|-------------------------------------|
| ROLLOVER | RSI ≥ 68 and falling |
| EXTENDED | RSI ≥ 68 and rising |
| CONTINUATION | RSI 50–68 and rising |
| STRONG | RSI > 50 and rising (below extended band) |
| DIVERGENCE | RSI divergence detected |
| NEUTRAL | default |

Feeds:
- `pullback_score` via `rollover_score` (20% weight)  
- `immediate_continuation_score` via `continuation_score` (15% weight)

---

## Premium / discount

**Dealing range (M15, symbol-agnostic):**

| Trend | range_low | range_high |
|-------|-----------|------------|
| Bullish | protected_low or swing_low | swing_high or current close |
| Bearish | swing_low or current close | protected_high or swing_high |

```text
position_pct = (close - range_low) / (range_high - range_low) × 100
```

| Location | Bullish pullback pressure |
|----------|---------------------------|
| Deep Discount | 15 |
| Discount | 30 |
| Equilibrium | 45 |
| Premium | 70 |
| Deep Premium | 85 |

Deep premium **raises pullback pressure** but does **not** auto-flip trend bias.

Configurable: `InpPbV2DeepDiscountPct` (0.25), `InpPbV2DeepPremiumPct` (0.75).

---

## Entry location score

```text
entry_location_score =
    0.40 × pd_favorability
  + 0.30 × (100 - extension_score)
  + 0.20 × protected_structure_intact
  + 0.10 × (100 - reversal_risk)
```

| Score | Label |
|-------|-------|
| 80–100 | Excellent |
| 65–79 | Good |
| 50–64 | Acceptable |
| 35–49 | Weak |
| 0–34 | Poor / chase |

New market states:
- `NO TRADE — POOR ENTRY LOCATION` (entry ≤ 34, trend ≥ 60)  
- `IMPULSE STRONG — WAIT FOR RETRACEMENT` (disp ≥ 70, ext ≥ 65, pb ≥ 55)

---

## MSS displacement gate

**M1:** MSS = CHoCH always  
**M2:** MSS only when CHoCH **and** `displacement_score ≥ InpPbV2MinMssDisplacement` (default 55)

CHoCH can exist without MSS if displacement is weak (local structure shift).

---

## Updated pullback score (M2)

```text
pullback_score =
    0.20 × extension_score
  + 0.20 × momentum_rollover_score
  + 0.12 × premium_discount_pressure
  + 0.08 × rejection_score
  + 0.12 × ltf_structure_shift
  + 0.12 × bb_reclaim
  + 0.16 × displacement_exhaustion
```

`displacement_exhaustion` peaks when both displacement and extension are high.

---

## JSON additions (backward compatible)

New top-level fields: `milestone`, `displacement_score`, `entry_location_score`, `momentum_state`, `rsi_level`, `rsi_slope`, `premium_discount_location`, `range_position_pct`

New objects: `displacement`, `momentum`, `dealing_range`

---

## Tests

| Suite | Result |
|-------|--------|
| V1 + V2 pullback tests | **10 passed** |

MQL5 compile: not verified in CI — recompile EA in MetaEditor.

---

## Known limitations (post-M2)

- FVG detection is simplified 3-candle gap (not full Gold SMC FVG engine)  
- Dealing range uses M15 structure only (no H4 external range yet)  
- Liquidity integration deferred to Milestone 3  
- POI ranking deferred to Milestone 4  
- Scores remain uncalibrated  

---

## Do not start Milestone 3 until

- [ ] MetaEditor compile succeeds  
- [ ] Live heartbeat shows M2 JSON fields  
- [ ] Spot-check: strong trend + deep premium → low entry_location, elevated pullback_score  

---

# CHATGPT REVIEW PACKAGE

```json
{
  "milestone": 2,
  "v1_modified": false,
  "v2_compiles": false,
  "tests_pass": true,
  "displacement_formula": "0.25*body + 0.20*range + 0.15*persistence + 0.10*close_quality + 0.10*ema_accel + 0.10*bos + 0.10*fvg",
  "momentum_states": ["NEUTRAL", "CONTINUATION", "STRONG", "EXTENDED", "ROLLOVER", "DIVERGENCE"],
  "premium_discount_formula": "M15 structural range from protected_low/high to swing high/low; position_pct = (close-low)/(high-low)*100",
  "entry_location_formula": "0.40*pd_favorability + 0.30*(100-extension) + 0.20*protected_intact + 0.10*(100-reversal_risk)",
  "pullback_score_formula_m2": "0.20*ext + 0.20*mom_rollover + 0.12*pd_pressure + 0.08*reject + 0.12*ltf + 0.12*bb + 0.16*disp_exhaust",
  "mss_gate": "MSS requires CHoCH and displacement_score >= InpPbV2MinMssDisplacement (default 55)",
  "files_modified": [
    "MQL5/Include/VantageAI/VantagePullbackV2.mqh",
    "MQL5/Experts/VantageMT5AIDecisionAssistant.mq5",
    "MQL5/Include/VantageAI/VantageDashboard.mqh",
    "backend/app/static/pullback.html",
    "backend/tests/test_pullback_v2_status.py"
  ],
  "known_issues": [
    "Simplified FVG gap detection only",
    "MQL5 compile not verified in automated CI",
    "Dealing range M15-only; no multi-TF external range yet",
    "Scores uncalibrated"
  ],
  "questions_for_chatgpt": [
    "Is 55 the right default MSS displacement threshold for XAUUSD M15?",
    "Should displacement_exhaustion weight (16%) dominate pullback_score more than extension (20%)?",
    "Is M15 protected-low to swing-high sufficient for FX pairs dealing range?",
    "Should entry_location_score block continuation states more aggressively when <= 34?"
  ]
}
```
