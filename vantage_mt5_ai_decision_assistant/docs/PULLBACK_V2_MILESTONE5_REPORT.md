# Pullback Probability Desk V2 — Milestone 5 Report

**Date:** 2026-08-12  
**Scope:** Expected pullback depth engine, OTE integration, continuation-after-pullback refinement  
**V1 modified:** No

---

## Delivered

Milestone 5 replaces the M1–M4 depth placeholder with a structured depth engine and adds OTE confluence for pullback targeting and post-pullback continuation scoring.

1. **OTE resolution** — prefers Gold SMC OTE band; M15 dealing-range fallback (618/705/790 fib)  
2. **Expected depth engine** — blends OTE mid (40%), POI mid (35%), 61.8% fib (25%) + heuristic anchor  
3. **Depth outputs** — target band (low/mid/high), ATR distance, fib retrace %, source label  
4. **Continuation-after-pullback refinement** — OTE alignment, POI confluence, reversal risk, liquidity/POI penalties  
5. **New market states** — OTE confluence, post-pullback resumption  
6. **UI + tests** — OTE/depth KPIs, cont-after-PB emphasis  

---

## Files modified

| File | Change |
|------|--------|
| `MQL5/Include/VantageAI/VantagePullbackV2.mqh` | OTE + depth engines, refined cont-after-PB, JSON `"milestone": 5` |
| `MQL5/Experts/VantageMT5AIDecisionAssistant.mq5` | Inputs L7 (OTE / depth) |
| `MQL5/Include/VantageAI/VantageDashboard.mqh` | OTE + ContPB HUD row |
| `backend/app/static/pullback.html` | M5 OTE/depth KPIs |
| `backend/tests/test_pullback_v2_status.py` | M5 `ote` + `depth` assertions |
| `docs/PULLBACK_V2_IMPLEMENTATION_PLAN.md` | Status updated |

---

## OTE resolution

```text
ResolveOte(dom, m15, dr, poi, gsm):
  if prefer_gold_smc_ote AND gsm valid with ote band:
    return MapGoldSmcOte(...)
  else if enable_ote AND dealing range valid:
    return CalcOteFallback(...)  // mirrors Gold SMC MapOte logic
```

**Bullish bias:** OTE band retraces from `dealing_high` toward `dealing_low` using fib percentages.  
**Bearish bias:** symmetric from `dealing_low` upward.

`alignment_score` (0–100) feeds continuation-after-pullback.

---

## Expected depth engine

```text
target_mid =
  0.40 × OTE mid (if valid, on correct side of price)
+ 0.35 × POI mid (if valid)
+ 0.25 × 61.8% fib of dealing range
→ blended 85% with 15% heuristic anchor
```

| Output | Description |
|--------|-------------|
| `target_low/high` | OTE bounds ± POI extension |
| `expected_pullback_atr` | `\|close - target_mid\| / M15 ATR` |
| `fib_retrace_pct` | Retrace as % of dealing range |
| `expected_depth` | SHALLOW / MODERATE / DEEP / STRUCTURAL_FAILURE |
| `source` | `ote+poi`, `ote`, `poi`, or `heuristic` |

---

## Continuation-after-pullback (M5 formula)

```text
continuation_after_pullback_score =
    0.28 × trend_strength
  + 0.22 × protected_intact
  + 0.15 × trend_align
  + 0.12 × ote_alignment
  + 0.10 × poi_confluence
  + 0.08 × (100 - reversal_risk)
  + 0.05 × displacement
```

**Bonuses:** POI+OTE overlap +8; price in OTE + protected intact +5; inside high-quality POI +6  
**Penalties:** liquidity rejected against trend −15; heavily mitigated POI −8  

Replaces M1–M4 formula (`0.40×strength + 0.35×protected + 0.25×align`).

---

## New market states

| Condition | State |
|-----------|-------|
| Price in OTE + POI overlap + pullback ≥ 50 | OTE + POI CONFLUENCE — PULLBACK TARGET |
| Price in OTE + pullback ≥ 48 | PRICE IN OTE — WATCH PULLBACK REACTION |
| Cont-after-PB ≥ 78 + (in OTE or inside POI) + rev risk < 35 | POST-PULLBACK RESUMPTION LIKELY |

---

## EA inputs (group L7)

| Input | Default |
|-------|---------|
| `InpPbV2UseGoldSmcOte` | true |
| `InpPbV2EnableOte` | true |
| `InpPbV2OteLowPct` | 0.618 |
| `InpPbV2OteMidPct` | 0.705 |
| `InpPbV2OteHighPct` | 0.790 |

---

## JSON additions

```json
"ote": {
  "valid": true,
  "ote_low": 3320.0,
  "ote_mid": 3328.0,
  "ote_high": 3335.0,
  "price_in_ote": false,
  "poi_overlaps_ote": true,
  "alignment_score": 88.0,
  "from_gold_smc": true
},
"depth": {
  "target_low": 3318.0,
  "target_mid": 3328.0,
  "target_high": 3336.0,
  "expected_pullback_atr": 0.72,
  "expected_depth": "MODERATE",
  "fib_retrace_pct": 64.0,
  "source": "ote+poi"
},
"milestone": 5
```

---

## Tests

| Suite | Result |
|-------|--------|
| V1 + V2 pullback tests | **10 passed** |

---

## Known limitations (post-M5)

- Depth engine uses closed-bar targets only (no intrabar projection)  
- OTE fallback uses M15 dealing range (same as M2 PD engine, not H4 external range)  
- No historical outcome validation until Milestone 6  
- Scores remain uncalibrated  

---

## Do not start Milestone 6 until

- [ ] MetaEditor compile succeeds  
- [ ] Live heartbeat shows M5 `ote` + `depth` JSON  
- [ ] Spot-check: extended bull + OTE below price → MODERATE/DEEP depth with `ote+poi` source  
- [ ] Spot-check: POI+OTE overlap → elevated `continuation_after_pullback_score`  

---

# CHATGPT REVIEW PACKAGE

```json
{
  "milestone": 5,
  "v1_modified": false,
  "v2_compiles": false,
  "tests_pass": true,
  "depth_formula": "0.40*ote_mid + 0.35*poi_mid + 0.25*fib618 blended 85% with 15% heuristic",
  "continuation_after_pullback_m5": "0.28*strength + 0.22*protected + 0.15*align + 0.12*ote + 0.10*poi + 0.08*(100-rev) + 0.05*disp",
  "ote_sources": ["Gold SMC ote_* fields", "M15 dealing range fib fallback"],
  "new_market_states": [
    "OTE + POI CONFLUENCE — PULLBACK TARGET",
    "PRICE IN OTE — WATCH PULLBACK REACTION",
    "POST-PULLBACK RESUMPTION LIKELY"
  ],
  "files_modified": [
    "MQL5/Include/VantageAI/VantagePullbackV2.mqh",
    "MQL5/Experts/VantageMT5AIDecisionAssistant.mq5",
    "MQL5/Include/VantageAI/VantageDashboard.mqh",
    "backend/app/static/pullback.html",
    "backend/tests/test_pullback_v2_status.py"
  ],
  "known_issues": [
    "M15-only OTE/dealing range fallback",
    "No CSV logging until M6",
    "Scores uncalibrated"
  ]
}
```
