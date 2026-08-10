# News & Economic Calendar Intelligence — Architecture Audit

**Document type:** Phase 1 architecture audit + phased integration plan  
**Status:** Review only — **no implementation started**  
**Date:** 2026-08-10  
**Scope:** `vantage_mt5_ai_decision_assistant` (FastAPI backend, static dashboard, MQL5 EA) + optional `vantage_mt5_execution` (unchanged for news)

---

## Executive Summary

The Vantage MT5 AI Decision Assistant is a **multi-strategy advisory platform**. Price, structure, and most strategy logic run in **MQL5 on closed bars**; the backend receives JSON via `POST /api/v1/heartbeat`, stores live state in **in-memory `monitor_store`**, persists only **signal** and **execution** ledgers to SQLite, and exposes static HTML desks plus WebSocket updates.

**News today is minimal and fragmented:**

- MQL5 uses native **`CalendarValueHistory`** for **USD high-impact window gating** only (`VantageM5Desk.mqh`, `VantageLiquidityGrab.mqh`).
- Backend reads **`news_blocked` / `news_available` / `minutes_to_high_impact`** from the EA `strategy` blob as a **single gate** (`strategy_desk.py`, `signal_ledger.py`).
- Python **`NewsRiskService`** in `amd_ifvg_logic.py` is a **disabled placeholder**.
- Monitor **“calendar”** UI is **closed-deal P/L history**, not economic events.
- **No** external news APIs, **no** macro bias engine, **no** Python `MetaTrader5` package.

The proposed **News & Macro Intelligence Engine** must be a **separate layer** that feeds **context, filters, and confluence** — never standalone trade generation. It should reuse heartbeat/WebRequest patterns, confluence types, AI validation, and Discord dedupe — without embedding news logic inside ICT, SMC, Box Theory, or other strategy modules.

**Critical constraint:** Do not rewrite working strategy modules or break heartbeat contracts. Additive APIs and a new `app/analysis/macro/` (or `app/market_news/`) package only.

---

## Table of Contents

