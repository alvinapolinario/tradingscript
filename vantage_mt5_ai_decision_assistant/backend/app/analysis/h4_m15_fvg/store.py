"""SQLite persistence for H4→M15 FVG setups."""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from app.analysis.h4_m15_fvg.explain import setup_to_json
from app.analysis.h4_m15_fvg.types import H4M15Setup

_lock = threading.Lock()
_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "h4_m15_fvg.db"
_initialized = False
_last_setup_states: dict[str, str] = {}


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema() -> None:
    global _initialized
    if _initialized:
        return
    with _lock:
        if _initialized:
            return
        conn = _connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS fvg_zones (
                    fvg_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    formation_time INTEGER NOT NULL,
                    lower_boundary REAL NOT NULL,
                    upper_boundary REAL NOT NULL,
                    gap_atr REAL NOT NULL,
                    status TEXT NOT NULL,
                    parent_fvg_id TEXT,
                    payload_json TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS fvg_setups (
                    setup_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    htf_fvg_id TEXT NOT NULL,
                    entry_fvg_id TEXT,
                    state TEXT NOT NULL,
                    setup_score REAL,
                    setup_grade TEXT,
                    payload_json TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_fvg_setups_symbol ON fvg_setups(symbol, updated_at DESC);
                """
            )
            conn.commit()
            _initialized = True
        finally:
            conn.close()


def setup_state_changed(setup_id: str, state: str) -> bool:
    """Return True when setup state changed since last seen (in-memory)."""
    with _lock:
        prev = _last_setup_states.get(setup_id)
        changed = prev != state
        _last_setup_states[setup_id] = state
        return changed


def reset_state_tracking() -> None:
    with _lock:
        _last_setup_states.clear()


def save_setup_snapshot(setup: H4M15Setup) -> bool:
    _ensure_schema()
    payload = setup_to_json(setup)
    state_val = setup.state.value
    changed = setup_state_changed(setup.setup_id, state_val)
    z = setup.htf_fvg
    ef = setup.entry_fvg
    now = setup.updated_time or setup.created_time
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO fvg_zones (
                    fvg_id, symbol, timeframe, direction, formation_time,
                    lower_boundary, upper_boundary, gap_atr, status, parent_fvg_id,
                    payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(fvg_id) DO UPDATE SET
                    status=excluded.status,
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at
                """,
                (
                    z.fvg_id,
                    setup.symbol,
                    z.timeframe,
                    z.direction,
                    z.created_time,
                    z.lower,
                    z.upper,
                    z.gap_atr,
                    z.status.value if hasattr(z.status, "value") else str(z.status),
                    z.parent_fvg_id or "",
                    json.dumps({"lower": z.lower, "upper": z.upper, "mitigation_pct": z.mitigation_pct}),
                    z.created_at or now,
                    now,
                ),
            )
            if ef:
                conn.execute(
                    """
                    INSERT INTO fvg_zones (
                        fvg_id, symbol, timeframe, direction, formation_time,
                        lower_boundary, upper_boundary, gap_atr, status, parent_fvg_id,
                        payload_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(fvg_id) DO UPDATE SET
                        status=excluded.status,
                        payload_json=excluded.payload_json,
                        updated_at=excluded.updated_at
                    """,
                    (
                        ef.fvg_id,
                        setup.symbol,
                        ef.timeframe,
                        ef.direction,
                        ef.created_time,
                        ef.lower,
                        ef.upper,
                        ef.gap_atr,
                        ef.status.value if hasattr(ef.status, "value") else str(ef.status),
                        ef.parent_fvg_id or z.fvg_id,
                        json.dumps({"lower": ef.lower, "upper": ef.upper}),
                        ef.created_at or now,
                        now,
                    ),
                )
            conn.execute(
                """
                INSERT INTO fvg_setups (
                    setup_id, symbol, direction, htf_fvg_id, entry_fvg_id,
                    state, setup_score, setup_grade, payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(setup_id) DO UPDATE SET
                    entry_fvg_id=excluded.entry_fvg_id,
                    state=excluded.state,
                    setup_score=excluded.setup_score,
                    setup_grade=excluded.setup_grade,
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at
                """,
                (
                    setup.setup_id,
                    setup.symbol,
                    setup.direction,
                    z.fvg_id,
                    ef.fvg_id if ef else "",
                    setup.state.value,
                    setup.setup_score,
                    setup.setup_grade,
                    json.dumps(payload),
                    setup.created_time,
                    now,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    return changed


def list_setups(symbol: str, limit: int = 20) -> list[dict[str, Any]]:
    _ensure_schema()
    sym = (symbol or "").upper()
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                """
                SELECT payload_json FROM fvg_setups
                WHERE symbol = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (sym, limit),
            ).fetchall()
            return [json.loads(r["payload_json"]) for r in rows]
        finally:
            conn.close()


def clear_store() -> None:
    """Test helper."""
    global _initialized
    with _lock:
        if _DB_PATH.exists():
            _DB_PATH.unlink()
        _initialized = False
        _last_setup_states.clear()
