# ICT Strategy Hardening

## 1. Audit Findings Addressed

- **MSS causality**: MSS must break a **frozen pre-sweep swing** within the post-sweep displacement window (close-confirmed).
- **Displacement scoring**: Replaced weak single-candle scorer path with explicit `DisplacementEvent` metrics (`body_atr`, `range_atr`, `body_ratio`, multi-candle leg).
- **Execution FVG selection**: FVG must be same-direction, `created_time >= sweep` and `>= displacement.start`, within `max_fvg_bars_after_mss` of MSS.
- **Pre-sweep / unrelated FVG rejection**: Hard causal filters with explicit reasons (`FVG_PRE_SWEEP`, `FVG_PRE_DISPLACEMENT`, `NO_CAUSAL_FVG`).
- **Entry lifecycle**: Distinct `FVG_TOUCHED` → `ENTRY_READY` (two-pass); no same-pass jump to legacy `TRIGGERED`.
- **Score vs validity**: `causality_errors` cap score; gates include `causality`.
- **Impulse double-counting**: Grouped displacement+MSS+FVG into `impulse_quality` weight.
- **Symmetric invalidation**: Opposite-side sweep invalidates bullish and bearish setups.
- **Python canonical**: `engine_source: PYTHON_CANONICAL` on analyze; MQL5 blobs tagged `MQL5_LEGACY` on status API.
- **Replay safety**: `replay.py` + `test_ict_replay.py` incremental bar harness.
- **Persistence**: SQLite `data/ict_setups.db` via `app/analysis/ict/store.py`.

## 2. Previous Strategy Flow

```
HTF bias → liquidity → sweep → best post-sweep displacement score
→ latest-bar MSS vs latest swing → any post-sweep M5 FVG → touch = TRIGGERED
```

## 3. New Canonical Strategy Flow

```
HTF CONTEXT → LIQUIDITY MAP → LIQUIDITY SWEEP
→ freeze MSS target (pre-sweep swing)
→ DISPLACEMENT LEG (1–N bars, directional)
→ MSS (close break of frozen swing, within displacement window)
→ EXECUTION FVG (causal window)
→ WAIT FOR RETRACE → FVG_TOUCHED → ENTRY_READY
```

## 4. Event Model

Explicit IDs on: `LiquiditySweepEvent`, `DisplacementEvent`, `StructureBreakEvent`, execution `FvgZone` links (`displacement_event_id`, `mss_event_id`).

## 5. Liquidity Sweep

Unchanged reclaim math (SSL: low < level, close > level; BSL: high > level, close < level). Extended with `event_id`, `penetration_atr`, `reclaim_confirmed`.

## 6. Displacement

`displacement_leg.py` — configurable thresholds:

- `displacement_min_body_atr` (default 0.8)
- `displacement_min_range_atr` (default 1.0)
- `displacement_min_body_ratio` (default 0.60)
- `max_displacement_bars_after_sweep` (default 4)

## 7. MSS Causality

`freeze_mss_target()` at sweep; `detect_causal_mss()` requires close confirmation, `broken_swing_id == mss_target`, time within displacement + `max_mss_bars_after_displacement`.

## 8. Execution FVG Causality

`select_execution_fvg()` — rejects pre-sweep and pre-displacement FVGs; accepts FVG during displacement through `max_fvg_bars_after_mss` after MSS.

## 9. Entry Lifecycle

States: `EXECUTION_FVG_FOUND` → `WAITING_FOR_RETRACE` → `FVG_TOUCHED` → `ENTRY_READY`. Legacy `TRIGGERED` retained for API rank compatibility. **No OrderSend / auto-trade.**

## 10. State Machine

New states added to `STATE_RANK`; terminal states do not regress. Stage timeouts: `max_bars_sweep_to_displacement`, `max_mss_bars_after_displacement`, etc.

## 11. Invalidation

Structural SL around sweep extreme ± ATR buffer. Opposite liquidity sweep invalidates symmetrically.

## 12. Expiration

Global `max_setup_age_candles` plus displacement/MSS/FVG stage timeouts and retrace chase (`RETRACE_TIMEOUT`).

## 13. Scoring

Hard gates: sweep, displacement, MSS, execution FVG, causality chronology. Quality: HTF, liquidity, **impulse_quality**, PD, session, RR.

## 14. Persistence

SQLite tables `ict_setups`, `ict_events`. In-memory `state_store` unchanged for active setup merge.

## 15. Python/MQL5 Architecture

**Canonical**: `backend/app/analysis/ict/` via `/api/v1/ict/analyze`. **Legacy**: MQL5 EA ICT blob on heartbeat — status API labels `engine_source`.

## 16. Replay Safety

