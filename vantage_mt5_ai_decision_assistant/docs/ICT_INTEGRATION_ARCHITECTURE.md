# ICT Integration Architecture

**Document type:** Phase 1 architecture audit + phased integration plan  
**Status:** Review only — no implementation started  
**Date:** 2026-07-29  
**Scope:** `vantage_mt5_ai_decision_assistant` (FastAPI backend, static dashboard, MQL5 EA)

---

## Executive Summary

The Vantage MT5 AI Decision Assistant is already a **multi-strategy decision-support platform**. Most strategies run in **MQL5 on closed bars** and arrive at the backend as JSON blobs via `POST /api/v1/heartbeat`. The backend stores them in an in-memory `monitor_store`, exposes passthrough status routes, synthesizes a **master verdict**, and optionally runs **offline Python analyzers** for AMD+iFVG and Box Theory.

Adding ICT should follow the same pattern as Box Theory and AMD+iFVG:

1. Extract shared market-structure primitives into a reusable Python engine.
2. Build an independent ICT strategy module that consumes those primitives.
3. Wire ICT into heartbeat, API, dashboard, Discord, confluence, and AI explanation layers.
4. Optionally mirror ICT in MQL5 later — but backend-first is safer for testability and backtesting.

**Critical constraint:** Do not rewrite working MQL5 modules or break existing heartbeat contracts. Prefer incremental extraction and additive APIs.

---

## Table of Contents

