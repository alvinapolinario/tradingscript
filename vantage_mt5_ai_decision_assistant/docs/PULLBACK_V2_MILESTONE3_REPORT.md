# Pullback Probability Desk V2 — Milestone 3 Report

**Date:** 2026-08-12  
**Scope:** Liquidity integration (`VantageLiquidityGrab` + structural fallback)  
**V1 modified:** No

---

## Delivered

Milestone 3 adds a liquidity layer to V2 that answers: *where is the nearest liquidity draw, what state is price in relative to it, and how does that affect pullback vs continuation pressure?*

1. **Liquidity state machine** — NONE / APPROACHING / TOUCHED / SWEPT / REJECTED / ACCEPTED_BEYOND  
2. **Primary source:** `VantageLiquidityGrab` module when enabled and valid  
3. **Fallback:** M15 swing high/low (BSL/SSL proxy) + M5 closed-bar sweep logic  
4. **Score integration** — liquidity term in `pullback_score` and `immediate_continuation_score`  
5. **Reversal nuance** — +12 reversal risk when liquidity is rejected against dominant trend  
6. **New market states** — liquidity sweep / rejection overlays  
7. **UI + tests** — web desk KPIs, backend passthrough assertions  

---

## Files modified

| File | Change |
|------|--------|
| `MQL5/Include/VantageAI/VantagePullbackV2.mqh` | Liquidity engines, scoring, JSON `"milestone": 3` |
| `MQL5/Experts/VantageMT5AIDecisionAssistant.mq5` | Inputs L5; LG eval before V2; optional LG pointer |
| `MQL5/Include/VantageAI/VantageDashboard.mqh` | HUD row shows draw / state / distance |
| `backend/app/static/pullback.html` | M3 liquidity KPIs + target line |
| `backend/tests/test_pullback_v2_status.py` | M3 `liquidity` object assertions |
| `docs/PULLBACK_V2_IMPLEMENTATION_PLAN.md` | Status updated |

**V1 files NOT modified:** `VantagePullback.mqh`

---

## Liquidity resolution

```text
ResolveLiquidity(dom, m15, m5, lg):
  if prefer_liquidity_grab AND lg.valid AND lg.analysis_active AND lg.liquidity_level_price > 0:
    return MapLiquidityGrab(...)
  else:
    return CalcLiquidityFallback(...)
```

### MapLiquidityGrab

Maps `ENUM_LG_STATE` / `ENUM_LG_STATUS` from `VantageLiquidityGrabResult` into PbV2 states:

| LG signal | PbV2 state |
|-----------|------------|
| APPROACHING / LG_STATUS_APPROACH | APPROACHING |
| LG_STATUS_TEST | TOUCHED |
| SWEPT / SWEEP_UNCONFIRMED / FAILED | SWEPT |
| REJECTED / DISPLACEMENT / MSS / CONFIRMED (non-breakout) | REJECTED |
| BREAKOUT / GENUINE_BREAKOUT | ACCEPTED_BEYOND |

Counter-trend grab against dominant direction with rejection boosts pullback pressure (≥88) and caps continuation (≤22). Accepted beyond with trend boosts continuation (≥82).

### CalcLiquidityFallback

| Dominant | Draw | Target |
|----------|------|--------|
| Bullish | `buy_side` | M15 swing high, else BB upper |
| Bearish | `sell_side` | M15 swing low, else BB lower |

M5 closed-bar classification (tolerance 0.08× M15 ATR):

- Wick through level + close back → **REJECTED**  
- Close beyond level → **ACCEPTED_BEYOND**  
- Wick through only → **SWEPT**  
- Within `liquidity_touch_atr` → **TOUCHED**  
- Distance ≤ `liquidity_approach_atr` → **APPROACHING**  

---

## State-dependent score contributions

`ScoreLiquidityState(dom, state)` → `pullback_pressure`, `continuation_boost` (0–100 scale inputs):

| State | Pullback pressure | Continuation boost |
|-------|-------------------|--------------------|
| APPROACHING | 25 | 70 |
| TOUCHED | 40 | 60 |
| SWEPT | 55 | 45 |
| REJECTED | 85 | 25 |
| ACCEPTED_BEYOND | 20 | 85 |
| NONE / default | 35 | 40 |

---

## Updated score weights (M3)

**Pullback score:**

```text
pullback_score =
    0.18 × extension
  + 0.18 × momentum_rollover
  + 0.10 × pd_pressure
  + 0.08 × rejection
  + 0.10 × ltf_pullback
  + 0.10 × bb_reclaim
  + 0.14 × displacement_exhaustion
  + 0.12 × liquidity_pressure
```

**Immediate continuation:**

```text
immediate_continuation_score =
    0.22 × trend_align
  + 0.18 × (100 - extension)
  + 0.14 × adx
  + 0.14 × bos
  + 0.14 × momentum_continuation
  + 0.08 × displacement
  + 0.10 × liquidity_continuation
```

**Reversal risk:** +12 when `liquidity_state == rejected` and draw aligns with dominant trend (BSL rejected in bull trend, SSL rejected in bear trend).

---

## New market states

Inserted early in `MapStateV2()` priority:

