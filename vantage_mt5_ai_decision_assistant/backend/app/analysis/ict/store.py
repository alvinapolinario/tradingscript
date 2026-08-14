"""SQLite persistence for ICT setups and event payloads."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

_lock = threading.Lock()
_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "ict_setups.db"
_initialized = False
_entry_emitted: set[str] = set()


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
                CREATE TABLE IF NOT EXISTS ict_setups (
                    setup_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    state TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ict_events (
                    event_id TEXT PRIMARY KEY,
                    setup_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_time INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_ict_setups_symbol ON ict_setups(symbol, updated_at DESC);
                """
            )
            conn.commit()
            _initialized = True
        finally:
            conn.close()


def get_persisted_setup(setup_id: str) -> dict[str, Any] | None:
    """Load last persisted analyze payload for setup_id."""
    _ensure_schema()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT payload_json FROM ict_setups WHERE setup_id=?",
                (setup_id,),
            ).fetchone()
        finally:
            conn.close()
    if not row:
        return None
    try:
        return json.loads(row["payload_json"])
    except json.JSONDecodeError:
        return None


def get_latest_persisted_setup(symbol: str) -> dict[str, Any] | None:
    items = list_persisted_setups(symbol, limit=1)
    return items[0] if items else None


def persist_setup_payload(payload: dict[str, Any]) -> None:
    """Persist latest analyze payload and timeline events."""
    _ensure_schema()
    setup_id = str(payload.get("setup_id") or "")
    if not setup_id:
        return
    now = int(time.time())
    sym = str(payload.get("symbol") or "").upper()
    direction = str(payload.get("direction") or "")
    state = str(payload.get("state") or payload.get("status") or "")
    blob = json.dumps(payload, default=str)

    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO ict_setups (setup_id, symbol, direction, state, payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(setup_id) DO UPDATE SET
                    state=excluded.state,
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at
                """,
                (setup_id, sym, direction, state, blob, now, now),
            )
            for ev in payload.get("event_timeline") or []:
                eid = f"{setup_id}-{ev.get('event')}-{ev.get('time')}"
                conn.execute(
                    """
                    INSERT OR IGNORE INTO ict_events
                    (event_id, setup_id, event_type, event_time, payload_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        eid,
                        setup_id,
                        str(ev.get("event") or ""),
                        int(ev.get("time") or 0),
                        json.dumps(ev),
                        now,
                    ),
                )
            conn.commit()
        finally:
            conn.close()


def entry_ready_already_emitted(entry_event_id: str) -> bool:
    return entry_event_id in _entry_emitted


def mark_entry_ready_emitted(entry_event_id: str) -> None:
    if entry_event_id:
        _entry_emitted.add(entry_event_id)


def list_persisted_setups(symbol: str, limit: int = 10) -> list[dict[str, Any]]:
    _ensure_schema()
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT payload_json FROM ict_setups WHERE symbol=? ORDER BY updated_at DESC LIMIT ?",
                (symbol.upper(), limit),
            ).fetchall()
        finally:
            conn.close()
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            out.append(json.loads(row["payload_json"]))
        except json.JSONDecodeError:
            continue
    return out


def clear_store() -> None:
    """Test helper."""
    global _initialized, _entry_emitted
    with _lock:
        if _DB_PATH.exists():
            _DB_PATH.unlink()
        _initialized = False
        _entry_emitted.clear()
