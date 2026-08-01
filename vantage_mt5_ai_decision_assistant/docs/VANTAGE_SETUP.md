# Vantage MT5 AI Decision Assistant — Setup Guide

Advisory-only system for a **Vantage Markets MetaTrader 5** account.  
It does **not** open, modify, partially close, or close any position.

---

## 1. Installing Vantage MT5 desktop

1. Download the Vantage MetaTrader 5 terminal from your Vantage client portal / official site.
2. Install on Windows (or your VPS Windows image).
3. Launch **Vantage MT5** (not a different broker’s terminal if you intend to use Vantage pricing).

## 2. Logging into a Vantage demo account

1. File → Login to Trade Account.
2. Enter demo login, password, and the **exact server** provided in the Vantage welcome email.
3. Confirm the bottom-right status shows connected.

## 3. Finding the exact broker server

1. In MT5: Toolbox → Trade, or Account details.
2. Note **AccountInfo server** string (example shapes only): `VantageInternational-Demo`, `VantageInternational-Live`, etc.
3. Servers differ by region and account type — **never hard-code** one server in the EA.

The EA displays company + server at init and warns only if neither contains a recognizable “Vantage” reference. It does **not** reject other names.

## 4. Checking the exact gold symbol

**Your verified Vantage symbol is `XAUUSD`** (Gold vs US Dollar).

1. Open Market Watch (Ctrl+M).
2. Confirm **XAUUSD** is visible (right-click → Show All if needed).
3. Open an **XAUUSD M30** chart.
4. Attach the EA to **that chart**. The EA always uses `_Symbol` and never auto-switches symbols.

Other Vantage builds may show suffixes (`XAUUSD.`, `XAUUSD+`, `GOLD`). Use whatever appears in *your* Market Watch — but for this account, use plain **XAUUSD**.

## 5. Viewing symbol specifications

1. Market Watch → right-click **XAUUSD** → Specification.
2. Your verified Vantage profile (screenshot reference):

| Field | Value |
|-------|--------|
| Symbol | XAUUSD |
| Digits | **2** |
| Contract size | **100** |
| Spread | Floating |
| Stops level | **20** |
| Volume min / step / max | **0.01 / 0.01 / 100** |
| Filling | Immediate or Cancel |
| Calculation | CFD Leverage |
| Execution | Market |
| Sessions | Mon–Thu ~01:00–23:58; Fri ends ~23:57 (server time) |

3. The EA reads these live via `SymbolInfo*` on init and logs a comparison against this reference. It does **not** hard-fail if a future account differs slightly.

## 6. Allowing the local FastAPI URL for WebRequest

1. MT5 → Tools → Options → Expert Advisors.
2. Enable **Allow WebRequest for listed URL**.
3. Add exactly:
   ```
   http://187.77.142.118:8000
   ```
4. OK → restart the terminal if prompted.

If this step is skipped, the EA logs clear setup guidance and sets action `BACKEND_OFFLINE`.

## 7. Installing and compiling the EA

1. Open MT5 → File → Open Data Folder.
2. Copy project files:
   - `MQL5/Experts/VantageMT5AIDecisionAssistant.mq5` → `MQL5/Experts/`
   - `MQL5/Include/VantageAI/*` → `MQL5/Include/VantageAI/`
3. In MetaEditor: open the EA → Compile (F7).
4. Confirm zero errors. The build must **not** reference `CTrade` / `Trade.mqh`.

## 8. Starting the FastAPI backend

```powershell
cd d:\2026_Projects\trading_scripts\vantage_mt5_ai_decision_assistant\backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python run.py
```

Defaults:

- Monitor UI: **http://187.77.142.118:8000/monitor**
- Health: `GET /health`
- Heartbeat: `POST /api/v1/heartbeat`
- Analyze: `POST /api/v1/analyze`
- Auth: `Authorization: Bearer <LOCAL_API_TOKEN>`

Open the monitor page in a browser to see:

- API online / offline
- Live **WebSocket** updates (`ws://187.77.142.118:8000/ws/monitor`) — no page refresh polling
- Vantage EA connected (heartbeat within ~45s)
- Symbol, spread, dual decisions (new entry + existing position), risk status
- Equity risk %, estimated SL loss, add/new position allowed
- **Decision Brief** (situation, prioritized recommendations, checklist — not raw logs)

