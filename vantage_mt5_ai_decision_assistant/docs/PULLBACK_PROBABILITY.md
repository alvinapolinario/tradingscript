# Pullback Probability Analyzer

Advisory-only multi-timeframe probability desk for **H1 / M15 / M5**.

Computed on the MT5 EA (`VantagePullback.mqh`), sent on heartbeat as top-level `"pullback"`, and shown on the chart HUD plus the web **Pullback Desk** (`/pullback`).

> This module estimates the relative likelihood of pullback, continuation, consolidation, or reversal using rule-based technical factors. It does not predict the future, place orders, or identify institutional intent.

## Advisory invariant

- Never opens, modifies, partially closes, or closes positions (`OrderSend` / `CTrade` forbidden).
- Does **not** change SETUP_OK, Signal Center accept rules, or Analyzer Take/Ignore.
- Probabilities and levels are decision-support only — not trade instructions.

## What it does

On each **closed M5** bar the EA:

1. Builds indicator snapshots on H1, M15, and M5 (EMA 20/50/200, RSI, ATR, Bollinger, ADX, swings).
2. Derives a **dominant trend** (H1 weighted highest).
3. Scores four probabilities that normalize to ~100%: **Pullback**, **Continuation**, **Consolidation**, **Reversal**.
4. Maps a human **market state** string, S/R, pullback target band, and invalidation.
5. Optionally draws chart lines and fires deduped alerts.
6. Serializes the result into heartbeat `"pullback"` for `/pullback`.

## Surfaces

| Surface | Path / key |
|---------|------------|
| Chart HUD | Compact `VAI_tpb*` rows (trend, probs, scores, state, reason) |
| Chart objects | `VAI_PB_*` HLines: support, resistance, target lo/hi, invalidation |
| Heartbeat | Top-level `"pullback": { ... }` (never nested under `"strategy"`) |
| Web desk | `/pullback` → polls `GET /api/v1/pullback/status` (~11s) |
| Nav | Workspace → **Pullback Desk** |
| Symbol selector | Same monitor pair list as other desks (`POST /api/v1/monitor/select-symbol`) |

## Cadence / non-repaint

| Event | Behavior |
|-------|----------|
| New **M5 closed** bar | Full evaluate (indicators + probs + state) |
| Same M5 bar | Cached result returned (no recompute) |
| Dashboard timer (~5s) | Reads cached snap for HUD |
| Heartbeat (~15s) | Includes last snap |
| Deinit / re-init | Chart objects cleared / recreated |

Analysis uses **closed bars** (`CopyRates` / buffers from shift 1). Swings require left and right confirmation bars.

## Architecture

```
VantageMT5AIDecisionAssistant.mq5
  └─ CVantagePullback (VantagePullback.mqh)
        ├─ FillTf(H1/M15/M5) → EMA/RSI/ATR/BB/ADX/structure/candles/div
        ├─ Score probs + Normalize4
        ├─ MapState → market_state
        ├─ UpdateChart → VAI_PB_*
        ├─ MaybeAlert → popup / push / sound
        └─ ToJson → heartbeat "pullback"
Backend
  ├─ HeartbeatRequest.pullback → monitor_state
  ├─ GET /api/v1/pullback/status (passthrough)
  └─ GET /pullback → static/pullback.html
```

## Indicators (per TF)

| Indicator | Default | Role |
|-----------|---------|------|
| EMA fast / slow / long | 20 / 50 / 200 | Trend stack, distance, invalidation fallback |
| RSI | 14 (OB 70 / OS 30) | Extremes → pullback vs trend; mid-range → consolidation |
| ATR | 14 | Extension, EMA distance, S/R room |
| Bollinger | 20, 2σ | Outside→inside reclaim; squeeze; band walk |
| ADX + DI | 14 (min 20) | Trend strength / softening / range |
| Swings | L=3, R=3 | Structure, BOS/CHoCH heuristic, S/R |

## Dominant trend

Weighted vote:

`H1×3 + M15×2 + M5×1`

- Sum ≥ 2 → bullish dominant  
- Sum ≤ −2 → bearish dominant  
- Else fall back to H1 (then M15)

H1 vs M15 opposite (both non-zero) → **CONFLICTING TIMEFRAMES**.

Trend labels include Strong / Moderate bullish or bearish from EMA stack + ADX.

## Probabilities

Four scores start from small bases, accumulate weighted factors, then **Normalize4** so they sum to ~100.

| Probability | Meaning |
|-------------|---------|
| **Pullback** | Mean-reversion / dig into the trend is more likely than chasing |
| **Continuation** | Impulse with the dominant trend more likely |
| **Consolidation** | Range / squeeze / low ADX |
| **Reversal** | Structural turn — **capped unless HTF CHoCH/BOS** |

### Hard rules

1. RSI extremes **against** the trend raise **pullback**, not BUY/SELL signals.
2. High **extension** raises pullback and can force **DO NOT CHASE**; alone does **not** raise reversal.
3. Reversal without M15/H1 CHoCH is **capped** (≤ ~28 before normalize).
4. M5 bounce / M5-only structure shift ≠ HTF reversal.
5. Divergence is supporting evidence only (splits into pullback + some reversal weight).

