# Liquidity Grab Monitor

Rule-based **buy-side / sell-side liquidity grab** detection for **XAUUSD / Gold** — advisory only, integrated with the Vantage MT5 AI Decision Assistant.

## Overview

The module identifies when price sweeps a recognized liquidity pool, rejects the breakout, displaces in the opposite direction, and optionally confirms a **Market Structure Shift (MSS)**. It deliberately **does not** classify every wick as a confirmed grab.

**No trade execution** — no `OrderSend`, `CTrade`, or position changes.

## Architecture

```
EA (VantageMT5AIDecisionAssistant.mq5)
  ├── Groups U–Z inputs → FillLiquidityGrabConfig()
  ├── MaybeEvalLiquidityGrab() on timer / heartbeat
  └── heartbeat JSON key: liquidity_grab

MQL5
  ├── VantageLiquidityGrabTypes.mqh   — enums, structs, config
  └── VantageLiquidityGrab.mqh        — levels, sweep, state machine, score, chart, alerts

Backend
  ├── GET /api/v1/liquidity-grab/status
  ├── GET /liquidity-grab  (web desk)
  └── monitor_state passthrough: liquidity_grab_supported
```

## State Machine

| State | Label |
|-------|-------|
| IDLE | No active sweep |
| APPROACHING | Price within ATR distance of level |
| SWEPT | Valid penetration beyond level |
| REJECTED | Close back inside / wick rejection |
| DISPLACEMENT_CONFIRMED | Opposite ATR displacement |
| MSS_CONFIRMED | Structural break by close (default) |
| CONFIRMED | Score ≥ threshold + MSS (if required) |
| GENUINE_BREAKOUT | Holds beyond level — grab cancelled |
| FAILED_OR_EXPIRED | Window expired without confirmation |

## Status Labels

- `NO_VALID_SETUP` (0–39)
- `LIQUIDITY_APPROACH` / `LIQUIDITY_TEST` (40–54)
- `LIQUIDITY_SWEEP_UNCONFIRMED` (55–69)
- `LIQUIDITY_GRAB_CONFIRMED` (70–84)
- `HIGH_CONFIDENCE_LIQUIDITY_GRAB` (85–100)
- `GENUINE_BREAKOUT`
- `FAILED_SWEEP`

**Mandatory:** Without MSS, score is capped at **69** when `InpLiqGrabRequireMss=true` (default).

## Scoring Table (defaults)

| Component | Points |
|-----------|--------|
| PDH/PDL/PWH/PWL level | +12 |
| Session high/low | +10 |
| Equal highs/lows | +10 |
| Swing high/low | +8 |
| Valid ATR sweep | +8 |
| Close back inside | +12 |
| Strong rejection wick (≥35%) | +6 |
| Opposite displacement | +12 |
| Internal MSS | +16 |
| External MSS | +8 extra |
| Post-displacement FVG | +5 |
| Elevated tick volume | +4 |
| HTF alignment | +8 |
| London/NY session | +5 |
| Countertrend | −10 |
| News restricted | −10 |
| No close back inside | −12 |

## Default Configuration

| Setting | Default |
|---------|---------|
| Detection TF | M5 |
| Confirmation TF | M5 |
| Secondary confirmation | M15 |
| Context TF | H1 |
| Major context | H4 |
| Swing left/right | 3 / 3 |
| ATR period | 14 |
| Min/max sweep ATR | 0.03 / 0.50 |
| Spread multiplier | 2.0 |
| Equal level ATR mult | 0.08 |
| Min wick ratio | 0.35 |
| Require MSS | true |
| Require close for MSS | true |
| Confirmation window | 5 M5 bars |
| Confirmed threshold | 70 |
| High confidence | 85 |
| News before/after | 15 / 15 min |

## Dashboard

- **On-chart HUD:** prefix `tlg0`–`tlg6` in `VantageDashboard.mqh`
- **Web desk:** `/liquidity-grab` — card **LIQUIDITY GRAB MONITOR**
- **Chart objects:** prefix `VAI_LG_*` (level, sweep, MSS, label)

## News Integration

Uses MT5 `CalendarValueHistory` (USD high-impact) when available — same pattern as M5 Desk. Marks `news_restricted` and applies penalty. No fabricated news data.

## Example Heartbeat JSON

```json
{
  "liquidity_grab": {
    "status": "LIQUIDITY_GRAB_CONFIRMED",
    "direction": "BUY_SIDE_GRAB_BEARISH_REVERSAL",
    "confidence_score": 82.0,
    "liquidity_level_type": "ASIAN_HIGH",
    "liquidity_level_price": 4043.80,
    "sweep_price": 4044.25,
    "mss_detected": true,
    "mss_level": 4039.90,
    "higher_timeframe_bias": "BEARISH",
    "action_guidance": "Conditions met — monitor invalidation level"
  }
}
```

## Tests

```bash
cd backend
pytest tests/test_liquidity_grab_status.py tests/test_liquidity_grab_static.py -q
```

## Strategy Tester Checklist

1. Attach EA to **XAUUSD** (or broker suffix variant).
2. Enable **U. Liquidity Grab Monitor — Core**.
3. Visual mode M5 — verify `VAI_LG_*` objects on sweep events.
4. Confirm no orders in Experts log.
5. Optional: enable `InpLiqGrabDebug` for `[LiquidityGrab]` logs.

## Known Limitations

- Session hours use configurable UTC offsets (not full IANA DST tables in MQL5).
- M45 not native in MT5 — use M30/H1 for context if needed.
- Tick volume quality varies by broker.
- Restart clears in-memory candidates (no persistence file yet).

## Manual Validation

- [ ] Wick above level without MSS → unconfirmed only (score ≤ 69)
- [ ] Two closes beyond level → GENUINE_BREAKOUT
- [ ] EURUSD chart → disable blob, no false grabs
- [ ] Heartbeat includes `liquidity_grab` on VPS monitor
