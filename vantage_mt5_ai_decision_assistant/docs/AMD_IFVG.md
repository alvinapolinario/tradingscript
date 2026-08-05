# AMD + iFVG Strategy Module

Advisory-only Gold (XAUUSD) strategy desk: **Accumulation → Manipulation → Distribution** with **inversion Fair Value Gap (iFVG)** entry refinement.

## Architecture

| Layer | Role |
|-------|------|
| **MT5 EA** (`VantageAmdIfvg.mqh`) | Closed-bar detection on M15 (setup) + M5 (entry); chart rectangles; heartbeat JSON |
| **FastAPI** | Passthrough `/api/v1/amd-ifvg/status`; offline mirror `/api/v1/amd-ifvg/analyze` |
| **Python engine** (`amd_ifvg_logic.py`) | Deterministic tests, offline analyze, future backtest |
| **Web desk** (`/amd-ifvg`) | Decision, checklist, trade plan, reasoning |

Live path matches other Vantage modules: **EA computes → heartbeat → dashboard**. The backend does not repaint or use future candles.

## Quick start

1. Recompile `VantageMT5AIDecisionAssistant.mq5` (groups **AP–AS**).
2. Attach EA to **XAUUSD** (or broker alias, e.g. `XAUUSD+`).
3. Open `http://127.0.0.1:8000/amd-ifvg` (or VPS URL).
4. Confirm monitor shows **AMD+iFVG** chip when heartbeat includes `amd_ifvg`.

## EA inputs (summary)

- **AP** — enable, Gold-only gate, aliases
- **AQ** — H4 / H1 / M15 / M5 timeframes
- **AR** — accumulation, sweep, displacement, FVG/iFVG thresholds, min score, risk %
- **AS** — chart objects, dashboard slice, debug

## API

### Status (live passthrough)

```http
GET /api/v1/amd-ifvg/status
```

### Offline analyze

```http
POST /api/v1/amd-ifvg/analyze
Content-Type: application/json

{
  "symbol": "XAUUSD",
  "candles": { "M15": [...], "M5": [...], "H1": [...] },
  "market": { "bid": 2650.0, "ask": 2650.3, "spread_points": 30 }
}
```

Requires ≥80 setup candles for full analysis (configurable in Python engine).

## Decision bands

| Confidence | Meaning |
|------------|---------|
| 85–100 | High-quality setup |
| 75–84 | Valid setup (default min trade score) |
| 65–74 | Developing — typically **WAIT** |
| &lt; 65 | **NO_TRADE** |

Decisions: `BUY`, `SELL`, `WAIT`, `NO_TRADE`.

## State machine (v1)

1. `SEARCHING_FOR_ACCUMULATION`
2. `ACCUMULATION_DETECTED`
3. `WAITING_FOR_LIQUIDITY_SWEEP`
4. `MANIPULATION_DETECTED`
5. `WAITING_FOR_DISPLACEMENT` / `WAITING_FOR_MSS`
6. `WAITING_FOR_IFVG_INVERSION`
7. `WAITING_FOR_RETRACE`
8. `ENTRY_ZONE_ACTIVE`
9. `INVALIDATED` / `EXPIRED`

Setup IDs and full DB persistence are **phase 2** — v1 uses EA-side last snapshot + Python tests.

## Discord alerts

When `DISCORD_ENABLED=true` and a webhook URL is set, the backend sends alerts on EA heartbeats for:

| Condition | Alert |
|-----------|--------|
| `decision` = **BUY** or **SELL** | AMD + iFVG trade (conf ≥ 75 default) |
| `decision` = **WAIT** + `setup_state` = **ENTRY_ZONE_ACTIVE** | Entry zone active (conf ≥ 75) |

Works with `DISCORD_TRADES_ONLY=true` (category `amd_ifvg` is included in trades-only mode).

Optional env:

```env
DISCORD_TRADES_MIN_AMD_IFVG_CONF=75
TELEGRAM_ALERT_AMD_IFVG=true
```

Disable: `TELEGRAM_ALERT_AMD_IFVG=false` (also disables Discord amd_ifvg category when not in trades-only mode).

## Testing

```bash
cd backend
pytest tests/test_amd_ifvg_logic.py tests/test_amd_ifvg_status.py tests/test_amd_ifvg_static.py -q
```

## Known limitations (v1)

- H4/H1 bias is simplified (neutral default in MQL5 v1).
- Session context and news filter: Python placeholder `NewsRiskService`; EA does not block on news yet.
- No auto-trading, no order placement.
- Backtest engine and setup DB migrations are planned — not claimed profitable until validated.
- Chart drawing: accumulation + iFVG zones; TP/SL lines expanded in later phases.

## Files

| File | Purpose |
|------|---------|
| `backend/app/analysis/amd_ifvg_logic.py` | Python detection engine |
| `backend/app/static/amd-ifvg.html` | Web desk |
| `MQL5/Include/VantageAI/VantageAmdIfvg*.mqh` | MT5 engine |
| `backend/tests/test_amd_ifvg_*.py` | Unit + API + static audits |
