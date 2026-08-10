# Box Theory Strategy

Advisory-only consolidation box strategy: detect range → breakout/breakdown → retest → confirmation → scored BUY/SELL signal. **Never auto-trades.**

## Flow

```
Liquidity sweep (optional)
      ↓
Valid box (touches + inside ratio + ATR height)
      ↓
Breakout candle close (not wick-only)
      ↓
Retest (default BREAKOUT_RETEST_MODE)
      ↓
Price-action confirmation
      ↓
HTF / FVG / volume / ATR scoring
      ↓
BUY / SELL alert (if score ≥ minimum)
```

## Module layout

```
backend/app/analysis/box_theory/
  types.py          — enums, Candle, BoxRange, BoxStrategyConfig
  utils.py          — ATR, candle parsing, body helpers
  detector.py       — detect_box()
  breakout.py       — detect_breakout()
  retest.py         — detect_retest()
  fakeout.py        — BULL_TRAP / BEAR_TRAP
  liquidity.py      — sweep before breakout
  scorer.py         — confidence 0–100
  risk.py           — entry, SL, TP1–3, RR
  service.py        — analyze_box_strategy()
  history.py        — in-memory history ring buffer

backend/app/box_discord_notify.py — dedicated Discord webhook + dedupe
```

Core engine accepts candle arrays only — reusable for backtests:

```python
from app.analysis.box_theory import analyze_box_strategy, candles_from_payload

result = analyze_box_strategy(
    symbol="XAUUSD",
    candles_box=candles_m15,
    candles_entry=candles_m5,
    candles_structure=candles_h1,
    bid=3401.0,
)
```

## Configuration

Environment (Docker `.env` on VPS):

```env
DISCORD_BOX_WEBHOOK_URL=https://discord.com/api/webhooks/...
DISCORD_BOX_ALERTS_ENABLED=true
# Optional — default: BUY_CONFIRMED,SELL_CONFIRMED,BULL_TRAP,BEAR_TRAP
DISCORD_BOX_ALERT_EVENTS=
```

Analyze POST body `config` overrides (same keys as `BoxStrategyConfig`):

| Key | Default | Notes |
|-----|---------|-------|
| `lookback_candles` | 50 | Box scan window |
| `min_box_candles` | 8 | Minimum bars in range |
| `min_touches` | 2 | Per boundary |
| `require_retest` | true | Prefer retest before signal |
| `entry_mode` | BREAKOUT_RETEST_MODE | Or BREAKOUT_MODE |
| `minimum_signal_score` | 70 | Min confidence for BUY/SELL |

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/box-theory/status` | Live EA passthrough + desk links |
| POST | `/api/v1/box-theory/analyze` | Offline analysis from candles |
| GET | `/api/v1/strategies/box/{symbol}` | Compact status |
| GET | `/api/v1/strategies/box/{symbol}/history` | Backend history snapshots |

Desk UI: `/box-theory`

## Discord

Separate webhook from main Vantage alerts. Default events only:

- `BUY_CONFIRMED`
- `SELL_CONFIRMED`
- `BULL_TRAP`
- `BEAR_TRAP`

Duplicate protection via `signal_id` = `symbol|box_start|box_end|direction|event`.

## Assumptions

- Gold / XAUUSD only (same validator as other modules).
- FVG detection reuses `amd_ifvg_logic.detect_fvgs` — no duplicate FVG engine.
- EA heartbeat key `box_theory` is reserved; Python analyze works today without MQL5.
- MQL5: `VantageBoxTheory.mqh` + EA input groups **AT–AW** send live `box_theory` heartbeat JSON.
- History is in-memory per backend process (not persisted to DB).

## Example BUY notification

```
🟢 BOX THEORY — BUY SIGNAL

Symbol: XAUUSD
Box TF: M15 · Entry TF: M5

Box High: 3400.00 · Box Low: 3380.00
Breakout: 3402.50 · Retest: 3400.40
Entry: 3401.20 · Stop Loss: 3395.50
TP1/TP2/TP3 · RR 1:3.2 · Confidence 78/100 — HIGH
HTF Bias: BULLISH · Liquidity Sweep: YES · FVG: YES

Status: ANALYSIS ONLY — NO AUTO TRADE
```

## Tests

```bash
cd backend && pytest tests/test_box_theory_logic.py tests/test_box_theory_status.py tests/test_box_theory_static.py -q
```
