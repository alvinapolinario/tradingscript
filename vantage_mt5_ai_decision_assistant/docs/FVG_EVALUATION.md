# FVG System Evaluation

**Document type:** Forensic audit (read-only)  
**Repository:** `vantage_mt5_ai_decision_assistant`  
**Audit date:** 2026-08-14  
**Auditor role:** SMC / ICT / multi-timeframe FVG systems review  

---

## 1. Executive Summary

This project contains **multiple independent FVG implementations** rather than one unified FVG engine. The **canonical 3-candle ICT formula is mathematically correct** in the primary engines (`market_structure/fvg.py`, `VantageGoldSMCZones.mqh`, Pullback V2 fallback, Python ICT/AMD/Box Theory). Closed-bar discipline is generally respected (`CopyRates(..., shift=1)` / caller-supplied closed candles).

However, the repository **does not implement the requested 4H → M15 strategy** as a linked pipeline:

```text
4H FVG → price enters 4H FVG → M15 confirmation → M15 FVG → retrace into M15 FVG → entry
```

**What exists instead:**

| Module | HTF context | Setup TF | Entry FVG TF | State machine | Linked sequence |
|--------|-------------|----------|--------------|---------------|-----------------|
| **Gold SMC** | H4/H1 bias | M15 | M15 POI (FVG/OB) | Partial (zone status) | No HTF FVG touch gate |
| **ICT (MQL5 + Python)** | H1 bias | M15 sweep/MSS | **M5** FVG | Yes (full lifecycle) | Yes, but not 4H FVG anchored |
| **AMD iFVG** | H4 macro config | M15 accumulation | **M5 iFVG** | Yes | No HTF FVG |
| **Pullback V2** | Via Gold SMC | M15 POI | M15 (advisory) | No | No |
| **Liquidity Grab** | H4 EMA bias | M15 | Boolean flag only | Yes (LG states) | No FVG zones stored |
| **Box Theory** | HTF confirmation | M15 box | M5 FVG check | Partial | No |

**Verdict:** FVG **detection** is **FUNCTIONAL** in core engines. FVG **strategy orchestration** for HTF-location + LTF-confirmation entry is **EARLY DEVELOPMENT**.

**Classification:** **FUNCTIONAL** (detection) / **EARLY DEVELOPMENT** (multi-TF strategy)  
**Overall score:** **52 / 100**

---

## 2. Current FVG Architecture

### 2.1 Layer diagram

