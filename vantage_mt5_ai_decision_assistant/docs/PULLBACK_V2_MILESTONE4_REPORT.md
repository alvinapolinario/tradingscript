# Pullback Probability Desk V2 — Milestone 4 Report

**Date:** 2026-08-12  
**Scope:** FVG / OB integration + POI ranking (Gold SMC primary + M15 fallback)  
**V1 modified:** No

---

## Delivered

Milestone 4 adds a **Point of Interest (POI) ranking layer** to V2. The engine identifies where a pullback is most likely to react — FVG, order block, breaker, or inverse FVG — and scores how attractive that zone is as a retrace target.

1. **POI resolution** — prefers `VantageGoldSMCResult.primary_poi_*` when Gold SMC is active; otherwise M15 fallback scan  
2. **Fallback FVG detection** — 3-candle imbalance with min ATR gap + mitigation tracking  
3. **Fallback OB detection** — displacement candle + prior opposite candle origin  
4. **POI ranking** — trend-aligned zones below/above price scored by quality, freshness, discount/premium, distance  
5. **Score integration** — `pullback_target_score` in `pullback_score`; `confluence_score` in `immediate_continuation_score`  
6. **Entry location boost** when price is inside or approaching a high-quality POI  
7. **New market states** — POI retrace / reaction overlays  
8. **UI + tests** — web desk POI KPIs, dashboard row, backend passthrough  

---

## Files modified

| File | Change |
|------|--------|
| `MQL5/Include/VantageAI/VantagePullbackV2.mqh` | POI engines, scoring, JSON `"milestone": 4` |
| `MQL5/Experts/VantageMT5AIDecisionAssistant.mq5` | Inputs L6; Gold SMC eval before V2; optional GSM pointer |
| `MQL5/Include/VantageAI/VantageDashboard.mqh` | HUD POI row (`tpbv4`) |
| `backend/app/static/pullback.html` | M4 POI KPIs + zone line |
| `backend/tests/test_pullback_v2_status.py` | M4 `poi` object assertions |
| `docs/PULLBACK_V2_IMPLEMENTATION_PLAN.md` | Status updated |

**V1 files NOT modified:** `VantagePullback.mqh`

---

## POI resolution

```text
ResolvePoi(dom, m15, dr, gsm):
  if prefer_gold_smc_poi AND gsm.valid AND gsm.analysis_active AND gsm.gold_symbol_valid
     AND gsm.primary_poi_type != "None":
    return MapGoldSmcPoi(...)
  else:
    return CalcPoiFallback(...)
```

### MapGoldSmcPoi

Maps Gold SMC Phase 4 fields into V2 POI snapshot:

| Gold SMC field | V2 field |
|----------------|----------|
| `primary_poi_type` | `poi.primary_type` |
| `primary_poi_dir` | `poi.primary_dir` |
| `poi_upper/lower/mid/ce` | zone bounds |
| `poi_quality` | quality |
| `poi_mitigation_pct` | mitigation |
| `has_fresh_fvg/has_valid_ob/has_breaker/has_inverse_fvg` | fvg/ob counts |

### CalcPoiFallback (M15)

- Scans up to `max_poi_scan` closed M15 bars  
- Detects bullish/bearish FVGs with `min_fvg_atr` threshold  
- Detects OB from displacement + prior opposite candle  
- Ranks candidates with `RankPoiCandidate()` — requires trend alignment  
- Picks highest-ranked zone as primary POI  

### FinalizePoiSnap

Computes:

| Output | Meaning |
|--------|---------|
| `distance_atr` | Distance from M15 close to POI edge |
| `price_inside` | Close inside POI bounds |
| `price_approaching` | Within `poi_approach_atr` |
| `pullback_target_score` | How attractive as pullback landing zone (0–100) |
| `confluence_score` | POI quality + alignment + source bonus |

---

## Updated score weights (M4)

**Pullback score:**

```text
pullback_score =
    0.16 × extension
  + 0.16 × momentum_rollover
  + 0.09 × pd_pressure
  + 0.08 × rejection
  + 0.09 × ltf_pullback
  + 0.09 × bb_reclaim
  + 0.13 × displacement_exhaustion
  + 0.11 × liquidity_pressure
  + 0.09 × poi_pullback_target
```

**Immediate continuation:**

```text
immediate_continuation_score =
    0.21 × trend_align
  + 0.17 × (100 - extension)
  + 0.13 × adx
  + 0.13 × bos
  + 0.13 × momentum_continuation
  + 0.08 × displacement
  + 0.09 × liquidity_continuation
  + 0.06 × poi_confluence
```

**Entry location:** +6 when `pullback_target_score >= 65`; +10 when inside POI with score ≥ 75.