### Factor weights (group K — relative)

| Weight input | Default | Typical effect |
|--------------|--------:|----------------|
| `InpPbWRsiExtreme` | 10 | OS in bear / OB in bull → pullback |
| `InpPbWRsiRecover` | 8 | RSI turning back from extreme; mid-trend RSI → continuation |
| `InpPbWExtension` | 15 | ATR-normalized extension → pullback |
| `InpPbWBb` | 10 | Band reclaim → pullback; squeeze → cons; band walk + rising ADX → cont |
| `InpPbWEmaDist` | 10 | \|price−EMA20\| ≥ 1.2 ATR → pullback |
| `InpPbWCandle` | 8 | Pin / engulf rejection against trend → pullback |
| `InpPbWDivergence` | 7 | RSI divergence (supporting) |
| `InpPbWSr` | 7 | Room to counter-trend S/R (≥ 0.6 ATR) |
| `InpPbWStructure` | 10 | M5-only shift → pullback; M15/H1 CHoCH → reversal |
| `InpPbWAdx` | 8 | Rising strong ADX → cont; falling → pb/cons; low → cons |
| `InpPbWMtf` | 7 | H1+M15 aligned → cont; conflict → cons (+ slight rev) |

### Extension score

`0.55×M15_extension + 0.45×M5_extension` (ATR-normalized stretch from local equilibrium / bands).

### Pullback quality (0–100)

Composite of RSI extreme, extension, BB reclaim, rejection candle, S/R room, and H1/M15 alignment — how “clean” a pullback setup looks, independent of raw probability.

### Trend strength score

`0.5×H1 + 0.35×M15 + 0.15×M5` trend-strength composites.

## Market states

| State | Typical trigger |
|-------|-----------------|
| `TREND ACTIVE – WAIT FOR PULLBACK` | Aligned trend, not extended enough to chase |
| `DO NOT CHASE – MARKET EXTENDED` | Extension ≥ threshold and continuation not dominant |
| `PULLBACK DEVELOPING` | High pullback + rejection candle + meaningful extension |
| `CONSOLIDATION` | Low ADX / squeeze / mid RSI emphasis |
| `POSSIBLE REVERSAL – UNCONFIRMED` | Elevated reversal without full HTF confirmation path |
| `REVERSAL CONFIRMED` | High reversal with HTF structure evidence in MapState |
| `CONFLICTING TIMEFRAMES` | H1 vs M15 disagreement |
| `INSUFFICIENT DATA` | Missing history / indicators |

Exact MapState priority also considers probability thresholds (`thr_pullback`, `thr_continuation`, `thr_reversal`, `thr_extension`).

## Levels

| Field | Construction |
|-------|----------------|
| Nearest support / resistance | Recent M15 swing low/high (fallback EMA50) |
| Pullback target band | Span between M15 EMA20 and BB middle |
| Invalidation | Bearish dominant → swing high (else EMA50); bullish → swing low (else EMA50) |

These are analytical ranges — not broker stop/limit orders.

## Chart objects (`VAI_PB_*`)

Enabled by `InpPbShowChartObj` (default on):

| Key | Color (approx) | Meaning |
|-----|----------------|---------|
| `sup` | Dodger blue | Nearest support |
| `res` | Orange red | Nearest resistance |
| `inv` | Magenta | Invalidation |
| `tlo` / `thi` | Gold | Pullback target band |

Objects update in place; cleared on release/deinit.

## Alerts (group L)

Off by default for popup/push/sound. Priority (first match wins per evaluate):

1. Extension ≥ `InpPbThrExtension`  
2. Else pullback ≥ `InpPbThrPullback`  
3. Else continuation ≥ `InpPbThrContinue`  
4. Else reversal ≥ `InpPbThrReversal`

Dedup: event key includes M5 bar time + type; cooldown `InpPbAlertCoolSec` (default 300s). Push suppressed in signal-replay mode.

## EA inputs

| Group | Contents |
|-------|----------|
| **I** | `InpPullbackEnable`, H1/M15/M5 timeframes |
| **J** | EMA/RSI/ATR/BB/ADX/swing sizes |
| **K** | Factor weights |
| **L** | Alerts, thresholds, UTC offset, chart objects, HUD |

Master switch: `InpPullbackEnable` (default `true`).

`InpPbUtcOffsetHrs` adjusts session labeling (Asian / London / NY style notes) relative to server time.

## Heartbeat JSON (key fields)

```json
{
  "version": "1.0",
  "advisory_only": true,
  "valid": true,
  "dominant_direction": 1,
  "dominant_trend": "Moderate Bullish",
  "pullback_probability": 62.0,
  "continuation_probability": 18.0,
  "consolidation_probability": 12.0,
  "reversal_probability": 8.0,
  "extension_score": 71.0,
  "pullback_quality": 55.0,
  "trend_strength": 64.0,
  "market_state": "DO NOT CHASE – MARKET EXTENDED",
  "explanation": "…",
  "short_reason": "DO NOT CHASE – MARKET EXTENDED",
  "nearest_support": 3300.0,
  "nearest_resistance": 3350.0,
  "pullback_target_low": 3310.0,
  "pullback_target_high": 3320.0,
  "invalidation": 3360.0,
  "reasons_positive": "…;",
  "reasons_negative": "…;",
  "session": "London"
}
```