```text
┌─────────────────────────────────────────────────────────────────┐
│ MT5 EA: VantageMT5AIDecisionAssistant.mq5                       │
│  ├─ Gold SMC (VantageGoldSMC*.mqh)     → M15 FVG/OB POI         │
│  ├─ ICT (VantageIct.mqh)               → M15 setup, M5 FVG entry  │
│  ├─ AMD iFVG (VantageAmdIfvg.mqh)      → M15 setup, M5 iFVG     │
│  ├─ Liquidity Grab                     → post-disp FVG bool       │
│  ├─ Pullback V2                        → consumes Gold SMC POI    │
│  └─ Box Theory                         → M5 FVG confirmation    │
└───────────────────────────┬─────────────────────────────────────┘
                            │ heartbeat JSON (passthrough)
┌───────────────────────────▼─────────────────────────────────────┐
│ Python backend (FastAPI)                                        │
│  ├─ market_structure/fvg.py          ← canonical detect/mitigate  │
│  ├─ analysis/ict/*                   ← full state machine       │
│  ├─ analysis/amd_ifvg_logic.py        ← iFVG pipeline           │
│  └─ analysis/box_theory/service.py    ← M5 FVG via detect_fvgs  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│ UI: gold-smc.html, ict.html, amd-ifvg.html, pullback.html     │
│ Storage: monitor_state (in-memory), signal_ledger (SQLite)      │
│          — no dedicated FVG table                               │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Key files

| File | Role |
|------|------|
| `backend/app/market_structure/fvg.py` | `detect_fvgs`, `update_fvg_mitigation`, `try_invert_fvg` |
| `backend/app/market_structure/types.py` | `FvgZone`, `FvgStatus`, `midpoint` |
| `MQL5/Include/VantageAI/VantageGoldSMCZones.mqh` | Primary MQL5 FVG engine (M15 only) |
| `MQL5/Include/VantageAI/VantageIct.mqh` | M15 setup, M5 FVG entry |
| `backend/app/analysis/ict/state_machine.py` | Full ICT lifecycle |
| `MQL5/Include/VantageAI/VantagePullbackV2.mqh` | POI via Gold SMC + M15 fallback |

---

## 3. Existing FVG Detection Logic

### 3.1 Standard 3-candle model (correct in core engines)

**Bullish:** `Candle1.high < Candle3.low` → zone `[C1.high, C3.low]`  
**Bearish:** `Candle1.low > Candle3.high` → zone `[C3.high, C1.low]`

**Python** (`fvg.py` lines 26–62): oldest-first indexing, `c1=candles[i-2]`, `c2=candles[i-1]`, `c3=candles[i]`.

**Gold SMC MQL5** (`VantageGoldSMCZones.mqh` lines 180–227): series arrays, `candle1=i+2`, `candle2=i+1`, `candle3=i`, called only on `tf_confirm` (default **M15**, line 474).

### 3.2 Non-canonical detectors

| Location | Issue |
|----------|-------|
| `VantageLiquidityGrab.mqh:532–538` | Bool only, no min ATR, no zone stored |
| `VantagePullbackV2.mqh:592–607` | `DetectRecentFvg` — 2-bar heuristic, not strict ICT |

---

## 4. Bullish FVG Evaluation

| Engine | Correct | Min gap | Displacement gate |
|--------|:-------:|:-------:|:-----------------:|
| Python `fvg.py` | ✅ | ✅ | Partial |
| Gold SMC Zones | ✅ | ✅ (0.12 ATR default) | ✅ optional |
| Pullback V2 fallback | ✅ | ✅ | ✅ |
| ICT MQL5 M5 | ✅ | ✅ | ❌ on middle candle |
| Liquidity Grab | ⚠️ | ❌ | ❌ |

---

## 5. Bearish FVG Evaluation

Same engines — bearish branch mirrors correctly. ICT MQL5 (`VantageIct.mqh:317–326`) assigns zones correctly.

---

## 6. Mitigation and Invalidation Logic

### Python (`update_fvg_mitigation`)

- Bullish partial: `(upper - price) / width * 100`
- Full fill: `price <= lower` → `FULLY_MITIGATED`
- No separate `INVALIDATED` on close break (unlike Gold SMC)

### Gold SMC MQL5 (`UpdateFvgMitigation`, lines 105–147)

- Status ladder: `FRESH → TOUCHED → PARTIALLY_MITIGATED (≥50%) → FULLY_MITIGATED (≥99%)`
- **Close beyond zone → `SMC_ZONE_INVALIDATED`**
- CE/midpoint stored but **not used as distinct state**

### ICT MQL5

- **No FVG mitigation tracking**

| Requested state | Python | Gold SMC | ICT MQL5 |
|-----------------|:------:|:--------:|:--------:|
| UNTOUCHED | ✅ | ✅ | implicit |
| PARTIALLY_MITIGATED | ✅ | ✅ | ❌ |
| MIDPOINT_REACHED | ❌ | ❌ | ❌ |
| FULLY_FILLED | ✅ | ✅ | ❌ |
| INVALIDATED | enum only | ✅ | ❌ |
| EXPIRED | enum only | ❌ | setup-level (Python ICT) |

---

## 7. Multi-Timeframe Evaluation

| Component | H4 | H1 | M15 | M5 |
|-----------|:--:|:--:|:---:|:--:|
| Gold SMC FVG detect | ❌ | ❌ | ✅ | ❌ |
| Gold SMC bias/structure | ✅ | ✅ | ✅ | ✅ |
| ICT setup | ❌ | ✅ | ✅ | ❌ |
| ICT entry FVG | ❌ | ❌ | ❌ | ✅ |

No `htf_parent_fvg_id` or cross-TF event linking exists.

---

## 8. 4H → M15 Strategy Compatibility

| Step | Supported? |
|------|:----------:|
| Detect **4H FVG** | ❌ |
| Track H4 FVG touch | ❌ |
| M15 confirmation after H4 touch | ❌ |
| M15 FVG after displacement (`createdAt > touch`) | ❌ |
| Retrace into M15 FVG entry | ⚠️ Partial (ICT uses **M5**) |

**Closest pipeline:** Python ICT — `H1 bias → M15 SSL sweep → M15 MSS → M5 FVG → retrace` (`analysis/ict/models/bullish.py`).

---

## 9. Liquidity Sweep Analysis

- **ICT MQL5** (`VantageIct.mqh:230–265): wick through level + close back — closed M15 bar ✅
- **Python ICT:** full sweep + quality score + state machine
- **Liquidity Grab:** comprehensive BSL/SSL; FVG is weak boolean only

