"""Macro intelligence orchestrator — build currency/symbol/desk status."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import Settings
from app.market_news.central_bank import build_central_bank_context, build_central_bank_map
from app.market_news.conflict import macro_technical_conflict
from app.market_news.pair_bias import build_pair_macro_bias, currency_sentiments_for_symbol, normalize_symbol, parse_symbol_legs
from app.market_news.providers.registry import get_registry
from app.market_news.risk_window import build_event_risk
from app.market_news.sentiment import build_currency_sentiment
from app.market_news.store import get_central_bank_overlay, get_central_bank_overlays
from app.market_news.surprise import interpret_surprise
from app.market_news.types import EconomicEvent, MacroBiasDirection, NormalizedNewsItem, NewsImportance, parse_utc

_MAJOR_CCYS = ("USD", "EUR", "GBP", "JPY", "AUD", "CHF", "CAD", "NZD")


def _load_inputs() -> tuple[list[EconomicEvent], list[NormalizedNewsItem]]:
    registry = get_registry()
    events, _ = registry.fetch_calendar(unbounded=True, limit=500)
    news, _ = registry.fetch_latest(limit=100)
    return events, news


def _upcoming_events(events: list[EconomicEvent], *, currencies: set[str], now: datetime, limit: int = 8) -> list[dict]:
    rows: list[tuple[datetime, dict]] = []
    for event in events:
        if event.currency not in currencies:
            continue
        dt = parse_utc(event.scheduled_at)
        if dt is None or dt < now - timedelta(hours=6):
            continue
        surprise = interpret_surprise(event)
        payload = event.to_dict()
        if surprise:
            payload["surprise_label"] = surprise.label
            payload["surprise_direction"] = surprise.direction.value
        rows.append((dt, payload))
    rows.sort(key=lambda x: x[0])
    return [row for _, row in rows[:limit]]


def _recent_news(news: list[NormalizedNewsItem], *, currencies: set[str], limit: int = 8) -> list[dict]:
    out = []
    for item in news:
        if currencies and not (set(item.currencies) & currencies):
            continue
        out.append(item.to_dict())
        if len(out) >= limit:
            break
    return out


def _timeline(events: list[EconomicEvent], news: list[NormalizedNewsItem], *, currencies: set[str], now: datetime, limit: int = 12) -> list[dict]:
    rows: list[tuple[datetime, dict]] = []
    for event in events:
        if event.currency not in currencies:
            continue
        dt = parse_utc(event.scheduled_at)
        if dt is None:
            continue
        rows.append(
            (
                dt,
                {
                    "type": "event",
                    "at": event.scheduled_at,
                    "title": event.event,
                    "currency": event.currency,
                    "importance": event.importance.value,
                    "status": event.status.value,
                },
            )
        )
    for item in news:
        if currencies and not (set(item.currencies) & currencies):
            continue
        dt = parse_utc(item.published_at) or now
        rows.append(
            (
                dt,
                {
                    "type": "news",
                    "at": item.published_at,
                    "title": item.headline,
                    "currencies": item.currencies,
                    "importance": item.importance.value,
                },
            )
        )
    rows.sort(key=lambda x: x[0], reverse=True)
    return [row for _, row in rows[:limit]]


def _infer_technical_direction(ea: dict[str, Any] | None) -> MacroBiasDirection:
    if not ea:
        return MacroBiasDirection.NEUTRAL
    for key in ("ict", "swing_strategy", "amd_ifvg", "gold_smc"):
        block = ea.get(key) or {}
        if not isinstance(block, dict):
            continue
        htf = block.get("htf_bias")
        if isinstance(htf, dict):
            htf_dir = str(htf.get("direction") or "").upper()
            if "BULL" in htf_dir or htf_dir in {"LONG", "BUY"}:
                return MacroBiasDirection.BULLISH
            if "BEAR" in htf_dir or htf_dir in {"SHORT", "SELL"}:
                return MacroBiasDirection.BEARISH
        for field in ("direction", "swing_direction", "higher_timeframe_bias"):
            raw = block.get(field)
            if not raw:
                continue
            text = str(raw).upper()
            if "BULL" in text or text in {"LONG", "BUY"}:
                return MacroBiasDirection.BULLISH
            if "BEAR" in text or text in {"SHORT", "SELL"}:
                return MacroBiasDirection.BEARISH
        decision = str(block.get("decision") or "").upper()
        if decision == "BUY":
            return MacroBiasDirection.BULLISH
        if decision == "SELL":
            return MacroBiasDirection.BEARISH
    return MacroBiasDirection.NEUTRAL


def _seed_path(settings: Settings) -> str | None:
    path = str(settings.central_bank_seed_path or "").strip()
    return path or None


def _central_bank_for_currency(
    currency: str,
    *,
    events: list[EconomicEvent],
    news: list[NormalizedNewsItem],
    now: datetime,
    settings: Settings,
) -> dict[str, Any]:
    seed_path = _seed_path(settings)
    overlay = get_central_bank_overlay(currency)
    ctx = build_central_bank_context(
        currency,
        events=events,
        news=news,
        now=now,
        seed_path=seed_path,
        overlay=overlay,
    )
    return ctx.to_dict() if ctx else {}


def build_currency_status(currency: str, settings: Settings) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    events, news = _load_inputs()
    ccy = currency.upper()
    sentiment = build_currency_sentiment(ccy, events=events, news=news, now=now)
    risk = build_event_risk(
        events,
        now=now,
        before_minutes=settings.news_risk_high_before,
        after_minutes=settings.news_risk_high_after,
        currencies=[ccy],
    )
    return {
        "advisory_only": True,
        "enabled": settings.market_news_enabled,
        "currency": ccy,
        "sentiment": sentiment.to_dict(),
        "central_bank": _central_bank_for_currency(
            ccy, events=events, news=news, now=now, settings=settings
        ),
        "event_risk": risk.to_dict(),
        "upcoming_events": _upcoming_events(events, currencies={ccy}, now=now),
        "recent_news": _recent_news(news, currencies={ccy}),
        "timeline": _timeline(events, news, currencies={ccy}, now=now),
    }


def build_symbol_status(
    symbol: str,
    settings: Settings,
    *,
    ea_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    events, news = _load_inputs()
    sym = normalize_symbol(symbol)
    base, quote = parse_symbol_legs(sym)
    currencies = {base, quote}

    pair_bias = build_pair_macro_bias(sym, events=events, news=news, now=now)
    ccy_map = currency_sentiments_for_symbol(sym, events=events, news=news, now=now)
    risk = build_event_risk(
        events,
        now=now,
        before_minutes=settings.news_risk_high_before,
        after_minutes=settings.news_risk_high_after,
        currencies=sorted(currencies),
    )
    technical = _infer_technical_direction(ea_snapshot)
    alignment = macro_technical_conflict(pair_bias.direction, technical)
    seed_path = _seed_path(settings)
    cb_overlays = get_central_bank_overlays(sorted(currencies))
    central_bank = build_central_bank_map(
        currencies,
        events=events,
        news=news,
        now=now,
        seed_path=seed_path,
        overlays=cb_overlays,
    )

    return {
        "advisory_only": True,
        "enabled": settings.market_news_enabled,
        "symbol": sym,
        "macro_bias": {
            "direction": pair_bias.direction.value,
            "confidence": pair_bias.confidence,
            "horizon": pair_bias.horizon.value,
        },
        "horizons": {k: v.value for k, v in pair_bias.horizons.items()},
        "currency_bias": {k: {"direction": v.direction.value, "confidence": v.confidence} for k, v in ccy_map.items()},
        "central_bank": central_bank,
        "event_risk": risk.to_dict(),
        "technical_alignment": alignment.to_dict(),
        "drivers": pair_bias.drivers,
        "counter_drivers": pair_bias.counter_drivers,
        "recent_news": _recent_news(news, currencies=currencies),
        "upcoming_events": _upcoming_events(events, currencies=currencies, now=now),
        "timeline": _timeline(events, news, currencies=currencies, now=now),
    }


def _global_news_feed(news: list[NormalizedNewsItem], *, limit: int = 15) -> list[dict]:
    return [item.to_dict() for item in news[:limit]]


def _calendar_table(events: list[EconomicEvent], *, now: datetime, limit: int = 24) -> list[dict]:
    rows: list[tuple[datetime, dict]] = []
    for event in events:
        dt = parse_utc(event.scheduled_at)
        if dt is None or dt < now - timedelta(days=1):
            continue
        surprise = interpret_surprise(event)
        payload = event.to_dict()
        if surprise:
            payload["surprise_label"] = surprise.label
            payload["surprise_direction"] = surprise.direction.value
        rows.append((dt, payload))
    rows.sort(key=lambda x: x[0])
    return [row for _, row in rows[:limit]]


def _major_currency_heatmap(
    events: list[EconomicEvent],
    news: list[NormalizedNewsItem],
    *,
    now: datetime,
) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for ccy in _MAJOR_CCYS:
        sentiment = build_currency_sentiment(ccy, events=events, news=news, now=now)
        out[ccy] = sentiment.to_dict()
    return out


def build_macro_desk_status(
    settings: Settings,
    *,
    symbol: str | None = None,
    ea_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    events, news = _load_inputs()
    sym = normalize_symbol(symbol or "XAUUSD")
    payload = build_symbol_status(sym, settings, ea_snapshot=ea_snapshot)
    payload["module"] = "market_news"
    payload["status_line"] = (
        f"Macro {payload['macro_bias']['direction']} {payload['macro_bias']['confidence']:.0f}% · "
        f"{payload['event_risk']['message'] or 'Calendar synced'}"
    )
    payload["news_feed"] = _global_news_feed(news)
    payload["calendar_table"] = _calendar_table(events, now=now)
    payload["major_currency_bias"] = _major_currency_heatmap(events, news, now=now)
    payload["high_impact_upcoming"] = [
        row
        for row in payload["calendar_table"]
        if row.get("importance") in {NewsImportance.HIGH.value, NewsImportance.CRITICAL.value}
    ][:8]
    payload["ai_interpret_enabled"] = bool(settings.market_news_ai_enabled and settings.use_llm)
    return payload
