# Box Theory Backend Audit

Read-only audit of `backend/app/analysis/box_theory/` and its wiring. No code was modified.

**Audit date:** 2026-07-29  
**Scope:** Python backend Box Theory strategy module  
**Purpose:** Document actual implementation vs intended H1 → M15 → M5 architecture before strategy modifications

---

## Table of Contents

1. [How the Backend Detects a Valid Box](#1-how-the-backend-detects-a-valid-box)
2. [Timeframes Used](#2-timeframes-used)
3. [Intended vs Actual Structure](#3-intended-vs-actual-structure)
4. [Files, Classes, and Functions](#4-files-classes-and-functions)
5. [Execution Flow](#5-execution-flow)
6. [Box Validation Rules](#6-box-validation-rules)
7. [Breakout Logic](#7-breakout-logic)
8. [Retest Logic](#8-retest-logic)
9. [Fakeout Handling](#9-fakeout-handling)
10. [HTF Market-Structure Integration](#10-htf-market-structure-integration)
11. [Optional Confirmations](#11-optional-confirmations)
12. [Confidence / Scoring System](#12-confidence--scoring-system)
13. [Signal States](#13-signal-states)
14. [Repainting / Look-Ahead Bias](#14-repainting--look-ahead-bias)
15. [Duplicate Signals](#15-duplicate-signals)
16. [Final Architecture Assessment](#16-final-architecture-assessment)
17. [Comparison vs Recommended Architecture](#17-comparison-vs-recommended-architecture)
18. [Summary](#summary)

---

## 1. How the Backend Detects a Valid Box

**File:** `backend/app/analysis/box_theory/detector.py` → `detect_box()`

On the **box-timeframe candle array** (default M15):

1. Requires at least `lookback_candles` bars (default 50).
2. Scans every span from `min_box_candles` (8) to `lookback_candles` within the last lookback window.
3. For each span:
   - `box_high` = max high, `box_low` = min low in the span
   - Height must be between `min_box_height_atr × ATR` and `max_box_height_atr × ATR`
   - **Upper touches:** count of bars where high or close is within `touch_tolerance_atr × ATR` of `box_high` (default ≥ 2)
   - **Lower touches:** same for `box_low`
   - **Inside ratio:** share of closes between low and high (default ≥ 65%)
4. Computes a **quality score** (40 base + touch bonus + inside-ratio bonus).
5. Returns the **highest-quality** span as `BoxRange` (high, low, mid, height, touches, start/end time, age).

There is **no persistent box state** — each call re-scans history and picks the best span.

---

## 2. Timeframes Used

| Stage | Config field | Default | Actual candle input |
|--------|----------------|---------|---------------------|
| Market structure / HTF bias | `structure_timeframe` | H1 | `candles_structure` (API: `H1` / `structure`) |
| Box detection | `box_timeframe` | M15 | `candles_box` (API: `M15` / `box`) |
| Breakout detection | *(same as box)* | M15 | **`candles_box`** — not M5 |
| Retest detection | `entry_timeframe` | M5 | `candles_entry` (API: `M5` / `entry`) |
| FVG check | `entry_timeframe` | M5 | `candles_entry` |
| Volume confirmation | *(implicit box TF)* | M15 | **`candles_box`** |
| ATR expansion | *(implicit box TF)* | M15 | **`candles_box`** |
| Liquidity sweep | *(implicit box TF)* | M15 | **`candles_box`** |
| Final BUY/SELL | orchestrator | — | `service.py` |

**Important:** Config labels say H1/M15/M5, but **breakout is evaluated on the box (M15) array**, not on M5. That differs from the intended “M5 entry confirmation” model.

If `candles_entry` / `candles_structure` are omitted, both fall back to **`candles_box`**.

---

## 3. Intended vs Actual Structure

### Intended Architecture

```text
H1 = Higher-Timeframe Bias / Market Structure

        ↓

M15 = Box Detection
      - Box High
      - Box Low
      - Box Mid
      - Minimum touches
      - Consolidation validation

        ↓

M5 = Entry Confirmation
     - Breakout candle close
     - Retest
     - Rejection/confirmation candle

        ↓

Signal
BUY / SELL / WAIT
```

### Assessment: ⚠️ Partially Correct

| Intended | Backend reality |
|----------|-----------------|
| H1 = structure bias | ⚠️ Simple 20-bar close-direction count on H1 (`htf_bias()`), not BOS/CHoCH/structure |
| M15 = box | ✅ Box detection on M15 (when API/EA supply M15) |
| M5 = breakout + retest + confirmation | ❌ Breakout on **M15**; only **retest + FVG** use M5 |
| Signal after full chain | ⚠️ Scoring combines all steps, but breakout/retest timing logic has gaps (see §14) |

---

## 4. Files, Classes, and Functions

| Responsibility | Location |
|----------------|----------|
| **Orchestration** | `service.py` → `analyze_box_strategy()` |
| **Market structure (HTF bias)** | `scorer.py` → `htf_bias()` |
| **Box detection** | `detector.py` → `detect_box()` |
| **Breakout** | `breakout.py` → `detect_breakout()` |
| **Retest** | `retest.py` → `detect_retest()` |
| **Fakeout / traps** | `fakeout.py` → `detect_fakeout()` |
| **Liquidity sweep** | `liquidity.py` → `detect_liquidity_sweep()` |
| **FVG** | `amd_ifvg_logic.py` → `detect_fvgs()` (reused); **no iFVG** in box module |
| **Signal scoring** | `scorer.py` → `score_signal()`, `volume_confirmed()`, `atr_expansion()` |
| **Risk management** | `risk.py` → `calculate_risk_plan()` |
| **Final BUY/SELL** | `service.py` (lines 170–203, 183–196) |
| **Types / config** | `types.py` → `BoxStrategyConfig`, enums |
| **Utilities** | `utils.py` → `atr()`, `validate_candles()`, `candles_from_payload()` |
| **API entry** | `routers/api.py` → `box_theory_analyze()` |
| **Discord alerts** | `box_discord_notify.py` → `maybe_box_theory_alert()` |
| **History (no lifecycle state)** | `history.py` → `record_box_result()` |

There is **no separate class-based service layer** — it is a functional pipeline centered on `analyze_box_strategy()`.

---

## 5. Execution Flow

### Actual Sequence

```text
Market Data (candles_box, candles_entry, candles_structure)
    ↓
Gold symbol validation
    ↓
Candle validation (sorted, no duplicates)
    ↓
Box Detector (M15 / candles_box)
    ↓
[No box] → FORMING / WAIT
    ↓
[Box age < min_box_candles] → FORMING / WAIT
    ↓
Breakout Detector (M15 / candles_box)     ← not M5
    ↓
Fakeout Detector (M15, after box.end_time)
    ↓
[Trap, no breakout] → BULL_TRAP / BEAR_TRAP / INVALID
    ↓
[No breakout] → VALID / WATCH
    ↓
Liquidity Sweep (M15, before breakout time)
    ↓
Retest Detector (M5 / candles_entry, after breakout time)
    ↓
FVG check (M5, last 3 FVGs via detect_fvgs)
    ↓
HTF bias (H1 / candles_structure)
    ↓
Volume + ATR expansion (M15 / candles_box)
    ↓
Signal Scoring
    ↓
Retest gating (require_retest / BREAKOUT_RETEST_MODE)
    ↓
Confidence vs minimum_signal_score (70)
    ↓
Optional block_countertrend (default OFF)
    ↓
Risk plan (only if BUY/SELL)
    ↓
Box age expiration check (may override to EXPIRED / INVALID)
    ↓
BUY / SELL / WAIT / WATCH / INVALID
```

### Deviations from Recommended Flow

- HTF runs **after** breakout/retest/sweep, not before box gating.
- Liquidity sweep is **after** breakout, not before.
- Breakout is on **M15**, not M5.
- No dedicated “momentum” or RSI stage.

---

## 6. Box Validation Rules

```text
Box High               ✅ Implemented   (max high in span)
Box Low                ✅ Implemented   (min low in span)
Box Mid                ✅ Implemented   ((high+low)/2)
Upper Touches          ✅ Implemented   (≥ min_touches, ATR tolerance)
Lower Touches          ✅ Implemented   (≥ min_touches, ATR tolerance)
Minimum Box Candles    ✅ Implemented   (min_box_candles=8; also FORMING gate)
Inside Range Majority  ✅ Implemented   (min_inside_ratio=0.65)
Min Height (ATR)       ✅ Implemented   (min_box_height_atr=0.35)
Max Height (ATR)       ✅ Implemented   (max_box_height_atr=2.5)
Touch Tolerance (ATR)  ✅ Implemented   (touch_tolerance_atr=0.15)
Lookback Window        ✅ Implemented   (lookback_candles=50)
Best-span selection    ⚠️ Partially     (picks highest quality, not a stable box ID)
Box invalidation rules ⚠️ Partially     (EXPIRED by age; INVALIDATED enum unused)
Chase / distance filter ❌ Missing      (chase_max_atr in config, never used)
```

---

## 7. Breakout Logic

**File:** `backend/app/analysis/box_theory/breakout.py` → `detect_breakout()`

### Bullish Breakout

- Requires **`close > box.high + breakout_buffer_atr × ATR`**
- Requires **body ratio ≥ min_breakout_body_ratio** (default 0.45)
- If `high > box.high` but **`close <= box.high`** → skipped (wick-only filter)

### Bearish Breakout

- Requires **`close < box.low - buffer`**
- Same body-ratio rule
- No explicit wick-only skip for bearish (only close-based rule)

### Method Summary

| Method | Used for signal? |
|--------|------------------|
| **CLOSE beyond boundary + buffer** | ✅ Yes — primary rule |
| HIGH/LOW pierce only | ❌ No — explicitly rejected (bullish) |
| Wick-only | ❌ No — filtered on bullish; bearish needs close below low |

### Caveats

- Breakout is scanned on **M15**, not M5.
- Loop finds the **first** qualifying bar after `box.end_time` in the array (not necessarily the latest state).
- `box.end_time` is always the **last bar of the chosen span**, which is the **last bar in the lookback window** — see §14.

---

## 8. Retest Logic

**File:** `backend/app/analysis/box_theory/retest.py` → `detect_retest()` on **M5** (`candles_entry`)

| Rule | Implemented? |
|------|----------------|
| Wait for retest (default) | ✅ `require_retest=true`, `entry_mode=BREAKOUT_RETEST_MODE` |
| Enter immediately after breakout | ✅ Possible if `require_retest=false` and `BREAKOUT_MODE` |
| Retest tolerance | ✅ `retest_tolerance_atr × ATR` (default 0.25) |
| Max retest candles | ✅ `max_retest_candles=10` |
| Confirmation candle | ⚠️ Partial — bullish/bearish close rules **or** auto-confirm when `candles_waited >= confirmation_candles` (default 1) even if not confirmed |
| Retest near broken boundary | ✅ Price near `box.high` (bull) / `box.low` (bear) |

### Preferred Sequence

```text
Box
 ↓
Breakout Close
 ↓
Wait
 ↓
Price returns to broken Box boundary
 ↓
Retest
 ↓
Rejection / confirmation
 ↓
BUY or SELL
```

**Assessment:**

- ✅ Conceptually supported when retest mode is on.
- ⚠️ Retest can be marked `detected=True, confirmed=False` and still proceed if `confirmation_candles=1` (weak confirmation).
- ❌ Breakout on M15 + retest on M5 is a **timeframe split** that may not align with “M5 breakout close”.

---

## 9. Fakeout Handling

**File:** `backend/app/analysis/box_theory/fakeout.py` → `detect_fakeout()`

### Bull Trap

```text
Price moves above Box High
but closes/re-enters inside Box
→ No BUY
```

**Status:** ✅ Implemented → `INVALID`, no BUY

### Bear Trap

```text
Price moves below Box Low
but closes/re-enters inside Box
→ No SELL
```

**Status:** ✅ Implemented → `INVALID`, no SELL

### Orchestration (`service.py`)

- Trap **without** prior breakout → early return `INVALID`
- Trap **after** breakout (`fakeout.time >= breakout.time`) → overrides to `INVALID`

### Gaps

- Only the **first** trap after `box.end_time` is considered.
- A valid breakout followed by a later trap may still have produced a BUY/SELL path before trap detection order is applied (trap check runs before scoring, so post-breakout trap blocks signal — ✅).
- Trap detection uses **`c.time > after_time` (strict)** — same timing issue as breakout (§14).

---

## 10. HTF Market-Structure Integration

**File:** `backend/app/analysis/box_theory/scorer.py` → `htf_bias()`

### What It Actually Does

- Last 20 **H1 closes** (when `candles_structure` supplied)
- Counts up vs down closes
- `BULLISH` if ups ≥ downs + 6, `BEARISH` if downs ≥ ups + 6, else `NEUTRAL`

### Scoring Impact

| Condition | Effect |
|-----------|--------|
| HTF aligned with breakout direction | **+15** |
| HTF counter to breakout | **−15** (`countertrend_penalty`) |
| `block_countertrend=true` | Blocks BUY/SELL → **WAIT** |

**Default:** `block_countertrend=false` — countertrend trades are **penalized, not blocked**.

### Example Alignment

```text
H1 Bullish + M15 Bullish Breakout + M5 Bullish Retest = Strong BUY candidate
→ ✅ Implemented via +15 HTF alignment bonus
```

```text
H1 Bearish + M15 Bullish Breakout = Lower confidence / countertrend BUY
→ ✅ Implemented via −15 countertrend penalty (not hard block by default)
```

**Assessment:** ⚠️ HTF exists as a **simple bias score**, not true market structure (no swing structure, BOS, CHoCH, premium/discount). It does **not** gate box detection or breakout.

---

## 11. Optional Confirmations

```text
Liquidity Sweep     ✅ Implemented — optional scoring (+10); not mandatory
FVG                 ✅ Implemented — optional scoring (+15); uses detect_fvgs on M5
iFVG                ❌ Not Implemented — no try_invert_fvg / iFVG logic in box module
ATR Expansion       ✅ Implemented — optional scoring (+10); on M15 box candles
RSI                 ❌ Not Implemented
Volume              ✅ Implemented — optional scoring (+10); on M15; skipped if volume=0
Market Structure    ⚠️ Partial — htf_bias only; optional scoring (+15 / −15)
Momentum            ❌ Not Implemented (no RSI/MACD/etc.)
Strong breakout body ✅ Implemented — +10 if body_ratio ≥ 0.65
```

None of these are **mandatory filters** except what retest mode + `minimum_signal_score` indirectly require.

---

## 12. Confidence / Scoring System

**File:** `backend/app/analysis/box_theory/scorer.py` → `score_signal()`

### Score Components

```text
Valid Box (quality ≥ 50)              +15
Breakout / breakdown close            +40
Strong breakout body (≥ 0.65)         +10
Retest detected                       +10
Retest confirmed                      +10
Liquidity sweep                       +10
FVG confirmed                         +15
HTF aligned                           +15
HTF countertrend                      −15
ATR expansion                         +10
Volume above avg                      +10
```

**Theoretical max:** ~145 before cap → **capped at 100**.

### Quality Bands

```text
LOW         0 – 49
MODERATE   50 – 69
HIGH       70 – 84
VERY HIGH  85 – 100
```

**BUY/SELL threshold:** `minimum_signal_score = 70` (default).

**Note:** Early exits (`WATCH`, `FORMING`, traps) use **scaled box quality** (×0.4, ×0.6), not the full scorer.

---

## 13. Signal States

### `BoxStatus` (market phase)

| Status | Condition |
|--------|-----------|
| `FORMING` | No box **or** `box.age_candles < min_box_candles` |
| `VALID` | Box valid, no breakout |
| `BREAKOUT_UP` / `BREAKOUT_DOWN` | Breakout found (intermediate before retest/scoring) |
| `RETESTING` | Breakout + retest required + (no retest **or** unconfirmed retest) |
| `CONFIRMED_BULLISH` / `CONFIRMED_BEARISH` | Breakout + passes retest gate + score ≥ 70 |
| `BULL_TRAP` / `BEAR_TRAP` | Fakeout detected (with/without breakout) |
| `EXPIRED` | `box.age_candles > max_box_age_candles` (80) — **can override BUY/SELL** |
| `INVALIDATED` | **Enum exists but never set in service.py** |

### `SignalDecision` (action)

| Signal | Condition |
|--------|-----------|
| `WAIT` | No box; forming; waiting for retest; unconfirmed retest; score < 70; blocked countertrend; insufficient candles |
| `WATCH` | Valid box, no breakout |
| `BUY` | Bullish breakout + retest rules passed + confidence ≥ 70 + not expired/blocked |
| `SELL` | Bearish breakout + retest rules passed + confidence ≥ 70 + not expired/blocked |
| `INVALID` | Trap detected; box expired (overrides prior BUY/SELL) |

**Gap:** Expiration runs **after** BUY/SELL assignment and can flip a confirmed signal to `INVALID` in the same response.

---

## 14. Repainting / Look-Ahead Bias

### Good Practices

- Uses closed OHLC arrays only (no explicit future bars).
- `validate_candles()` enforces sorted, unique timestamps.
- No peeking at `candles[i+1]` inside detectors.

### Concerns

1. **Box `end_time` = last bar of span = last bar in lookback window**  
   Breakout requires `c.time > box.end_time`. On a single synchronized M15 array, **no bar can satisfy that** unless a **new** bar is appended on a later evaluation. Live behavior depends on **re-running** with an extended array each bar.

2. **Breakout on M15, retest on M5**  
   On one snapshot, M5 can contain bars **newer** than the last M15 bar while breakout still can't fire (M15-only). Multi-TF alignment is inconsistent.

3. **First-breakout-wins**  
   `detect_breakout()` returns the **earliest** post-box breakout in the array, not the latest cycle. Re-analyzing full history can **revive old breakouts**.

4. **Best-span box re-selection**  
   Each call may pick a **different** box span/quality winner — no sticky box ID across evaluations.

5. **Retest auto-confirm at `confirmation_candles=1`**  
   Can confirm without a true rejection candle.

6. **Tests pass** because they **append** a breakout bar with `time = box.end_time + 60` — that pattern is **not** how live single-pass M15-only data behaves unless the array is extended between runs.

**Look-ahead safety rating:** ⚠️ **Partially safe** — no explicit future-candle cheat, but **stateless re-scan + box/breakout timing** can misrepresent live progression.

---

## 15. Duplicate Signals

| Aspect | Behavior |
|--------|----------|
| **Box identity** | `BOX-{start_time}-{end_time}` string; changes when best span changes |
| **Signal identity** | `{symbol}\|{box.start}\|{box.end}\|{direction}\|{last_event}` |
| **Backend state machine** | ❌ None — stateless per call |
| **History** | In-memory deque (`history.py`); overwrites if same `signal_id` |
| **Repeated BUY/SELL** | ✅ Possible on each analyze if conditions still met |
| **Discord dedupe** | ✅ In-memory `signal_id` set + cooldown (`box_discord_notify.py`); lost on restart |
| **Telegram** | ❌ Not implemented for Box Theory |

---

## 16. Final Architecture Assessment

```text
BOX THEORY BACKEND AUDIT

Overall Structure:          ⚠️ Partially Correct

HTF Structure:              ⚠️ Partially Correct  (simple bias, not true structure)
Box Detection:              ✅ Correct             (rules implemented; sticky ID missing)
Breakout Logic:             ⚠️ Partially Correct  (close-based ✅; wrong TF; timing issue)
Retest Logic:               ⚠️ Partially Correct  (M5 retest ✅; weak confirm; TF split)
Fakeout Protection:         ✅ Correct             (traps block signals)
Liquidity Integration:      ⚠️ Partially Correct  (scoring only; after breakout; M15)
FVG/iFVG Integration:       ⚠️ Partially Correct  (FVG only; no iFVG)
Signal Scoring:             ✅ Correct             (documented point system)
Risk Management:            ✅ Correct             (SL/TP/RR; only on BUY/SELL)
Duplicate Protection:       ⚠️ Partially Correct  (Discord only; no engine state)
Discord Integration:        ⚠️ Partially Correct  (separate webhook; needs main Discord enabled)
Look-Ahead Safety:          ⚠️ Partially Correct  (stateless rescan + box/breakout timing)
```

---

## 17. Comparison vs Recommended Architecture

### Recommended Architecture

```text
             H1
      MARKET STRUCTURE
      Bull / Bear / Neutral
              │
              ▼
             M15
        BOX DETECTION
       High / Mid / Low
              │
              ▼
      LIQUIDITY CONTEXT
    Sweep / No Sweep
              │
              ▼
        BREAKOUT CLOSE
      Above / Below Box
              │
              ▼
             M5
          RETEST
              │
              ▼
     ENTRY CONFIRMATION
       Rejection Candle
       FVG / iFVG
       Momentum
              │
              ▼
        SIGNAL SCORING
              │
              ▼
      ┌───────┴────────┐
      │                │
    < Threshold      >= Threshold
      │                │
     WAIT            BUY/SELL
```

### Mismatch Table

| # | Recommended | Backend now | Severity | File / function to change |
|---|-------------|-------------|----------|---------------------------|
| 1 | H1 structure **before** box | HTF scored **after** breakout | **MEDIUM** | `service.py` — reorder; optional HTF gate |
| 2 | M15 box only | ✅ M15 box | — | — |
| 3 | M5 **breakout close** | M15 breakout | **HIGH** | `service.py` L89 → use `entry_c`; `breakout.py` |
| 4 | Liquidity **before** breakout | Sweep **after** breakout, before retest | **MEDIUM** | `service.py` L138 ordering |
| 5 | M5 retest + rejection | M5 retest ✅; weak confirm at 1 bar | **MEDIUM** | `retest.py` L38–46 |
| 6 | iFVG optional confirm | FVG only via `detect_fvgs` | **MEDIUM** | `service.py` L141–148; reuse `try_invert_fvg` |
| 7 | RSI / momentum | Not implemented | **LOW** | New module or reuse existing indicators |
| 8 | Sticky box lifecycle | Re-picks best span every call | **HIGH** | New state store or `service.py` |
| 9 | Box ends **before** breakout bar | Box ends at last window bar | **HIGH** | `detector.py` — exclude current bar or fix `end_time` |
| 10 | `INVALIDATED` status | Enum unused | **LOW** | `service.py` |
| 11 | `chase_max_atr` filter | Config unused | **LOW** | `service.py` |
| 12 | Countertrend block | Penalty only (default) | **LOW** | `types.py` default / `service.py` |
| 13 | Discord standalone | Requires main Discord enabled | **MEDIUM** | `discord_notify.py` L298–299 |
| 14 | Telegram alerts | Config flag only | **LOW** | `telegram_notify.py` |
| 15 | Expiration after signal | Can nullify BUY/SELL same tick | **MEDIUM** | `service.py` L209–212 ordering |

---

## Summary

The backend **does implement** a recognizable Box Theory pipeline: box touches, ATR height, inside ratio, **close-based** breakout with wick filter, optional retest, traps, sweep/FVG/HTF/volume/ATR scoring, and risk output.

It **does not yet fully match** the intended **H1 → M15 box → M5 breakout/retest** architecture. The largest gaps are:

1. **Breakout on M15 instead of M5**
2. **Box `end_time` vs breakout timing** on a single candle array
3. **Stateless re-scan** (no persistent box/signal lifecycle)
4. **HTF = simple bias**, not institutional structure
5. **FVG only**, no iFVG
6. **No RSI/momentum**

When ready to modify the strategy, the highest-impact fixes are **`detector.py` + `service.py` (box end / lifecycle)** and **moving breakout to M5 (`breakout.py` + `service.py`)**.

---

## Key File Paths

```
backend/app/analysis/box_theory/service.py     # orchestrator
backend/app/analysis/box_theory/detector.py    # box detection
backend/app/analysis/box_theory/breakout.py
backend/app/analysis/box_theory/retest.py
backend/app/analysis/box_theory/fakeout.py
backend/app/analysis/box_theory/liquidity.py
backend/app/analysis/box_theory/scorer.py
backend/app/analysis/box_theory/risk.py
backend/app/analysis/box_theory/types.py
backend/app/box_discord_notify.py
backend/app/routers/api.py
docs/BOX_THEORY.md                             # user-facing strategy docs
```
