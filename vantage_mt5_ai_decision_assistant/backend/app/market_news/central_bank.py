"""Central bank context — static seed + high-impact event overlays."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.market_news.surprise import interpret_surprise
from app.market_news.types import (
    CentralBankContext,
    EconomicEvent,
    EconomicEventStatus,
    MacroBiasDirection,
    NewsCategory,
    NewsImportance,
    NormalizedNewsItem,
    parse_utc,
)

_DEFAULT_SEED_PATH = Path(__file__).resolve().parent / "data" / "central_bank_seed.json"

_BIAS_ORDER = ("DOVISH", "MILD_DOVISH", "NEUTRAL", "MILD_HAWKISH", "HAWKISH")
_HIGH_IMPORTANCE = {NewsImportance.HIGH, NewsImportance.CRITICAL}
_CB_CATEGORIES = {NewsCategory.CENTRAL_BANK, NewsCategory.INTEREST_RATE}

_RATE_EVENT_TERMS = (
    "INTEREST RATE",
    "RATE DECISION",
    "OFFICIAL BANK RATE",
    "CASH RATE",
    "POLICY RATE",
    "FOMC",
    "ECB",
    "BOJ",
    "BOE",
    "RBA",
    "RBNZ",
    "BOC",
    "SNB",
)


def default_seed_path() -> Path:
    return _DEFAULT_SEED_PATH


def _enum_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _bias_index(bias: str) -> int:
    text = str(bias or "NEUTRAL").strip().upper()
    if text in _BIAS_ORDER:
        return _BIAS_ORDER.index(text)
    if "HAWK" in text:
        return _BIAS_ORDER.index("HAWKISH")
    if "DOVE" in text:
        return _BIAS_ORDER.index("DOVISH")
    return _BIAS_ORDER.index("NEUTRAL")


def _shift_bias(bias: str, steps: int) -> str:
    idx = _bias_index(bias)
    idx = max(0, min(len(_BIAS_ORDER) - 1, idx + steps))
    return _BIAS_ORDER[idx]


def _surprise_to_bias_steps(direction: MacroBiasDirection) -> int:
    if direction in {MacroBiasDirection.STRONGLY_BULLISH, MacroBiasDirection.BULLISH}:
        return 1
    if direction in {MacroBiasDirection.MILD_BULLISH}:
        return 1
    if direction in {MacroBiasDirection.STRONGLY_BEARISH, MacroBiasDirection.BEARISH}:
        return -1
    if direction in {MacroBiasDirection.MILD_BEARISH}:
        return -1
    return 0


def _context_from_row(row: dict[str, Any]) -> CentralBankContext:
    drivers = row.get("drivers") or []
    if isinstance(drivers, str):
        drivers = json.loads(drivers)
    return CentralBankContext(
        central_bank=str(row.get("central_bank") or row.get("institution") or ""),
        currency=str(row.get("currency") or "").upper(),
        policy_bias=str(row.get("policy_bias") or "NEUTRAL").upper(),
        confidence=float(row.get("confidence") or 50.0),
        policy_rate=row.get("policy_rate"),
        next_meeting_at=row.get("next_meeting_at"),
        drivers=list(drivers),
    )


@lru_cache
def load_seed_banks(seed_path: str | None = None) -> dict[str, CentralBankContext]:
    path = Path(seed_path) if seed_path else _DEFAULT_SEED_PATH
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, CentralBankContext] = {}
    for row in raw.get("banks") or []:
        ctx = _context_from_row(row)
        if ctx.currency:
            out[ctx.currency] = ctx
    return out


def _is_cb_relevant(event: EconomicEvent) -> bool:
    imp = event.importance
    if hasattr(imp, "value"):
        try:
            imp = NewsImportance(_enum_value(imp))
        except ValueError:
            imp = NewsImportance.MEDIUM
    if imp not in _HIGH_IMPORTANCE:
        return False
    cat = event.category
    if hasattr(cat, "value"):
        try:
            cat = NewsCategory(_enum_value(cat))
        except ValueError:
            cat = NewsCategory.OTHER
    if cat in _CB_CATEGORIES:
        return True
    name = event.event.upper()
    return any(term in name for term in _RATE_EVENT_TERMS)


def _next_meeting_for_currency(currency: str, events: list[EconomicEvent], now: datetime) -> str | None:
    best: datetime | None = None
    for event in events:
        if event.currency != currency or not _is_cb_relevant(event):
            continue
        dt = parse_utc(event.scheduled_at)
        if dt is None or dt < now:
            continue
        if best is None or dt < best:
            best = dt
    return best.isoformat() if best else None


def _released_rate_from_events(currency: str, events: list[EconomicEvent]) -> float | None:
    latest: tuple[datetime, float] | None = None
    for event in events:
        if event.currency != currency or event.actual is None:
            continue
        status = _enum_value(event.status).upper()
        if status not in {EconomicEventStatus.RELEASED.value, EconomicEventStatus.REVISED.value}:
            continue
        if not _is_cb_relevant(event):
            continue
        dt = parse_utc(event.scheduled_at) or datetime.min.replace(tzinfo=timezone.utc)
        if latest is None or dt > latest[0]:
            latest = (dt, float(event.actual))
    return latest[1] if latest else None


def _event_bias_adjustments(
    currency: str,
    events: list[EconomicEvent],
    now: datetime,
) -> tuple[int, float, list[str]]:
    steps = 0
    confidence_delta = 0.0
    drivers: list[str] = []
    for event in events:
        if event.currency != currency or not _is_cb_relevant(event):
            continue
        surprise = interpret_surprise(event)
        if surprise and _enum_value(event.status).upper() in {
            EconomicEventStatus.RELEASED.value,
            EconomicEventStatus.REVISED.value,
        }:
            step = _surprise_to_bias_steps(surprise.direction)
            if step:
                steps += step
                confidence_delta += min(12.0, surprise.confidence * 0.12)
                drivers.append(surprise.driver)
            continue
        dt = parse_utc(event.scheduled_at)
        if dt and dt >= now:
            hours = (dt - now).total_seconds() / 3600.0
            if hours <= 72:
                confidence_delta += 4.0
                drivers.append(f"Upcoming CB/rate event: {event.event}")
    return steps, confidence_delta, drivers


def _news_bias_adjustments(currency: str, news: list[NormalizedNewsItem]) -> tuple[int, float, list[str]]:
    steps = 0
    confidence_delta = 0.0
    drivers: list[str] = []
    for item in news:
        if currency not in item.currencies:
            continue
        text = f"{item.headline} {item.summary}".upper()
        if any(term in text for term in ("HAWK", "HIKE", "TIGHTEN", "HIGHER FOR LONGER")):
            steps += 1
            confidence_delta += 6.0
            drivers.append(item.headline[:100])
        elif any(term in text for term in ("DOVE", "CUT", "EASE", "LOWER RATES", "PAUSE")):
            steps -= 1
            confidence_delta += 6.0
            drivers.append(item.headline[:100])
    return steps, confidence_delta, drivers[:3]


def merge_central_bank_context(
    seed: CentralBankContext,
    *,
    events: list[EconomicEvent],
    news: list[NormalizedNewsItem],
    now: datetime | None = None,
    overlay: CentralBankContext | None = None,
) -> CentralBankContext:
    now = now or datetime.now(timezone.utc)
    base = overlay or seed
    ccy = seed.currency

    policy_bias = base.policy_bias
    confidence = base.confidence
    policy_rate = base.policy_rate
    next_meeting = base.next_meeting_at
    drivers = list(base.drivers)

    event_steps, event_conf, event_drivers = _event_bias_adjustments(ccy, events, now)
    news_steps, news_conf, news_drivers = _news_bias_adjustments(ccy, news)
    steps = event_steps + news_steps
    if steps:
        policy_bias = _shift_bias(policy_bias, steps)
    confidence = min(92.0, max(35.0, confidence + event_conf + news_conf))

    released_rate = _released_rate_from_events(ccy, events)
    if released_rate is not None:
        policy_rate = released_rate

    upcoming = _next_meeting_for_currency(ccy, events, now)
    if upcoming:
        next_meeting = upcoming

    for d in event_drivers + news_drivers:
        if d and d not in drivers:
            drivers.append(d)

    return CentralBankContext(
        central_bank=base.central_bank or seed.central_bank,
        currency=ccy,
        policy_bias=policy_bias,
        confidence=round(confidence, 1),
        policy_rate=policy_rate,
        next_meeting_at=next_meeting,
        drivers=drivers[:8],
    )


def build_central_bank_context(
    currency: str,
    *,
    events: list[EconomicEvent],
    news: list[NormalizedNewsItem],
    now: datetime | None = None,
    seed_path: str | None = None,
    overlay: CentralBankContext | None = None,
) -> CentralBankContext | None:
    ccy = currency.upper()
    seeds = load_seed_banks(seed_path)
    seed = seeds.get(ccy)
    if seed is None and overlay is None:
        return None
    if seed is None:
        seed = overlay  # type: ignore[assignment]
    return merge_central_bank_context(
        seed,
        events=events,
        news=news,
        now=now,
        overlay=overlay,
    )


def build_central_bank_map(
    currencies: set[str],
    *,
    events: list[EconomicEvent],
    news: list[NormalizedNewsItem],
    now: datetime | None = None,
    seed_path: str | None = None,
    overlays: dict[str, CentralBankContext] | None = None,
) -> dict[str, dict[str, Any]]:
    overlays = overlays or {}
    out: dict[str, dict[str, Any]] = {}
    for ccy in sorted(currencies):
        ctx = build_central_bank_context(
            ccy,
            events=events,
            news=news,
            now=now,
            seed_path=seed_path,
            overlay=overlays.get(ccy),
        )
        if ctx:
            out[ccy] = ctx.to_dict()
    return out


def refresh_central_bank_overlays(events: list[EconomicEvent]) -> list[CentralBankContext]:
    """Build overlay contexts from released high-impact CB/rate events."""
    now = datetime.now(timezone.utc)
    seeds = load_seed_banks()
    updated: list[CentralBankContext] = []
    seen: set[str] = set()
    for event in events:
        if event.currency in seen or not _is_cb_relevant(event):
            continue
        status = _enum_value(event.status).upper()
        if status not in {EconomicEventStatus.RELEASED.value, EconomicEventStatus.REVISED.value}:
            continue
        seed = seeds.get(event.currency)
        if not seed:
            continue
        ctx = merge_central_bank_context(seed, events=[event], news=[], now=now)
        updated.append(ctx)
        seen.add(event.currency)
    return updated
