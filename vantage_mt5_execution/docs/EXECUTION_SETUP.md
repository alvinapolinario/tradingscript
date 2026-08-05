# Auto-Execution Setup (Demo default · Live opt-in)

Optional trade execution for Swing Strategy **STRONG** signals (and Scalping **SCALP** signals).

| Component | Role |
|-----------|------|
| `VantageMT5AIDecisionAssistant` | Advisory EA — unchanged, no orders |
| `VantageSwingExecutor` | Separate EA — polls backend, places orders |
| FastAPI `/api/v1/execution/*` | Signal queue + dedup ledger |
| `/execution` web desk | Fill journal |

## Demo (default)

Works out of the box on a **Vantage demo account** — no extra flags.

1. Copy MQL5 files from `vantage_mt5_execution/MQL5/` into your terminal folder.
2. Compile `VantageSwingExecutor.mq5`.
3. Allow WebRequest for your backend URL.
4. Attach **both** EAs on XAUUSD:
   - `VantageMT5AIDecisionAssistant` (heartbeat)
   - `VantageSwingExecutor` (execution)

Leave `InpAllowLiveExecution = false` on demo.

## Live account (explicit opt-in — real money)

**Three gates must all be enabled:**

### 1. MT5 EA inputs

| Input | Value |
|-------|--------|
| `InpAllowLiveExecution` | **true** |
| `InpLiveConfirmPhrase` | **I_ACCEPT_LIVE_RISK** (exact match) |

On init you will see an Alert: *LIVE EXECUTION ENABLED — real money at risk.*

### 2. VPS backend `.env`

```env
EXECUTION_ALLOW_LIVE=true
```

Use the **Docker parent** `.env` at  
`/var/www/tradingscript/vantage_mt5_ai_decision_assistant/.env`  
(not only `backend/.env`).

Redeploy after changing:

```bash
bash /var/www/tradingscript/vantage_mt5_ai_decision_assistant/deploy/update-from-github.sh
```

### 3. Operational checklist

- [ ] Advisory EA online on live XAUUSD (heartbeat)
- [ ] Swing Strategy groups AK–AO enabled; mode matches executor
- [ ] `InpRiskPct` and `InpMaxLot` reviewed for live account size
- [ ] `InpMaxSpreadPoints` appropriate for live gold spread
- [ ] WebRequest URL allowed in MT5
- [ ] Test with **Test Discord** / monitor before leaving unattended

If backend live is disabled, executor polls return `live_blocked` and **no orders** are reserved.

## Executor inputs (defaults)

| Input | Default | Notes |
|-------|---------|-------|
| `InpBackendUrl` | VPS URL | Must match advisory EA |
| `InpApiToken` | Bearer token | Same as `LOCAL_API_TOKEN` |
| `InpAllowLiveExecution` | **false** | Set true only on live |
| `InpLiveConfirmPhrase` | empty | Required on live |
| `InpMagicNumber` | 880001 | Tags executor positions |
| `InpRiskPct` | 0.50 | Equity risk per trade |
| `InpMinConfidence` | 85 | Swing; use 72 for scalping |

## Signal rules

### Swing mode

- `STRONG SWING BUY` / `STRONG SWING SELL`
- Confidence ≥ 85 · entry quality Good/Excellent
- Fresh `eval_bar_m5` (≤ 2 M5 bars)

### Scalping mode

- `SCALP BUY` / `SCALP SELL`
- Confidence ≥ 72 · `InpMinConfidence=72` on executor
- Fresh `eval_bar_m5` (≤ 1 M5 bar)

**Advisory `InpSwingTradeMode` must match executor `InpTradingMode`.**

## API flow

```
Executor  GET  /api/v1/execution/next?symbol=XAUUSD&account_mode=LIVE|DEMO
Backend   → reserves PENDING row (or live_blocked if server gate off)
Executor  → market order via CTrade
Executor  POST /api/v1/execution/ack  { status, account_mode, ... }
```

## Safety

- Demo runs without extra config
- Live requires EA phrase + backend `EXECUTION_ALLOW_LIVE`
- Advisory EA never calls `OrderSend`
- One pending reservation per symbol (dedup)
- Fingerprint dedup on STRONG bar

## Disclaimer

Live execution uses **real money**. Demo vs live slippage and spreads differ. Past signal quality does not guarantee future results. Not financial advice.