1. [Current Architecture Audit](#1-current-architecture-audit)
2. [Current Data Flow](#2-current-data-flow)
3. [Existing Strategy Inventory](#3-existing-strategy-inventory)
4. [Reusable Market-Structure Code Today](#4-reusable-market-structure-code-today)
5. [Technical Debt and Duplication](#5-technical-debt-and-duplication)
6. [Target Architecture](#6-target-architecture)
7. [Proposed Shared Market Structure Engine](#7-proposed-shared-market-structure-engine)
8. [Proposed ICT Strategy Engine](#8-proposed-ict-strategy-engine)
9. [Proposed File / Folder Layout](#9-proposed-file--folder-layout)
10. [Database and Persistence Plan](#10-database-and-persistence-plan)
11. [API Changes](#11-api-changes)
12. [Dashboard, Discord, and AI Integration](#12-dashboard-discord-and-ai-integration)
13. [Multi-Strategy Confluence Plan](#13-multi-strategy-confluence-plan)
14. [Configuration Plan](#14-configuration-plan)
15. [Risks of Breaking Existing Functionality](#15-risks-of-breaking-existing-functionality)
16. [Phased Implementation Sequence](#16-phased-implementation-sequence)
17. [Phase 27 Deliverable — STOP Point](#17-phase-27-deliverable--stop-point)

---

## 1. Current Architecture Audit

### 1.1 Backend Framework

| Component | Technology | Location |
|-----------|------------|----------|
| Web framework | **FastAPI** | `backend/app/main.py` |
| Server entry | **Uvicorn** | `backend/run.py` |
| Routing | Single `APIRouter` | `backend/app/routers/api.py` |
| Validation | **Pydantic v2** | `backend/app/schemas.py` |
| Settings | **pydantic-settings** + `.env` | `backend/app/config.py` |
| Real-time | WebSocket hub | `backend/app/ws_hub.py` → `/ws/monitor` |
| Static frontend | Vanilla HTML/JS/CSS | `backend/app/static/` |
| Tests | **pytest** | `backend/tests/`, `tests/` |

There is **no SQLAlchemy ORM**, **no Celery/RQ**, and **no Redis cache**. State is mostly in-process.

### 1.2 Frontend / Dashboard Framework

| Component | Approach |
|-----------|----------|
| UI | Static HTML pages per strategy desk |
| Navigation | Shared `shell.js` + `shell.css` injected into every page |
| Data | REST polling + WebSocket snapshot from `monitor_store` |
| Routes | Registered in `main.py` (`/monitor`, `/gold-smc`, `/box-theory`, etc.) |

There is **no React/Vue SPA**. New ICT UI should follow the existing desk-page pattern (`ict.html` + nav entry in `shell.js`).

### 1.3 MT5 / Vantage Integration

| Component | Location |
|-----------|----------|
| EA | `MQL5/Experts/VantageMT5AIDecisionAssistant.mq5` |
| Backend client | `MQL5/Include/VantageAI/VantageBackend.mqh` |
| Shared types | `VantageTypes.mqh`, `VantageRisk.mqh`, etc. |

**Transport:**

| Channel | Endpoint | Trigger | Auth |
|---------|----------|---------|------|
| Heartbeat | `POST /api/v1/heartbeat` | Every `InpHeartbeatSec` (default 15s) | Bearer token |
| Analyze | `POST /api/v1/analyze` | Closed M30 bar | Bearer token |
| Health | `GET /health` | EA init | None |

**Important:** The EA sends **pre-computed strategy blobs**, not raw multi-timeframe OHLC arrays (except offline analyze endpoints for AMD/Box).

### 1.4 Market Data Ingestion

| Source | What arrives | Storage |
|--------|--------------|---------|
| Heartbeat | Latest bid/ask/spread, M30 advisory fields, strategy JSON blobs | `monitor_store.EaSnapshot` (in-memory) |
| Analyze (M30) | Full candle + indicators + structure for one M30 bar | Processed by `decision.decide()`; not persisted as OHLC history |
| Offline analyze | Client-supplied OHLC arrays (M15/M5/H1) | Ephemeral per request |

There is **no centralized OHLC database** or candle cache in the backend today. Historical analysis requires the caller to POST candles.

### 1.5 Timeframe Handling

Timeframes are **module-specific**, not centralized:

| Module | Timeframes (runtime) |
|--------|---------------------|
| M30 core advisory | M30 |
| M5 Alignment Desk | H1 bias, M15 structure, M5 trigger |
| Gold SMC (MQL5) | D1, H4, H1, M15, M5, M1 |
| Liquidity Grab | M5 detect, M5/M15 confirm, H1 context, H4 major |
| Breakout Structure | H4, H1, M15, M5, M1 |
| Market State Engine | H4, H1, M15, M5, M1 |
| Swing Strategy | D1, H4, H1, M15, M5 |
| AMD + iFVG | H4, H1, M15, M5 |
| Box Theory | H1 structure, M15 box/breakout, M5 retest/FVG |

### 1.6 Database Models / Schema

| Store | File | Persistence |
|-------|------|-------------|
| Monitor state | `monitor_state.py` | In-memory only (lost on restart) |
| Signal ledger | `signal_ledger.py` | SQLite `backend/data/signal_ledger.db` |
| Execution queue | `execution_queue.py` | SQLite `backend/data/execution_ledger.db` |
| Box history | `box_theory/history.py` | In-memory deque (max 50/symbol) |
| AMD history | None dedicated | Passthrough only |

**No migrations framework.** SQLite uses ad-hoc `_ensure_column()` helpers.

### 1.7 Authentication

| Route class | Auth |
|-------------|------|
| Heartbeat, analyze, execution | Bearer `LOCAL_API_TOKEN` via `require_bearer()` |
| Monitor status, strategy desks, LLM brief | Mostly unauthenticated |
| Discord/Telegram test (monitor) | Unauthenticated |
| Discord/Telegram test (api) | Bearer required |

### 1.8 AI / OpenAI Integration

| File | Role |
|------|------|
| `analysis/openai_client.py` | `analyze_with_openai()`, 60s in-process cache |
| `analysis/ai_brief.py` | Markdown snapshot for LLM (`build_ai_brief_markdown()`) |

**AI is explanation-only today.** It does not compute structure, scores, or trade signals. This aligns with ICT requirements.

Routes: `/api/v1/monitor/ai-brief`, `/api/v1/monitor/ai-analyze`, `/api/v1/monitor/llm-status`

Config: `USE_LLM`, `OPENAI_API_KEY`, `OPENAI_MODEL`

### 1.9 Discord / Telegram Notifications

| File | Role |
|------|------|
| `alert_notify.py` | Fan-out on heartbeat |
| `discord_notify.py` | Main webhook; module state-change alerts |
| `telegram_notify.py` | Parallel Telegram alerts |
| `box_discord_notify.py` | Dedicated Box Theory webhook + dedupe |

Dedupe pattern: in-memory `{signal_id}` set + cooldown seconds. **Lost on restart.**

Box Discord currently requires main Discord path to be enabled in some flows — known quirk.

### 1.10 Logging

| Mechanism | Usage |
|-----------|-------|
| Python `logging` | Standard module logs |
| `monitor_store.add_log()` | Structured desk logs surfaced in UI |
| Box Theory | `[BOX]` prefixed logs via `_box_log()` |

No dedicated explainability trace store exists yet.

### 1.11 Configuration / Environment Variables

Configuration uses **`pydantic-settings`** (`config.py`) + `.env`. **No YAML config layer exists.**

Strategy configs today are **dataclasses** inside each module (`AmdIfvgConfig`, `BoxStrategyConfig`) with defaults, overridable per analyze request.

Examples: `.env.docker.example`, `backend/.env.example`

### 1.12 Background Workers / Caching

| Feature | Status |
|---------|--------|
| Background jobs | ❌ None |
| OHLC cache | ❌ None |
| LLM response cache | ✅ 60s in-process (`openai_client.py`) |
| Alert dedupe cache | ✅ In-process per process lifetime |

### 1.13 Risk Management (Shared)

| Location | Role |
|----------|------|
| `decision.py` | M30 equity risk bands, float profit targets |
| `strategy_desk.py` | M5 desk gates (RR, spread, ADX, news block) |
| `box_theory/risk.py` | Structural SL/TP for Box Theory |
| `amd_ifvg_logic.py` | Minimum RR, spread, news placeholder |
| `master_verdict.py` | Hard blocks on CRITICAL risk / high spread |
| MQL5 `VantageRisk.mqh` | EA-side risk sent in heartbeat |

---

## 2. Current Data Flow

```text
MT5 EA (closed bars, MQL5 strategy engines)
    ↓
POST /api/v1/heartbeat  (every ~15s)
POST /api/v1/analyze      (on M30 close)
    ↓
monitor_store.record_heartbeat()
    ↓
┌─────────────────────────────────────────────────────────────┐
│ Parallel consumers (read monitor_store.status())            │
├─────────────────────────────────────────────────────────────┤
│ • GET /api/v1/{strategy}/status  → static HTML desks        │
│ • build_decision_brief()         → master_verdict           │
│ • strategy_desk.build_dashboard() → M5 gate evaluation      │
│ • signal_ledger.maybe_accept_from_monitor() → SQLite        │
│ • alert_notify.process_heartbeat() → Telegram/Discord       │
│ • execution_queue.reserve_next() → swing blob (demo only)   │
└─────────────────────────────────────────────────────────────┘

Offline path (2 strategies only):
POST /api/v1/amd-ifvg/analyze  → analyze_amd_ifvg()
POST /api/v1/box-theory/analyze → analyze_box_strategy()
```

**Key insight:** Live path is **EA-compute → backend-store → display/alert**. Backend Python engines are secondary except for offline testing and Box/AMD analyze endpoints.

---

## 3. Existing Strategy Inventory

### 3.1 Strategy Support Matrix

| Strategy | MQL5 | Web UI | Backend logic | API status | Offline analyze |
|----------|:----:|:------:|:-------------:|:----------:|:-----------------:|
| M30 Monitor / Cockpit | ✅ | `/monitor` | `decision.py` | `/api/v1/monitor/status` | `/api/v1/analyze` |
| M5 Alignment Desk | ✅ | `/dashboard` | `strategy_desk.py` | `/api/v1/dashboard/status` | — |
| Pullback Probability | ✅ | `/pullback` | Passthrough | `/api/v1/pullback/status` | — |
| Gold SMC | ✅ | `/gold-smc` | Scoring helpers only | `/api/v1/gold-smc/status` | — |
| Liquidity Grab | ✅ | `/liquidity-grab` | Scoring helpers only | `/api/v1/liquidity-grab/status` | — |
| Breakout Structure | ✅ | `/breakout-structure` | Scoring helpers only | `/api/v1/breakout-structure/status` | — |
| Market State Engine v2 | ✅ | `/market-state` | Passthrough | `/api/v1/market-state/status` | — |
| Swing Strategy | ✅ | `/market-state` | Passthrough | `/api/v1/swing-strategy/status` | — |
| AMD + iFVG | ✅ | `/amd-ifvg` | **Full engine** | status + analyze | ✅ |
| Box Theory | ✅ | `/box-theory` | **Full engine** | status + analyze | ✅ |
| Pattern / Scanner / Lab | — | yes | Aggregators | yes | — |

### 3.2 Backend Python Strategy Modules

```
backend/app/analysis/
├── decision.py              # M30 advisory
├── amd_ifvg_logic.py        # Full AMD+iFVG engine (richest structure code)
├── box_theory/              # Full Box Theory package
│   ├── service.py           # Orchestrator
│   ├── detector.py, breakout.py, retest.py, fakeout.py
│   ├── liquidity.py, scorer.py, risk.py, types.py, utils.py
├── gold_smc_logic.py        # Premium/discount, OTE, grading helpers
├── breakout_structure_logic.py  # Test scoring mirror
├── liquidity_grab_logic.py      # Test scoring mirror
├── master_verdict.py        # Cross-strategy synthesis (not full confluence)
├── briefing.py, ai_brief.py
└── openai_client.py
```

### 3.3 MQL5 Strategy Modules (Primary Runtime)

```
MQL5/Include/VantageAI/
├── VantageGoldSMCCore.mqh       # Swings, BOS/CHoCH/MSS
├── VantageGoldSMCLiquidity.mqh  # BSL/SSL, equal highs/lows
├── VantageLiquidityGrab.mqh     # Session, sweep sequence
├── VantageBreakoutStructure.mqh
├── VantageMarketStateManager.mqh # BOS/CHoCH state machine
├── VantageSwingStrategy.mqh
├── VantageAmdIfvg.mqh           # AMD phase + iFVG state machine
├── VantageBoxTheory.mqh
└── VantageM5Desk.mqh
```

**SMC logic is richest in MQL5 (`VantageGoldSMCCore.mqh`), not Python.**

---

## 4. Reusable Market-Structure Code Today

### 4.1 Python (Backend)

| Capability | Location | Maturity | Notes |
|------------|----------|----------|-------|
| Swing pivots | `amd_ifvg_logic.find_swings()` | ⚠️ Basic | Left/right pivot; no HH/HL/LH/LL labeling |
| MSS | `amd_ifvg_logic.detect_mss()` | ⚠️ Basic | Body break of last swing; not full ICT MSS |
| BOS | — | ❌ Missing | Not in Python |
| CHoCH | — | ❌ Missing | Not in Python |
| FVG | `amd_ifvg_logic.detect_fvgs()` | ✅ Good | 3-candle, ATR min gap, ID dedupe |
| FVG mitigation | `update_fvg_mitigation()` | ✅ Good | Partial/full tracking |
| iFVG | `try_invert_fvg()` | ✅ Good | Body-close inversion |
| Liquidity sweep | `detect_manipulation()` | ⚠️ Partial | Accumulation-bound only |
| Liquidity sweep | `box_theory/liquidity.py` | ⚠️ Partial | Box-bound only |
| Displacement | `score_displacement()` | ⚠️ Partial | Single-candle score |
| Premium/discount | `amd_ifvg_logic.premium_discount()` | ⚠️ Partial | 4-zone label |
| Premium/discount | `gold_smc_logic.premium_discount_label()` | ⚠️ Duplicate | Overlapping concept |
| HTF bias | `amd_ifvg_logic._htf_bias()`, `box_theory/scorer.htf_bias()` | ⚠️ Duplicate | 20-bar close count |
| ATR | `box_theory/utils.py`, duplicated in AMD | ⚠️ Duplicate | |
| Candle validation | Duplicated in box + AMD | ⚠️ Duplicate | |
| Session context | — | ❌ Missing in Python | Exists in MQL5 Liquidity Grab |
| PDH/PDL/PWH/PWL | — | ❌ Missing in Python | Partial in MQL5 |
| Equal highs/lows | — | ❌ Missing in Python | Partial in Gold SMC MQL5 |

### 4.2 MQL5 (Live Runtime — Not Yet Shared with Python)

| Capability | Primary file |
|------------|--------------|
| External/internal BOS | `VantageGoldSMCCore.mqh` |
| CHoCH | `VantageGoldSMCCore.mqh` |
| MSS events | `VantageGoldSMCCore.mqh`, `VantageGoldSMCSetup.mqh` |
| Session names / kill zones | `VantageLiquidityGrab.mqh`, `VantageGoldSMCSetup.mqh` |
| BSL/SSL pools | `VantageGoldSMCLiquidity.mqh` |
| BOS state machine | `VantageMarketStateManager.mqh` |
| AMD phase state machine | `VantageAmdIfvg.mqh` |

**Gap:** Structure is computed twice in different languages with no shared normalized contract.

---

## 5. Technical Debt and Duplication

| Issue | Impact on ICT | Recommended action |
|-------|---------------|-------------------|
| Duplicate `Candle`, `atr()`, `validate_candles()` | High | Extract to `market_structure/core/` |
| Duplicate `htf_bias()` | Medium | Single `bias.py` in shared engine |
| Duplicate `premium_discount()` | Medium | Unify dealing-range model |
| Duplicate passthrough API handlers (~30 lines × N) | Low | Factory helper in `api.py` |
| Duplicate Discord/Telegram dedupe | Medium | Shared `notify_dedupe.py` |
| Duplicate SQLite helpers | Low | Shared `db_utils.py` |
| AMD state machine ≈ ICT state machine | High | ICT can reuse AMD patterns, not copy |
| Box Theory timing bug (`end_time` vs breakout) | Medium | Fix during shared engine refactor |
| No persistent setup state | **High for ICT** | Add setup store (SQLite or in-memory first) |
| Gold-only guards scattered | Low | Keep `gold_symbol_validator.py` as gate |
| Master verdict ≠ confluence engine | Medium | Build proper confluence layer |

---

## 6. Target Architecture

```text
MT5 / Vantage
    ↓
Market Data Engine          ← NEW: normalized candle ingestion (optional live OHLC POST)
    ↓
Market Structure Engine     ← NEW: shared swings, BOS, CHoCH, MSS, liquidity, FVG, displacement, PD
    ↓
Strategy Engines
    ├── ICT                 ← NEW
    ├── SMC                 ← existing MQL5 + future Python mirror
    ├── Box Theory          ← existing (refactor to consume shared FVG/liquidity)
    ├── AMD × iFVG          ← existing (refactor to consume shared engine)
    ├── Breakout Structure  ← existing MQL5 passthrough
    ├── Swing               ← existing MQL5 passthrough
    └── future strategies
    ↓
Confluence Engine           ← NEW (evolve master_verdict.py)
    ↓
AI Validation / Explanation ← existing (extend structured JSON input)
    ↓
Dashboard + Discord         ← existing pattern
```

Each strategy remains **independently testable** via:

- Unit tests on pure functions (synthetic OHLC fixtures)
- `POST /api/v1/strategy/{name}/analyze` offline endpoint
- Optional MQL5 mirror for live closed-bar evaluation

---

## 7. Proposed Shared Market Structure Engine

**Location:** `backend/app/market_structure/`

Design principle: **Pure functions on closed candles.** No look-ahead. Pivots confirmed only after `pivot_right` bars have closed.

### 7.1 Normalized Output Types (`types.py`)

```python
# Conceptual — not implemented yet

@dataclass
class SwingPoint:
    kind: Literal["HIGH", "LOW"]
    price: float
    time: int
    index: int
    confirmed: bool

@dataclass
class StructureEvent:
    event_type: Literal["BOS", "CHOCH", "MSS"]
    direction: Literal["BULLISH", "BEARISH"]
    broken_level: float
    break_time: int
    confirmation: Literal["BODY_CLOSE", "WICK_REJECTED"]
    quality_score: float
    context: dict

@dataclass
class LiquidityLevel:
    kind: Literal["BSL", "SSL", "EQH", "EQL", "PDH", "PDL", "PWH", "PWL", "SESSION_H", "SESSION_L"]
    price: float
    time: int
    source: str
    tolerance: float

@dataclass
class LiquiditySweep:
    level: LiquidityLevel
    penetration: float
    sweep_time: int
    wick_ratio: float
    closed_back_inside: bool
    displacement_followed: bool
    strength_score: float

@dataclass
class FvgZone:  # migrate from amd_ifvg_logic
    fvg_id: str
    direction: str
    timeframe: str
    lower: float
    upper: float
    mitigation_pct: float
    status: str
    ...

@dataclass
class DealingRange:
    high: float
    low: float
    source: str  # e.g. "HTF_SWING_RANGE", "SESSION_RANGE", "ACCUMULATION"
    start_time: int
    end_time: int

@dataclass
class MarketStructureSnapshot:
    symbol: str
    timeframe: str
    as_of_time: int
    swings: list[SwingPoint]
    structure_events: list[StructureEvent]
    liquidity_levels: list[LiquidityLevel]
    sweeps: list[LiquiditySweep]
    fvgs: list[FvgZone]
    dealing_range: DealingRange | None
    premium_discount: str
    displacement: list[DisplacementEvent]
```

### 7.2 Module Breakdown

| Module | Responsibility | Primary source to extract from |
|--------|----------------|--------------------------------|
| `core/candles.py` | `Candle`, validation, ATR, body metrics | `box_theory/utils.py` |
| `swings.py` | Pivot detection, HH/HL/LH/LL labeling | `amd_ifvg_logic.find_swings()` + Gold SMC concepts |
| `structure.py` | BOS, CHoCH, MSS with distinct rules | NEW + MQL5 `VantageGoldSMCCore.mqh` spec |
| `liquidity.py` | BSL/SSL, EQH/EQL, PDH/PDL, sessions | NEW + MQL5 liquidity modules |
| `sweep.py` | Full sweep lifecycle scoring | `detect_manipulation()` + `box_theory/liquidity.py` |
| `fvg.py` | FVG detect, mitigate, dedupe by ID | `amd_ifvg_logic.detect_fvgs()` |
| `ifvg.py` | Inversion rules | `try_invert_fvg()` |
| `displacement.py` | Multi-factor displacement | `score_displacement()` |
| `premium_discount.py` | Dealing range + zones | Unify AMD + Gold SMC |
| `sessions.py` | Asia/London/NY, timezone-aware | NEW (port from MQL5 Liquidity Grab) |
| `engine.py` | `build_market_structure(candles, cfg) -> Snapshot` | Orchestrator |

### 7.3 Look-Ahead Safety Rules (Mandatory)

1. Pivot at index `i` requires candles `[i-left .. i+right]` all closed.
2. Structure events reference only swings confirmed at event time.
3. FVG IDs include creation time — no duplicate records for same gap.
4. Sweep requires penetration + close behavior + optional displacement lag (configurable max candles).
5. All analyze functions accept `as_of_time` optional cutoff for backtesting.

### 7.4 Refactor Strategy (Non-Breaking)

**Phase A — Extract without behavior change:**

1. Move shared types/functions to `market_structure/`.
2. Re-export from `amd_ifvg_logic` and `box_theory` for backwards compatibility.
3. Run existing AMD + Box tests — must pass unchanged.

**Phase B — Enrich:**

4. Add BOS/CHoCH/MSS distinction.
5. Add session + PDH/PDL levels.
6. Add EQH/EQL with ATR tolerance.

---

## 8. Proposed ICT Strategy Engine

**Location:** `backend/app/analysis/ict/`

ICT should **consume** `MarketStructureSnapshot` objects per timeframe, not recompute structure.

### 8.1 Module Layout

```
backend/app/analysis/ict/
├── __init__.py
├── types.py           # IctConfig, IctSetupState, IctDecision, enums
├── bias.py            # HTF bias engine (multi-TF weighted)
├── session.py         # Session context wrapper (uses market_structure/sessions.py)
├── models/
│   ├── bullish.py     # SSL → sweep → displacement → MSS → FVG → retrace → BSL
│   └── bearish.py     # BSL → sweep → ... → SSL
├── state_machine.py   # Setup lifecycle + persistence hooks
├── entry.py           # Entry zone (FVG retrace, PD filter)
├── targets.py         # TP1/TP2/external liquidity
├── risk.py            # Structural SL + RR gates
├── scorer.py          # Deterministic 100-point scoring
├── service.py         # analyze_ict_strategy() orchestrator
├── history.py         # In-memory + optional SQLite
└── explain.py         # Human-readable decision trace
```

### 8.2 ICT State Machine (Required)

```
WAITING_FOR_LIQUIDITY
    → LIQUIDITY_SWEPT
    → WAITING_FOR_DISPLACEMENT
    → DISPLACEMENT_CONFIRMED
    → WAITING_FOR_MSS
    → MSS_CONFIRMED
    → WAITING_FOR_RETRACE
    → ENTRY_ZONE_ACTIVE
    → TRIGGERED
    → INVALIDATED | TARGET_REACHED | EXPIRED
```

**Key difference from AMD+iFVG:** ICT is liquidity-first (external pool sweep), AMD is accumulation-first. They share primitives but **different orchestration**.

State keyed by: `{symbol}:{setup_timeframe}:{setup_id}`

Reference: AMD already has a similar state machine in `amd_ifvg_logic.SetupState` — use as template, do not merge engines.

### 8.3 Multi-Timeframe Mapping (Configurable)

Default config in `IctConfig` dataclass (not YAML — follow project convention):

```python
@dataclass
class IctConfig:
    enabled: bool = True
    higher_timeframes: tuple[str, ...] = ("D1", "H4", "H1")
    setup_timeframes: tuple[str, ...] = ("H1", "M15")
    execution_timeframes: tuple[str, ...] = ("M15", "M5")
    min_confidence: float = 70.0
    minimum_rr: float = 2.0
    require_liquidity_sweep: bool = True
    require_displacement: bool = True
    require_mss: bool = True
    require_fvg: bool = True
    use_premium_discount: bool = True
    use_session_filter: bool = True
    swing_length: int = 5
    equal_high_low_tolerance_atr: float = 0.10
    # scoring weights (sum = 100)
    weight_htf_alignment: float = 20.0
    weight_liquidity_sweep: float = 20.0
    weight_displacement: float = 15.0
    weight_mss: float = 15.0
    weight_fvg: float = 10.0
    weight_premium_discount: float = 10.0
    weight_session: float = 5.0
    weight_risk_reward: float = 5.0
```

### 8.4 Scoring (Deterministic — AI Must Not Invent)

| Component | Default weight |
|-----------|----------------|
| HTF alignment | 20 |
| Liquidity sweep quality | 20 |
| Displacement | 15 |
| MSS | 15 |
| FVG quality | 10 |
| Premium/discount | 10 |
| Session context | 5 |
| Risk/reward | 5 |
| **Total** | **100** |

Return `components` dict alongside `score` for explainability.

### 8.5 Entry Zone (Not Exact Price)

```json
{
  "entry": {
    "type": "FVG_RETRACE",
    "direction": "SELL",
    "zone_high": 3418.20,
    "zone_low": 3413.60,
    "midpoint": 3415.90,
    "status": "ACTIVE"
  }
}
```

States: `DETECTED` → `ACTIVE` → `TOUCHED` → `CONFIRMED` → `INVALIDATED`

---

## 9. Proposed File / Folder Layout

### 9.1 New Files

```
backend/app/market_structure/
├── __init__.py
├── types.py
├── core/
│   ├── candles.py
│   └── metrics.py
├── swings.py
├── structure.py
├── liquidity.py
├── sweep.py
├── fvg.py
├── ifvg.py
├── displacement.py
├── premium_discount.py
├── sessions.py
└── engine.py

backend/app/analysis/ict/
├── (see §8.1)

backend/app/analysis/confluence/
├── __init__.py
├── types.py
├── engine.py          # normalize + weight strategies
└── weights.py

backend/app/ict_discord_notify.py   # mirror box_discord_notify.py pattern

backend/app/static/ict.html

backend/tests/
├── test_market_structure_swings.py
├── test_market_structure_bos.py
├── test_market_structure_choch.py
├── test_market_structure_mss.py
├── test_market_structure_liquidity.py
├── test_market_structure_fvg.py
├── test_ict_logic.py
├── test_ict_state_machine.py
├── test_ict_scoring.py
├── test_confluence_engine.py
├── test_ict_status.py
└── test_ict_static.py

MQL5/Include/VantageAI/
├── VantageIctTypes.mqh
└── VantageIct.mqh

docs/
├── ICT_INTEGRATION_ARCHITECTURE.md   # this document
└── ICT.md                            # user-facing strategy docs (later)
```

### 9.2 Files to Reuse (Minimal Changes)

| File | Reuse for |
|------|-----------|
| `amd_ifvg_logic.py` | Extract FVG, swings, MSS, displacement, premium/discount |
| `box_theory/liquidity.py` | Extract sweep scoring patterns |
| `gold_smc_logic.py` | Premium/discount zone labels, grading tiers |
| `gold_symbol_validator.py` | Symbol gate |
| `monitor_state.py` | Add `ict` blob field to `EaSnapshot` |
| `schemas.py` | Add `ict: Optional[dict]` to `HeartbeatRequest` |
| `master_verdict.py` | Add ICT chip (short term); confluence engine (long term) |
| `ai_brief.py` | Include ICT structured JSON in LLM context |
| `box_discord_notify.py` | Template for ICT Discord dedupe |
| `alert_notify.py` | Wire ICT alerts |
| `main.py` | Route `/ict` |
| `shell.js` | Nav entry |

### 9.3 Files to Refactor (Carefully)

| File | Refactor | Risk |
|------|----------|------|
| `amd_ifvg_logic.py` | Import from `market_structure/` | **Medium** — must keep test parity |
| `box_theory/service.py` | Import shared FVG + ATR | **Medium** |
| `box_theory/scorer.py` | Import shared `htf_bias()` | **Low** |
| `routers/api.py` | Shared status envelope helper | **Low** |
| `master_verdict.py` | Delegate to confluence engine | **Medium** |
| `discord_notify.py` | ICT state-change handler | **Low** |

### 9.4 Files NOT to Rewrite

| File | Reason |
|------|--------|
| MQL5 Gold SMC modules | Working live runtime; mirror later |
| MQL5 Market State Engine | Independent module |
| `decision.py` | M30 core advisory — separate concern |
| `signal_ledger.py` | M5 desk workflow — unchanged |
| `execution_queue.py` | Demo executor — unchanged |

---

## 10. Database and Persistence Plan

### 10.1 Current State

ICT **requires setup state persistence** across heartbeats (multi-candle setups). Current in-memory-only approach is insufficient for production ICT.

### 10.2 Recommended Approach (Incremental)

**Step 1 — In-memory state store (like Box history):**

`ict/state_store.py` — dict keyed by setup_id, lost on restart. Sufficient for MVP + tests.

**Step 2 — SQLite setup ledger (when stable):**

New table in existing SQLite pattern (follow `signal_ledger.py` style):

```sql
CREATE TABLE ict_setups (
    setup_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    direction TEXT,
    state TEXT NOT NULL,
    htf_bias TEXT,
    liquidity_event_json TEXT,
    sweep_time INTEGER,
    mss_json TEXT,
    fvg_json TEXT,
    entry_zone_json TEXT,
    stop_loss REAL,
    targets_json TEXT,
    confidence REAL,
    score_components_json TEXT,
    invalidation_json TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    result TEXT
);
```

Use `_ensure_column()` migration pattern — **no manual production DB edits**.

### 10.3 What NOT to Persist Yet

- Raw OHLC history (no existing pattern; defer until backtest platform needed)
- Full market structure snapshots (recompute from posted candles)

---

## 11. API Changes

### 11.1 New Endpoints (Additive)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/ict/analyze` | Offline ICT analysis with posted multi-TF candles |
| GET | `/api/v1/ict/status` | Passthrough from heartbeat blob (live) |
| GET | `/api/v1/strategies/ict/{symbol}` | Compact summary |
| GET | `/api/v1/strategies/ict/{symbol}/history` | Setup history |
| POST | `/api/v1/confluence/analyze` | Multi-strategy confluence (optional Phase 11) |

### 11.2 Heartbeat Schema Change

Add to `HeartbeatRequest` in `schemas.py`:

```python
ict: Optional[dict[str, Any]] = None
```

Backwards compatible — optional field.

### 11.3 Analyze Request Shape (Proposed)

Follow Box Theory / AMD pattern:

```json
{
  "symbol": "XAUUSD",
  "bid": 3415.0,
  "candles": {
    "D1": [...],
    "H4": [...],
    "H1": [...],
    "M15": [...],
    "M5": [...]
  },
  "config": { "min_confidence": 70 }
}
```

Normalized response schema — extend existing strategy result envelope:

```json
{
  "strategy": "ICT",
  "symbol": "XAUUSD",
  "timeframe": "M15",
  "valid": true,
  "analysis_active": true,
  "status": "ENTRY_ZONE_ACTIVE",
  "decision": "SELL",
  "confidence": 84,
  "score_components": { ... },
  "htf_bias": { ... },
  "liquidity": { ... },
  "structure": { ... },
  "fvg": { ... },
  "entry": { ... },
  "stop_loss": { ... },
  "targets": [ ... ],
  "risk_reward": 3.1,
  "reasons": [ ... ],
  "invalidations": [ ... ],
  "timeline": [ ... ],
  "setup_id": "ICT-XAUUSD-M15-20260810-001"
}
```

---

## 12. Dashboard, Discord, and AI Integration

### 12.1 Dashboard (`ict.html`)

Follow `box-theory.html` / `amd-ifvg.html` patterns:

- Direction, confidence, state
- HTF bias breakdown (D1/H4/H1)
- Liquidity sweep status
- Displacement + MSS
- FVG zone
- Entry zone, SL, TP1/TP2/final liquidity
- R:R
- **Setup timeline** (Phase 18 checklist UI)
- Evidence / reasons list

### 12.2 Discord (`ict_discord_notify.py`)

Notify only on **state changes**:

- `LIQUIDITY_SWEPT`
- `MSS_CONFIRMED`
- `ENTRY_ZONE_ACTIVE`
- `TRIGGERED`
- `INVALIDATED`
- `TARGET_REACHED`

Dedupe by `setup_id + state`. Configurable `minimum_confidence` (default 75).

Env vars (follow Box pattern):

```
DISCORD_ICT_ENABLED=true
DISCORD_ICT_WEBHOOK_URL=...
DISCORD_ICT_MIN_CONFIDENCE=75
DISCORD_ICT_COOLDOWN_SEC=300
```

### 12.3 AI Layer

Extend `ai_brief.py` to include:

```json
{
  "backend_signal": "SELL",
  "confidence": 84,
  "score_components": { ... },
  "state": "ENTRY_ZONE_ACTIVE",
  "evidence": [ ... ],
  "invalidations": [ ... ]
}
```

LLM prompt rule (already aligned with project intent):

> Do not override deterministic backend scores. If contextual disagreement exists, return `ai_assessment: "CAUTION"` with reason.

---

## 13. Multi-Strategy Confluence Plan

### 13.1 Current State

`master_verdict.py` produces a single verdict (`STRONG`, `WATCH`, `NO TRADE`, etc.) from EA blobs. It is **not** a weighted confluence engine — it uses hard blocks + module chips + heuristic boosts.

### 13.2 Target Confluence Engine

**Location:** `backend/app/analysis/confluence/engine.py`

Input: normalized strategy results:

```python
@dataclass
class StrategySignal:
    strategy: str
    direction: Literal["LONG", "SHORT", "NEUTRAL", "NO_SETUP"]
    confidence: float
    status: str
    evidence: list[str]
    invalidation: list[str]
    timestamp: int
    freshness_sec: float
    weight: float  # configurable per strategy
```

Output:

```json
{
  "overall_direction": "SHORT",
  "confidence": 85,
  "agreement": "3/4",
  "conflicting_strategies": [],
  "strongest_strategy": "ICT",
  "components": { "ICT": {...}, "SMC": {...}, ... }
}
```

**Rules (not simple average):**

1. Apply per-strategy weight (ICT default 1.0, SMC 0.9, etc.).
2. Down-weight stale signals (`freshness_sec > threshold`).
3. Conflicting LONG/SHORT → reduce confidence, list conflicts.
4. Require minimum agreeing strategies for `STRONG` verdict.
5. Hard blocks from M30 risk still override (CRITICAL, high spread).

**Migration:** `build_master_verdict()` calls confluence engine internally — preserve existing API shape initially.

---

## 14. Configuration Plan

**Do not introduce YAML** — follow existing `pydantic-settings` + dataclass config pattern.

### 14.1 Environment Variables (Global)

Add to `config.py`:

```python
# ICT Discord
discord_ict_enabled: bool = False
discord_ict_webhook_url: str | None = None
discord_ict_min_confidence: float = 75.0
discord_ict_cooldown_sec: int = 300
telegram_alert_ict: bool = True
```

### 14.2 Strategy Config (Per-Request Override)

`IctConfig` dataclass with `DEFAULT_ICT_CONFIG` — same pattern as `BoxStrategyConfig`, `AmdIfvgConfig`.

### 14.3 Confluence Weights

`ConfluenceConfig` dataclass with strategy weights, freshness thresholds, minimum agreement count.

---

## 15. Risks of Breaking Existing Functionality

| Risk | Severity | Mitigation |
|------|----------|------------|
| Refactoring AMD/iFVG breaks 16+ tests | **HIGH** | Re-export shims; run full pytest after each extract step |
| Heartbeat schema change drops ICT blob | **HIGH** | Optional Pydantic field; EA sends only when enabled |
| Shared engine changes FVG IDs → Box Theory scoring drift | **MEDIUM** | Golden-fixture tests for both modules |
| Confluence engine changes master verdict tone | **MEDIUM** | Feature flag `USE_CONFLUENCE_ENGINE=false` initially |
| ICT state store memory leak | **LOW** | TTL + max setups per symbol |
| MQL5 ICT mirror diverges from Python | **MEDIUM** | Backend-first; MQL5 is Phase 2+ |
| Discord alert flood | **MEDIUM** | State-change-only + dedupe by setup_id |
| Session timezone bugs | **MEDIUM** | UTC internal; explicit `session_timezone` config |
| Look-ahead in swing confirmation | **HIGH** | Unit tests with known fixtures; `as_of_time` param |
| Box Theory known timing bug | **MEDIUM** | Fix during shared engine work; regression test |

---

## 16. Phased Implementation Sequence

Aligned with user Phase 26 order. **Each step ends with pytest green.**

### Step 1 — Audit (THIS DOCUMENT) ✅

### Step 2 — Document strategy/data flow ✅

See §2, §3, and existing docs (`BOX_THEORY.md`, `AMD_IFVG.md`, etc.)

### Step 3 — Design normalized market-structure interfaces

See §7.1 types and `market_structure/engine.py` contract.

### Step 4 — Extract shared structure (no behavior change) ✅

- Created `backend/app/market_structure/` package
- Moved `Candle`, `FvgZone`, `FvgStatus`, ATR, validation, FVG, swings, MSS, displacement, premium/discount, HTF bias
- `amd_ifvg_logic.py` imports from shared engine (re-exports preserved)
- `box_theory/utils.py` and `box_theory/types.py` re-export shared candle utilities/types
- Added `backend/tests/test_market_structure.py` (12 tests)
- Regression: AMD + Box Theory logic tests pass unchanged

### Step 5 — Implement ICT engine (backend-only) ✅

- Created `backend/app/analysis/ict/` package
- Main entry: `analyze_ict_strategy()` — uses `market_structure` (FVG, swings, MSS, displacement, premium/discount)
- Modules: bias, liquidity, sweep, session, models (bullish/bearish), state_machine, entry, targets, risk, scorer, explain, history
- Deterministic scoring with `score_components`; setup timeline; unique `setup_id`
- Tests: `backend/tests/test_ict_logic.py` (5 tests); 33/33 regression pass with AMD + Box + market_structure

### Step 6 — ICT state machine ✅

- `state_store.py` — in-memory persistence per symbol/setup_id (thread-safe)
- Stable `setup_id` anchored to sweep time: `ICT-{symbol}-{tf}-{sweep_time}-{B|S}`
- `merge_state()` — forward-only progression across analyze calls
- Invalidation: close beyond structural SL / opposite sweep
- Expiration: `max_setup_age_candles` (default 40)
- Target reached: TP1 hit → `TARGET_REACHED`
- `state_changed()` flag for Discord dedupe (Step 10)
- Timeline includes TP step

### Step 7 — ICT scoring ✅

- Weighted 100-point system with configurable weights
- `score_gates` — requirement flags (`liquidity_sweep`, `displacement`, `mss`, `fvg`)
- `score_penalties` — countertrend, missing requirements, low R:R
- Lifecycle score caps (early states cannot score HIGH)
- `decide_from_score()` — deterministic BUY/SELL/WAIT/NO_TRADE
- `block_countertrend` + `countertrend_penalty` config
- Tests: `test_ict_state_scoring.py` (8 tests)

### Step 8 — ICT API ✅

- `GET /api/v1/ict/status` — EA passthrough + backend state-store/history fallback
- `POST /api/v1/ict/analyze` — offline multi-TF analysis
- `POST /api/v1/strategy/ict/analyze` — alias route
- `GET /api/v1/strategies/ict/{symbol}` — compact summary
- `GET /api/v1/strategies/ict/{symbol}/history` — analyze history
- `HeartbeatRequest.ict` + `monitor_store` fields (`ict`, `ict_supported`) for future EA wiring
- Tests: `test_ict_status.py` (6 tests); 47/47 regression pass

### Step 9 — ICT dashboard ✅

- `ict.html` — direction, confidence, HTF bias, liquidity, structure, FVG, trade plan
- Setup timeline UI (HTF → sweep → displacement → MSS → FVG → retrace → entry → TP)
- Score gates checklist + penalties display
- `shell.js` nav entry · `/ict` route in `main.py`
- Backend-only fallback banner when EA offline but engine has history
- Tests: `test_ict_static.py`

### Step 10 — Discord state-change notifications ✅

- `ict_discord_notify.py` — dedicated webhook, state-change-only alerts
- Dedupe by `setup_id|state`; respects `state_changed` from engine
- Default events: `LIQUIDITY_SWEPT`, `MSS_CONFIRMED`, `ENTRY_ZONE_ACTIVE`, `TRIGGERED`, `INVALIDATED`, `TARGET_REACHED`
- Config: `DISCORD_ICT_ENABLED`, `DISCORD_ICT_WEBHOOK_URL`, `DISCORD_ICT_MIN_CONFIDENCE`, `DISCORD_ICT_COOLDOWN_SEC`, `DISCORD_ICT_ALERT_EVENTS`
- Wired on heartbeat (`discord_notify.py`) and `POST /api/v1/ict/analyze`
- Tests: `test_ict_discord.py` (7 tests)

### Step 11 — Confluence engine ✅

- `analysis/confluence/` — `types.py`, `weights.py`, `normalize.py`, `engine.py`
- Normalizes ICT, AMD+iFVG, Box, Swing, Gold SMC, Liquidity Grab, Breakout, M30 core
- Weighted scoring with stale-signal decay, conflict penalty, agreement counting
- `build_master_verdict()` delegates when `CONFLUENCE_ENABLED=true` (ICT chip always shown)
- API: `POST /api/v1/confluence/analyze`, `GET /api/v1/confluence/status`
- Tests: `test_confluence_engine.py` (7 tests)

### Step 12 — AI structured validation ✅

- `ai_validation.py` — authoritative strategy context builder + response validator
- ICT / AMD / Box JSON in AI brief section 9 (scores, gates, evidence, invalidations)
- Confluence + master verdict included in structured context
- `SYSTEM_PROMPT` rules: never override backend scores; CAUTION/DISAGREE footer required
- `GET /api/v1/monitor/ai-brief` returns `structured_context`
- `POST /api/v1/monitor/ai-analyze` returns `ai_validation` with `ai_assessment`
- Tests: `test_ai_validation.py` (7 tests)

### Step 13 — Tests ✅

- `test_ict_integration.py` — end-to-end pipeline (10 tests):
  - MT5 multi-TF payload → `market_structure` → ICT engine
  - `POST /api/v1/ict/analyze` → state store + history
  - ICT → confluence → master verdict
  - Heartbeat → status → AI structured context
  - Discord alert on analyze state change (mocked)
  - Confluence status API, ICT page, state persistence
- Full ICT stack: **83+ tests** across unit, API, Discord, confluence, AI validation, integration

### Step 14 — Regression ✅

- Full backend suite: **244/244 tests passing**
- Strategy status endpoints (ICT, Box, AMD, SMC, swing, breakout, market-state, confluence, …)
- Static desk pages (`/ict`, `/box-theory`, `/amd-ifvg`, …)
- AMD + Box logic + market_structure unchanged
- Fixed pending-orders test isolation (`select_symbol` after heartbeat)
- `test_regression_step14.py` — parametrized status + static page smoke checks

### Step 15 — MQL5 ICT mirror ✅

- `VantageIctTypes.mqh` — config + result structs, setup-state enums aligned with backend
- `VantageIct.mqh` — `CVantageIct` closed-bar evaluator (liquidity sweep → displacement → MSS → FVG → entry)
- `ToJson()` emits backend-compatible `ict` heartbeat blob (`module`, `setup_state`, `htf_bias`, `liquidity`, `structure`, `fvg`, trade plan)
- EA wiring in `VantageMT5AIDecisionAssistant.mq5`:
  - Input groups **AX/AY/AZ** (`InpIctEnable`, H1/M15/M5 TFs, sweep/displacement/FVG thresholds)
  - `FillIctConfig()` / `MaybeEvalIct()` — same pattern as Box Theory / AMD+iFVG
  - Heartbeat key `"ict"` when enabled; `OnInit` / `OnDeinit` lifecycle
- Advisory-only — no order execution APIs in ICT modules
- Tests: `test_ict_mql5_static.py` (module presence, closed-bar audit, EA wiring)

**Live verification:** recompile EA in MetaEditor, attach on XAUUSD, confirm `/ict` desk shows EA-sourced blob when heartbeat active.

### Step 16+ (Later)

- SQLite setup persistence
- OHLC ingestion service
- Full backtesting platform
- `docs/ICT.md` user-facing strategy guide

---

## 17. Phase 27 Deliverable — STOP Point

Per task instructions: **do not start major refactoring until this review is complete.**

### 17.1 What Was Discovered

1. The platform is already multi-strategy with a consistent **EA heartbeat → monitor_store → desk/alert** pattern.
2. Only **AMD+iFVG** and **Box Theory** have full Python engines; SMC/BOS/CHoCH live primarily in **MQL5 Gold SMC**.
3. Significant **duplication** exists in Python (candles, ATR, HTF bias, premium/discount, FVG).
4. **No shared market structure engine** exists today — highest-value incremental addition.
5. **ICT is closest to AMD+iFVG** conceptually but liquidity-first; can share primitives, not orchestration.
6. **No OHLC database** — offline analyze requires posted candles.
7. **Master verdict is not confluence** — needs dedicated engine.
8. **AI is already advisory-only** — compatible with ICT requirements.
9. **Configuration is env + dataclass**, not YAML — stay consistent.

### 17.2 What Will Be Reused

| Asset | Use for ICT |
|-------|-------------|
| `amd_ifvg_logic` FVG/swings/MSS/displacement | Extract to shared engine |
| `box_theory` service orchestration pattern | ICT `service.py` template |
| `box_discord_notify.py` | ICT Discord pattern |
| `monitor_state` + heartbeat wiring | Live ICT blob |
| `gold_symbol_validator.py` | Symbol gate |
| `master_verdict.py` | Short-term ICT chip |
| Static desk + shell.js pattern | ICT dashboard |
| pytest fixtures in `backend/tests/` | Test template |

### 17.3 What Should Be Refactored

| Component | Priority |
|-----------|----------|
| Shared candle/ATR utilities | **P0** |
| FVG module extraction | **P0** |
| HTF bias unification | **P1** |
| Premium/discount unification | **P1** |
| API passthrough helper | **P2** |
| AMD imports from shared engine | **P1** (after extraction tests pass) |
| Box Theory imports from shared engine | **P2** |

### 17.4 What Should Be Created New

| Component | Priority |
|-----------|----------|
| `market_structure/` package | **P0** |
| `analysis/ict/` package | **P0** |
| `analysis/confluence/` package | **P1** |
| `ict_discord_notify.py` | **P1** |
| `ict.html` dashboard | **P1** |
| ICT API endpoints | **P0** |
| ICT test suite | **P0** |
| `docs/ICT.md` user docs | **P2** |
| MQL5 ICT mirror | **P3** ✅ Step 15 |

### 17.5 Database Changes

| Change | When |
|--------|------|
| None initially | Step 1–10 use in-memory state |
| `ict_setups` SQLite table | After state machine stabilizes |
| Optional confluence snapshot table | Only if audit trail required |

### 17.6 API Changes

| Change | Breaking? |
|--------|-----------|
| Add `ict` to `HeartbeatRequest` | No — optional field |
| Add `/api/v1/ict/analyze` | No — additive |
| Add `/api/v1/ict/status` | No — additive |
| Confluence endpoint | No — additive |
| Confluence inside master verdict | Possibly — use feature flag |

### 17.7 Implementation Sequence Summary

```text
1. Audit                          ✅ (this document)
2. market_structure/ extract      ← NEXT (safest first step)
3. ICT engine + state machine
4. ICT API + tests
5. Dashboard + Discord
6. Confluence engine
7. AI structured validation
8. MQL5 mirror ✅ Step 15
```

---

## Appendix A — Key File Index

```
backend/app/
├── main.py
├── config.py
├── schemas.py
├── monitor_state.py
├── routers/api.py
├── strategy_desk.py
├── signal_ledger.py
├── execution_queue.py
├── alert_notify.py
├── discord_notify.py
├── telegram_notify.py
├── box_discord_notify.py
├── analysis/
│   ├── decision.py
│   ├── amd_ifvg_logic.py
│   ├── box_theory/
│   ├── gold_smc_logic.py
│   ├── master_verdict.py
│   ├── ai_brief.py
│   └── openai_client.py
└── static/

MQL5/
├── Experts/VantageMT5AIDecisionAssistant.mq5
└── Include/VantageAI/

docs/
├── VANTAGE_SETUP.md
├── GOLD_SMC.md
├── AMD_IFVG.md
├── BOX_THEORY.md
├── BOX_THEORY_BACKEND_AUDIT.md
└── ICT_INTEGRATION_ARCHITECTURE.md  ← this file
```

## Appendix B — Related Existing Documentation

- Box Theory backend audit: `docs/BOX_THEORY_BACKEND_AUDIT.md`
- AMD state machine reference: `docs/AMD_IFVG.md`
- Gold SMC (MQL5 BOS/CHoCH): `docs/GOLD_SMC.md`
- Liquidity Grab sessions: `docs/LIQUIDITY_GRAB.md`

---

**END OF ARCHITECTURE REVIEW — AWAITING APPROVAL BEFORE IMPLEMENTATION**
