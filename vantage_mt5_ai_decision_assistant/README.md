# Vantage MT5 AI Decision Assistant

Advisory-only decision assistant for **Vantage Markets MetaTrader 5** accounts.

**Primary mode:** recommendations only.  
**Forbidden:** opening, modifying, partially closing, or closing positions.

## Project layout

```
vantage_mt5_ai_decision_assistant/
├── MQL5/
│   ├── Experts/VantageMT5AIDecisionAssistant.mq5
│   └── Include/VantageAI/          # account, symbol, risk, positions, analysis, backend, UI
├── backend/                        # FastAPI (default public URL below)
├── tests/                          # pytest + static advisory audits
└── docs/VANTAGE_SETUP.md           # full install / VPS / WebRequest guide
```

**Public API base:** `http://187.77.142.118:8000`

## Quick start

1. Follow [docs/VANTAGE_SETUP.md](docs/VANTAGE_SETUP.md).
2. Start backend (local or Docker on VPS).
3. Open the web monitor: **http://187.77.142.118:8000/monitor** (M30 advisory cockpit)
4. Optional separate desk: **http://187.77.142.118:8000/dashboard** (M5 / M15 / H1 alignment playbook)
5. Accepted signals: **http://187.77.142.118:8000/signals** (ledger cards when M5 desk is SETUP_OK)
6. Smart Analyzer: **http://187.77.142.118:8000/analyzer** (Take/Ignore desk — no MT5 orders)
7. Allow `http://187.77.142.118:8000` in MT5 WebRequest settings.
8. EA `InpBackendUrl` = `http://187.77.142.118:8000` · `InpBearerToken` = backend `LOCAL_API_TOKEN`
9. Compile and attach the EA to your chart.

The monitor shows API status, EA connection, dual decisions, risk, and a **Decision Brief** (analysis + recommendations).

The **M5 Alignment Desk** (`/dashboard`) is a separate surface with fixed rules: M5 analysis, M15 structure, H1 bias, EMA 20/50/200, ATR/ADX 14 (min ADX 20), min R:R 2.0, risk 0.50%, pair-specific max spread, news block 30m/15m, setup age ≤ 3 M5 closes, candle-close confirmation, direction only with H1+M15 alignment.

When the desk reaches **SETUP_OK**, the backend stores an advisory BUY/SELL on the **Accepted Signal Ledger** (`/signals`, `GET /api/v1/signals`) with score, entry band, stop, and T2 — still no auto-trading.

**Smart Analyzer** (`/analyzer`) is the live decision desk: STANDARD/SCALPING modes, score gauge, schematic evidence chart with entry/SL/TP overlays, and **TAKE / Ignore** buttons that only record your choice (`POST /api/v1/signals/{id}/decision`) — never send an MT5 order. Shared left sidebar links Market Overview, Analyzer, Signal Center, and Opportunity Radar.

## Design guarantees

| Topic | Behaviour |
|-------|-----------|
| Broker | Soft Vantage name warning only — no hard reject |
| Symbol | Chart `_Symbol`; optional gold discovery is informational |
| Specs | All `SymbolInfo*` fields dynamic (digits, contract, lots, filling, …) |
| Candles | Confirmed closed M30 only for entry/exit advice |
| Risk | `OrderCalcProfit` / `OrderCalcMargin` — no generic gold pip formula |
| Privacy | Masked login locally; never sent raw to backend/AI |
| Execution | No `CTrade` / `OrderSend` / position modify-close |

## Advisory decisions (v1.2)

New-entry and existing-position advice are **separate**:

| Field | Values |
|-------|--------|
| New Entry | `BUY_ALLOWED`, `SELL_ALLOWED`, `WAIT`, `NO_NEW_TRADE`, `HIGH_SPREAD`, `RISK_BLOCKED` |
| Existing Position | `HOLD`, `HOLD_WITH_CAUTION`, `PROTECT_PROFIT`, `EXIT_WARNING`, `CRITICAL_RISK`, `POSITION_DATA_UNAVAILABLE` |
| Risk Status | `LOW` (&lt;1%), `MODERATE` (&lt;2%), `HIGH` (&lt;5%), `VERY_HIGH` (&lt;10%), `CRITICAL` (≥10%) |

Configurable max open-position equity risk defaults to **2%** (`InpMaxPositionRiskPct` / `MAX_POSITION_RISK_PCT`). Critical risk shows a red warning and one push per state change — never auto-closes.

## Tests

```powershell
cd vantage_mt5_ai_decision_assistant
pip install -r backend/requirements.txt
$env:PYTHONPATH = "$PWD\backend"
pytest -q
```

## Disclaimer

Not financial advice. Demo first. Live automatic trading is disabled in this release.