| Condition | State label |
|-----------|-------------|
| `liquidity_state == swept` AND `immediate_continuation < 50` | LIQUIDITY SWEEP — WAIT FOR CONFIRMATION |
| `liquidity_state == rejected` AND `pullback_score >= 55` | LIQUIDITY REJECTION — PULLBACK PRESSURE |

---

## EA inputs (group L5)

| Input | Default | Purpose |
|-------|---------|---------|
| `InpPbV2UseLiquidityGrab` | true | Prefer LG module when valid |
| `InpPbV2LiqApproachAtr` | 0.60 | Fallback approaching band |
| `InpPbV2LiqTouchAtr` | 0.15 | Fallback touch band |

**Eval order:** `MaybeEvalLiquidityGrab` runs before `MaybeEvalPullbackV2` on init, timer, and tick paths so `g_liqgrabsnap` is fresh when V2 evaluates.

---

## JSON additions (backward compatible)

New top-level fields: `liquidity_draw`, `liquidity_state`, `liquidity_distance_atr`, `liquidity_from_grab_module`

New object:

```json
"liquidity": {
  "draw": "buy_side",
  "state": "approaching",
  "target_price": 3360.0,
  "target_label": "PDH",
  "distance_atr": 0.32,
  "from_liquidity_grab": true
}
```

`"milestone": 3`

---

## Conceptual cases (spot-check guide)

| Case | Setup | Expected V2 behavior |
|------|-------|----------------------|
| C — BSL approaching | Bull trend, price within 0.6 ATR of buy-side level | `approaching`, high continuation boost, elevated immediate_continuation |
| D — BSL swept, unconfirmed | Wick through swing high, close back inside | `swept`, LIQUIDITY SWEEP state if continuation < 50 |
| E — BSL swept + rejection | Wick through + bearish close back below level | `rejected`, LIQUIDITY REJECTION state, pullback_score elevated, reversal_risk +12 |
| F — BSL accepted beyond | Close holds above swept high | `accepted_beyond`, continuation favored, pullback pressure low |

---

## Tests

| Suite | Result |
|-------|--------|
| V1 + V2 pullback tests | **10 passed** |

MQL5 compile: not verified in CI — recompile EA in MetaEditor.

---

## Known limitations (post-M3)

- Fallback liquidity uses M15 swing proxy only (no session PDH/PDL in fallback path)  
- LG module limited to supported symbols (XAUUSD/EURUSD/USDJPY); fallback covers others  
- FVG/OB POI ranking still deferred to Milestone 4  
- Expected depth remains heuristic placeholder until M5  
- Scores remain uncalibrated  

---

## Do not start Milestone 4 until

- [ ] MetaEditor compile succeeds  
- [ ] Live heartbeat shows M3 `liquidity` JSON  
- [ ] Spot-check: BSL rejection in bull trend → `LIQUIDITY REJECTION — PULLBACK PRESSURE`  
- [ ] Spot-check: LG disabled → fallback still populates draw/state  

---

# CHATGPT REVIEW PACKAGE

```json
{
  "milestone": 3,
  "v1_modified": false,
  "v2_compiles": false,
  "tests_pass": true,
  "liquidity_sources": ["VantageLiquidityGrab (primary)", "M15 swing + M5 sweep fallback"],
  "liquidity_states": ["none", "approaching", "touched", "swept", "rejected", "accepted_beyond"],
  "pullback_score_formula_m3": "0.18*ext + 0.18*mom_rollover + 0.10*pd + 0.08*reject + 0.10*ltf + 0.10*bb + 0.14*disp_exhaust + 0.12*liq_pressure",
  "continuation_formula_m3": "0.22*align + 0.18*(100-ext) + 0.14*adx + 0.14*bos + 0.14*mom_cont + 0.08*disp + 0.10*liq_cont",
  "reversal_liquidity_addon": "+12 when rejected liquidity aligns with dominant trend draw",
  "new_market_states": [
    "LIQUIDITY SWEEP — WAIT FOR CONFIRMATION",
    "LIQUIDITY REJECTION — PULLBACK PRESSURE"
  ],
  "ea_inputs_l5": [
    "InpPbV2UseLiquidityGrab",
    "InpPbV2LiqApproachAtr",
    "InpPbV2LiqTouchAtr"
  ],
  "files_modified": [
    "MQL5/Include/VantageAI/VantagePullbackV2.mqh",
    "MQL5/Experts/VantageMT5AIDecisionAssistant.mq5",
    "MQL5/Include/VantageAI/VantageDashboard.mqh",
    "backend/app/static/pullback.html",
    "backend/tests/test_pullback_v2_status.py"
  ],
  "known_issues": [
    "Fallback lacks session PDH/PDL levels",
    "MQL5 compile not verified in automated CI",
    "Scores uncalibrated"
  ],
  "questions_for_chatgpt": [
    "Should REJECTED liquidity weight pullback_pressure at 85 or higher when LG confirms MSS?",
    "Is 0.60 ATR the right default approach band for XAUUSD vs FX?",
    "Should ACCEPTED_BEYOND reduce pullback_score more aggressively in extended premium?",
    "Should V2 require LG module on gold and fallback-only on FX?"
  ]
}
```
