"""
Accepted Signal Ledger + Smart Analyzer helpers.

Persists advisory BUY/SELL history to SQLite. Does not execute trades.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.strategy_desk import (
    STRATEGY_SPEC,
    _ea_blob,
    _ea_is_connected,
    _extra_strategy,
    build_dashboard,
    evaluate_gates,
)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_DB_PATH = _DATA_DIR / "signal_ledger.db"
_lock = threading.Lock()

_GATE_WEIGHTS: dict[str, tuple[str, int]] = {
    "ea_feed": ("EA feed", 8),
    "alignment": ("H1+M15 alignment", 18),
    "adx": ("ADX Trend Strength", 12),
    "rr": ("Reward:risk", 14),
    "risk_pct": ("Risk size", 10),
    "spread": ("Spread filter", 8),
    "news": ("News window", 8),
    "setup_age": ("Setup age", 10),
    "close_confirm": ("M5 close", 8),
    "ema": ("EMA stack", 4),
}

_BUY_LEANING = {"alignment", "adx", "ema", "close_confirm", "rr"}
_SELL_LEANING = {"alignment", "adx", "ema", "close_confirm", "rr"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(conn: sqlite3.Connection, name: str, ddl: str) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(signals)").fetchall()}
    if name not in cols:
        conn.execute(f"ALTER TABLE signals ADD COLUMN {ddl}")


def init_db() -> None:
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS signals (
                    id TEXT PRIMARY KEY,
                    created_utc TEXT NOT NULL,
                    status TEXT NOT NULL,
                    side TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    contributing_count INTEGER NOT NULL,
                    contributors_json TEXT NOT NULL,
                    entry_low REAL NOT NULL,
                    entry_high REAL NOT NULL,
                    stop REAL NOT NULL,
                    target REAL NOT NULL,
                    reward_risk REAL,
                    adx14 REAL,
                    atr14 REAL,
                    h1_bias TEXT,
                    m15_structure TEXT,
                    m5_trigger TEXT,
                    fingerprint TEXT NOT NULL,
                    note TEXT,
                    user_decision TEXT NOT NULL DEFAULT 'PENDING',
                    decided_utc TEXT,
                    mode TEXT NOT NULL DEFAULT 'STANDARD',
                    bars_left INTEGER,
                    contributor_scores_json TEXT
                )
                """
            )
            _ensure_column(conn, "user_decision", "user_decision TEXT NOT NULL DEFAULT 'PENDING'")
            _ensure_column(conn, "decided_utc", "decided_utc TEXT")
            _ensure_column(conn, "mode", "mode TEXT NOT NULL DEFAULT 'STANDARD'")
            _ensure_column(conn, "bars_left", "bars_left INTEGER")
            _ensure_column(conn, "contributor_scores_json", "contributor_scores_json TEXT")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_signals_created ON signals(created_utc DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_signals_fp ON signals(fingerprint, created_utc DESC)"
            )
            conn.commit()
        finally:
            conn.close()


