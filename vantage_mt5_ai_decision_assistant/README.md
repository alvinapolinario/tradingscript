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

**Public API base:** `http://YOUR_SERVER:8000`

## Quick start

1. Follow [docs/VANTAGE_SETUP.md](docs/VANTAGE_SETUP.md).
2. Start backend (local or Docker on VPS).
3. Open the web monitor: **http://YOUR_SERVER:8000/monitor** (M30 advisory cockpit)
4. Optional separate desk: **http://YOUR_SERVER:8000/dashboard** (M5 / M15 / H1 alignment playbook)
5. Accepted signals: **http://YOUR_SERVER:8000/signals** (ledger cards when M5 desk is SETUP_OK)
6. Smart Analyzer: **http://YOUR_SERVER:8000/analyzer** (Take/Ignore desk — no MT5 orders)
7. Pullback Desk: **http://YOUR_SERVER:8000/pullback** (H1/M15/M5 probabilities — see [docs/PULLBACK_PROBABILITY.md](docs/PULLBACK_PROBABILITY.md))
8. Gold SMC Intelligence: **http://YOUR_SERVER:8000/gold-smc** (XAUUSD/Gold-only SMC desk — see [docs/GOLD_SMC.md](docs/GOLD_SMC.md))
9. Liquidity Grab Monitor: **http://YOUR_SERVER:8000/liquidity-grab** (sweep → rejection → MSS sequence — see [docs/LIQUIDITY_GRAB.md](docs/LIQUIDITY_GRAB.md))
10. Breakout Structure: **http://YOUR_SERVER:8000/breakout-structure** (trendline breakout + structure grade — see [docs/BREAKOUT_STRUCTURE.md](docs/BREAKOUT_STRUCTURE.md))
11. Market State Engine v2: **http://YOUR_SERVER:8000/market-state** (lifecycle intelligence + timeline — see [docs/MARKET_STATE.md](docs/MARKET_STATE.md))
12. Swing Strategy Engine: **http://YOUR_SERVER:8000/swing-strategy** (multi-TF SMC swing validation — see [docs/SWING_STRATEGY.md](docs/SWING_STRATEGY.md))
13. AMD + iFVG Strategy: **http://YOUR_SERVER:8000/amd-ifvg** (Accumulation/Manipulation/Distribution + inversion FVG — see [docs/AMD_IFVG.md](docs/AMD_IFVG.md))
14. Box Theory Strategy: **http://YOUR_SERVER:8000/box-theory** (consolidation box → breakout → retest — see [docs/BOX_THEORY.md](docs/BOX_THEORY.md))
15. Demo Execution journal (optional): **http://YOUR_SERVER:8000/execution** — requires separate `VantageSwingExecutor` EA; see [../vantage_mt5_execution/docs/EXECUTION_SETUP.md](../vantage_mt5_execution/docs/EXECUTION_SETUP.md)
16. **Telegram alerts:** configure `TELEGRAM_*` in backend `.env` — see [docs/VANTAGE_SETUP.md](docs/VANTAGE_SETUP.md) §10b
17. **Discord alerts:** configure `DISCORD_*` webhook in backend `.env` — see [docs/VANTAGE_SETUP.md](docs/VANTAGE_SETUP.md) §10c
18. Allow `http://YOUR_SERVER:8000` in MT5 WebRequest settings.
19. EA `InpBackendUrl` = `http://YOUR_SERVER:8000` · `InpBearerToken` = backend `LOCAL_API_TOKEN`
20. Compile and attach the EA to your chart.

The monitor shows API status, EA connection, dual decisions, risk, and a **Decision Brief** (analysis + recommendations).

The **M5 Alignment Desk** (`/dashboard`) is a separate surface with fixed rules: M5 analysis, M15 structure, H1 bias, EMA 20/50/200, ATR/ADX 14 (min ADX 20), min R:R 2.0, risk 0.50%, pair-specific max spread, news block 30m/15m, setup age ≤ 3 M5 closes, candle-close confirmation, direction only with H1+M15 alignment.

When the desk reaches **SETUP_OK**, the backend stores an advisory BUY/SELL on the **Accepted Signal Ledger** (`/signals`, `GET /api/v1/signals`) with score, entry band, stop, and T2 — still no auto-trading.

**Smart Analyzer** (`/analyzer`) is the live decision desk: STANDARD/SCALPING modes, score gauge, **TradingView Advanced Chart** (with EMA 20/50/200), desk entry/SL/TP strip, and **TAKE / Ignore** buttons that only record your choice — never send an MT5 order.

Also live: **Pattern Strategy** (`/patterns`), **Strategy Scanner** (`/scanner`), and **Strategy Lab** (`/lab`) — advisory pattern catalog, multi-pair desk ranking, and session playbook what-ifs. Shared left sidebar links the full workspace.

## Auto-execution (optional, separate package)

The advisory EA **never** auto-trades. A separate **VantageSwingExecutor** EA polls the backend for Swing Strategy **STRONG** (or Scalping **SCALP**) signals:

| Item | Location |
|------|----------|
| Executor EA | `../vantage_mt5_execution/MQL5/Experts/VantageSwingExecutor.mq5` |
| Setup guide | [../vantage_mt5_execution/docs/EXECUTION_SETUP.md](../vantage_mt5_execution/docs/EXECUTION_SETUP.md) |
| Web journal | **http://YOUR_SERVER:8000/execution** |
| API | `GET /api/v1/execution/next`, `POST /api/v1/execution/ack` |

**Demo (default):** attach executor on a Vantage demo account — no extra flags.

**Live (opt-in):** set `InpAllowLiveExecution=true`, `InpLiveConfirmPhrase=I_ACCEPT_LIVE_RISK` on the EA, and `EXECUTION_ALLOW_LIVE=true` on the VPS Docker `.env`. Real money — see setup guide.

Requires advisory EA heartbeat (Swing Strategy groups AK–AO) and both EAs on XAUUSD.

Before an order is reserved the backend checks it against the live price: stop and target on the correct side, reward:risk ≥ `EXECUTION_MIN_RR` (1.0), stop ≤ `EXECUTION_MAX_SL_ATR` × H4 ATR (3.0), and price no further than `EXECUTION_MAX_ENTRY_DRIFT_ATR` × H4 ATR (0.5) beyond the entry zone. The executor also stops for the day after `InpMaxTradesPerDay` entries or an `InpMaxDailyLossPct` loss, and refuses a trade rather than round up to the broker minimum lot when the risk budget is smaller.

## Strategy research (backtest scorecard)

`python -m app.research.cli` replays the ICT, H4→M15 FVG, Box Theory and AMD+iFVG engines over exported M5 history with real spread and writes `strategy_scorecard.json` + `report.md`: win rate, average R, profit factor, drawdown, t-stat, verdict (EDGE / INCONCLUSIVE / NO_EDGE), confidence calibration, and an out-of-sample confidence floor. With the scorecard in the data directory, live alerts show a **Backtest evidence** line, and `EVIDENCE_GATE_ENABLED=true` suppresses alerts from strategies without proven edge. Export history with `MQL5/Scripts/VantageExportHistory.mq5`. Full guide: [docs/STRATEGY_RESEARCH.md](docs/STRATEGY_RESEARCH.md).


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
pip install -r backend/requirements-dev.txt
pytest -q
```

`pytest.ini` puts `backend` on the path and runs both `backend/tests` and `tests`. CI (`.github/workflows/python-app.yml`) runs the same on Python 3.12 — the Docker image's version.

## Disclaimer

Not financial advice. Demo first. Live automatic trading is disabled in this release.