---

## 10. MSS / BOS Analysis

- **ICT MQL5:** breaks 8-bar M15 structure on sweep bar — simplified
- **Python ICT:** `detect_mss()` with pivot swings — more robust
- **Gold SMC Core:** BOS/CHoCH/MSS with displacement gate — bias, not FVG entry gate

---

## 11. Displacement Analysis

- **Gold SMC `DispScore`:** body_atr + range_atr + close_pos → 0–100; optional FVG gate
- **Python FVG:** middle-candle body_atr score, no hard gate by default
- **ICT MQL5:** single sweep-bar body vs ATR — does not match requested `bodyRatio >= 0.60 AND rangeATRRatio >= 1.20`

---

## 12. FVG Quality Scoring

| Module | Factors |
|--------|---------|
| Gold SMC | `40 + disp*0.4 + gap_atr*10` per zone |
| ICT Python | Weighted 0–100: HTF, sweep, displacement, MSS, FVG, PD, session, R:R |
| Pullback V2 POI | quality + mitigation penalty + FVG confluence +10 |

No unified FVG setup score. `gap_atr` stored but no Weak/Moderate/Strong band labels in JSON.

---

## 13. Risk and Invalidation

- **ICT MQL5:** SL at sweep + 0.15×ATR buffer; TP from minimum R:R
- **Python ICT:** `check_invalidation()`, expiration by candle age
- **Gold SMC:** zone invalidation on close through POI

---

## 14. Look-Ahead and Repainting Risks

| Risk | Status |
|------|--------|
| Incomplete candles | ✅ Generally safe (shift=1) |
| Future leakage in mitigation | ✅ Scans only after `created` |
| ICT MQL5 FVG pick | ⚠️ First of 12 M5 bars, not post-sweep filter |
| Python ICT FVG filter | ✅ `exec_candles if time >= sweep.sweep_time` |
| Live bid for in-zone | ⚠️ Intrabar (ICT MQL5) |

---

## 15. Database / Data Model Review

**No dedicated FVG table.** `signal_ledger` stores generic signals only. ICT `IctSetupRecord` has `fvg_id`, bounds in memory/API — not persisted long-term.

Recommended fields (fvg_id, mitigation_state, htf_parent_fvg_id, setup_state, etc.) are **mostly missing** from SQLite.

---

## 16. Architecture Gaps

1. No unified FVG service (6+ implementations)
2. No H4 FVG detection
3. No cross-TF event linking
4. No CE/midpoint interaction state
5. Inconsistent invalidation across modules
6. MQL5 ICT weaker than Python ICT
7. No FVG persistence for backtest

---

## 17. Recommended Algorithm

```text
ON each closed H4 bar:
    detect new H4 FVGs → store → state = WAITING_FOR_HTF_MITIGATION

ON each closed M15 bar:
    FOR active HTF setups:
        IF price enters H4 FVG → HTF_FVG_TOUCHED
        IF HTF_FVG_TOUCHED → detect liquidity sweep → LIQUIDITY_SWEPT
        IF LIQUIDITY_SWEPT → displacement + MSS → MSS_CONFIRMED
        IF MSS_CONFIRMED → detect M15 FVG where created_time > htf_touch AND > mss_time
        IF LTF FVG → WAITING_FOR_RETRACE
        IF price in entry FVG → score, SL, RR → ENTRY_READY
        check_expiration / invalidation
```

Extend existing Python ICT state machine rather than building from scratch.

---

## 18. Recommended State Machine

```text
WAITING_FOR_HTF_FVG → HTF_FVG_FOUND → WAITING_FOR_HTF_MITIGATION
→ HTF_FVG_TOUCHED → LIQUIDITY_SWEPT → DISPLACEMENT_CONFIRMED
→ MSS_CONFIRMED → WAITING_FOR_LTF_FVG → LTF_FVG_CREATED
→ WAITING_FOR_RETRACE → ENTRY_READY → TRADE_ACTIVE
→ TARGET_REACHED | SETUP_INVALIDATED | SETUP_EXPIRED
```

---

## 19. Recommended Implementation Plan