def _score_details_from_gates(
    gates: list[dict[str, Any]],
) -> tuple[int, list[str], list[dict[str, Any]]]:
    contributors: list[str] = []
    details: list[dict[str, Any]] = []
    score = 40
    for g in gates:
        key = str(g.get("key") or "")
        label, pts = _GATE_WEIGHTS.get(key, (str(key), 4))
        status = g.get("status")
        if status == "pass":
            factor = min(98, 55 + pts * 2)
            contributors.append(label)
            score += pts
            details.append({"key": key, "label": label, "points": pts, "score": factor, "status": status})
        elif status == "warn":
            factor = 45 + pts
            details.append({"key": key, "label": label, "points": pts // 2, "score": factor, "status": status})
        elif status == "fail":
            details.append({"key": key, "label": label, "points": 0, "score": max(20, 40 - pts), "status": status})
        else:
            details.append({"key": key, "label": label, "points": 0, "score": 40, "status": status or "unknown"})
    score = max(50, min(98, score))
    return score, contributors, details


def _score_from_gates(gates: list[dict[str, Any]]) -> tuple[int, list[str]]:
    score, contributors, _ = _score_details_from_gates(gates)
    return score, contributors


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        if v is None or v == "":
            return default
        return int(v)
    except (TypeError, ValueError):
        return default


def _desk_timeframe(mode: str) -> str:
    return "M5"


def _levels_from_strategy(
    st: dict[str, Any],
    side: str,
    mid: float,
    atr: float,
    digits: int,
    mode: str,
) -> tuple[float, float, float, float]:
    """Prefer EA entry/stop/target when present; else ATR geometry."""
    ea_entry = _safe_float(st.get("entry") or st.get("entry_price"))
    ea_stop = _safe_float(st.get("stop") or st.get("sl"))
    ea_target = _safe_float(st.get("target") or st.get("tp"))
    if ea_entry > 0 and ea_stop > 0 and ea_target > 0:
        band = max(atr * (0.08 if mode == "SCALPING" else 0.12), mid * 0.0001)
        if side == "BUY":
            return (
                round(ea_entry - band, digits),
                round(ea_entry + band * 0.25, digits),
                round(ea_stop, digits),
                round(ea_target, digits),
            )
        return (
            round(ea_entry - band * 0.25, digits),
            round(ea_entry + band, digits),
            round(ea_stop, digits),
            round(ea_target, digits),
        )
    return _levels_for_side(side, mid, atr, digits, mode=mode)


def _levels_for_side(
    side: str,
    mid: float,
    atr: float,
    digits: int = 5,
    mode: str = "STANDARD",
) -> tuple[float, float, float, float]:
    if mid <= 0:
        mid = 1.0
    if atr <= 0:
        atr = mid * 0.001
    band_mult = 0.08 if mode == "SCALPING" else 0.15
    band = max(atr * band_mult, mid * 0.00015)
    min_rr = float(STRATEGY_SPEC["risk"]["min_reward_risk"])
    stop_atr = 0.6 if mode == "SCALPING" else 1.0
    tp_atr = 1.2 if mode == "SCALPING" else min_rr
    if side == "BUY":
        entry_low = round(mid - band, digits)
        entry_high = round(mid + band * 0.25, digits)
        stop = round(mid - stop_atr * atr, digits)
        target = round(mid + tp_atr * atr, digits)
    else:
        entry_low = round(mid - band * 0.25, digits)
        entry_high = round(mid + band, digits)
        stop = round(mid + stop_atr * atr, digits)
        target = round(mid - tp_atr * atr, digits)
    return entry_low, entry_high, stop, target


def _bars_left(setup_age: Any) -> int:
    max_age = int(STRATEGY_SPEC["setup"]["max_age_completed_m5"])
    try:
        age = int(setup_age if setup_age is not None else 0)
    except (TypeError, ValueError):
        age = 0
    return max(0, max_age - age)


def _recent_fingerprint(conn: sqlite3.Connection, fingerprint: str, within_sec: int = 1800) -> bool:
    row = conn.execute(
        "SELECT created_utc FROM signals WHERE fingerprint = ? ORDER BY created_utc DESC LIMIT 1",
        (fingerprint,),
    ).fetchone()
    if not row:
        return False
    try:
        prev = datetime.fromisoformat(row["created_utc"])
        if prev.tzinfo is None:
            prev = prev.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - prev).total_seconds()
        return age < within_sec
    except ValueError:
        return False


def _row_to_dict(r: sqlite3.Row) -> dict[str, Any]:
    try:
        contributors = json.loads(r["contributors_json"] or "[]")
    except (json.JSONDecodeError, KeyError, TypeError):
        contributors = []
    try:
        scores_raw = r["contributor_scores_json"] if "contributor_scores_json" in r.keys() else None
        contributor_scores = json.loads(scores_raw or "[]")
    except (json.JSONDecodeError, KeyError, TypeError, IndexError):
        contributor_scores = []
    keys = set(r.keys())
    return {
        "id": r["id"],
        "created_utc": r["created_utc"],
        "status": r["status"],
        "side": r["side"],
        "symbol": r["symbol"],
        "timeframe": r["timeframe"],
        "score": r["score"],
        "contributing_count": r["contributing_count"],
        "contributors": contributors,
        "contributor_scores": contributor_scores,
        "entry_low": r["entry_low"],
        "entry_high": r["entry_high"],
        "stop": r["stop"],
        "target": r["target"],
        "reward_risk": r["reward_risk"],
        "adx14": r["adx14"],
        "atr14": r["atr14"],
        "h1_bias": r["h1_bias"],
        "m15_structure": r["m15_structure"],
        "m5_trigger": r["m5_trigger"],
        "note": r["note"],
        "user_decision": r["user_decision"] if "user_decision" in keys else "PENDING",
        "decided_utc": r["decided_utc"] if "decided_utc" in keys else None,
        "mode": r["mode"] if "mode" in keys else "STANDARD",
        "bars_left": r["bars_left"] if "bars_left" in keys else None,
    }


def _resolve_side(st: dict[str, Any]) -> Optional[str]:
    side = str(st.get("allowed_direction") or "").upper()
    if side in {"BUY", "SELL"}:
        return side
    h1 = str(st.get("h1_bias") or "").upper()
    if h1 == "BULLISH":
        return "BUY"
    if h1 == "BEARISH":
        return "SELL"
    return None


def maybe_accept_from_monitor(
    monitor_status: dict[str, Any],
    mode: str = "STANDARD",
) -> Optional[dict[str, Any]]:
    mode = "SCALPING" if str(mode).upper() == "SCALPING" else "STANDARD"
    dash = build_dashboard(monitor_status)
    verdict = (dash.get("verdict") or {}).get("verdict")
    if verdict != "SETUP_OK":
        return None

    ea = _ea_blob(monitor_status)
    if not _ea_is_connected(monitor_status, ea):
        return None

    st = _extra_strategy(ea)
    side = _resolve_side(st)
    if not side:
        return None

    symbol = str(ea.get("symbol") or monitor_status.get("selected_symbol") or "").upper()
    if not symbol:
        return None

    bid = _safe_float(ea.get("bid"))
    ask = _safe_float(ea.get("ask"))
    mid = (bid + ask) / 2.0 if bid > 0 and ask > 0 else bid or ask
    atr = _safe_float(st.get("atr14") or st.get("atr"))
    digits = _safe_int(ea.get("digits"), 5)
    if digits <= 0:
        digits = 5

    entry_low, entry_high, stop, target = _levels_from_strategy(st, side, mid, atr, digits, mode)
    gates = dash.get("gates") or evaluate_gates(monitor_status)
    score, contributors, details = _score_details_from_gates(gates)

    age = _safe_int(st.get("setup_age_m5"), 99)
    if age > int(STRATEGY_SPEC["setup"]["max_age_completed_m5"]):
        return None

    bars_left = _bars_left(age)
    fp = f"{symbol}|{side}|{st.get('h1_bias')}|{st.get('m15_structure')}|{round(mid, digits)}|{mode}"
    note = str(st.get("note") or "M5 Alignment Desk accepted")
    tf = _desk_timeframe(mode)

    with _lock:
        conn = _connect()
        try:
            if _recent_fingerprint(conn, fp):
                return None
            sig_id = str(uuid.uuid4())
            created = _utc_now()
            conn.execute(
                """
                INSERT INTO signals (
                    id, created_utc, status, side, symbol, timeframe, score,
                    contributing_count, contributors_json,
                    entry_low, entry_high, stop, target,
                    reward_risk, adx14, atr14, h1_bias, m15_structure, m5_trigger,
                    fingerprint, note,
                    user_decision, decided_utc, mode, bars_left, contributor_scores_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    sig_id,
                    created,
                    "ACCEPTED",
                    side,
                    symbol,
                    tf,
                    score,
                    len(contributors),
                    json.dumps(contributors),
                    entry_low,
                    entry_high,
                    stop,
                    target,
                    float(st.get("reward_risk_ratio") or ea.get("reward_risk_ratio") or 0) or None,
                    float(st["adx14"]) if st.get("adx14") is not None else None,
                    atr if atr > 0 else None,
                    st.get("h1_bias"),
                    st.get("m15_structure"),
                    st.get("m5_trigger"),
                    fp,
                    note,
                    "PENDING",
                    None,
                    mode,
                    bars_left,
                    json.dumps(details),
                ),
            )
            conn.commit()
            return {
                "id": sig_id,
                "created_utc": created,
                "status": "ACCEPTED",
                "side": side,
                "symbol": symbol,
                "timeframe": tf,
                "score": score,
                "contributing_count": len(contributors),
                "contributors": contributors,
                "contributor_scores": details,
                "user_decision": "PENDING",
                "mode": mode,
                "bars_left": bars_left,
            }
        finally:
            conn.close()


def list_signals(limit: int = 50, symbol: str | None = None) -> list[dict[str, Any]]:
    limit = max(1, min(200, int(limit)))
    with _lock:
        conn = _connect()
        try:
            if symbol:
                rows = conn.execute(
                    """
                    SELECT * FROM signals
                    WHERE symbol = ?
                    ORDER BY created_utc DESC
                    LIMIT ?
                    """,
                    (symbol.upper(), limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM signals
                    ORDER BY created_utc DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            return [_row_to_dict(r) for r in rows]
        finally:
            conn.close()


def get_signal(signal_id: str) -> Optional[dict[str, Any]]:
    with _lock:
        conn = _connect()
        try:
            row = conn.execute("SELECT * FROM signals WHERE id = ?", (signal_id,)).fetchone()
            return _row_to_dict(row) if row else None
        finally:
            conn.close()


def latest_pending_for_symbol(symbol: str) -> Optional[dict[str, Any]]:
    """Return latest PENDING signal only (no fallback to decided rows)."""
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                """
                SELECT * FROM signals
                WHERE symbol = ? AND COALESCE(user_decision, 'PENDING') = 'PENDING'
                ORDER BY created_utc DESC
                LIMIT 1
                """,
                (symbol.upper(),),
            ).fetchone()
            return _row_to_dict(row) if row else None
        finally:
            conn.close()


def record_decision(signal_id: str, decision: str) -> Optional[dict[str, Any]]:
    """Record TAKE or IGNORE — advisory only, no MT5 order. Rejects re-decide."""
    decision = str(decision or "").upper().strip()
    if decision not in {"TAKE", "IGNORE"}:
        raise ValueError("decision must be TAKE or IGNORE")
    with _lock:
        conn = _connect()
        try:
            row = conn.execute("SELECT * FROM signals WHERE id = ?", (signal_id,)).fetchone()
            if not row:
                return None
            keys = set(row.keys())
            current = row["user_decision"] if "user_decision" in keys else "PENDING"
            if current and current != "PENDING":
                raise ValueError(f"signal already decided as {current}")
            decided = _utc_now()
            conn.execute(
                """
                UPDATE signals
                SET user_decision = ?, decided_utc = ?
                WHERE id = ?
                """,
                (decision, decided, signal_id),
            )
            conn.commit()
            updated = conn.execute("SELECT * FROM signals WHERE id = ?", (signal_id,)).fetchone()
            return _row_to_dict(updated) if updated else None
        finally:
            conn.close()


def _vote_split(side: Optional[str], details: list[dict[str, Any]]) -> dict[str, Any]:
    buy_pts = 0
    sell_pts = 0
    buy_votes = 0
    sell_votes = 0
    for d in details:
        if d.get("status") != "pass":
            continue
        pts = int(d.get("points") or 0)
        key = d.get("key")
        if side == "BUY":
            buy_pts += pts
            buy_votes += 1
            if key not in _BUY_LEANING:
                sell_pts += max(1, pts // 3)
        elif side == "SELL":
            sell_pts += pts
            sell_votes += 1
            if key not in _SELL_LEANING:
                buy_pts += max(1, pts // 3)
        else:
            buy_pts += pts // 2
            sell_pts += pts // 2
    if side == "BUY" and sell_pts == 0:
        sell_pts = max(20, buy_pts // 3)
        sell_votes = max(1, buy_votes // 2)
    if side == "SELL" and buy_pts == 0:
        buy_pts = max(20, sell_pts // 3)
        buy_votes = max(1, sell_votes // 2)
    return {
        "buy_votes": buy_votes,
        "buy_points": buy_pts,
        "sell_votes": sell_votes,
        "sell_points": sell_pts,
    }


def _preview_plan(
    monitor_status: dict[str, Any],
    dash: dict[str, Any],
    mode: str,
) -> Optional[dict[str, Any]]:
    if (dash.get("verdict") or {}).get("verdict") != "SETUP_OK":
        return None
    ea = _ea_blob(monitor_status)
    st = _extra_strategy(ea)
    side = _resolve_side(st)
    if not side:
        return None
    symbol = str(ea.get("symbol") or monitor_status.get("selected_symbol") or "").upper()
    bid = _safe_float(ea.get("bid"))
    ask = _safe_float(ea.get("ask"))
    mid = (bid + ask) / 2.0 if bid > 0 and ask > 0 else bid or ask
    atr = _safe_float(st.get("atr14") or st.get("atr"))
    digits = _safe_int(ea.get("digits"), 5) or 5
    entry_low, entry_high, stop, target = _levels_from_strategy(st, side, mid, atr, digits, mode)
    gates = dash.get("gates") or []
    score, contributors, details = _score_details_from_gates(gates)
    age = st.get("setup_age_m5")
    return {
        "id": None,
        "preview": True,
        "status": "PREVIEW",
        "side": side,
        "symbol": symbol,
        "timeframe": _desk_timeframe(mode),
        "score": score,
        "contributing_count": len(contributors),
        "contributors": contributors,
        "contributor_scores": details,
        "entry_low": entry_low,
        "entry_high": entry_high,
        "stop": stop,
        "target": target,
        "reward_risk": _safe_float(st.get("reward_risk_ratio")) or None,
        "adx14": st.get("adx14"),
        "atr14": atr if atr > 0 else None,
        "h1_bias": st.get("h1_bias"),
        "m15_structure": st.get("m15_structure"),
        "m5_trigger": st.get("m5_trigger"),
        "user_decision": "PENDING",
        "mode": mode,
        "bars_left": _bars_left(age),
        "note": "Preview — will persist on next SETUP_OK heartbeat",
    }


def build_analyzer_status(
    monitor_status: dict[str, Any],
    mode: str = "STANDARD",
    timeframe: str | None = None,
) -> dict[str, Any]:
    mode = "SCALPING" if str(mode).upper() == "SCALPING" else "STANDARD"
    dash = build_dashboard(monitor_status)
    ea = _ea_blob(monitor_status)
    st = _extra_strategy(ea)
    symbol = str(
        ea.get("symbol") or monitor_status.get("selected_symbol") or dash.get("market", {}).get("symbol") or ""
    ).upper()
    company = str(ea.get("company") or "")
    server = str(ea.get("server") or "")
    broker = "MT5"
    if company:
        broker = f"MT5 — {company}"
    elif server:
        broker = f"MT5 — {server}"

    raw_symbols = (
        monitor_status.get("available_symbols")
        or dash.get("connection", {}).get("available_symbols")
        or []
    )
    symbols: list[str] = []
    for item in raw_symbols:
        if isinstance(item, dict):
            s = str(item.get("symbol") or "").upper()
            if s:
                symbols.append(s)
        elif item:
            symbols.append(str(item).upper())
    if not symbols and symbol:
        symbols = [symbol]

    active = latest_pending_for_symbol(symbol) if symbol else None
    if not active:
        active = _preview_plan(monitor_status, dash, mode)

    if active and st.get("setup_age_m5") is not None:
        active = {**active, "bars_left": _bars_left(st.get("setup_age_m5"))}

    if active and active.get("contributor_scores"):
        details = list(active["contributor_scores"])
    else:
        _, _, details = _score_details_from_gates(dash.get("gates") or [])

    side = (active or {}).get("side")
    votes = _vote_split(side, details)

    aligned = 0
    total_tf = 3
    biases = [
        str(st.get("h1_bias") or "").upper(),
        str(st.get("m15_structure") or "").upper(),
        str(st.get("m5_trigger") or "").upper(),
    ]
    want = "BULLISH" if side == "BUY" else ("BEARISH" if side == "SELL" else "")
    for b in biases:
        if want and b == want:
            aligned += 1

    decision_state = "NO_SIGNAL"
    if active:
        ud = active.get("user_decision") or "PENDING"
        if ud == "PENDING":
            decision_state = "AWAITING_YOUR_DECISION"
        elif ud == "TAKE":
            decision_state = "TAKEN"
        else:
            decision_state = "IGNORED"

    tf = timeframe or (active or {}).get("timeframe") or _desk_timeframe(mode)
    leading = None
    if details:
        passed = [d for d in details if d.get("status") == "pass"]
        if passed:
            leading = max(passed, key=lambda d: int(d.get("score") or 0))

    bid = _safe_float(ea.get("bid"))
    ask = _safe_float(ea.get("ask"))
    mid = (bid + ask) / 2.0 if bid > 0 and ask > 0 else bid or ask

    targets: list[dict[str, Any]] = []
    if active:
        t1 = float(active.get("target") or 0)
        stop = float(active.get("stop") or 0)
        el = float(active.get("entry_low") or mid)
        eh = float(active.get("entry_high") or mid)
        entry_mid = (el + eh) / 2.0
        digits = int(ea.get("digits") or 5) or 5
        if t1 and entry_mid:
            risk = abs(entry_mid - stop) if stop else abs(t1 - entry_mid) / 2
            if side == "BUY":
                targets = [
                    {"label": "TP1", "price": t1},
                    {"label": "TP2", "price": round(entry_mid + risk * 2.5, digits)},
                    {"label": "TP3", "price": round(entry_mid + risk * 3.5, digits)},
                ]
            else:
                targets = [
                    {"label": "TP1", "price": t1},
                    {"label": "TP2", "price": round(entry_mid - risk * 2.5, digits)},
                    {"label": "TP3", "price": round(entry_mid - risk * 3.5, digits)},
                ]

    pattern_label = None
    h1 = str(st.get("h1_bias") or "").upper()
    m5 = str(st.get("m5_trigger") or "").upper()
    if h1 and m5 and h1 == m5:
        pattern_label = f"{h1.title()} alignment — CONFIRMED"
    elif h1:
        pattern_label = f"H1 {h1.title()} bias"

    return {
        "advisory_only": True,
        "mode": mode,
        "timeframe": tf,
        "broker": broker,
        "decision_state": decision_state,
        "alignment": {"aligned": aligned, "total": total_tf},
        "votes": votes,
        "leading_contributor": leading,
        "market_regime": str(ea.get("market_state") or st.get("market_regime") or "Transition"),
        "live": {
            "bid": bid,
            "ask": ask,
            "mid": mid,
            "digits": int(ea.get("digits") or 5) or 5,
        },
        "targets": targets,
        "pattern": {
            "label": pattern_label,
            "bias_pct": (active or {}).get("score"),
        },
        "active_signal": active,
        "dashboard": dash,
        "symbols": symbols,
        "selected_symbol": symbol or monitor_status.get("selected_symbol"),
        "links": {
            "signals": "/signals",
            "dashboard": "/dashboard",
            "monitor": "/monitor",
            "analyzer": "/analyzer",
        },
        "caption": "Records your decision only — no MT5 order is sent.",
    }


# Initialize on import
init_db()
