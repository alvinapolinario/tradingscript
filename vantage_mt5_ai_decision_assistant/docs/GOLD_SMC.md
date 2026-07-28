# Gold SMC Intelligence Engine

Advisory-only Smart Money Concepts desk specialized for **spot Gold (XAUUSD / GOLD)**.

> Smart Money Concepts are interpretive market-analysis concepts. The module
> provides rule-based technical analysis and cannot identify actual institutional
> orders or guarantee future price movement.

## Phase status

| Phase | Status |
|-------|--------|
| 1 — Types, strict symbol gate, EA disable path, heartbeat/web scaffold | **Done** |
| 2 — Structure (swings, BOS/CHoCH/MSS, HTF priority) | **Done** |
| 3 — Liquidity map & sweeps | **Done** |
| 4 — Displacement, FVG, order blocks | **Done** |
| 5 — Premium/discount, OTE, inducement, PO3 | **Done** |
| 6 — Scoring, setup phases, narrative | **Done** |
| 7 — Full HUD / chart objects / alerts | **Done** |
| 8 — Scenario tests, performance polish, documentation | **Done** |

## What it does

On approved Gold charts the EA computes a multi-timeframe SMC map (structure → liquidity → POI → PD/OTE/PO3 → confluence score), draws optional `VAI_GSMC_*` objects, may fire deduped alerts, and ships a top-level `"gold_smc"` blob on heartbeat for `/gold-smc`.

It never places, modifies, or cancels orders and does not affect SETUP_OK or the Signal Center.

## Why Gold only

Gold behavior (session liquidity, ATR swings, PDH/PDL reactions) differs from FX/crypto.
The module **rejects** all non-approved instruments and never produces an SMC setup for them.

## Symbol validation (strict)

Default aliases: `XAUUSD,GOLD` (configurable comma list).

| Symbol | Result |
|--------|--------|
| XAUUSD, XAUUSD.a, XAUUSDm, m.XAUUSD | Accept |
| GOLD, GOLD.pro | Accept |
| EURUSD, XAGUSD, XAUEUR, BTCUSD, US30, OIL, GOLDENCOIN | Reject |

Rejected message:

`Gold SMC Intelligence Engine is disabled. This module supports XAUUSD/Gold only.`

Python mirror: `backend/app/analysis/gold_symbol_validator.py`.  
**Do not** use `VantageNameLooksLikeGold()` for this gate.

## SMC terminology (engine meanings)

| Term | Engine meaning |
|------|----------------|
| External structure | Higher-significance swings (`swing_left/right_ext`) |
| Internal structure | Faster swings (`swing_left/right_int`) |
| BOS | Body close beyond structure with displacement (default mode) |
| CHoCH | Early character change — warning, not full reversal |
| MSS | Stronger displacement + meaningful structure shift |
| BSL / SSL | Buy-side / sell-side liquidity pools |
| Sweep | Raid of liquidity; wick-only ≠ confirmed; not auto-reversal |
| FVG | Three-candle imbalance ≥ min ATR; tiny gaps rejected |
| Order block | Opposite candle before displacement; random opposites rejected |
| Breaker | Failed OB that flips after break |
| Premium / Discount | Location in dealing range relative to EQ |
| OTE | Fib confluence band only — never a standalone setup |
| PO3 | Session accumulation → manipulation → distribution heuristic |

## Phase rules (summary)

- **2 Structure:** closed bars; M5 cannot override H1; H4 preferred on H4/H1 conflict.
- **3 Liquidity:** PDH/PDL, PWH/PWL, Asian/London/NY (UTC + offset), equal H/L, draws/sweeps.
- **4 POI:** M15 displacement, FVG/iFVG/OB/breaker/mitigation; primary POI by quality + bias.
- **5 Context:** dealing range, PD bands, OTE, inducement, optional PO3.
- **6 Setup:** weighted 0–100 score, grades A+…Invalid, named types only if score ≥ gate.
- **7 Visual:** `VAI_GSMC_*` categories + optional alerts (cooldown + event key).
- **8 Polish:** scenario CI, light inter-bar refresh, debug/performance logs, this guide.

## Confidence scoring

Weights (configurable, group **S**): HTF 15, liquidity 12, displacement 12, structure 14, OB 10, FVG 8, PD 7, session 5, PD/PW 4, OTE 4, LTF 6, vol/spread 3.

| Score | Band | Grade |
|------:|------|-------|
| 90–100 | Exceptional | A+ |
| 80–89 | Strong | A |
| 70–79 | Moderate | B |
| 60–69 | Developing/Moderate | C |
| 45–59 | Weak | D |
| &lt;45 | No Valid / Weak | Invalid |

Below `min_setup_score` (default 45) → `No Valid SMC Setup` (candidate kept).

## Non-repainting behavior

- Structure / FVG / OB use `CopyRates(..., shift 1, …)` — **closed bars only**.
- Swings require left **and** right bars to confirm (no future peek).
- Full engine recompute is cached on the last closed **M5** bar.
- Between M5 closes, only **light refresh** updates entry proximity / OTE-in-price (no structure rewrite).
- Zones change status when mitigated/invalidated; origins are not silently moved.
- Chart objects update in place under `VAI_GSMC_*` and clear on deinit / non-gold.