`replay_ict_sequence()` feeds closed bars incrementally; tests verify determinism and chronology.

## 17. Tests

- `test_ict_replay.py` — replay, FVG rejection, frozen MSS, two-pass ENTRY_READY
- Existing ICT suite updated for new states/scoring

## 18. API Changes

Added fields: `engine_source`, `state`, `state_reason`, `causality_valid`, `causality_errors`, `liquidity_event`, `displacement_event`, `mss_event`, `execution_fvg`, `event_timeline`, `entry_ready`, `entry_event_id`, `ote`, `order_block`, `poi_confluence`. Version `2.1`.

## 19. Backward Compatibility

Existing keys preserved (`status`, `setup_state`, `liquidity`, `structure`, `fvg`, `entry`, `decision`). `TRIGGERED` enum retained; prefer `ENTRY_READY`.

## 20. Remaining Limitations

- MQL5 ICT not rewritten; no full parity on heartbeat without candle export.
- PDH/PDL still rolling-range approximation (Phase 2).
- HTF bias unchanged (momentum context, not full ICT structure).
- `entry_trigger_mode` enum defined; TOUCH default implemented.
- OTE / OB / breaker implemented in Phase 4 (`poi.py`) — confluence scoring only.

## 21. Recommended Phase 2

- ICT candle export + Python-on-heartbeat (H4→M15 pattern)
- True session PDH/PDL boundaries
- Full event rehydration from SQLite on analyze merge
- OTE / OB / iFVG (only after replay/backtest calibration)

---

# Phase 2 — Implemented

## 22. Python-on-Heartbeat

- **MQL5**: `VantageIctFeed.mqh` exports closed `D1/H4/H1/M15/M5` as `ict_candles` on new M15 bar (`InpIctFeedEnable`).
- **Backend**: `process_ict_heartbeat()` in `heartbeat.py` runs `analyze_ict_strategy()`; monitor overwrites `ea.ict` with Python result.
- **Desk**: `/ict` shows **Python canonical** vs **MQL5 legacy** badge; legacy snapshot preserved in `mql5_legacy` when both present.

## 23. True PDH/PDL

- `session_levels.py`: prefers last closed **D1** bar; falls back to **session-partitioned** M15 using `trading_day_timezone` (default `America/New_York`) and `trading_day_reset_hour` (default `17`).
- Liquidity map labels source (`D1_PREVIOUS_BAR` vs `SESSION_PARTITION_*`); no longer uses blind 96-bar rolling window for PDH/PDL when D1 is available.

## 24. SQLite Rehydration

- `get_persisted_setup(setup_id)` loads last payload from `data/ict_setups.db`.
- `rehydrate_context_from_payload()` restores event identity, FVG links, `entry_ready_emitted`, touch times before causal merge on same `setup_id`.

## 25. Phase 3 — Implemented

- **MQL5 legacy suppression**: `InpIctLegacyHeartbeat=false` (default) omits `ict` JSON when Python feed is active; chart HUD still runs locally.
- **Entry trigger modes**: `TOUCH`, `CLOSED_BAR_TOUCH`, `CE_TOUCH` via `entry_trigger.py`.
- **Signal Center**: `build_ict_advisory_cards()` — ENTRY_READY Python-only advisory cards on `/api/v1/signals`.
- **Confluence**: ICT active only on `ENTRY_READY` + `causality_valid`; MQL5 legacy ignored when `ict_python_engine`.
- **Discord**: `ENTRY_READY` / `FVG_TOUCHED` events; skips `MQL5_LEGACY`; dedupe via `entry_event_id`.
- **Replay API**: `POST /api/v1/ict/replay` for chronological backtest steps.

## 26. Phase 4 — Implemented

- **OTE**: `poi.py` — impulse-leg fib band (618/705/790) from displacement high/low; confluence only, never standalone setup.
- **Order blocks**: causal OB = last opposite candle before displacement leg; linked via `source_displacement_event_id`.
- **Breaker blocks**: invalidated OB promoted when price reclaims with displacement aligned to trade bias.
- **Scoring**: optional `weight_ote`, `weight_order_block`, `weight_breaker` confluence bonuses (hard gates unchanged).
- **API**: `ote`, `order_block`, `poi_confluence` on analyze payload; timeline events `ORDER_BLOCK`, `BREAKER`, `OTE_BAND`.
- **Desk**: `/ict` trade plan shows OTE band and OB/breaker status.

## 27. Remaining (optional)

- Remove MQL5 ICT chart module when feed-only mode proven in production.
- Kill-zone hard filters (London/NY open) — scoring-only session today.
- Dedicated replay calibration CLI for OTE/OB thresholds.

