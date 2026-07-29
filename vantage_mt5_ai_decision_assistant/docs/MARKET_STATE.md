# Institutional Market State Engine v2

Advisory-only lifecycle intelligence for **XAUUSD / Gold**. Never places, modifies, or closes MT5 orders.

## Architecture

All engines publish through a single orchestrator:

```
SwingEngine → MarketStructureEngine → TrendlineEngine → BreakoutEngine
→ SupportResistanceEngine → RetestEngine → LiquidityEngine → MarketContextEngine
→ MachineLearningEngine → ScoringEngine → Dashboard / Web desk
```

## EA inputs (groups AG–AJ)

| Group | Purpose |
|-------|---------|
| AG | Enable, Gold-only gate, symbol aliases |
| AH | HTF/execution timeframes (H4, H1, M15, M5, M1) |
| AI | Swing/BOS/trendline/retest detection thresholds |
| AJ | On-chart HUD, chart objects, debug logging |

## Heartbeat blob

Key: `market_state_engine` (distinct from legacy `market_state` trend label on the main decision feed).

Endpoint: `GET /api/v1/market-state/status`  
Web desk: `/market-state` (includes **Market Timeline** widget)

## Lifecycle labels

Dashboard and web UI never show binary `None`. States include:

- **Waiting**, **Potential**, **Confirmed**, **Retesting**, **Continuation**, **Failed**, **Approaching**, **Waiting Retest**, **Confirmed Flip**

## Files

| File | Role |
|------|------|
| `MQL5/Include/VantageAI/VantageMarketStateTypes.mqh` | Enums, config, result structs |
| `MQL5/Include/VantageAI/VantageMarketStateManager.mqh` | Central orchestrator + inline engines |
| `backend/app/static/market-state.html` | Web desk with timeline |
| `backend/tests/test_market_state_*.py` | Static + API passthrough tests |

## Deploy

1. Recompile `VantageMT5AIDecisionAssistant.mq5` in MT5.
2. Attach EA on **XAUUSD** with groups AG–AJ enabled.
3. VPS: `bash /var/www/tradingscript/vantage_mt5_ai_decision_assistant/deploy/update-from-github.sh`
4. Hard refresh browser (Ctrl+F5) on `/market-state`.