Backend stores the blob as-is (`pullback_supported` becomes true once present).

## How to read the desk

1. Confirm EA online and **pullback supported** (recompiled build).
2. Read **market state** first — that is the operational headline.
3. Compare the four probabilities; the largest is the bias, not a certainty.
4. Check **extension** — high + DO NOT CHASE means wait, don’t market-chase.
5. Use target band / S/R / invalidation as context for a potential pullback zone.
6. Read **reasons positive / negative** for explainability.
7. If H1≠M15 → treat as conflicting; lower confidence in directional calls.

### Interpretation cheat sheet

| You see | Do this (advisory) |
|---------|-------------------|
| High pullback + extended | Wait for dig / reclaim; don’t chase |
| High continuation + ADX rising | Trend may keep going; pullback less urgent |
| High consolidation | Expect chop; reduce narrative conviction |
| High reversal without HTF CHoCH | Treat as watch only |
| CONFLICTING TIMEFRAMES | Stand aside or wait for alignment |

## Web desk features

- KPI tiles: Pullback / Continuation / Consolidation / Reversal  
- Scores: Extension, Pullback quality, Trend strength  
- Levels grid + explanation + reason lists  
- **Symbol selector** for multi-pair monitor store  

URL: `http://<host>:8000/pullback`

## MT5 sync / recompile

VPS `update-from-github.sh` updates the API/static pages only. On Windows MT5:

1. Copy into the terminal data folder:
   - `MQL5/Include/VantageAI/VantagePullback.mqh`
   - `VantageDashboard.mqh` (HUD rows)
   - `Experts/VantageMT5AIDecisionAssistant.mq5`
2. MetaEditor → compile `VantageMT5AIDecisionAssistant.mq5`.
3. Reload the EA on the chart.
4. Wait for a new M5 close + heartbeat; open `/pullback`.

Experts log should mention Pullback enable/evaluate. The desk shows **unsupported** until a build heartbeats with `"pullback"`.

## Testing

### Backend regression

```powershell
cd vantage_mt5_ai_decision_assistant\backend
$env:PYTHONPATH = "$PWD"
pytest tests/test_pullback_status.py -q
```

Covers: offline empty, unsupported without blob, heartbeat passthrough, page + symbol selector, heartbeat field accept.

### Manual scenarios (Strategy Tester / live)

Log probs / state for:

1. Strong H1 bull + M15 bull + M5 overbought extended → high pullback, DO NOT CHASE  
2. Strong H1 bear + RSI oversold → high pullback (not auto-buy)  
3. Aligned H1/M15/M5 + ADX rising + no extension → higher continuation  
4. Flat ADX + BB squeeze → consolidation  
5. M5 CHoCH only, H1 intact → reversal capped / unconfirmed  
6. H1 bull vs M15 bear → CONFLICTING TIMEFRAMES  
7. Bullish divergence without HTF break → POSSIBLE REVERSAL – UNCONFIRMED  
8. HTF BOS + CHoCH + hold beyond EMA → REVERSAL CONFIRMED path  
9. Near swing S/R with room → quality ↑  
10. Session dead zone (UTC offset) → note in session field  
11. Candle rejection into pullback zone → PULLBACK DEVELOPING  
12. Extreme extension alone → chase risk, not reversal  
13. Alerts fire once per M5 candle key + cooldown  
14. Chart objects update / clear on deinit (no duplicates)  
15. Heartbeat JSON compact; `/pullback` updates after ~15s  
16. No `OrderSend` / no change to SETUP_OK or signal ledger after Analyzer Take/Ignore  

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Desk “unsupported” | Recompile EA with `VantagePullback.mqh`; wait for heartbeat |
| Always INSUFFICIENT DATA | Warm up history on H1/M15/M5; check symbol has bars |
| No HUD rows | `InpPullbackEnable` + `InpPbShowDash` |
| No chart lines | `InpPbShowChartObj` |
| No alerts | Enable popup/push/sound + thresholds; cooldown |
| Session label wrong | `InpPbUtcOffsetHrs` vs broker server time |
| Probabilities look stuck | Wait for **new M5 close**; same-bar uses cache |

## Known limitations

- Structure / BOS / CHoCH here are lightweight heuristics — not the Gold SMC engine.
- Works on the attached chart symbol (any instrument the EA runs on); not Gold-gated.
- Divergence detection is a simple dual-window RSI compare — supporting only.
- Band “walk” continuation can coexist with high extension — read state + extension together.
- Does not consume news calendar (M5 desk news block is separate).

## Related docs

- Install / VPS: [VANTAGE_SETUP.md](VANTAGE_SETUP.md)  
- Gold SMC (separate desk): [GOLD_SMC.md](GOLD_SMC.md)  
- Module source: `MQL5/Include/VantageAI/VantagePullback.mqh`
