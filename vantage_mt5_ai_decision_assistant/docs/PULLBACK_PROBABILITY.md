# Pullback Probability Analyzer

Advisory-only H1 / M15 / M5 probability desk. Computed on the MT5 EA (`VantagePullback.mqh`), mirrored on heartbeat as top-level `"pullback"`, and shown on chart HUD + web **Pullback Desk** (`/pullback`).

Does **not** place, modify, or cancel orders. Does **not** change SETUP_OK, Signal Center accept rules, or Analyzer Take/Ignore.

## Surfaces

| Surface | What |
|---------|------|
| Chart HUD | Compact `VAI_pb*` rows (trend, 4 probs, scores, state, reason) |
| Chart objects | `VAI_PB_*` HLines: S/R, target band, invalidation |
| Heartbeat | `"pullback": { ... }` (never nested under `"strategy"`) |
| Web | `GET /pullback` → polls `GET /api/v1/pullback/status` |

## Cadence

- Full evaluate on new **M5 closed** bar (and timer if M5 closed since last eval).
- Dashboard refreshes from cached snap (~5s).
- Heartbeat includes last snap (~15s).

## Probabilities

Four integers (approx. sum 100%): **Pullback**, **Continuation**, **Consolidation**, **Reversal**.

Hard rules (EA):

- RSI extremes raise **pullback** against the trend — not BUY/SELL.
- Extreme extension raises pullback + DO NOT CHASE; alone does not raise reversal.
- Reversal needs HTF structure break + CHoCH + hold beyond key EMA; otherwise reversal is capped.
- H1 vs M15 disagreement → CONFLICTING TIMEFRAMES.
- M5 bounce alone never upgrades to REVERSAL CONFIRMED.

## Market states (examples)

- `TREND ACTIVE – WAIT FOR PULLBACK`
- `DO NOT CHASE – MARKET EXTENDED`
- `PULLBACK DEVELOPING`
- `CONSOLIDATION`
- `POSSIBLE REVERSAL – UNCONFIRMED`
- `REVERSAL CONFIRMED`
- `CONFLICTING TIMEFRAMES`
- `INSUFFICIENT DATA`

## EA inputs

Groups **I–L** on `VantageMT5AIDecisionAssistant.mq5`: timeframes, indicators, weights, alerts/display (`InpPullbackEnable`, `InpPbShowDash`, `InpPbShowChartObj`, thresholds, UTC offset).

## MT5 sync / recompile

VPS `update-from-github.sh` updates the API only. On Windows MT5:

1. Copy `MQL5/Include/VantageAI/VantagePullback.mqh` (and updated Dashboard / Expert) into the terminal data folder `MQL5\Include\VantageAI\` and `MQL5\Experts\`.
2. MetaEditor → compile `VantageMT5AIDecisionAssistant.mq5`.
3. Reload EA on the chart.
4. Wait for a new M5 close + heartbeat; open `/pullback`.

Experts log should show pullback evaluate activity; web desk shows “unsupported” until that build heartbeats with `"pullback"`.

## Manual test scenarios (Strategy Tester / live)

Log factor scores / state for:

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
15. Heartbeat JSON size stays compact; `/pullback` updates after ~15s  
16. No `OrderSend` / no change to SETUP_OK or signal ledger after Take/Ignore  

## Backend regression

```bash
cd vantage_mt5_ai_decision_assistant/backend
python -m pytest tests/test_pullback_status.py tests/test_pending_orders.py tests/test_analyzer.py -q

# repo-root advisory suite (needs PYTHONPATH=backend)
cd ..
PYTHONPATH=backend python -m pytest tests/test_advisory_enforcement.py -q
```
