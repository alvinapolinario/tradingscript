"""SQLite persistence for market news and economic calendar."""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from app.market_news.types import CentralBankContext, EconomicEvent, NormalizedNewsItem, NewsAnalysisRecord, economic_event_from_dict, news_item_from_dict

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_DB_PATH = _DATA_DIR / "market_news.db"
_lock = threading.Lock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, name: str, ddl: str) -> None:
    cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if name not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def init_db() -> None:
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS economic_events (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    external_event_id TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    country TEXT NOT NULL DEFAULT '',
                    event_name TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'OTHER',
                    importance TEXT NOT NULL DEFAULT 'MEDIUM',
                    scheduled_at TEXT NOT NULL,
                    previous REAL,
                    forecast REAL,
                    actual REAL,
                    status TEXT NOT NULL DEFAULT 'SCHEDULED',
                    content_hash TEXT NOT NULL,
                    broker TEXT NOT NULL DEFAULT '',
                    terminal TEXT NOT NULL DEFAULT '',
                    raw_json TEXT,
                    created_utc TEXT NOT NULL,
                    updated_utc TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_econ_events_natural
                ON economic_events(source, external_event_id, scheduled_at)
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_econ_events_sched ON economic_events(scheduled_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_econ_events_ccy ON economic_events(currency, scheduled_at DESC)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS news_items (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    external_id TEXT NOT NULL DEFAULT '',
                    headline TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    body TEXT NOT NULL DEFAULT '',
                    published_at TEXT NOT NULL,
                    currencies_json TEXT NOT NULL DEFAULT '[]',
                    symbols_json TEXT NOT NULL DEFAULT '[]',
                    category TEXT NOT NULL DEFAULT 'OTHER',
                    importance TEXT NOT NULL DEFAULT 'MEDIUM',
                    raw_url TEXT NOT NULL DEFAULT '',
                    content_hash TEXT NOT NULL,
                    raw_json TEXT,
                    created_utc TEXT NOT NULL,
                    updated_utc TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_news_content_hash ON news_items(content_hash)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_news_published ON news_items(published_at DESC)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS calendar_ingest_log (
                    id TEXT PRIMARY KEY,
                    ingested_utc TEXT NOT NULL,
                    source TEXT NOT NULL,
                    broker TEXT NOT NULL DEFAULT '',
                    terminal TEXT NOT NULL DEFAULT '',
                    server_time_utc TEXT NOT NULL DEFAULT '',
                    received_count INTEGER NOT NULL DEFAULT 0,
                    inserted_count INTEGER NOT NULL DEFAULT 0,
                    updated_count INTEGER NOT NULL DEFAULT 0,
                    unchanged_count INTEGER NOT NULL DEFAULT 0,
                    error_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS central_bank_context (
                    currency TEXT PRIMARY KEY,
                    institution TEXT NOT NULL,
                    policy_bias TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    policy_rate REAL,
                    next_meeting_at TEXT,
                    drivers_json TEXT NOT NULL DEFAULT '[]',
                    source TEXT NOT NULL DEFAULT 'SEED',
                    updated_utc TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS news_analysis (
                    analysis_hash TEXT PRIMARY KEY,
                    headline TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'OTHER',
                    time_horizon TEXT NOT NULL DEFAULT 'INTRADAY',
                    payload_json TEXT NOT NULL,
                    ai_model TEXT NOT NULL DEFAULT '',
                    source_refs_json TEXT NOT NULL DEFAULT '[]',
                    analyzed_at TEXT NOT NULL,
                    created_utc TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_news_analysis_at ON news_analysis(analyzed_at DESC)"
            )
            _ensure_column(conn, "economic_events", "broker", "broker TEXT NOT NULL DEFAULT ''")
            _ensure_column(conn, "economic_events", "terminal", "terminal TEXT NOT NULL DEFAULT ''")
            conn.commit()
        finally:
            conn.close()


@dataclass
class UpsertStats:
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    errors: int = 0
    error_messages: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "inserted": self.inserted,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "errors": self.errors,
            "error_messages": self.error_messages or [],
        }


def _event_row_signature(row: sqlite3.Row) -> tuple[Any, ...]:
    return (
        row["source"],
        row["external_event_id"],
        row["currency"],
        row["country"],
        row["event_name"],
        row["category"],
        row["importance"],
        row["scheduled_at"],
        row["previous"],
        row["forecast"],
        row["actual"],
        row["status"],
        row["content_hash"],
        row["broker"],
        row["terminal"],
    )


def _event_signature(ev: EconomicEvent, *, broker: str = "", terminal: str = "") -> tuple[Any, ...]:
    return (
        ev.source.value,
        ev.external_event_id or ev.event_id,
        ev.currency,
        ev.country,
        ev.event,
        ev.category.value,
        ev.importance.value,
        ev.scheduled_at,
        ev.previous,
        ev.forecast,
        ev.actual,
        ev.status.value,
        ev.content_hash,
        broker,
        terminal,
    )


def upsert_economic_event(
    event: EconomicEvent,
    *,
    broker: str = "",
    terminal: str = "",
) -> str:
    """Insert or update one event. Returns inserted | updated | unchanged."""
    ext_id = event.external_event_id or event.event_id
    now = _utc_now()
    sig = _event_signature(event, broker=broker, terminal=terminal)
    with _lock:
        conn = _connect()
        try:
            existing = conn.execute(
                "SELECT * FROM economic_events WHERE id = ?",
                (event.event_id,),
            ).fetchone()
            if not existing:
                existing = conn.execute(
                    """
                    SELECT * FROM economic_events
                    WHERE source = ? AND external_event_id = ? AND scheduled_at = ?
                    """,
                    (event.source.value, ext_id, event.scheduled_at),
                ).fetchone()

            if existing and _event_row_signature(existing) == sig:
                return "unchanged"

            if existing:
                conn.execute(
                    """
                    UPDATE economic_events SET
                        source = ?, external_event_id = ?, currency = ?, country = ?,
                        event_name = ?, category = ?, importance = ?, scheduled_at = ?,
                        previous = ?, forecast = ?, actual = ?, status = ?,
                        content_hash = ?, broker = ?, terminal = ?, raw_json = ?,
                        updated_utc = ?
                    WHERE id = ?
                    """,
                    (
                        event.source.value,
                        ext_id,
                        event.currency,
                        event.country,
                        event.event,
                        event.category.value,
                        event.importance.value,
                        event.scheduled_at,
                        event.previous,
                        event.forecast,
                        event.actual,
                        event.status.value,
                        event.content_hash,
                        broker,
                        terminal,
                        json.dumps(event.raw) if event.raw else None,
                        now,
                        existing["id"],
                    ),
                )
                conn.commit()
                return "updated"

            conn.execute(
                """
                INSERT INTO economic_events (
                    id, source, external_event_id, currency, country, event_name,
                    category, importance, scheduled_at, previous, forecast, actual,
                    status, content_hash, broker, terminal, raw_json, created_utc, updated_utc
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    event.event_id,
                    event.source.value,
                    ext_id,
                    event.currency,
                    event.country,
                    event.event,
                    event.category.value,
                    event.importance.value,
                    event.scheduled_at,
                    event.previous,
                    event.forecast,
                    event.actual,
                    event.status.value,
                    event.content_hash,
                    broker,
                    terminal,
                    json.dumps(event.raw) if event.raw else None,
                    now,
                    now,
                ),
            )
            conn.commit()
            return "inserted"
        finally:
            conn.close()


def upsert_economic_events(
    events: list[EconomicEvent],
    *,
    broker: str = "",
    terminal: str = "",
) -> UpsertStats:
    stats = UpsertStats(error_messages=[])
    for ev in events:
        try:
            result = upsert_economic_event(ev, broker=broker, terminal=terminal)
            if result == "inserted":
                stats.inserted += 1
            elif result == "updated":
                stats.updated += 1
            else:
                stats.unchanged += 1
        except Exception as exc:
            stats.errors += 1
            stats.error_messages.append(str(exc))
    return stats


def upsert_news_item(item: NormalizedNewsItem) -> str:
    now = _utc_now()
    sig = (
        item.source.value,
        item.external_id,
        item.headline,
        item.summary,
        item.body,
        item.published_at,
        json.dumps(item.currencies),
        json.dumps(item.symbols),
        item.category.value,
        item.importance.value,
        item.raw_url,
        item.content_hash,
    )
    with _lock:
        conn = _connect()
        try:
            existing = conn.execute(
                "SELECT * FROM news_items WHERE content_hash = ?",
                (item.content_hash,),
            ).fetchone()
            if existing:
                row_sig = (
                    existing["source"],
                    existing["external_id"],
                    existing["headline"],
                    existing["summary"],
                    existing["body"],
                    existing["published_at"],
                    existing["currencies_json"],
                    existing["symbols_json"],
                    existing["category"],
                    existing["importance"],
                    existing["raw_url"],
                    existing["content_hash"],
                )
                if row_sig == sig:
                    return "unchanged"
                conn.execute(
                    """
                    UPDATE news_items SET
                        source = ?, external_id = ?, headline = ?, summary = ?, body = ?,
                        published_at = ?, currencies_json = ?, symbols_json = ?,
                        category = ?, importance = ?, raw_url = ?, raw_json = ?, updated_utc = ?
                    WHERE id = ?
                    """,
                    (
                        item.source.value,
                        item.external_id,
                        item.headline,
                        item.summary,
                        item.body,
                        item.published_at,
                        json.dumps(item.currencies),
                        json.dumps(item.symbols),
                        item.category.value,
                        item.importance.value,
                        item.raw_url,
                        json.dumps(item.raw) if item.raw else None,
                        now,
                        existing["id"],
                    ),
                )
                conn.commit()
                return "updated"

            item_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO news_items (
                    id, source, external_id, headline, summary, body, published_at,
                    currencies_json, symbols_json, category, importance, raw_url,
                    content_hash, raw_json, created_utc, updated_utc
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    item_id,
                    item.source.value,
                    item.external_id,
                    item.headline,
                    item.summary,
                    item.body,
                    item.published_at,
                    json.dumps(item.currencies),
                    json.dumps(item.symbols),
                    item.category.value,
                    item.importance.value,
                    item.raw_url,
                    item.content_hash,
                    json.dumps(item.raw) if item.raw else None,
                    now,
                    now,
                ),
            )
            conn.commit()
            return "inserted"
        finally:
            conn.close()


def _row_to_event_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "source": row["source"],
        "external_event_id": row["external_event_id"],
        "event_id": row["id"],
        "currency": row["currency"],
        "country": row["country"],
        "event": row["event_name"],
        "category": row["category"],
        "importance": row["importance"],
        "scheduled_at": row["scheduled_at"],
        "previous": row["previous"],
        "forecast": row["forecast"],
        "actual": row["actual"],
        "status": row["status"],
        "content_hash": row["content_hash"],
        "broker": row["broker"],
        "terminal": row["terminal"],
        "created_utc": row["created_utc"],
        "updated_utc": row["updated_utc"],
    }


def list_economic_events(
    *,
    limit: int = 100,
    currency: str | None = None,
    source: str | None = None,
    from_utc: str | None = None,
    to_utc: str | None = None,
) -> list[dict[str, Any]]:
    limit = max(1, min(500, int(limit)))
    clauses: list[str] = []
    params: list[Any] = []
    if currency:
        clauses.append("currency = ?")
        params.append(currency.upper())
    if source:
        clauses.append("source = ?")
        params.append(source.upper())
    if from_utc:
        clauses.append("scheduled_at >= ?")
        params.append(from_utc)
    if to_utc:
        clauses.append("scheduled_at <= ?")
        params.append(to_utc)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                f"""
                SELECT * FROM economic_events
                {where}
                ORDER BY scheduled_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
            return [_row_to_event_dict(r) for r in rows]
        finally:
            conn.close()


def get_economic_event(event_id: str) -> dict[str, Any] | None:
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT * FROM economic_events WHERE id = ?",
                (event_id,),
            ).fetchone()
            return _row_to_event_dict(row) if row else None
        finally:
            conn.close()


def upsert_news_items(items: list[NormalizedNewsItem]) -> UpsertStats:
    stats = UpsertStats(error_messages=[])
    for item in items:
        try:
            result = upsert_news_item(item)
            if result == "inserted":
                stats.inserted += 1
            elif result == "updated":
                stats.updated += 1
            else:
                stats.unchanged += 1
        except Exception as exc:
            stats.errors += 1
            stats.error_messages.append(str(exc))
    return stats


def list_news_items(
    *,
    limit: int = 50,
    source: str | None = None,
    currency: str | None = None,
) -> list[dict[str, Any]]:
    limit = max(1, min(200, int(limit)))
    clauses: list[str] = []
    params: list[Any] = []
    if source:
        clauses.append("source = ?")
        params.append(source.upper())
    if currency:
        clauses.append("currencies_json LIKE ?")
        params.append(f'%"{currency.upper()}"%')
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                f"""
                SELECT * FROM news_items
                {where}
                ORDER BY published_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
            out: list[dict[str, Any]] = []
            for row in rows:
                out.append(
                    {
                        "id": row["id"],
                        "source": row["source"],
                        "external_id": row["external_id"],
                        "headline": row["headline"],
                        "summary": row["summary"],
                        "published_at": row["published_at"],
                        "currencies": json.loads(row["currencies_json"] or "[]"),
                        "symbols": json.loads(row["symbols_json"] or "[]"),
                        "category": row["category"],
                        "importance": row["importance"],
                        "content_hash": row["content_hash"],
                    }
                )
            return out
        finally:
            conn.close()


def log_calendar_ingest(
    *,
    source: str,
    broker: str,
    terminal: str,
    server_time_utc: str,
    received_count: int,
    stats: UpsertStats,
) -> str:
    ingest_id = str(uuid.uuid4())
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO calendar_ingest_log (
                    id, ingested_utc, source, broker, terminal, server_time_utc,
                    received_count, inserted_count, updated_count, unchanged_count, error_count
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    ingest_id,
                    _utc_now(),
                    source,
                    broker,
                    terminal,
                    server_time_utc,
                    received_count,
                    stats.inserted,
                    stats.updated,
                    stats.unchanged,
                    stats.errors,
                ),
            )
            conn.commit()
            return ingest_id
        finally:
            conn.close()


def event_from_row(row: dict[str, Any]) -> EconomicEvent:
    return economic_event_from_dict(row)


def news_from_row(row: dict[str, Any]) -> NormalizedNewsItem:
    return news_item_from_dict(row)


def get_central_bank_overlay(currency: str) -> CentralBankContext | None:
    ccy = currency.upper()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT * FROM central_bank_context WHERE currency = ?",
                (ccy,),
            ).fetchone()
            if not row:
                return None
            return CentralBankContext(
                central_bank=row["institution"],
                currency=row["currency"],
                policy_bias=row["policy_bias"],
                confidence=float(row["confidence"]),
                policy_rate=row["policy_rate"],
                next_meeting_at=row["next_meeting_at"],
                drivers=json.loads(row["drivers_json"] or "[]"),
            )
        finally:
            conn.close()


def get_central_bank_overlays(currencies: Sequence[str] | None = None) -> dict[str, CentralBankContext]:
    clauses = ""
    params: list[Any] = []
    if currencies:
        placeholders = ",".join("?" for _ in currencies)
        clauses = f" WHERE currency IN ({placeholders})"
        params = [c.upper() for c in currencies]
    out: dict[str, CentralBankContext] = {}
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                f"SELECT * FROM central_bank_context{clauses}",
                params,
            ).fetchall()
            for row in rows:
                out[row["currency"]] = CentralBankContext(
                    central_bank=row["institution"],
                    currency=row["currency"],
                    policy_bias=row["policy_bias"],
                    confidence=float(row["confidence"]),
                    policy_rate=row["policy_rate"],
                    next_meeting_at=row["next_meeting_at"],
                    drivers=json.loads(row["drivers_json"] or "[]"),
                )
            return out
        finally:
            conn.close()


def upsert_central_bank_context(ctx: CentralBankContext, *, source: str = "EVENT") -> None:
    now = _utc_now()
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO central_bank_context (
                    currency, institution, policy_bias, confidence, policy_rate,
                    next_meeting_at, drivers_json, source, updated_utc
                ) VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(currency) DO UPDATE SET
                    institution = excluded.institution,
                    policy_bias = excluded.policy_bias,
                    confidence = excluded.confidence,
                    policy_rate = excluded.policy_rate,
                    next_meeting_at = excluded.next_meeting_at,
                    drivers_json = excluded.drivers_json,
                    source = excluded.source,
                    updated_utc = excluded.updated_utc
                """,
                (
                    ctx.currency.upper(),
                    ctx.central_bank,
                    ctx.policy_bias,
                    ctx.confidence,
                    ctx.policy_rate,
                    ctx.next_meeting_at,
                    json.dumps(ctx.drivers),
                    source,
                    now,
                ),
            )
            conn.commit()
        finally:
            conn.close()


def get_news_analysis(analysis_hash: str) -> dict[str, Any] | None:
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT * FROM news_analysis WHERE analysis_hash = ?",
                (analysis_hash,),
            ).fetchone()
            if not row:
                return None
            payload = json.loads(row["payload_json"] or "{}")
            payload["analysis_hash"] = row["analysis_hash"]
            payload["ai_model"] = row["ai_model"]
            payload["analyzed_at"] = row["analyzed_at"]
            payload["source_refs"] = json.loads(row["source_refs_json"] or "[]")
            payload["cached"] = True
            return payload
        finally:
            conn.close()


def save_news_analysis(record: NewsAnalysisRecord) -> None:
    now = _utc_now()
    payload = record.to_dict()
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO news_analysis (
                    analysis_hash, headline, category, time_horizon, payload_json,
                    ai_model, source_refs_json, analyzed_at, created_utc
                ) VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(analysis_hash) DO UPDATE SET
                    headline = excluded.headline,
                    category = excluded.category,
                    time_horizon = excluded.time_horizon,
                    payload_json = excluded.payload_json,
                    ai_model = excluded.ai_model,
                    source_refs_json = excluded.source_refs_json,
                    analyzed_at = excluded.analyzed_at
                """,
                (
                    record.analysis_hash,
                    record.headline,
                    record.category.value,
                    record.time_horizon.value,
                    json.dumps(payload),
                    record.ai_model,
                    json.dumps(record.source_refs[:12]),
                    record.analyzed_at,
                    now,
                ),
            )
            conn.commit()
        finally:
            conn.close()


init_db()
