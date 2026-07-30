# Demo Auto-Execution Setup

Optional **demo-only** trade execution for Swing Strategy **STRONG** signals.

| Component | Role |
|-----------|------|
| `VantageMT5AIDecisionAssistant` | Advisory EA — unchanged, no orders |
| `VantageSwingExecutor` | Separate EA — polls backend, places demo orders |
| FastAPI `/api/v1/execution/*` | Signal queue + dedup ledger |
| `/execution` web desk | Demo fill journal |

## Requirements

- **Vantage demo account** (live accounts are refused at EA init)
- Advisory EA running on XAUUSD with Swing Strategy enabled (groups AK–AO)
- Backend reachable from MT5 (`http://187.77.142.118:8000` or your VPS URL)
- Same `LOCAL_API_TOKEN` / `InpApiToken` as the advisory EA

## Install (MT5)

1. Copy from repo:

```
vantage_mt5_execution/MQL5/Experts/VantageSwingExecutor.mq5
  → Terminal/MQL5/Experts/

vantage_mt5_execution/MQL5/Include/VantageExecution/*
  → Terminal/MQL5/Include/VantageExecution/
```

2. MetaEditor → compile `VantageSwingExecutor.mq5` (zero errors).

3. **Tools → Options → Expert Advisors → Allow WebRequest** for your backend URL.

4. Attach **both** EAs on demo XAUUSD (same or separate charts):
   - `VantageMT5AIDecisionAssistant` (heartbeat / swing blob)
   - `VantageSwingExecutor` (demo execution)

## Executor inputs (defaults)

| Input | Default | Notes |
|-------|---------|-------|
| `InpBackendUrl` | `http://187.77.142.118:8000` | Must match advisory EA |
| `InpApiToken` | (your token) | Bearer token |
| `InpPollSeconds` | 5 | Timer poll interval |
| `InpAllowLiveExecution` | **false** | Must stay false |
| `InpMagicNumber` | 880001 | Identifies executor positions |
| `InpRiskPct` | 0.50 | Equity risk per trade |
| `InpMinConfidence` | 85 | Matches backend gate |

## Signal rules (phase 1)

The backend reserves orders only when the advisory heartbeat `swing_strategy` blob has:

- `signal` = `STRONG SWING BUY` or `STRONG SWING SELL`
- `confidence` ≥ 85
- `entry_quality` = Good or Excellent
- Fresh `eval_bar_m5` (≤ 2 M5 bars)
- Valid `stop_loss` and `tp1`

Non-STRONG signals (`SWING BUY`, `WAIT`, etc.) are **never** executed.

## API flow

```
Executor  GET  /api/v1/execution/next?symbol=XAUUSD
Backend   → reserves PENDING row, returns order spec
Executor  → market order via CTrade (SL/TP from blob)
Executor  POST /api/v1/execution/ack  { status: FILLED|REJECTED|SKIPPED }
```

Journal: `GET /api/v1/execution/history` and web desk `/execution`.

## CSV journal

When `InpJournalCsv=true`, fills log to:

`Terminal/MQL5/Files/vantage_exec_<SYMBOL>.csv`

## Safety

- **Demo account hard gate** — EA refuses init on live
- **Advisory EA unchanged** — no `OrderSend` in advisory tree
- **One pending reservation per symbol** — prevents double-fire
- **Fingerprint dedup** — same STRONG bar cannot fill twice

## Deploy (VPS backend)

```bash
bash /var/www/tradingscript/vantage_mt5_ai_decision_assistant/deploy/update-from-github.sh
```

Backend update does **not** copy MQL5 files — recompile executor on Windows MT5 separately.

## Manual checklist

1. Demo login confirmed in MT5
2. Advisory EA online on `/swing-strategy` desk
3. Executor attached; Journal shows `[VantageExec] Started`
4. On STRONG signal → `/execution` shows PENDING then FILLED
5. On SWING BUY (non-strong) → no execution row

## Disclaimer

Demo execution validates **infrastructure and fill mechanics**, not profitability. Demo vs live slippage and spreads differ. Not financial advice.