**Expected depth:** uses POI distance when available.

---

## New market states

| Condition | State label |
|-----------|-------------|
| `poi_price_inside` AND `pullback_target >= 70` AND `pullback_score >= 50` | INSIDE POI — PULLBACK REACTION ZONE |
| `poi_price_approaching` AND `pullback_target >= 65` AND `pullback_score >= 52` | POI RETRACE APPROACHING — WATCH REACTION |

---

## EA inputs (group L6)

| Input | Default | Purpose |
|-------|---------|---------|
| `InpPbV2UseGoldSmcPoi` | true | Prefer Gold SMC primary POI |
| `InpPbV2MinFvgAtr` | 0.12 | Fallback min FVG gap (× M15 ATR) |
| `InpPbV2MaxPoiScan` | 80 | Fallback M15 lookback bars |
| `InpPbV2PoiApproachAtr` | 0.50 | Approaching POI band |

**Eval order:** `MaybeEvalLiquidityGrab` → `MaybeEvalGoldSmc` → `MaybeEvalPullbackV2`

---

## JSON additions (backward compatible)

New object:

```json
"poi": {
  "primary_type": "Fair Value Gap",
  "primary_dir": "Bullish",
  "status": "fresh",
  "upper": 3338.0,
  "lower": 3332.0,
  "mid": 3335.0,
  "quality": 72.0,
  "mitigation_pct": 0.0,
  "distance_atr": 0.45,
  "pullback_target_score": 78.0,
  "confluence_score": 68.0,
  "fvg_count": 2,
  "ob_count": 1,
  "price_inside": false,
  "price_approaching": true,
  "from_gold_smc": true
}
```

`"milestone": 4`

---

## Tests

| Suite | Result |
|-------|--------|
| V1 + V2 pullback tests | **10 passed** |

MQL5 compile: not verified in CI — recompile EA in MetaEditor.

---

## Known limitations (post-M4)

- Fallback POI is M15-only (no M5 precision POI yet)  
- Fallback lacks breaker / inverse FVG / OB+FVG overlap logic from full Gold SMC Zones engine  
- Gold SMC POI only on approved Gold symbols; FX uses fallback  
- Expected depth / OTE refinement deferred to Milestone 5  
- Scores remain uncalibrated  

---

## Do not start Milestone 5 until

- [ ] MetaEditor compile succeeds  
- [ ] Live heartbeat shows M4 `poi` JSON on XAUUSD (Gold SMC path)  
- [ ] Live heartbeat shows fallback POI on EURUSD  
- [ ] Spot-check: extended bull trend + POI below price → elevated `pullback_target_score`  

---

# CHATGPT REVIEW PACKAGE

```json
{
  "milestone": 4,
  "v1_modified": false,
  "v2_compiles": false,
  "tests_pass": true,
  "poi_sources": ["VantageGoldSMC primary_poi (Gold)", "M15 FVG/OB fallback scan"],
  "pullback_score_formula_m4": "0.16*ext + 0.16*mom + 0.09*pd + 0.08*reject + 0.09*ltf + 0.09*bb + 0.13*disp + 0.11*liq + 0.09*poi_target",
  "continuation_formula_m4": "0.21*align + 0.17*(100-ext) + 0.13*adx + 0.13*bos + 0.13*mom + 0.08*disp + 0.09*liq + 0.06*poi_conf",
  "new_market_states": [
    "INSIDE POI — PULLBACK REACTION ZONE",
    "POI RETRACE APPROACHING — WATCH REACTION"
  ],
  "ea_inputs_l6": [
    "InpPbV2UseGoldSmcPoi",
    "InpPbV2MinFvgAtr",
    "InpPbV2MaxPoiScan",
    "InpPbV2PoiApproachAtr"
  ],
  "files_modified": [
    "MQL5/Include/VantageAI/VantagePullbackV2.mqh",
    "MQL5/Experts/VantageMT5AIDecisionAssistant.mq5",
    "MQL5/Include/VantageAI/VantageDashboard.mqh",
    "backend/app/static/pullback.html",
    "backend/tests/test_pullback_v2_status.py"
  ],
  "known_issues": [
    "Fallback POI lacks full Gold SMC Zones feature parity",
    "MQL5 compile not verified in automated CI",
    "Scores uncalibrated"
  ],
  "questions_for_chatgpt": [
    "Should POI pullback_target weight (9%) exceed liquidity (11%) for XAUUSD?",
    "Is M15-only fallback sufficient for FX pairs or should M5 POI be added in M5?",
    "Should heavily mitigated POI reduce pullback_score directly vs only capping target score?",
    "Should V2 rank multiple POIs and expose top-3 instead of primary only?"
  ]
}
```