## Performance

- Heavy work runs on new closed M5 (or force).
- ATR handles reused; lookbacks capped (`structure_lookback`, max FVG/OB).
- Chart redraw only when objects enabled; session lines default off to limit clutter.
- Optional `InpGoldSmcDebug` logs `[GoldSMC][PERFORMANCE]` eval timing (not every tick).

## Surfaces

| Surface | Path / key |
|---------|------------|
| Chart HUD | `VAI_tsmc*` |
| Chart objects | `VAI_GSMC_*` |
| Heartbeat | top-level `"gold_smc"` |
| Web desk | `/gold-smc` → `GET /api/v1/gold-smc/status` |
| Nav | Workspace → **Gold SMC** |

## EA input groups

| Group | Content |
|-------|---------|
| M–N | Enable, aliases, TF map, HUD |
| O | Structure |
| P | Liquidity / sessions |
| Q | FVG / OB |
| R | OTE / inducement / PO3 |
| S | Score weights / min score |
| T | Chart categories / alerts / debug |

## Dashboard interpretation

1. Confirm **ACTIVE – GOLD ONLY** (not disabled).
2. Read HTF bias → liquidity draw → primary POI.
3. Check PD / OTE / PO3 confluence.
4. Use **score + grade + setup type**; if `No Valid SMC Setup`, read candidate + reasons against.
5. Entry / invalidation / T1–T3 are analytical only.
6. Last alert is informational (if alerts enabled).

## Configuration tips

- Start with chart objects on, session lines off, alerts off.
- Raise `InpGoldSmcMinScore` if too many weak named setups.
- Align UTC offset / session hours to your broker server time.
- Enable `InpGoldSmcDebug` only while diagnosing (Experts log volume).

## Testing procedure

```powershell
cd vantage_mt5_ai_decision_assistant\backend
$env:PYTHONPATH = "$PWD"
pytest tests/test_gold_smc_status.py tests/test_gold_smc_scenarios.py tests/test_gold_smc_static.py -q
```

Coverage:

1. Symbol accept/reject matrix (scenarios 1–5 + validator).
2. Forty synthetic scenario blobs (structure → setup → targets) via `gold_smc_logic.py`.
3. Static audits: modules present, no `OrderSend`/`CTrade`, closed-bar `CopyRates`, M5 cache, EA wiring, docs disclaimer.
4. Manual MT5: compile EA → attach XAUUSD → ACCEPTED log → objects → `/gold-smc` heartbeat; attach EURUSD → DISABLED.

## Scenario checklist (1–40)

1 XAUUSD accept · 2 suffix accept · 3 GOLD accept · 4 EURUSD reject · 5 XAGUSD reject ·  
6 Bullish H4/H1 · 7 Bearish H4/H1 · 8 H4/H1 conflict · 9 M5 correction in bearish H1 ·  
10 Bull BOS · 11 Bear BOS · 12 Wick≠BOS · 13 Bull CHoCH · 14 Bear CHoCH ·  
15 Bull MSS after SSL sweep · 16 Bear MSS after BSL sweep ·  
17 Bull FVG · 18 Bear FVG · 19 Tiny FVG reject · 20 Partial mitigate · 21 Full mitigate · 22 iFVG ·  
23 Bull OB · 24 Bear OB · 25 Random OB reject · 26 Breaker ·  
27 Premium sell · 28 Discount buy · 29 OTE confluence ·  
30 Asian sweep · 31 London PO3 · 32 NY reversal · 33 PDH sweep · 34 PDL sweep ·  
35 Exceptional displacement · 36 Spread warning · 37 No valid setup · 38 Invalidated · 39 T1 reached ·  
40 Non-repaint closed-bar narrative.

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Desk says unsupported | Recompile EA with Gold SMC includes; wait for heartbeat |
| Always DISABLED | Chart not Gold alias; check `InpGoldSmcAliases` |
| No chart objects | `InpGoldSmcShowChartObj` + category toggles |
| No alerts | `InpGoldSmcAlertEnable` + popup/push/sound |
| Score stuck Invalid | Incomplete confluence (no POI / HTF conflict / EQ) |
| Session times wrong | UTC offset + Asian/London/NY hour inputs |
| Log spam | Turn off `InpGoldSmcDebug` |

## MT5 sync

1. Copy `VantageGoldSMC*.mqh` + Expert/Dashboard into terminal `MQL5`.
2. MetaEditor → compile `VantageMT5AIDecisionAssistant.mq5`.
3. Reload EA; expect `[GoldSMC][SYMBOL] ACCEPTED … (Phase 8)`.
4. Open `/gold-smc` after VPS update + heartbeat.

## Known limitations

- Interpretive heuristics — not institutional-order detection.
- Session DST is manual via UTC offset / hours.
- Targets / R:R are analytical estimates — never auto-traded.
- Chart clutter if all session lines enabled.
- Full candle-by-candle MQL5 strategy tester suite is out of band; CI uses Python scenario contracts + static audits.
