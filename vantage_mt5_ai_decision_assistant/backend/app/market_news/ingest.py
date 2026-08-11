"""Ingest pipelines for market news providers."""
from __future__ import annotations

from typing import Any

from app.market_news.store import UpsertStats, log_calendar_ingest, upsert_central_bank_context, upsert_economic_event, upsert_news_items
from app.market_news.types import NewsImportance, NewsSource, economic_event_from_dict, news_item_from_dict
from app.schemas import MarketNewsIngestRequest, Mt5CalendarIngestRequest


def ingest_mt5_calendar(payload: Mt5CalendarIngestRequest | dict[str, Any]) -> dict[str, Any]:
    """
    Normalize and upsert MT5 economic calendar rows.
    Economic values must come from the payload — never fabricated here.
    """
    req = payload if isinstance(payload, Mt5CalendarIngestRequest) else Mt5CalendarIngestRequest.model_validate(payload)
    broker = str(req.broker or "").strip()
    terminal = str(req.terminal or "").strip()
    source = str(req.source or NewsSource.MT5_CALENDAR.value).upper()

    events = []
    errors: list[str] = []
    release_alerts: list = []
    for idx, raw in enumerate(req.events):
        try:
            data = raw.model_dump() if hasattr(raw, "model_dump") else dict(raw)
            data["source"] = source
            if not data.get("external_event_id") and data.get("event_id"):
                data["external_event_id"] = data["event_id"]
            event = economic_event_from_dict(data, default_source=NewsSource.MT5_CALENDAR)
            events.append(event)
        except Exception as exc:
            errors.append(f"event[{idx}]: {exc}")

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
            if result in ("inserted", "updated") and ev.importance in (
                NewsImportance.HIGH,
                NewsImportance.CRITICAL,
            ):
                if ev.actual is not None:
                    release_alerts.append(ev)
        except Exception as exc:
            stats.errors += 1
            stats.error_messages = (stats.error_messages or []) + [str(exc)]
    if errors:
        stats.errors += len(errors)
        stats.error_messages = (stats.error_messages or []) + errors

    try:
        from app.macro_discord_notify import maybe_alert_released_events

        maybe_alert_released_events(release_alerts)
    except Exception:
        pass

    cb_updated = 0
    try:
        from app.market_news.central_bank import refresh_central_bank_overlays

        for ctx in refresh_central_bank_overlays(events):
            upsert_central_bank_context(ctx, source="EVENT")
            cb_updated += 1
    except Exception:
        pass

    ingest_id = log_calendar_ingest(
        source=source,
        broker=broker,
        terminal=terminal,
        server_time_utc=str(req.server_time_utc or ""),
        received_count=len(req.events),
        stats=stats,
    )

    return {
        "advisory_only": True,
        "ok": stats.errors == 0 or stats.inserted + stats.updated + stats.unchanged > 0,
        "source": source,
        "ingest_id": ingest_id,
        "broker": broker or None,
        "terminal": terminal or None,
        "server_time_utc": req.server_time_utc or None,
        "received": len(req.events),
        "central_bank_updated": cb_updated,
        **stats.to_dict(),
    }


def ingest_news_items(payload: MarketNewsIngestRequest | dict[str, Any]) -> dict[str, Any]:
    """
    Bulk ingest normalized textual news (manual / future RSS/API adapters).
    Defaults source to MANUAL when omitted.
    """
    req = payload if isinstance(payload, MarketNewsIngestRequest) else MarketNewsIngestRequest.model_validate(payload)

    items = []
    errors: list[str] = []
    for idx, raw in enumerate(req.items):
        try:
            data = raw.model_dump() if hasattr(raw, "model_dump") else dict(raw)
            src = str(data.get("source") or "").strip().upper()
            if not src or src == NewsSource.NEWS_PROVIDER.value:
                data["source"] = NewsSource.MANUAL.value
            items.append(news_item_from_dict(data, default_source=NewsSource.MANUAL))
        except Exception as exc:
            errors.append(f"item[{idx}]: {exc}")

    stats = upsert_news_items(items)
    if errors:
        stats.errors += len(errors)
        stats.error_messages = (stats.error_messages or []) + errors

    return {
        "advisory_only": True,
        "ok": stats.errors == 0 or stats.inserted + stats.updated + stats.unchanged > 0,
        "source": NewsSource.MANUAL.value,
        "received": len(req.items),
        **stats.to_dict(),
    }
