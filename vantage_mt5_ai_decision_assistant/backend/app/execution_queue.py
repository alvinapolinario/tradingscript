"""
Demo execution queue — Swing Strategy signals by trade mode.

SWING mode: STRONG SWING BUY/SELL
SCALPING mode: SCALP BUY/SELL (M5 fast profile from advisory engine)
"""
from __future__ import annotations

import hashlib
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.strategy_desk import _ea_blob, _ea_is_connected

_DATA_DIR = __import__("pathlib").Path(__file__).resolve().parent.parent / "data"
_DB_PATH = _DATA_DIR / "execution_ledger.db"
_lock = threading.Lock()

SWING_SIGNALS = frozenset({"STRONG SWING BUY", "STRONG SWING SELL"})
SCALP_SIGNALS = frozenset({"SCALP BUY", "SCALP SELL"})
ALLOWED_ENTRY_QUALITY_SWING = frozenset({"GOOD", "EXCELLENT"})
ALLOWED_ENTRY_QUALITY_SCALP = frozenset({"AVERAGE", "GOOD", "EXCELLENT"})
M5_SECONDS = 300
DEFAULT_EXPIRES_SEC = 600

MODE_DEFAULTS: dict[str, dict[str, Any]] = {
    "SWING": {
        "signals": SWING_SIGNALS,
        "entry_quality": ALLOWED_ENTRY_QUALITY_SWING,
        "min_confidence": 85.0,
        "max_m5_bars": 2,
        "caption": "Demo execution — Swing mode (STRONG SWING signals).",
    },
    "SCALPING": {
        "signals": SCALP_SIGNALS,
        "entry_quality": ALLOWED_ENTRY_QUALITY_SCALP,
        "min_confidence": 72.0,
        "max_m5_bars": 1,
        "caption": "Demo execution — Scalping mode (SCALP BUY/SELL signals).",
    },
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(conn: sqlite3.Connection, name: str, ddl: str) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(executions)").fetchall()}
    if name not in cols:
        conn.execute(f"ALTER TABLE executions ADD COLUMN {ddl}")


def init_db() -> None:
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS executions (
                    id TEXT PRIMARY KEY,
                    created_utc TEXT NOT NULL,
                    updated_utc TEXT NOT NULL,
                    status TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    signal_label TEXT NOT NULL,
                    order_type TEXT NOT NULL,
                    stop_loss REAL NOT NULL,
                    take_profit REAL NOT NULL,
                    confidence REAL,
                    eval_bar_m5 INTEGER,
                    expires_utc TEXT,
                    ticket INTEGER,
                    reason TEXT,
                    swing_json TEXT,
                    trade_mode TEXT NOT NULL DEFAULT 'SWING'
                )
                """
            )
            _ensure_column(conn, "trade_mode", "trade_mode TEXT NOT NULL DEFAULT 'SWING'")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_exec_fp ON executions(fingerprint, status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_exec_created ON executions(created_utc DESC)"
            )
            conn.commit()
        finally:
            conn.close()


def _normalize_mode(mode: str) -> str:
    m = str(mode or "").upper().strip()
    if m in {"SCALPING", "SCALP"}:
        return "SCALPING"
    return "SWING"


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        if v is None:
            return default
        return int(v)
    except (TypeError, ValueError):
        return default


def _normalize_symbol(raw: str) -> str:
    s = str(raw or "").upper().strip()
    for suffix in ("+", ".", "m", "M"):
        if s.endswith(suffix) and len(s) > 4:
            s = s[: -len(suffix)]
    return s


def _symbols_match(a: str, b: str) -> bool:
    na, nb = _normalize_symbol(a), _normalize_symbol(b)
    if na == nb:
        return True
    return na.startswith("XAU") and nb.startswith("XAU")


def _fingerprint(symbol: str, signal: str, eval_bar_m5: int, stop_loss: float, mode: str) -> str:
    raw = f"{_normalize_symbol(symbol)}|{mode}|{signal}|{eval_bar_m5}|{stop_loss:.5f}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _parse_side(signal: str) -> Optional[str]:
    u = str(signal or "").upper()
    if "BUY" in u:
        return "BUY"
    if "SELL" in u:
        return "SELL"
    return None


def _entry_quality_ok(quality: Any, allowed: frozenset[str]) -> bool:
    q = str(quality or "").upper().strip()
    return q in allowed


def _is_fresh(eval_bar_m5: int, max_m5_bars: int = 2) -> bool:
    if eval_bar_m5 <= 0:
        return False
    now = int(datetime.now(timezone.utc).timestamp())
    age = now - eval_bar_m5
    return age <= max_m5_bars * M5_SECONDS


def _expire_stale_pending(conn: sqlite3.Connection) -> None:
    now = _utc_now()
    conn.execute(
        """
        UPDATE executions
        SET status = 'EXPIRED', updated_utc = ?, reason = 'reservation_timeout'
        WHERE status = 'PENDING' AND expires_utc IS NOT NULL AND expires_utc < ?
        """,
        (now, now),
    )


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    keys = row.keys()
    return {
        "signal_id": row["id"],
        "symbol": row["symbol"],
        "side": row["side"],
        "order_type": row["order_type"],
        "stop_loss": row["stop_loss"],
        "take_profit": row["take_profit"],
        "confidence": row["confidence"],
        "eval_bar_m5": row["eval_bar_m5"],
        "status": row["status"],
        "created_utc": row["created_utc"],
        "updated_utc": row["updated_utc"],
        "ticket": row["ticket"],
        "reason": row["reason"],
        "signal_label": row["signal_label"],
        "trade_mode": row["trade_mode"] if "trade_mode" in keys else "SWING",
    }


def _order_payload(row: sqlite3.Row, expires_in_sec: int = DEFAULT_EXPIRES_SEC) -> dict[str, Any]:
    keys = row.keys()
    return {
        "signal_id": row["id"],
        "symbol": row["symbol"],
        "side": row["side"],
        "order_type": row["order_type"],
        "stop_loss": row["stop_loss"],
        "take_profit": row["take_profit"],
        "confidence": row["confidence"],
        "eval_bar_m5": row["eval_bar_m5"],
        "expires_in_sec": expires_in_sec,
        "trade_mode": row["trade_mode"] if "trade_mode" in keys else "SWING",
    }


def _select_tp(swing: dict[str, Any], tp_level: str = "TP1") -> float:
    level = str(tp_level or "TP1").upper()
    if level == "TP2":
        return _safe_float(swing.get("tp2"))
    if level == "TP3":
        return _safe_float(swing.get("tp3"))
    return _safe_float(swing.get("tp1"))


def reserve_next(
    monitor_status: dict[str, Any],
    symbol: str,
    *,
    mode: str = "SWING",
    min_confidence: float | None = None,
    max_m5_bars: int | None = None,
    tp_level: str = "TP1",
) -> dict[str, Any]:
    """Return next actionable order or empty has_signal=false."""
    import json

    trade_mode = _normalize_mode(mode)
    cfg = MODE_DEFAULTS[trade_mode]
    min_conf = float(min_confidence if min_confidence is not None else cfg["min_confidence"])
    max_bars = int(max_m5_bars if max_m5_bars is not None else cfg["max_m5_bars"])
    allowed_signals = cfg["signals"]
    allowed_quality = cfg["entry_quality"]

    sym = str(symbol or "").upper().strip() or "XAUUSD"
    ea = _ea_blob(monitor_status)
    swing = ea.get("swing_strategy") if isinstance(ea.get("swing_strategy"), dict) else None

    base: dict[str, Any] = {
        "demo_execution": True,
        "has_signal": False,
        "trade_mode": trade_mode,
        "caption": cfg["caption"],
        "symbol": sym,
    }

    if not _ea_is_connected(monitor_status, ea):
        base["reason"] = "ea_offline"
        return base
    if not swing:
        base["reason"] = "no_swing_blob"
        return base
    if not swing.get("gold_symbol_valid", False):
        base["reason"] = swing.get("disable_reason") or "gold_only"
        return base

    blob_mode = _normalize_mode(str(swing.get("trade_mode") or "SWING"))
    if blob_mode != trade_mode:
        base["reason"] = "trade_mode_mismatch"
        base["expected_mode"] = trade_mode
        base["blob_mode"] = blob_mode
        return base

    ea_sym = str(swing.get("symbol") or ea.get("symbol") or sym)
    if not _symbols_match(ea_sym, sym):
        base["reason"] = "symbol_mismatch"
        return base

    signal_label = str(swing.get("signal") or "").upper()
    if signal_label not in allowed_signals:
        base["reason"] = "signal_not_allowed_for_mode"
        base["signal"] = signal_label
        return base

    confidence = _safe_float(swing.get("confidence"))
    if confidence < min_conf:
        base["reason"] = "low_confidence"
        return base
    if not _entry_quality_ok(swing.get("entry_quality"), allowed_quality):
        base["reason"] = "entry_quality"
        return base

    eval_bar = _safe_int(swing.get("eval_bar_m5"))
    if not _is_fresh(eval_bar, max_m5_bars=max_bars):
        base["reason"] = "stale_eval_bar"
        return base

    side = _parse_side(signal_label)
    if not side:
        base["reason"] = "side_unknown"
        return base

    stop_loss = _safe_float(swing.get("stop_loss"))
    take_profit = _select_tp(swing, tp_level)
    if stop_loss <= 0 or take_profit <= 0:
        base["reason"] = "invalid_levels"
        return base

    fp = _fingerprint(ea_sym, signal_label, eval_bar, stop_loss, trade_mode)
    now = _utc_now()
    expires_dt = datetime.now(timezone.utc).timestamp() + DEFAULT_EXPIRES_SEC
    expires_utc = datetime.fromtimestamp(expires_dt, tz=timezone.utc).isoformat()

    with _lock:
        conn = _connect()
        try:
            _expire_stale_pending(conn)

            row = conn.execute(
                """
                SELECT * FROM executions
                WHERE fingerprint = ? AND status IN ('PENDING', 'FILLED')
                ORDER BY created_utc DESC LIMIT 1
                """,
                (fp,),
            ).fetchone()
            if row:
                if row["status"] == "FILLED":
                    base["reason"] = "already_filled"
                    conn.commit()
                    return base
                base["has_signal"] = True
                base["order"] = _order_payload(row)
                conn.commit()
                return base

            pending_sym = conn.execute(
                """
                SELECT id FROM executions
                WHERE symbol = ? AND status = 'PENDING' AND trade_mode = ?
                LIMIT 1
                """,
                (_normalize_symbol(ea_sym), trade_mode),
            ).fetchone()
            if pending_sym:
                base["reason"] = "pending_exists"
                conn.commit()
                return base

            sig_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO executions (
                    id, created_utc, updated_utc, status, fingerprint,
                    symbol, side, signal_label, order_type,
                    stop_loss, take_profit, confidence, eval_bar_m5,
                    expires_utc, ticket, reason, swing_json, trade_mode
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    sig_id,
                    now,
                    now,
                    "PENDING",
                    fp,
                    _normalize_symbol(ea_sym),
                    side,
                    signal_label,
                    "MARKET",
                    stop_loss,
                    take_profit,
                    confidence,
                    eval_bar,
                    expires_utc,
                    None,
                    None,
                    json.dumps(swing),
                    trade_mode,
                ),
            )
            conn.commit()
            new_row = conn.execute(
                "SELECT * FROM executions WHERE id = ?", (sig_id,)
            ).fetchone()
            base["has_signal"] = True
            base["order"] = _order_payload(new_row)
            return base
        finally:
            conn.close()


def ack_execution(
    signal_id: str,
    status: str,
    *,
    ticket: int | None = None,
    reason: str | None = None,
) -> Optional[dict[str, Any]]:
    status = str(status or "").upper()
    if status not in {"FILLED", "REJECTED", "SKIPPED", "EXPIRED"}:
        raise ValueError("status must be FILLED, REJECTED, SKIPPED, or EXPIRED")

    now = _utc_now()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT * FROM executions WHERE id = ?", (signal_id,)
            ).fetchone()
            if not row:
                return None
            if row["status"] == "FILLED" and status != "FILLED":
                return _row_to_dict(row)

            conn.execute(
                """
                UPDATE executions
                SET status = ?, updated_utc = ?, ticket = ?, reason = ?
                WHERE id = ?
                """,
                (status, now, ticket, reason, signal_id),
            )
            conn.commit()
            updated = conn.execute(
                "SELECT * FROM executions WHERE id = ?", (signal_id,)
            ).fetchone()
            return _row_to_dict(updated) if updated else None
        finally:
            conn.close()


def list_history(
    limit: int = 50,
    symbol: str | None = None,
    mode: str | None = None,
) -> list[dict[str, Any]]:
    with _lock:
        conn = _connect()
        try:
            _expire_stale_pending(conn)
            conn.commit()
            params: list[Any] = []
            clauses: list[str] = []
            if symbol:
                clauses.append("symbol = ?")
                params.append(_normalize_symbol(symbol))
            if mode:
                clauses.append("trade_mode = ?")
                params.append(_normalize_mode(mode))
            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            params.append(limit)
            rows = conn.execute(
                f"""
                SELECT * FROM executions
                {where}
                ORDER BY created_utc DESC LIMIT ?
                """,
                tuple(params),
            ).fetchall()
            return [_row_to_dict(r) for r in rows]
        finally:
            conn.close()


def execution_summary(monitor_status: dict[str, Any]) -> dict[str, Any]:
    ea = _ea_blob(monitor_status)
    swing = ea.get("swing_strategy") if isinstance(ea.get("swing_strategy"), dict) else None
    items = list_history(limit=20)
    pending = sum(1 for i in items if i.get("status") == "PENDING")
    filled = sum(1 for i in items if i.get("status") == "FILLED")
    return {
        "demo_execution": True,
        "ea_online": _ea_is_connected(monitor_status, ea),
        "blob_trade_mode": (swing or {}).get("trade_mode") if swing else None,
        "current_signal": (swing or {}).get("signal") if swing else None,
        "current_confidence": (swing or {}).get("confidence") if swing else None,
        "pending_count": pending,
        "filled_count": filled,
        "recent": items[:10],
    }


init_db()