1. [Current System Architecture](#1-current-system-architecture)
2. [Existing MT5 Integration](#2-existing-mt5-integration)
3. [Existing AI Integration](#3-existing-ai-integration)
4. [Existing Strategy Modules](#4-existing-strategy-modules)
5. [Existing Discord / Telegram Integration](#5-existing-discord--telegram-integration)
6. [Existing Database & Storage](#6-existing-database--storage)
7. [Existing News / Calendar Implementation](#7-existing-news--calendar-implementation)
8. [Where the News Module Should Fit](#8-where-the-news-module-should-fit)
9. [Reusable Components](#9-reusable-components)
10. [Files to Modify](#10-files-to-modify)
11. [New Files / Modules Required](#11-new-files--modules-required)
12. [Proposed MQL5 Bridge Architecture](#12-proposed-mql5-bridge-architecture)
13. [Proposed API Endpoints](#13-proposed-api-endpoints)
14. [Proposed Database Changes](#14-proposed-database-changes)
15. [Proposed Dashboard Changes](#15-proposed-dashboard-changes)
16. [Target Logical Architecture](#16-target-logical-architecture)
17. [News Source Layer (Provider Abstraction)](#17-news-source-layer-provider-abstraction)
18. [Data Models (Normalized Schemas)](#18-data-models-normalized-schemas)
19. [Macro Intelligence Engine Components](#19-macro-intelligence-engine-components)
20. [Confluence & Trade Validation Integration](#20-confluence--trade-validation-integration)
21. [AI News Interpretation Layer](#21-ai-news-interpretation-layer)
22. [Discord News Alerts](#22-discord-news-alerts)
23. [Configuration & Security](#23-configuration--security)
24. [Caching, Dedup, Decay, Source Reliability](#24-caching-dedup-decay-source-reliability)
25. [Error Handling & Backwards Compatibility](#25-error-handling--backwards-compatibility)
26. [Testing Plan](#26-testing-plan)
27. [Risks](#27-risks)
28. [Phased Implementation Plan](#28-phased-implementation-plan)
29. [Phase 1 Deliverable — STOP Point](#29-phase-1-deliverable--stop-point)

---

## 1. Current System Architecture

### 1.1 Backend

| Component | Technology | Location |
|-----------|------------|----------|
| Web framework | FastAPI | `backend/app/main.py` |
| Server | Uvicorn | `backend/run.py` |
| REST router | Single `APIRouter` | `backend/app/routers/api.py` (~40 routes) |
| Validation | Pydantic v2 | `backend/app/schemas.py` |
| Settings | pydantic-settings + `.env` | `backend/app/config.py`, `backend/.env.example` |
| Live state | In-memory singleton | `backend/app/monitor_state.py` |
| Real-time | WebSocket hub | `backend/app/ws_hub.py` → `WS /ws/monitor` |
| Background work | asyncio lifespan only | `_status_ticker()` every 5s; no cron/Celery |
| Static UI | Vanilla HTML/JS/CSS | `backend/app/static/` + `shell.js` / `shell.css` |
| Tests | pytest | `backend/tests/`, repo-root `tests/` |

**No SQLAlchemy, no Redis, no SSE.**

### 1.2 Frontend

| Pattern | Detail |
|---------|--------|
| Navigation | `shell.js` injects sidebar; `data-nav` on `<body>` |
| Data fetch | REST polling per desk + WS on monitor/dashboard |
| New pages | Register route in `main.py`, add nav item in `shell.js` |

### 1.3 Data Flow (today)

```text
MT5 EA (MQL5 closed-bar logic)
    │ WebRequest + Bearer token
    ▼
POST /api/v1/heartbeat
    │ monitor_store.record_heartbeat()
    ├── signal_ledger.maybe_accept_from_monitor()  [SQLite]
    ├── alert_notify.process_heartbeat()           [Discord/Telegram]
    ├── push_monitor_update()                      [WebSocket]
    └── returns calendar_year/month for P/L sync

Browser desks
    │ GET /api/v1/{module}/status  (from monitor_store)
    │ WS /ws/monitor
    ▼
Static HTML render
```

Offline analysis (ICT, Box Theory, AMD+iFVG) accepts candles in POST body — independent of live heartbeat.

### 1.4 Authentication

| Surface | Auth |
|---------|------|
| EA-facing | `Authorization: Bearer <LOCAL_API_TOKEN>` on heartbeat, analyze, execution |
| Browser dashboards | **Open** (assumes localhost/VPN trust) |
| WebSocket | **Open** |

---

## 2. Existing MT5 Integration

### 2.1 Advisory EA

| Asset | Path |
|-------|------|
| Main EA | `MQL5/Experts/VantageMT5AIDecisionAssistant.mq5` |
| HTTP client | `MQL5/Include/VantageAI/VantageBackend.mqh` |
| Heartbeat builder | Main EA `BuildHeartbeatPayload()` |

**Endpoints used by EA:**

- `GET {base}/health`
- `POST {base}/api/v1/heartbeat` (Bearer)
- `POST {base}/api/v1/analyze` (Bearer, optional)

### 2.2 Python MetaTrader5

**Not used.** All terminal access is via MQL5. There is no `import MetaTrader5` anywhere in the repo.

### 2.3 OHLC / Tick Data

| Source | Mechanism |
|--------|-----------|
| Live prices | EA heartbeat: `bid`, `ask`, `spread_points` |
| Closed candles | EA modules read `CopyRates` locally; optional offline POST analyze sends candle arrays |
| Backend re-analysis | `app/market_structure/candles.py` parses posted OHLC |

### 2.4 Execution Module (separate repo)

`vantage_mt5_execution/` — `VantageSwingExecutor.mq5` polls `/api/v1/execution/next`. **No news logic.** News module must not auto-trigger execution.

### 2.5 Existing Economic Calendar in MQL5

`VantageM5Desk.mqh` → `EvalNewsWindow()`:

- `CalendarValueHistory(values, from, to, NULL, "USD")`
- `CalendarEventById` → filter `CALENDAR_IMPORTANCE_HIGH`
- Sets `news_available`, `news_blocked`, `minutes_to_high_impact`
- Serialized in heartbeat `strategy` JSON

`VantageLiquidityGrab.mqh` → similar window → `news_restricted` + score penalty.

**Limitations today:**

- USD-only filter for desk gating
- No event names, actual/forecast, or multi-currency feed to backend
- No dedicated HTTP calendar bridge
- Calendar unavailable on some brokers → `news_available=false` (fail-open for gate)

---

## 3. Existing AI Integration

| File | Role |
|------|------|
| `backend/app/analysis/openai_client.py` | httpx → OpenAI chat completions; 60s in-process cache |
| `backend/app/analysis/ai_brief.py` | Markdown monitor snapshot for LLM |
| `backend/app/analysis/ai_validation.py` | Structured backend context + ALIGNED/CAUTION/DISAGREE footer parsing |

**Gates:** `USE_LLM=true`, `OPENAI_API_KEY` in `.env` only.

**Endpoints:**

- `GET /api/v1/monitor/llm-status`
- `GET /api/v1/monitor/ai-brief`
- `POST /api/v1/monitor/ai-analyze`

**Pattern to reuse for news:** Precompute numeric fields server-side; LLM receives normalized JSON; validate structured output before persist; cache by content hash.

---

## 4. Existing Strategy Modules

### 4.1 MQL5-primary (heartbeat blobs)

| Module | EA include | Heartbeat key | Status API |
|--------|------------|---------------|------------|
| M5 Alignment Desk | `VantageM5Desk.mqh` | `strategy` | `/api/v1/dashboard/status` |
| Pullback | `VantagePullback.mqh` | `pullback` | `/api/v1/pullback/status` |
| Gold SMC | `VantageGoldSMC*.mqh` | `gold_smc` | `/api/v1/gold-smc/status` |
| Liquidity Grab | `VantageLiquidityGrab.mqh` | `liquidity_grab` | `/api/v1/liquidity-grab/status` |
| Breakout Structure | `VantageBreakoutStructure.mqh` | `breakout_structure` | `/api/v1/breakout-structure/status` |
| Market State | `VantageMarketStateManager.mqh` | `market_state_engine` | `/api/v1/market-state/status` |
| Swing | `VantageSwingStrategy.mqh` | `swing_strategy` | `/api/v1/swing-strategy/status` |
| AMD + iFVG | `VantageAmdIfvg.mqh` | `amd_ifvg` | `/api/v1/amd-ifvg/status` |
| Box Theory | `VantageBoxTheory.mqh` | `box_theory` | `/api/v1/box-theory/status` |
| ICT | `VantageIct.mqh` | `ict` | `/api/v1/ict/status` |

### 4.2 Python re-analysis engines

| Module | Path |
|--------|------|
| Shared structure | `backend/app/market_structure/` |
| ICT | `backend/app/analysis/ict/` |
| Box Theory | `backend/app/analysis/box_theory/` |
| AMD + iFVG | `backend/app/analysis/amd_ifvg_logic.py` |
| Gold SMC (tests/helpers) | `backend/app/analysis/gold_smc_logic.py` |
| Breakout / Liq Grab helpers | `breakout_structure_logic.py`, `liquidity_grab_logic.py` |

### 4.3 Cross-cutting synthesis

| Component | Path | Notes |
|-----------|------|-------|
| Master verdict | `backend/app/analysis/master_verdict.py` | Module chips + headline verdict |
| Confluence | `backend/app/analysis/confluence/` | Weighted multi-strategy; **disabled by default** |
| Decision engine | `backend/app/analysis/decision.py` | Rule-based advisory |
| Signal ledger | `backend/app/signal_ledger.py` | SETUP_OK → accepted signals |
| Strategy desk gates | `backend/app/strategy_desk.py` | Includes news gate #7 |

**Rule:** News logic must **not** be copied into any of the above strategy folders. Macro feeds **into** confluence / master verdict / AI context only.

---

## 5. Existing Discord / Telegram Integration

| File | Role |
|------|------|
| `backend/app/alert_notify.py` | Unified dispatcher |
| `backend/app/discord_notify.py` | Main webhook; dedupe + cooldown |
| `backend/app/telegram_notify.py` | Bot API |
| `backend/app/ict_discord_notify.py` | ICT-specific webhook |
| `backend/app/box_discord_notify.py` | Box Theory webhook |

**Triggers:** Heartbeat processing, execution acks, module-specific state changes.

**Patterns to reuse:** Cooldown maps, event dedupe keys, category toggles in `config.py`, `_safe()` wrapper so alert failures never break heartbeat.

**Proposed:** `macro_discord_notify.py` or extend `alert_notify.py` with `MACRO` category — high-impact release + macro/technical alignment only.

---

## 6. Existing Database & Storage

### 6.1 SQLite (persistent)

| DB file | Module | Tables |
|---------|--------|--------|
| `backend/data/signal_ledger.db` | `signal_ledger.py` | `signals` |
| `backend/data/execution_ledger.db` | `execution_queue.py` | `executions` |

Migration style: raw SQL + `_ensure_column()` on startup. **No Alembic.**

### 6.2 In-memory only

| Store | Module | Purpose |
|-------|--------|---------|
| EA snapshots | `monitor_state.py` | Per-symbol heartbeat blobs |
| ICT setups | `analysis/ict/state_store.py` | Active setup state |
| ICT / Box history | `history.py` deques | Last N results per symbol |
| P/L calendar cache | `monitor_state.py` | Month-keyed `pl_calendar` |
| LLM cache | `openai_client.py` | 60s response cache |

**No news tables exist.**

---

## 7. Existing News / Calendar Implementation

| Layer | What exists | Gap |
|-------|-------------|-----|
| MQL5 | USD high-impact **window block** | No full event payload to backend |
| Backend gate | `strategy_desk.py` news gate | Binary pass/fail only |
| Signal ledger | `"news"` gate weight (8 pts) | No macro bias |
| AMD Python | `NewsRiskService` placeholder | `enabled=False` |
| Liquidity Grab | `news_restricted` from EA | Score penalty only |
| Monitor UI | P/L calendar | Not economic calendar |
| Dashboard | News gate on gate board | No news feed |
| External APIs | None | — |

**Important naming collision:** `pl_calendar` / `calendar-month` API = **trade history**, not macro calendar. New module should use **`market-news`** or **`macro`** naming consistently.

---

## 8. Where the News Module Should Fit

```text
                    External News Providers (future)
                              │
MT5 Terminal ──► VantageMacroBridge.mq5 ──► POST /api/v1/market-news/mt5-calendar
                              │
                              ▼
              ┌───────────────────────────────────┐
              │   News Ingestion + Normalization   │
              │   app/market_news/ (or macro/)     │
              └─────────────────┬─────────────────┘
                                │
              ┌─────────────────▼─────────────────┐
              │   Macro Intelligence Engine        │
              │   sentiment · pair bias · surprise │
              │   horizon · CB context · risk window│
              └─────────────────┬─────────────────┘
                                │
         ┌──────────────────────┼──────────────────────┐
         │                      │                      │
   Strategy engines      Confluence engine      AI validation
   (unchanged internals)  (+ MACRO signal)      (+ macro context)
         │                      │                      │
         └──────────────────────┼──────────────────────┘
                                ▼
                    Master verdict / Analyzer
                                ▼
              News/Macro desk + Discord + WS push
```

**Integration points (read-only into strategies):**

1. **`compute_confluence()`** — add normalized `StrategySignal(strategy="MACRO", ...)`.
2. **`build_master_verdict()`** — optional macro chip + conflict flag.
3. **`build_analyzer_status()`** — macro bias block for Smart Analyzer.
4. **`build_ai_validation_context()`** — macro section for LLM.
5. **`evaluate_gates()`** — upgrade news gate to use centralized event-risk service.
6. **Desk UIs** — symbol-scoped macro panel via new status API.

---

## 9. Reusable Components

| Component | Reuse for news |
|-----------|----------------|
| `VantageBackend.mqh` WebRequest pattern | New bridge EA or extend heartbeat payload |
| `monitor_state.py` | Cache latest macro snapshot per symbol; WS broadcast |
| `ws_hub.push_monitor_update("macro")` | Live desk refresh |
| `confluence/types.py` `StrategySignal` | Macro as weighted confluence input |
| `confluence/engine.py` conflict detection | Macro vs technical conflict |
| `openai_client.py` + cache | AI interpretation with hash dedupe |
| `ai_validation.py` structured context | Extend with macro block |
| `alert_notify.py` | New alert category |
| `config.py` / `.env.example` | News provider keys, risk windows, weights |
| `shell.js` nav pattern | Add "News / Macro" desk |
| ICT architecture doc | Phasing template (`docs/ICT_INTEGRATION_ARCHITECTURE.md`) |
| `signal_ledger.py` gate weights | Reference for scoring patterns |
| pytest + `tmp_path` DB fixtures | News ledger tests |

---

## 10. Files to Modify

| File | Change (future) |
|------|-----------------|
| `backend/app/config.py` | Macro/news env vars (providers, weights, risk windows, decay) |
| `backend/.env.example` | Document new secrets |
| `backend/app/schemas.py` | Pydantic models for calendar ingest, news items, macro status |
| `backend/app/routers/api.py` | New `/api/v1/market-news/*` routes |
| `backend/app/main.py` | Serve `/market-news` or `/news-macro` page |
| `backend/app/static/shell.js` | Nav entry |
| `backend/app/monitor_state.py` | Optional macro snapshot attachment |
| `backend/app/strategy_desk.py` | Delegate news gate to macro risk service |
| `backend/app/signal_ledger.py` | Richer news gate context (optional) |
| `backend/app/analysis/master_verdict.py` | Macro chip + conflict |
| `backend/app/analysis/confluence/normalize.py` | **Do not** read EA news flags here; read macro engine output |
| `backend/app/analysis/confluence/weights.py` | `MACRO` default weight |
| `backend/app/analysis/ai_brief.py` | Include macro summary |
| `backend/app/analysis/ai_validation.py` | Macro context + conflict |
| `backend/app/analysis/amd_ifvg_logic.py` | Wire real `NewsRiskService` to macro engine |
| `backend/app/alert_notify.py` | Macro alert dispatch |
| `backend/app/discord_notify.py` or new notify module | High-impact + alignment embeds |
| `MQL5/Experts/VantageMT5AIDecisionAssistant.mq5` | Optional: include macro blob from bridge timer |
| `docs/VANTAGE_SETUP.md` | Setup for macro bridge + providers |

**Do NOT modify** ICT/SMC/Box internal detection logic for news.

---

## 11. New Files / Modules Required

Suggested package layout:

```text
backend/app/market_news/
├── __init__.py
├── types.py                 # NormalizedNewsItem, EconomicEvent, enums
├── providers/
│   ├── __init__.py
│   ├── base.py              # NewsProvider protocol
│   ├── mt5_calendar.py      # Ingest from POST mt5-calendar
│   ├── rss_provider.py      # Optional RSS adapter
│   └── manual_provider.py   # Admin-submitted articles
├── ingest.py                # Dedup, persist, source weighting
├── classify.py              # Rule + optional AI category
├── surprise.py              # Actual vs forecast engine
├── sentiment.py             # Currency sentiment
├── pair_bias.py             # Symbol-level bias + drivers
├── horizon.py               # IMMEDIATE … LONG_TERM
├── central_bank.py          # CB context model
├── decay.py                 # Time decay by category
├── conflict.py              # Macro vs technical conflict
├── risk_window.py           # Event approaching filter
├── service.py               # Orchestrator: build_macro_status(symbol)
├── ai_interpret.py          # Structured LLM output + validation
├── store.py                 # SQLite access / migrations
└── discord_notify.py        # Optional dedicated notifier

backend/app/static/market-news.html   # News / Macro desk

MQL5/Include/VantageAI/
├── VantageMacroBridgeTypes.mqh
└── VantageMacroBridge.mqh            # Or standalone Experts/VantageMacroBridge.mq5

backend/tests/
├── test_market_news_normalize.py
├── test_market_news_surprise.py
├── test_market_news_sentiment.py
├── test_market_news_pair_bias.py
├── test_market_news_conflict.py
├── test_market_news_risk_window.py
├── test_market_news_api.py
└── test_market_news_integration.py
```

---

## 12. Proposed MQL5 Bridge Architecture

### Option A (recommended): Lightweight standalone EA

`MQL5/Experts/VantageMacroBridge.mq5`

- Runs on any chart; timer every 60–300s (configurable)
- Queries calendar via:
  - `CalendarValueHistory` / `CalendarValueLast`
  - `CalendarEventByCurrency` / `CalendarEventById`
- Normalizes to JSON array (all configured currencies: USD, EUR, GBP, JPY, AUD, NZD, CAD, CHF)
- `POST /api/v1/market-news/mt5-calendar` via `WebRequest` + existing Bearer token pattern from `VantageBackend.mqh`
- Sends `terminal`, `broker`, `server_time`, `events[]`
- **No fake API key** — terminal is the source; backend trusts Bearer token only

### Option B: Extend main advisory EA heartbeat

- Add `macro_calendar` blob to existing heartbeat
- Pros: one EA, simpler ops
- Cons: larger payload, couples calendar refresh to chart symbol timer

### Bridge payload (example)

```json
{
  "source": "MT5_CALENDAR",
  "server_time_utc": "2026-08-10T12:00:00Z",
  "terminal": "MetaTrader 5",
  "broker": "VantageInternational-Live",
  "events": [
    {
      "event_id": "12345",
      "currency": "USD",
      "country": "US",
      "event": "Consumer Price Index",
      "importance": "HIGH",
      "scheduled_at": "2026-08-10T12:30:00Z",
      "previous": 2.9,
      "forecast": 2.8,
      "actual": null,
      "status": "SCHEDULED"
    }
  ]
}
```

Backend maps MQL5 importance enums → `LOW|MEDIUM|HIGH|CRITICAL`.

---

## 13. Proposed API Endpoints

Follow existing convention: **`/api/v1/...`** (task spec used `/api/market-news/...`; align with project norms).

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/api/v1/market-news/mt5-calendar` | Bearer | MT5 bridge ingest |
| `GET` | `/api/v1/market-news/latest` | Open | Recent normalized news + headlines |
| `GET` | `/api/v1/market-news/calendar` | Open | Upcoming/recent economic events |
| `GET` | `/api/v1/market-news/currency/{ccy}` | Open | Currency sentiment + CB context |
| `GET` | `/api/v1/market-news/symbol/{symbol}` | Open | Pair macro bias + horizons + events |
| `GET` | `/api/v1/market-news/status` | Open | Desk composite (like ICT status) |
| `POST` | `/api/v1/market-news/analyze` | Open | On-demand AI interpret (cached) |
| `POST` | `/api/v1/market-news/ingest` | Bearer | Manual/provider bulk ingest (future) |

**Example `GET /api/v1/market-news/symbol/USDJPY` response shape** — matches task spec §14 with additions:

```json
{
  "advisory_only": true,
  "symbol": "USDJPY",
  "macro_bias": {
    "direction": "BEARISH",
    "confidence": 78,
    "horizon": "MEDIUM_TERM"
  },
  "horizons": {
    "immediate": "BULLISH",
    "intraday": "NEUTRAL",
    "swing": "BEARISH",
    "medium_term": "BEARISH"
  },
  "currency_bias": {
    "USD": { "direction": "BEARISH", "confidence": 65 },
    "JPY": { "direction": "BULLISH", "confidence": 82 }
  },
  "central_bank": { },
  "event_risk": {
    "blocked": false,
    "minutes_to_next_high_impact": 135,
    "next_event": { "event": "US CPI", "currency": "USD" }
  },
  "technical_alignment": {
    "status": "CONFLICT",
    "recommendation": "WAIT",
    "reason": "Macro bearish vs short-term momentum bullish"
  },
  "recent_news": [],
  "upcoming_events": [],
  "timeline": []
}
```

Static page: `GET /market-news` → `market-news.html`.

---

## 14. Proposed Database Changes

New SQLite file recommended: **`backend/data/market_news.db`** (isolates from signal ledger).

### Tables

**`economic_events`**

| Column | Type | Notes |
|--------|------|-------|
| id | TEXT PK | uuid |
| source | TEXT | MT5_CALENDAR, … |
| external_event_id | TEXT | MQL5 event id |
| currency | TEXT | USD |
| country | TEXT | US |
| event_name | TEXT | CPI |
| category | TEXT | CPI_INFLATION |
| importance | TEXT | HIGH |
| scheduled_at | TEXT ISO | |
| previous | REAL nullable | |
| forecast | REAL nullable | |
| actual | REAL nullable | |
| status | TEXT | SCHEDULED/RELEASED/… |
| raw_json | TEXT | optional |
| content_hash | TEXT | dedup |
| created_at | TEXT | |
| updated_at | TEXT | |

Unique index: `(source, external_event_id, scheduled_at)` or `(source, content_hash)`.

**`news_items`**

| Column | Type |
|--------|------|
| id, source, external_id, headline, summary, body |
| published_at, category, importance |
| currencies_json, symbols_json |
| raw_url, content_hash, created_at |

**`news_analysis`**

| Column | Type |
|--------|------|
| id, news_id nullable, event_id nullable |
| currency, symbol nullable |
| direction, confidence, time_horizon |
| drivers_json, counter_drivers_json |
| ai_model, analyzed_at |
| analysis_hash | cache key |

**`currency_sentiment_snapshots`**

Rolling snapshots for timeline (symbol optional).

**`central_bank_context`**

| Column | Type |
|--------|------|
| institution, currency, policy_bias, confidence |
| policy_rate, next_meeting_at, drivers_json |
| updated_at |

**Migration approach:** `init_db()` + `_ensure_column()` matching existing ledger pattern; no direct ALTER of `signals` / `executions` tables.

---

## 15. Proposed Dashboard Changes

### New desk: **News / Macro** (`/market-news`)

Sections (task §21):

1. **Market News** — headline feed with category, horizon, affected CCYs/symbols
2. **Economic Calendar** — table with prev/forecast/actual/surprise
3. **Currency Bias** — heat list (↑/↓/→)
4. **Pair Macro Bias** — selected symbol with multi-horizon breakdown
5. **Timeline** — macro bias changes through session (task §23)
6. **Event Risk Banner** — high-impact countdown (task §20)

### Existing page enhancements (later phases)

| Page | Enhancement |
|------|-------------|
| Smart Analyzer | Macro block + conflict recommendation |
| ICT / AMD desks | Read-only “Macro context” panel (API-driven, not embedded logic) |
| Dashboard gate board | Upgrade news gate with next event name/time |
| Monitor | Keep P/L calendar separate; link to News desk |

Nav: add to `shell.js` `WORKSPACE` after Market Overview or before ICT.

---

## 16. Target Logical Architecture

```text
Vantage MT5
     │
     ├── Price / OHLC / Tick Data
     │          ↓
     │   Market Structure Engine (Python + MQL5)
     │          ↓
     │   Strategy Engines (ICT / SMC / Box / AMD / …)
     │
     └── Economic Calendar Bridge (VantageMacroBridge.mq5)
                ↓
        Macro Intelligence Engine (Python)
                ↑
        External News Providers (adapters)
                │
                ↓
          News Intelligence (ingest + classify + AI)
                │
                ↓
        Fundamental / Macro Bias
                │
        ┌───────┴────────┐
        │                │
 Technical Signals   Macro Signal (StrategySignal)
        │                │
        └───────┬────────┘
                ↓
         Confluence Engine (+ configurable macro weight)
                ↓
        AI Validation Layer
                ↓
       Dashboard + Discord + WebSocket
```

---

## 17. News Source Layer (Provider Abstraction)

```python
# providers/base.py — conceptual
class NewsProvider(Protocol):
    name: str
    def fetch_latest(self) -> list[NormalizedNewsItem]: ...
    def fetch_calendar(self, *, from_utc, to_utc, currencies) -> list[EconomicEvent]: ...
```

Implementations (phased):

1. **Mt5CalendarProvider** — reads from DB populated by bridge POST
2. **ManualNewsProvider** — POST ingest for user articles
3. **RssNewsProvider** — configurable feeds (no keys)
4. **LicensedApiProvider** — FXStreet/Reuters/etc. when keys present

Source reliability weights in config (task §27) applied at ingest/scoring time.

---

## 18. Data Models (Normalized Schemas)

See task phases 5–6. Implement as Pydantic models in `market_news/types.py`:

- `EconomicEvent` — calendar row with surprise computed fields
- `NormalizedNewsItem` — textual news
- `CurrencySentiment` — direction enum + confidence
- `PairMacroBias` — symbol, drivers, horizons map
- `MacroConflictResult` — status, recommendation, reason
- `EventRiskStatus` — blocked, minutes_to_event, buffer config

Enums:

- Direction: `STRONGLY_BULLISH` … `STRONGLY_BEARISH`
- Horizon: `IMMEDIATE`, `INTRADAY`, `SHORT_TERM`, `SWING`, `MEDIUM_TERM`, `LONG_TERM`
- Importance: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`
- Category: task §7 list

---

## 19. Macro Intelligence Engine Components

| Engine | File | Responsibility |
|--------|------|----------------|
| Ingest + dedup | `ingest.py` | Provider orchestration, hash keys |
| Classify | `classify.py` | Rule tables + optional AI fallback |
| Surprise | `surprise.py` | Actual vs forecast; configurable interpretation rules |
| Sentiment | `sentiment.py` | CCY-level bias aggregation |
| Pair bias | `pair_bias.py` | USDJPY, XAUUSD (USD + gold drivers) |
| Horizon | `horizon.py` | Multi-horizon map; allow conflicts |
| Central bank | `central_bank.py` | Static + event-driven updates |
| Decay | `decay.py` | Category/importance-based relevance decay |
| Risk window | `risk_window.py` | Pre/post high-impact buffers |
| Conflict | `conflict.py` | Macro vs confluence direction |
| Service | `service.py` | `build_macro_status(symbol, ea?, confluence?)` |

**Economic values** always originate from source data (MT5/API). AI fills interpretation only.

---

## 20. Confluence & Trade Validation Integration

### Confluence changes

1. Add `MACRO` to `DEFAULT_STRATEGY_WEIGHTS` (suggest **0.35–0.40** default macro vs **0.65** technical split — configurable).
2. New function `normalize_macro_signal(macro_status) -> StrategySignal` in `market_news/` or `confluence/normalize_macro.py`.
3. Extend `compute_confluence()` inputs: `signals = normalize_ea_signals(ea) + [macro_signal]`.
4. Conflict penalty when macro direction opposes dominant technical side (reuse existing conflict list + extra macro-specific penalty).

### Trade validation rule (task §18)

Macro never sets `decision=BUY/SELL` alone. Final verdict logic:

```text
if macro_conflict and technical_not_confirmed:
    WAIT
elif macro_aligned and technical_setup_complete:
    SETUP VALIDATED (elevated confidence)
else:
    existing strategy verdict unchanged
```

Wire into `master_verdict.py` and optional `build_analyzer_status()` — not into ICT state machine.

### Event risk filter (task §20)

Centralize in `risk_window.py`:

```yaml
# config concept
news_risk_high_impact_before_minutes: 30
news_risk_high_impact_after_minutes: 15
```

Expose as warnings on desks; optionally fail news gate (backward compatible with current `news_blocked`).

---

## 21. AI News Interpretation Layer

Flow:

1. Normalize article/event → deterministic fields
2. Check `news_analysis.analysis_hash` cache
3. If miss and `USE_LLM`: call OpenAI with **structured JSON schema** (task §16)
4. Validate with Pydantic; reject hallucinated numbers
5. Persist analysis; merge into sentiment engine

New file: `market_news/ai_interpret.py` — mirror `ai_validation.py` patterns.

Endpoint `POST /api/v1/market-news/analyze` for manual re-run (admin/debug).

---

## 22. Discord News Alerts

Alert types (deduped):

1. **HIGH IMPACT EVENT** — actual released + surprise interpretation
2. **EVENT APPROACHING** — optional 15/30m warning
3. **MACRO + TECHNICAL ALIGNMENT** — e.g. macro bearish + ICT MSS confirmed

Config additions:

- `DISCORD_MACRO_ALERTS_ENABLED`
- `DISCORD_MACRO_WEBHOOK_URL` (optional separate channel)
- Cooldown + fingerprint: `{event_id}:{status}` or `{symbol}:{alignment_state}`

Do not spam on every heartbeat.

---

## 23. Configuration & Security

Add to `config.py` / `.env.example`:

```env
# Market news / macro intelligence
MARKET_NEWS_ENABLED=true
MARKET_NEWS_DB=backend/data/market_news.db

# Event risk windows (minutes)
NEWS_RISK_HIGH_BEFORE=30
NEWS_RISK_HIGH_AFTER=15

# Confluence macro weight (0-1)
CONFLUENCE_MACRO_WEIGHT=0.35

# Optional external providers
# FXSTREET_API_KEY=
# NEWSAPI_KEY=

# AI news interpretation
MARKET_NEWS_AI_ENABLED=false

# Discord macro alerts
DISCORD_MACRO_ALERTS_ENABLED=false
# DISCORD_MACRO_WEBHOOK_URL=
```

**Never expose** keys to EA, browser, or MQL5. Bearer token for ingest endpoints only.

---

## 24. Caching, Dedup, Decay, Source Reliability

| Mechanism | Key |
|-----------|-----|
| Article dedup | `sha256(source + external_id + headline + published_at)` |
| Event dedup | `(source, external_event_id, scheduled_at)` |
| AI cache | `analysis_hash` on normalized input blob |
| In-process | Short TTL for `GET /status` composite (optional 30–60s) |
| Decay | `decay.py` — CPI breaking news vs CB policy shift half-lives |

---

## 25. Error Handling & Backwards Compatibility

| Failure | Behavior |
|---------|----------|
| MT5 bridge offline | Serve last known calendar; `event_risk.blocked=false` if stale beyond TTL; warn in UI |
| Provider timeout | Skip provider; log to monitor_store |
| Malformed AI JSON | Fall back to rule-based classification only |
| Missing forecast/actual | Surprise engine skips; no fabricated values |
| Duplicate events | Upsert by external id |
| Broker calendar unavailable | Same as today: gate shows unavailable, not crashed |

**Heartbeat contract:** Existing `strategy.news_*` fields remain until consumers migrate to macro API. Deprecate gradually.

---

## 26. Testing Plan

### Unit tests

- Normalization (MT5 payload → `EconomicEvent`)
- Dedup (same event twice)
- Surprise calculation + rule mapping
- Currency sentiment aggregation
- Pair bias (USDJPY, XAUUSD)
- Horizon assignment + conflict across horizons
- Source weighting
- Time decay
- Macro vs technical conflict
- Event risk window boundaries
- AI JSON validation (mock LLM)
- Discord dedupe keys

### Integration tests

```text
MT5 calendar JSON fixture
  → POST /api/v1/market-news/mt5-calendar
  → build_macro_status("USDJPY")
  → normalize_macro_signal + compute_confluence
  → GET /api/v1/market-news/symbol/USDJPY
  → static page contains sections
```

### Regression

- Full pytest suite (256+ tests) after each phase
- ICT / Box / AMD status endpoints unchanged
- Heartbeat without macro blob still succeeds

---

## 27. Risks

| Risk | Mitigation |
|------|------------|
| Breaking heartbeat payload size | Standalone bridge EA or optional compact blob |
| Duplicating M5 desk news logic | Centralize in Python; EA bridge becomes source of truth |
| AI hallucinating CPI/NFP numbers | Strict schema validation; numbers from DB only |
| Over-weighting macro in confluence | Default macro weight ≤ 0.35; configurable |
| Calendar differences by broker | Store `broker` on ingest; show data freshness |
| Naming collision with P/L calendar | Use `market-news` / `economic_events` naming only |
| Open dashboard APIs | Same as today; ingest endpoints Bearer-protected |
| Scope creep into auto-trading | Explicit `advisory_only` on all macro responses |
| SQLite write contention | Separate DB file; batch upserts on bridge interval |
| Stale macro bias misleading traders | Decay + `as_of_utc` on every response |

---

## 28. Phased Implementation Plan

Aligned with task §33 and project norms (incremental, test after each step).

### Step 1 — Audit (this document) ✅

Deliverable: `docs/NEWS_INTELLIGENCE_ARCHITECTURE.md` — **STOP here until approved.**

### Step 2 — Normalized types + provider interfaces

- `market_news/types.py`, `providers/base.py`
- Pydantic schemas in `schemas.py`
- No UI yet

### Step 3 — Database + ingest

- `market_news/store.py`, `market_news.db`
- `POST /api/v1/market-news/mt5-calendar` with fixture tests
- Dedup + upsert

### Step 4 — MQL5 bridge

- `VantageMacroBridge.mq5` + types include
- Multi-currency high/medium events
- Document WebRequest URL allowlist in `VANTAGE_SETUP.md`

### Step 5 — News provider abstraction

- Mt5CalendarProvider reading DB
- Manual ingest endpoint stub

### Step 6 — Macro intelligence core

- surprise, classify (rules), sentiment, pair_bias, horizon, risk_window
- `GET /api/v1/market-news/calendar`, `/currency/{ccy}`, `/symbol/{sym}`

### Step 7 — Central bank context (static seed + event updates)

- Configurable JSON seed for major CBs; update from high-impact events

### Step 8 — Confluence integration

- `normalize_macro_signal`, config weights, conflict detection
- Feature-flagged: `MARKET_NEWS_ENABLED` + `CONFLUENCE_ENABLED`

### Step 9 — Master verdict + analyzer + desk gates

- Macro chip, conflict recommendation, upgrade `strategy_desk` news gate

### Step 10 — News / Macro dashboard

- `market-news.html`, shell nav, timeline section

### Step 11 — AI interpretation (optional phase)

- Cached structured LLM; `POST /analyze`

### Step 12 — Discord alerts

- High-impact release + alignment alerts

### Step 13 — External provider adapter (optional)

- RSS or licensed API behind feature flag

### Step 14 — Full regression + VPS deploy docs

---

## 29. Phase 1 Deliverable — STOP Point

**Completed in this phase:**

1. Current system architecture documented  
2. Existing MT5 integration mapped (MQL5 calendar gating, no Python MT5)  
3. Existing AI integration mapped  
4. Existing strategy modules inventoried  
5. Discord/Telegram patterns documented  
6. Database models assessed (no news tables today)  
7. News module placement in architecture defined  
8. Reusable files listed  
9. Files to modify listed  
10. New files/modules proposed  
11. MQL5 bridge architecture proposed (`VantageMacroBridge.mq5`)  
12. API endpoints proposed (`/api/v1/market-news/*`)  
13. Database changes proposed (`market_news.db`)  
14. Dashboard changes proposed (`/market-news` desk)  
15. Risks and backwards-compatibility concerns documented  
16. Step-by-step implementation plan defined  

**Not started (awaiting approval):**

- Any production code changes  
- MQL5 bridge implementation  
- New database tables  
- Confluence weight changes  
- Discord macro alerts  

---

## Appendix A — Example Final Assistant Output (Target Behavior)

Task §32 — produced by combining existing desk status + macro service + confluence (future):

```text
USDJPY

TECHNICAL
ICT: Bearish 82%
SMC: Bearish 75%

MACRO
Bias: Bearish 78%

JPY: Bullish
USD: Mild Bearish

MAIN DRIVER
BoJ risks skewed hawkish; Fed expectations dovish.

CURRENT CONFLICT
Short-term USDJPY momentum remains bullish.

UPCOMING RISK
US CPI — 2h 15m

DECISION
WAIT FOR SHORT CONFIRMATION
```

This output is **explanatory** — not an auto-trade instruction.

---

## Appendix B — Related Documentation

| Doc | Relevance |
|-----|-----------|
| `docs/ICT_INTEGRATION_ARCHITECTURE.md` | Pattern for phased module integration |
| `docs/VANTAGE_SETUP.md` | EA WebRequest, VPS, env setup |
| `docs/PULLBACK_PROBABILITY.md` | Example of advisory-only isolated module |
| `README.md` | Platform overview |

---

*End of Phase 1 audit. Implementation begins only after review approval.*
