"""Market news & macro intelligence — normalized domain types."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Sequence


class MacroBiasDirection(str, Enum):
    STRONGLY_BULLISH = "STRONGLY_BULLISH"
    BULLISH = "BULLISH"
    MILD_BULLISH = "MILD_BULLISH"
    NEUTRAL = "NEUTRAL"
    MILD_BEARISH = "MILD_BEARISH"
    BEARISH = "BEARISH"
    STRONGLY_BEARISH = "STRONGLY_BEARISH"


class NewsTimeHorizon(str, Enum):
    IMMEDIATE = "IMMEDIATE"
    INTRADAY = "INTRADAY"
    SHORT_TERM = "SHORT_TERM"
    SWING = "SWING"
    MEDIUM_TERM = "MEDIUM_TERM"
    LONG_TERM = "LONG_TERM"


class NewsImportance(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class NewsCategory(str, Enum):
    CENTRAL_BANK = "CENTRAL_BANK"
    INTEREST_RATE = "INTEREST_RATE"
    CPI_INFLATION = "CPI_INFLATION"
    EMPLOYMENT = "EMPLOYMENT"
    GDP = "GDP"
    PMI = "PMI"
    RETAIL_SALES = "RETAIL_SALES"
    TRADE_BALANCE = "TRADE_BALANCE"
    GEOPOLITICAL = "GEOPOLITICAL"
    ENERGY = "ENERGY"
    COMMODITY = "COMMODITY"
    BOND_YIELDS = "BOND_YIELDS"
    GOVERNMENT_POLICY = "GOVERNMENT_POLICY"
    CORPORATE = "CORPORATE"
    MARKET_COMMENTARY = "MARKET_COMMENTARY"
    OTHER = "OTHER"


class EconomicEventStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    RELEASED = "RELEASED"
    REVISED = "REVISED"
    CANCELLED = "CANCELLED"


class NewsSource(str, Enum):
    MT5_CALENDAR = "MT5_CALENDAR"
    NEWS_PROVIDER = "NEWS_PROVIDER"
    RSS = "RSS"
    MANUAL = "MANUAL"
    BROKER = "BROKER"


class MacroConflictStatus(str, Enum):
    ALIGNED = "ALIGNED"
    CONFLICT = "CONFLICT"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


_CCY_RE = re.compile(r"^[A-Z]{3}$")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_utc(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def normalize_currency(code: str | None) -> str:
    c = str(code or "").strip().upper()
    if not _CCY_RE.match(c):
        raise ValueError(f"invalid currency code: {code!r}")
    return c


def normalize_currencies(values: Sequence[str] | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values or []:
        c = normalize_currency(raw)
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def normalize_importance(value: str | None, *, default: NewsImportance = NewsImportance.MEDIUM) -> NewsImportance:
    text = str(value or "").strip().upper()
    if not text:
        return default
    aliases = {
        "MODERATE": NewsImportance.MEDIUM,
        "NONE": NewsImportance.LOW,
    }
    if text in aliases:
        return aliases[text]
    try:
        return NewsImportance(text)
    except ValueError:
        return default


def normalize_event_status(value: str | None, *, actual: float | None = None) -> EconomicEventStatus:
    text = str(value or "").strip().upper()
    if text:
        try:
            return EconomicEventStatus(text)
        except ValueError:
            pass
    if actual is not None:
        return EconomicEventStatus.RELEASED
    return EconomicEventStatus.SCHEDULED


def normalize_category(value: str | None) -> NewsCategory:
    text = str(value or "").strip().upper()
    if not text:
        return NewsCategory.OTHER
    try:
        return NewsCategory(text)
    except ValueError:
        return NewsCategory.OTHER


def normalize_horizon(value: str | None, *, default: NewsTimeHorizon = NewsTimeHorizon.INTRADAY) -> NewsTimeHorizon:
    text = str(value or "").strip().upper()
    if not text:
        return default
    try:
        return NewsTimeHorizon(text)
    except ValueError:
        return default


def normalize_bias(value: str | None, *, default: MacroBiasDirection = MacroBiasDirection.NEUTRAL) -> MacroBiasDirection:
    text = str(value or "").strip().upper()
    if not text:
        return default
    try:
        return MacroBiasDirection(text)
    except ValueError:
        return default


def _stable_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def content_hash(*parts: str) -> str:
    joined = "|".join(p.strip() for p in parts if p is not None)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def news_dedupe_key(
    source: NewsSource | str,
    external_id: str | None,
    headline: str,
    published_at: str | None,
) -> str:
    src = str(source.value if isinstance(source, NewsSource) else source).upper()
    return content_hash(src, external_id or "", headline.strip(), published_at or "")


def event_dedupe_key(
    source: NewsSource | str,
    external_event_id: str,
    scheduled_at: str | None,
) -> str:
    src = str(source.value if isinstance(source, NewsSource) else source).upper()
    return content_hash(src, external_event_id, scheduled_at or "")


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass
class EconomicEvent:
    source: NewsSource
    event_id: str
    currency: str
    event: str
    scheduled_at: str
    importance: NewsImportance = NewsImportance.MEDIUM
    country: str = ""
    category: NewsCategory = NewsCategory.OTHER
    previous: float | None = None
    forecast: float | None = None
    actual: float | None = None
    status: EconomicEventStatus = EconomicEventStatus.SCHEDULED
    external_event_id: str = ""
    content_hash: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.currency = normalize_currency(self.currency)
        self.event = str(self.event or "").strip()
        if not self.event:
            raise ValueError("event name required")
        if not self.event_id:
            ext = self.external_event_id or self.event
            self.event_id = event_dedupe_key(self.source, ext, self.scheduled_at)
        if not self.content_hash:
            self.content_hash = self.event_id
        if self.actual is not None and self.status == EconomicEventStatus.SCHEDULED:
            self.status = EconomicEventStatus.RELEASED

    @property
    def surprise(self) -> float | None:
        if self.actual is None or self.forecast is None:
            return None
        return self.actual - self.forecast

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.value,
            "event_id": self.event_id,
            "external_event_id": self.external_event_id,
            "currency": self.currency,
            "country": self.country,
            "event": self.event,
            "category": self.category.value,
            "importance": self.importance.value,
            "scheduled_at": self.scheduled_at,
            "previous": self.previous,
            "forecast": self.forecast,
            "actual": self.actual,
            "surprise": self.surprise,
            "status": self.status.value,
            "content_hash": self.content_hash,
        }


@dataclass
class NormalizedNewsItem:
    source: NewsSource
    headline: str
    published_at: str
    external_id: str = ""
    summary: str = ""
    body: str = ""
    currencies: list[str] = field(default_factory=list)
    symbols: list[str] = field(default_factory=list)
    category: NewsCategory = NewsCategory.OTHER
    importance: NewsImportance = NewsImportance.MEDIUM
    raw_url: str = ""
    content_hash: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.headline = str(self.headline or "").strip()
        if not self.headline:
            raise ValueError("headline required")
        self.currencies = normalize_currencies(self.currencies)
        self.symbols = [str(s).strip().upper() for s in self.symbols if str(s).strip()]
        if not self.content_hash:
            self.content_hash = news_dedupe_key(
                self.source, self.external_id, self.headline, self.published_at
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.value,
            "external_id": self.external_id,
            "headline": self.headline,
            "summary": self.summary,
            "body": self.body,
            "published_at": self.published_at,
            "currencies": self.currencies,
            "symbols": self.symbols,
            "category": self.category.value,
            "importance": self.importance.value,
            "raw_url": self.raw_url,
            "content_hash": self.content_hash,
        }


@dataclass
class CurrencySentiment:
    currency: str
    direction: MacroBiasDirection
    confidence: float
    horizon: NewsTimeHorizon = NewsTimeHorizon.INTRADAY
    drivers: list[str] = field(default_factory=list)
    as_of_utc: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "currency": self.currency,
            "direction": self.direction.value,
            "confidence": round(self.confidence, 1),
            "horizon": self.horizon.value,
            "drivers": self.drivers[:8],
            "as_of_utc": self.as_of_utc,
        }


@dataclass
class PairMacroBias:
    symbol: str
    direction: MacroBiasDirection
    confidence: float
    horizon: NewsTimeHorizon = NewsTimeHorizon.MEDIUM_TERM
    drivers: list[str] = field(default_factory=list)
    counter_drivers: list[str] = field(default_factory=list)
    horizons: dict[str, MacroBiasDirection] = field(default_factory=dict)
    as_of_utc: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol.upper(),
            "direction": self.direction.value,
            "confidence": round(self.confidence, 1),
            "horizon": self.horizon.value,
            "drivers": self.drivers[:8],
            "counter_drivers": self.counter_drivers[:8],
            "horizons": {k: v.value for k, v in self.horizons.items()},
            "as_of_utc": self.as_of_utc,
        }


@dataclass
class MacroConflictResult:
    status: MacroConflictStatus
    recommendation: str
    reason: str
    technical_direction: str = ""
    macro_direction: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "recommendation": self.recommendation,
            "reason": self.reason,
            "technical_direction": self.technical_direction,
            "macro_direction": self.macro_direction,
        }


@dataclass
class EventRiskStatus:
    blocked: bool
    minutes_to_next_high_impact: int | None = None
    next_event: dict[str, Any] | None = None
    high_impact_before_minutes: int = 30
    high_impact_after_minutes: int = 15
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "blocked": self.blocked,
            "minutes_to_next_high_impact": self.minutes_to_next_high_impact,
            "next_event": self.next_event,
            "high_impact_before_minutes": self.high_impact_before_minutes,
            "high_impact_after_minutes": self.high_impact_after_minutes,
            "message": self.message,
        }


@dataclass
class CentralBankContext:
    central_bank: str
    currency: str
    policy_bias: str
    confidence: float
    policy_rate: float | None = None
    next_meeting_at: str | None = None
    drivers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "central_bank": self.central_bank,
            "currency": self.currency,
            "policy_bias": self.policy_bias,
            "confidence": round(self.confidence, 1),
            "policy_rate": self.policy_rate,
            "next_meeting_at": self.next_meeting_at,
            "drivers": self.drivers[:8],
        }


@dataclass
class NewsAnalysisRecord:
    """Structured interpretation — numeric facts must come from source data."""
    headline: str
    category: NewsCategory
    time_horizon: NewsTimeHorizon
    currencies: dict[str, CurrencySentiment] = field(default_factory=dict)
    symbols: dict[str, PairMacroBias] = field(default_factory=dict)
    drivers: list[str] = field(default_factory=list)
    counter_drivers: list[str] = field(default_factory=list)
    ai_model: str = ""
    analyzed_at: str = field(default_factory=_utc_now_iso)
    analysis_hash: str = ""
    source_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "headline": self.headline,
            "category": self.category.value,
            "time_horizon": self.time_horizon.value,
            "currencies": {k: v.to_dict() for k, v in self.currencies.items()},
            "symbols": {k: v.to_dict() for k, v in self.symbols.items()},
            "drivers": self.drivers[:8],
            "counter_drivers": self.counter_drivers[:8],
            "ai_model": self.ai_model,
            "analyzed_at": self.analyzed_at,
            "analysis_hash": self.analysis_hash,
            "source_refs": self.source_refs[:12],
        }


def economic_event_from_dict(payload: Mapping[str, Any], *, default_source: NewsSource = NewsSource.MT5_CALENDAR) -> EconomicEvent:
    src_raw = payload.get("source") or default_source.value
    try:
        source = NewsSource(str(src_raw).upper())
    except ValueError:
        source = default_source
    scheduled = payload.get("scheduled_at") or payload.get("time") or ""
    dt = parse_utc(scheduled)
    scheduled_iso = dt.isoformat() if dt else str(scheduled)
    actual = _optional_float(payload.get("actual"))
    return EconomicEvent(
        source=source,
        event_id=str(payload.get("event_id") or ""),
        external_event_id=str(payload.get("external_event_id") or payload.get("event_id") or ""),
        currency=str(payload.get("currency") or "USD"),
        country=str(payload.get("country") or ""),
        event=str(payload.get("event") or payload.get("event_name") or ""),
        category=normalize_category(payload.get("category")),
        importance=normalize_importance(payload.get("importance")),
        scheduled_at=scheduled_iso,
        previous=_optional_float(payload.get("previous")),
        forecast=_optional_float(payload.get("forecast")),
        actual=actual,
        status=normalize_event_status(payload.get("status"), actual=actual),
        raw=dict(payload),
    )


def news_item_from_dict(payload: Mapping[str, Any], *, default_source: NewsSource = NewsSource.NEWS_PROVIDER) -> NormalizedNewsItem:
    src_raw = payload.get("source") or default_source.value
    try:
        source = NewsSource(str(src_raw).upper())
    except ValueError:
        source = default_source
    published = payload.get("published_at") or payload.get("published") or ""
    dt = parse_utc(published)
    published_iso = dt.isoformat() if dt else str(published)
    currencies = payload.get("currencies")
    if isinstance(currencies, str):
        currencies = [currencies]
    symbols = payload.get("symbols")
    if isinstance(symbols, str):
        symbols = [symbols]
    return NormalizedNewsItem(
        source=source,
        external_id=str(payload.get("external_id") or payload.get("id") or ""),
        headline=str(payload.get("headline") or ""),
        summary=str(payload.get("summary") or ""),
        body=str(payload.get("body") or ""),
        published_at=published_iso,
        currencies=list(currencies or []),
        symbols=list(symbols or []),
        category=normalize_category(payload.get("category")),
        importance=normalize_importance(payload.get("importance"), default=NewsImportance.MEDIUM),
        raw_url=str(payload.get("raw_url") or payload.get("url") or ""),
        raw=dict(payload),
    )
