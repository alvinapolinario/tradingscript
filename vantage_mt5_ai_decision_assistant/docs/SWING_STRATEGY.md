# Swing Strategy Engine

Advisory-only swing trade validation for **XAUUSD / Gold**. Never places MT5 orders.

## Pipeline (14 steps)

1. Market structure (HH/HL/LH/LL, range, expansion/compression)
2. Trend classification (Strong Bullish → Strong Bearish) + trend score
3. Swing identification (ATR-filtered pivots on H4/H1)
4. SMC validation (BOS, liquidity grab, EQH/EQL, OB, FVG, premium/discount)
5. Pullback quality (depth % vs max threshold)
6. Momentum (RSI H1, MACD M15, body strength, volume, ATR expansion)
7. Breakout validation (body close, no immediate rejection)
8. AI confidence scoring (weighted multi-factor)
9. Entry quality (Excellent → Avoid)
10. Risk levels (SL, invalidation, TP1–TP3, R:R)
11. Trade decision (STRONG SWING BUY/SELL, SWING BUY/SELL, WAIT, NO TRADE)
12. Market explanation narrative
13. On-chart HUD + web desk
14. Multi-confirmation gating rules

## EA inputs (groups AK–AO)

| Group | Purpose |
|-------|---------|
| AK | Enable, **Trade mode (Swing / Scalping)**, Gold-only gate |
| AL | D1, H4, H1, M15, M5 timeframes |
| AM | Swing depth, ATR, pullback limits |
| AN | Min confidence, min R:R, RSI/MACD/volume thresholds |
| AO | HUD, chart objects, debug |

## Integration

- Heartbeat key: `swing_strategy`
- API: `GET /api/v1/swing-strategy/status`
- Web desk: `/swing-strategy`

## Files

- `MQL5/Include/VantageAI/VantageSwingStrategyTypes.mqh`
- `MQL5/Include/VantageAI/VantageSwingStrategy.mqh`
- `backend/app/static/swing-strategy.html`
- `backend/tests/test_swing_strategy_*.py`