**Separate M5 Alignment Desk:** [http://187.77.142.118:8000/dashboard](http://187.77.142.118:8000/dashboard)  
**Accepted Signal Ledger:** [http://187.77.142.118:8000/signals](http://187.77.142.118:8000/signals) (stores advisory BUY/SELL when desk is SETUP_OK)  
**Smart Analyzer:** [http://187.77.142.118:8000/analyzer](http://187.77.142.118:8000/analyzer) (Take/Ignore records a decision only — no MT5 order)
Playbook: M5 analysis / M15 structure / H1 bias · EMA 20/50/200 · ATR/ADX 14 (min ADX 20) · min R:R 2.0 · risk 0.50% · pair-specific max spread · news block 30m before / 15m after · setup age ≤ 3 completed M5 · candle-close confirmation · direction only with H1+M15 alignment.

With EA input **H. M5 Alignment Desk** enabled (`InpM5DeskEnable=true`, default), each heartbeat includes a `strategy` object so the gate board can go PASS/FAIL. Requires: backend running, WebRequest allowed for `http://187.77.142.118:8000`, EA attached to the selected pair, MetaEditor recompile after sync.

**Clear EA feed FAIL:** start backend (`python run.py`) → allow WebRequest URL → attach compiled EA → pick matching pair on `/dashboard` → wait ~15s.

**Do not put OpenAI/cloud keys in the EA.** Optional cloud keys stay only in the backend `.env`.

### Position risk (v1.2)

EA input group **E. Position risk thresholds** (editable): LOW &lt;1%, MODERATE &lt;2%, HIGH &lt;5%, VERY_HIGH &lt;10%, CRITICAL ≥10%.  
`InpMaxPositionRiskPct` default **2%**. Critical/over-max risk → red warning, one push per state change, suppress add/new exposure, never auto-close.

`InpFloatProfitTargetPct` default **10%**. When floating profit ≥ this % of equity → green chart warning + one push (`FLOAT_PROFIT_TARGET`) so you can manually limit/take profit. Monitor shows a **Floating P/L vs Equity** pie chart.

**Trading history calendar** (monitor): closed P/L by day as % of current equity (green/red cells). Use **Prev / Next / This month** to browse other months; the EA loads that month from MT5 deal history on the next heartbeat (~15s). Floating P/L is excluded.

**Account performance** (monitor + chart): total trades, wins/losses pie, win rate, profit factor, max drawdown $, max drawdown %, recovery factor, avg win/loss, consecutive streaks — MQL report–style from closed exit deals (`trade_stats`). `InpStatsLookbackDays=0` means all history.

Example (BUY @ 4090.67, SL 4062, ~34.68% equity risk): **CRITICAL** + Existing **HOLD_WITH_CAUTION** + New Entry **NO_NEW_TRADE**/**RISK_BLOCKED** + Add Position **NO**.

## 9. Attaching the EA (XAUUSD and/or BTCUSD)

The web monitor has a **Pair** selector (**XAUUSD** / **BTCUSD**). Each chart needs its own EA instance so both can heartbeat independently.

**Trade thesis levels:** default `InpLevelSource=AUTO_NON_GOLD` — gold uses the editable MANUAL inputs (~4088…); **BTCUSD / other pairs use AUTO levels from mid-price + ATR** (so the thesis card is not stuck on gold prices). Use `AUTO` for ATR on every symbol, or `MANUAL` to force the input map.

1. Open the symbol on **M30** (gold: **XAUUSD**, crypto: **BTCUSD** — use your broker’s exact name).
2. Navigator → Expert Advisors → drag `VantageMT5AIDecisionAssistant`.
3. Inputs:
   - `InpBackendUrl` = `http://187.77.142.118:8000`
   - `InpBearerToken` = same as backend `LOCAL_API_TOKEN`
   - `InpAdvisoryOnly` = **true** (required)
   - On BTCUSD: keep `InpLevelSource=AUTO_NON_GOLD` or `AUTO`; raise `InpMaxSpreadPoints` or set `0`
4. Enable Algo Trading (for timers/WebRequest; the EA still never sends orders).
5. **Clean chart (optional):**
   - `InpApiOnlyUi = true` — hide all on-chart HUD/lines/zones; data still in `/monitor`, `/gold-smc`, etc.
   - `InpChartHideHorizontalLines = true` (default) — hide PDH/BSL/TP/invalidation **H-lines** but **keep Gold SMC vertical premium/discount/OTE zones** on chart.
6. Check Experts log for masked login, symbol specs, and backend health.

## 10. Enabling MT5 push notifications

1. MT5 → Tools → Options → Notifications.
2. Configure MetaQuotes ID / push.
3. In EA inputs: `InpPushNotify = true`.
4. Notifications fire only on **state changes** with cooldown + one-per-closed-candle rules.

## 10b. Telegram alerts (recommended)

Alerts are sent from the **VPS backend** (bot token never goes in the EA).

### Setup

1. Telegram → [@BotFather](https://t.me/BotFather) → `/newbot` → copy **bot token**.
2. Open a chat with your bot and send any message (e.g. `hi`).
3. Open in a browser (replace `TOKEN`):
   `https://api.telegram.org/botTOKEN/getUpdates`
   Copy `"chat":{"id": ...}` → that is **TELEGRAM_CHAT_ID**.
4. On the VPS, edit `backend/.env`:

```env
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
TELEGRAM_COOLDOWN_SEC=300
```

5. Restart backend / run deploy script.
6. Test (replace with your `LOCAL_API_TOKEN`):

```bash
curl -X POST http://187.77.142.118:8000/api/v1/telegram/test \
  -H "Authorization: Bearer YOUR_LOCAL_API_TOKEN"
```

7. Check Telegram for **Vantage AI Telegram test**.

### What triggers alerts (default)

| Alert | Trigger |
|--------|---------|
| CRITICAL risk | `risk_status=CRITICAL` or over max position risk |
| Float profit target | Floating P/L ≥ target % of equity |
| New entry watch | `BUY_ALLOWED` / `SELL_ALLOWED` (on change) |
| Accepted signal | M5 desk SETUP_OK → signal ledger |
| Swing STRONG | `STRONG SWING BUY/SELL`, confidence ≥ 85 |
| Liquidity grab | `GRAB_CONFIRMED` / `HIGH_CONFIDENCE` |
| Gold SMC setup | Named setup, score ≥ 75 |
| Demo execution | Executor FILLED / REJECTED / SKIPPED |

Toggle each category with `TELEGRAM_ALERT_*=true/false` in `.env`.

`GET /health` includes a `telegram` block (`enabled`, `configured`, `cooldown_sec`).

## 10c. Discord alerts (recommended if Telegram bot creation is blocked)

Alerts are sent from the **VPS backend** via a channel webhook (no bot token needed).

### Setup

1. Discord → your server → create or pick a channel (e.g. `#trading-alerts`).
2. Channel settings → **Integrations** → **Webhooks** → **New Webhook**.
3. Name it (e.g. `Vantage AI`) → **Copy Webhook URL**.
4. On the VPS, edit `backend/.env`:

```env
DISCORD_ENABLED=true
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/123456789/abcdef...
DISCORD_COOLDOWN_SEC=300
```

5. Restart backend / run deploy script.
6. Test (replace with your `LOCAL_API_TOKEN`):

```bash
curl -X POST http://187.77.142.118:8000/api/v1/discord/test \
  -H "Authorization: Bearer YOUR_LOCAL_API_TOKEN"
```

7. Check Discord for **Vantage AI Discord test**.

**From the web UI:** open `/monitor` → expand **Ops / link diagnostics** → **Test Discord** (or click the **DC LIVE** pill in the header).

### What triggers alerts

Same categories as Telegram (§10b). Toggle with `TELEGRAM_ALERT_*` in `.env` — those flags apply to **both** Telegram and Discord when each channel is enabled.

`GET /health` includes a `discord` block (`enabled`, `configured`, `cooldown_sec`).

On `/monitor`, the header pill shows **DC LIVE** when configured.

### Background mode — Discord only, valid trades (no dashboard)

All modules already run **headless** on the EA timer + heartbeat (~15s). You do **not** need any web desk open.

**Requirements:**

1. **MT5** — `VantageMT5AIDecisionAssistant` attached, Algo Trading ON, modules enabled (`InpSwingEnable`, `InpGoldSmcEnable`, `InpLiqGrabEnable`, etc.).
2. **VPS** — Docker backend running with Discord in `.env` (parent folder, not `backend/.env`).
3. **Optional** — `InpApiOnlyUi=true` for a clean chart (data still flows to API).

**Recommended `.env` for trade-only Discord alerts:**

```env
DISCORD_ENABLED=true
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
DISCORD_TRADES_ONLY=true
DISCORD_TRADES_MIN_SWING_CONF=72.0
DISCORD_COOLDOWN_SEC=300
TELEGRAM_ENABLED=false
```

With `DISCORD_TRADES_ONLY=true`, Discord receives **only**:

| Alert | When |
|--------|------|
| **Master SETUP / STRONG** | All modules agree — actionable setup |
| **Swing trade** | STRONG SWING (≥85%) or SWING BUY/SELL (≥72%, not Avoid) |
| **Accepted signal** | M5 desk SETUP_OK → signal ledger |
| **CRITICAL risk** | Safety — over max position risk |

Skipped: WATCH, entry watch, float target, individual Liq Grab / Gold SMC pings (those still feed Master verdict).

Restart after editing: `docker compose up -d`

## 11. Testing on demo

1. Run with `InpRunDiagnostics = true`.
2. Verify dashboard: broker, masked account, digits, contract, spread, backend, action.
3. Wait for a newly closed M30 candle — only then should `/analyze` be called.
4. Force-stop the backend → expect `BACKEND_OFFLINE`.
5. Widen spread filter to a tiny value → expect `HIGH_SPREAD` and no fresh entry watches.

## 11a. Trader cockpit monitor layout

`/monitor` is organized as a **trader desk**, not a systems console:

1. **Decision strip** — primary action, new-entry, open-position, risk (first viewport)
2. **Trade thesis** — S/R, recovery levels, invalidation + floating P/L
3. **Market context / bias** — bid/ask, spread, candle freshness, bias pie
4. **Decision Brief + ChatGPT** — recommendations and Analyze
5. **Account performance + P/L calendar**
6. **Ops drawer** (collapsed) — API/EA link diagnostics

Pair selector and risk/live badges stay in the sticky header. Advisory only — no trade execution buttons.

## 11b. ChatGPT on the monitor (optional)

The Decision Brief card has **Copy AI brief** and **Analyze with ChatGPT**.

1. In `backend/.env` (never in the EA or browser):
   ```env
   OPENAI_API_KEY=sk-...
   OPENAI_MODEL=gpt-5.6-sol
   USE_LLM=true
   ```
2. Restart FastAPI.
3. Open `/monitor` → select pair → **Analyze with ChatGPT** (server calls OpenAI with the snapshot).
4. If LLM is off, use **Copy AI brief** and paste into ChatGPT manually.

The API key never leaves the backend process. Analysis is advisory only.

## 12. Signal backtest in Strategy Tester

This EA is **advisory-only** — Strategy Tester will show **0 deals / empty equity curve**. Use it to journal **signals**, not P/L.

1. MetaEditor: compile `VantageMT5AIDecisionAssistant.mq5` (F7).
2. MT5 → **View → Strategy Tester** (Ctrl+R).
3. Settings:
   - Expert: `VantageMT5AIDecisionAssistant`
   - Symbol: `XAUUSD` or `BTCUSD` (your broker name)
   - Period: **M30**
   - Model: **1 minute OHLC** or **Every tick**
   - Date range with enough history (EMA200 needs ~220+ M30 bars)
4. Inputs: leave `InpAdvisoryOnly=true`. Replay starts automatically in the tester (`InpBacktestMode` is optional on live charts). Set levels / `InpMaxSpreadPoints` for the symbol (BTC needs a higher spread limit or `0`).
5. Start. Visual mode shows a Comment with the latest signal; Journal prints a summary at the end.
6. Open the CSV:
   - Strategy Tester: `Terminal\Tester\Agent-*\MQL5\Files\vantage_signals_<SYMBOL>.csv`
   - Or copy from that agent folder into Excel

Columns: `time,symbol,bid,spread,trend,market_state,bullish_pct,bearish_pct,rsi,action,new_entry,risk_status,note`

No FastAPI / WebRequest is used in tester. A separate trading EA would be required for profit-factor style backtests.

**Do not backtest `VantageSwingExecutor`** — it polls the live VPS for signals via `WebRequest` and will show **0 trades** in Strategy Tester. Use the advisory EA above for signal replay; use the executor only on a **demo chart** with the backend running.

### Strategy Tester checklist

| Symptom | Cause | Fix |
|--------|--------|-----|
| 0 trades, empty equity | Wrong EA (`VantageSwingExecutor`) or expected (advisory never orders) | Use `VantageMT5AIDecisionAssistant`; read CSV / Journal, not the Results tab |
| Journal shows no `SIGNAL REPLAY MODE` | Old `.ex5` or wrong expert | Recompile (F7), sync to `MQL5/Experts/`, pick advisory EA in tester |
| CSV missing / 0 rows | `InpBacktestLogSignals=false` or init failed | Enable logging; check Experts for `Symbol spec failed` / `Backtest CSV open failed` |
| Only a few CSV rows on H1 chart | Coarse tick model skipped M30 closes | Prefer **M30** period; or use **1 minute OHLC** / **Every tick** (replay now catches missed M30 bars) |
| All rows `INCOMPLETE_HISTORY` | Range too short for EMA200 | Start date needs **220+ M30 bars** of history before first signal |

Journal success looks like: `SIGNAL REPLAY MODE` → `Signal journal: MQL5/Files/vantage_signals_XAUUSD.csv` → end summary `Bars logged: N`.

## 13. Troubleshooting common WebRequest errors

| Symptom | Likely cause | Fix |
|--------|---------------|-----|
| XAUUSD not syncing on **live** account (demo OK) | Live broker symbol differs (`XAUUSD+`, `GOLD`, `XAUUSD.a`) — heartbeat stored under wrong key | Deploy latest backend (maps broker gold → **XAUUSD**). Re-attach EA on your **live gold chart**; Pair = **XAUUSD** on `/monitor`. |
| EA offline after switching MT5 login | EA not re-attached / Algo Trading off on new account | Remove & re-drag EA on live XAUUSD M30; enable Algo Trading; check Experts log for heartbeat OK |
| err 4014 / 4060 | URL not allow-listed | Add `http://187.77.142.118:8000` |
| Connection failure | Backend not running | Start `python run.py` |
| HTTP 401 | Token mismatch | Align EA token and `.env` |
| Timeout | Backend hung / firewall | Check localhost:8000 `/health` |
| Malformed JSON | Proxy / wrong path | Confirm `/api/v1/analyze` |

## 14. Moving to a Windows VPS

1. Install Vantage MT5 on the VPS.
2. Run the FastAPI backend on the **same** VPS (`127.0.0.1`).
3. Keep WebRequest URL as localhost (preferred) or lock down any remote bind.
4. Use VPS auto-login + startup script for the backend.
5. Continue using **demo** until you fully understand advisory behaviour.

## 14b. Linux VPS — Docker (API only)

Your Linux VPS can host the **FastAPI backend** in Docker. MetaTrader 5 still runs on **Windows** (PC or Windows VPS); the EA calls the API over HTTP.

### Files
- `Dockerfile`
- `docker-compose.yml`
- `.env.docker.example` → copy to `.env`
- Optional nginx sample: `deploy/nginx-vantage-api.example.conf`

### Deploy
```bash
# on VPS — this host uses:
#   /var/www/tradingscript/vantage_mt5_ai_decision_assistant
cd /var/www/tradingscript/vantage_mt5_ai_decision_assistant
cp .env.docker.example .env
nano .env   # set LOCAL_API_TOKEN (and OPENAI_* if needed)

docker compose up -d --build
curl http://127.0.0.1:8000/health
```

Default publish port: **8000** (confirm it is free: `ss -tulnp | grep 8000`).

### Web UI map
| Sidebar | URL |
|---------|-----|
| Market Overview | `/monitor` |
| Smart Analyzer | `/analyzer` |
| Signal Center | `/signals` |
| Opportunity Radar | `/dashboard` |
| Pattern Strategy | `/patterns` |
| Strategy Scanner | `/scanner` |
| Strategy Lab | `/lab` |
| Other tools | `/coming-soon` |

Left nav is shared (`/static/shell.js`). Analyzer embeds a **TradingView Advanced Chart** (reference market data; Vantage desk levels stay in the strip below — ticks may differ from MT5).

### Firewall (if MT5 is remote)
```bash
# ufw example — lock to your home IP if possible
sudo ufw allow from YOUR.HOME.IP to any port 8000 proto tcp
sudo ufw reload
```

### MT5 EA settings
1. `InpBackendUrl` = `http://187.77.142.118:8000` (or your HTTPS domain if proxied)
2. `InpBearerToken` = same as `LOCAL_API_TOKEN` in `.env`
3. Tools → Options → Expert Advisors → Allow WebRequest for that exact URL
4. Open monitor: `http://187.77.142.118:8000/monitor` (or `/dashboard`)

### Useful commands
```bash
docker compose ps
docker compose logs -f vantage-api
docker compose restart vantage-api
docker compose down
```

### Update from GitHub
On this VPS the app lives at `/var/www/tradingscript/vantage_mt5_ai_decision_assistant`.

```bash
cd /var/www/tradingscript
git fetch origin main && git checkout main && git pull --ff-only origin main
cd vantage_mt5_ai_decision_assistant
docker compose up -d --build
curl -fsS http://127.0.0.1:8000/health
```

Or, after the helper script is on the server:

```bash
bash /var/www/tradingscript/vantage_mt5_ai_decision_assistant/deploy/update-from-github.sh
```

Keeps `.env` and the `vantage_signal_data` Docker volume (signal ledger). Rebuilds the image from `main`.

### Pending Orders desk (`/orders`)
- Backend: `GET /api/v1/orders/pending` + page `/orders` (advisory risk / trend / suggestions).
- **Requires a recompiled EA** that sends `pending_orders` on heartbeat/analyze (`VantagePendingOrders.mqh`).
- VPS `update-from-github.sh` updates the API only — recompile and reload the EA on Windows MT5 separately.
- Never places, modifies, or cancels MT5 pending orders from the web UI.

### Pullback Probability Desk (`/pullback`)
- Backend: `GET /api/v1/pullback/status` + page `/pullback` (EA-scored H1/M15/M5 probabilities; passthrough only).
- **Requires a recompiled EA** with `VantagePullback.mqh` that sends top-level `"pullback"` on heartbeat.
- Full guide: [PULLBACK_PROBABILITY.md](PULLBACK_PROBABILITY.md).
- Chart HUD + optional `VAI_PB_*` levels; alerts are candle-locked (popup/push/sound inputs).
- Does **not** affect SETUP_OK, Signal Center, or Analyzer Take/Ignore. See [PULLBACK_PROBABILITY.md](PULLBACK_PROBABILITY.md).
- VPS deploy updates the API only — recompile and reload the EA on Windows MT5 separately.

### Gold SMC Intelligence (`/gold-smc`)
- Backend: `GET /api/v1/gold-smc/status` + page `/gold-smc` (Gold-only SMC desk; Phase 8 complete — see `docs/GOLD_SMC.md`).
- **Requires a recompiled EA** with `VantageGoldSMC*.mqh` sending top-level `"gold_smc"`.
- Strict XAUUSD/GOLD alias validation — disabled on non-gold with an explicit HUD/web warning.
- Does **not** trade or affect SETUP_OK. See [GOLD_SMC.md](GOLD_SMC.md).

### Liquidity Grab Monitor (`/liquidity-grab`)
- Backend: `GET /api/v1/liquidity-grab/status` + page `/liquidity-grab` (Gold-only sweep → rejection → MSS desk).
- Sidebar: **Liquidity Grab Desk** under Workspace (shared `shell.js` nav).
- **Requires a recompiled EA** with `VantageLiquidityGrab*.mqh` sending top-level `"liquidity_grab"` (inputs groups U–Z).
- Does **not** trade or affect SETUP_OK. See [LIQUIDITY_GRAB.md](LIQUIDITY_GRAB.md).

### Demo auto-execution (optional — separate package)

- **Not part of the advisory EA.** Live auto-trading remains disabled in `VantageMT5AIDecisionAssistant`.
- Separate EA: `vantage_mt5_execution/MQL5/Experts/VantageSwingExecutor.mq5`
- Backend: `GET /api/v1/execution/next`, `POST /api/v1/execution/ack`, journal at `/execution`
- **Demo account only** — executor refuses init on live accounts
- Signal source: Swing Strategy **STRONG SWING BUY/SELL** only (confidence ≥ 85, Good/Excellent entry quality)
- Full guide: [../vantage_mt5_execution/docs/EXECUTION_SETUP.md](../vantage_mt5_execution/docs/EXECUTION_SETUP.md)

## 15. Explicit warning — advisory EA is not an auto-trader

> **The advisory EA release is advisory-only.**  
> It must not call `OrderSend`, must not import `CTrade`, and must not modify positions.  
> `InpAdvisoryOnly=false` causes init failure.  
> Optional demo execution uses a **separate** `VantageSwingExecutor` EA (demo account only).

---

## Privacy

- Full account login is used **locally** for diagnostics only.
- Dashboard/logs show **masked** login (last four digits).
- Analyze payloads send `account_login_masked` only — never the raw login to any AI provider.