| Phase | Scope |
|-------|-------|
| P1 | H4 `detect_fvgs` / `DetectFvgs`; store zone IDs |
| P2 | HTF touch + mitigation tracker |
| P3 | Extend ICT state machine with HTF_FVG_* states |
| P4 | Gate M15 FVG: `created_time > htf_touch && > mss_time` |
| P5 | Unified configurable scoring |
| P6 | SQLite `fvg_setups` + explain API |
| P7 | MQL5 parity or Python-analyze-only |
| P8 | Closed-bar backtest replay |

---

## 20. Priority Fixes

### HIGH — No H4 FVG detection

**File:** `VantageGoldSMCZones.mqh:474` — `DetectFvgs` only on M15.  
**Fix:** Add H4 pass; expose in heartbeat.

### HIGH — LTF FVG not linked to HTF touch / displacement time

**Problem:** Unrelated historical FVGs can become entry zones.  
**Fix:** Filter `created_time >= htf_touch_time` and `>= mss_time` (Python ICT already filters post-sweep for M5).

### HIGH — MQL5 ICT lacks mitigation and post-sweep FVG filter

**File:** `VantageIct.mqh:312–339`.  
**Fix:** Port Python bullish filter + `update_fvg_mitigation`.

### MEDIUM — Inconsistent invalidation (Python vs Gold SMC)

### MEDIUM — CE stored but not used in states

### LOW — Liquidity Grab `DetectFVG` has no min gap

---

## 21. Feature Matrix

| Feature | Existing | Correct | Needs Improvement | Missing |
| --------------------- | -------: | ------: | ----------------: | ------: |
| Bullish FVG detection | ✅ | ✅ | ⚠️ | |
| Bearish FVG detection | ✅ | ✅ | ⚠️ | |
| FVG midpoint (CE) | ✅ | ✅ | ⚠️ | |
| Mitigation tracking | ✅ | ✅ | ⚠️ | |
| HTF FVG (H4) | | | | ❌ |
| M15 confirmation pipeline | ⚠️ | partial | ✅ | |
| M15 entry FVG | ⚠️ | partial | ✅ | |
| Liquidity sweep | ✅ | ✅ | ⚠️ | |
| Displacement | ✅ | partial | ✅ | |
| MSS | ✅ | partial | ✅ | |
| BOS | ✅ | ✅ | ⚠️ | |
| Premium/discount | ✅ | ✅ | ⚠️ | |
| Setup state machine | ⚠️ | partial | ✅ | ❌ 4H→M15 |
| FVG scoring | ⚠️ | partial | ✅ | |
| Structural SL | ⚠️ | partial | ✅ | |
| Setup expiration | ⚠️ | partial | ✅ | |
| Duplicate prevention | ⚠️ | partial | ✅ | |
| Explainability | ⚠️ | partial | ✅ | |
| Persistent FVG store | | | | ❌ |

---

## 22. Final Assessment

| Dimension | /10 |
|-----------|:---:|
| FVG Detection Accuracy | 8 |
| Mitigation Logic | 6 |
| Market Structure Integration | 6 |
| Multi-Timeframe Logic | 4 |
| Liquidity Logic | 7 |
| Entry Confirmation | 5 |
| Risk Management | 5 |
| Explainability | 6 |
| Backtest Safety | 6 |
| Architecture Quality | 5 |
| **OVERALL** | **52 / 100** |

**Classification:** **FUNCTIONAL** (detection) / **EARLY DEVELOPMENT** (4H→M15 strategy)

**Blocks ADVANCED / PRODUCTION-READY:**

1. No 4H FVG + HTF touch-gated state machine  
2. Multiple divergent FVG implementations  
3. MQL5 vs Python ICT parity gap  
4. No persistent FVG setup store  
5. Entry FVG on M5 in ICT vs M15 in target strategy  

---

## Appendix — Key file paths

```
vantage_mt5_ai_decision_assistant/
  backend/app/market_structure/fvg.py
  backend/app/analysis/ict/models/bullish.py
  backend/app/analysis/ict/state_machine.py
  backend/app/analysis/ict/scorer.py
  MQL5/Include/VantageAI/VantageGoldSMCZones.mqh
  MQL5/Include/VantageAI/VantageIct.mqh
  MQL5/Include/VantageAI/VantagePullbackV2.mqh
  MQL5/Include/VantageAI/VantageLiquidityGrab.mqh
  docs/FVG_EVALUATION.md   ← this file
```

*End of evaluation. No code was modified during this audit.*
