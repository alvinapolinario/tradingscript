"""Symbol-level macro bias from currency legs."""
from __future__ import annotations

from datetime import datetime, timezone

from app.market_news.horizon import build_horizon_map
from app.market_news.sentiment import build_currency_sentiment, direction_to_score, score_to_direction
from app.market_news.types import CurrencySentiment, EconomicEvent, MacroBiasDirection, NewsTimeHorizon, NormalizedNewsItem, PairMacroBias

METAL_BASES = {"XAU", "XAG", "GOLD", "SILVER"}
CRYPTO_BASES = {"BTC", "ETH", "BITCOIN"}

# Primary macro desk pairs — gold plus major FX crosses (Step 14+ expansion).
DEFAULT_MAJOR_MACRO_PAIRS = ("XAUUSD", "EURUSD", "USDJPY")


def normalize_symbol(symbol: str) -> str:
    return (symbol or "").upper().replace("#", "").replace(".", "").strip()


def parse_symbol_legs(symbol: str) -> tuple[str, str]:
    """Return (base, quote) for FX/metal/crypto symbols."""
    sym = normalize_symbol(symbol)
    if sym in {"XAUUSD", "GOLDUSD", "GOLD"}:
        return "XAU", "USD"
    if sym in {"XAGUSD", "SILVER"}:
        return "XAG", "USD"
    if sym.endswith("USD") and len(sym) > 3:
        base = sym[:-3]
        if base in METAL_BASES | CRYPTO_BASES or len(base) in (3, 4):
            return base, "USD"
    if len(sym) == 6:
        return sym[:3], sym[3:]
    if len(sym) == 7 and sym[:3] in METAL_BASES | CRYPTO_BASES:
        return sym[:3], sym[3:]
    return sym[:3] if len(sym) >= 3 else sym, "USD"


def build_pair_macro_bias(
    symbol: str,
    *,
    events: list[EconomicEvent],
    news: list[NormalizedNewsItem],
    now: datetime | None = None,
) -> PairMacroBias:
    now = now or datetime.now(timezone.utc)
    sym = normalize_symbol(symbol)
    base, quote = parse_symbol_legs(sym)

    base_sent = build_currency_sentiment(base, events=events, news=news, now=now)
    quote_sent = build_currency_sentiment(quote, events=events, news=news, now=now)

    pair_score = direction_to_score(base_sent.direction) - direction_to_score(quote_sent.direction)
    direction, confidence = score_to_direction(pair_score)

    drivers = []
    counter = []
    if base_sent.direction != MacroBiasDirection.NEUTRAL:
        drivers.append(f"{base}: {base_sent.direction.value} ({base_sent.confidence:.0f}%)")
    if quote_sent.direction != MacroBiasDirection.NEUTRAL:
        counter.append(f"{quote}: {quote_sent.direction.value} ({quote_sent.confidence:.0f}%)")

    for d in base_sent.drivers[:3]:
        drivers.append(d)
    for d in quote_sent.drivers[:2]:
        counter.append(d)

    horizons = build_horizon_map(
        base_ccy=base,
        quote_ccy=quote,
        events=events,
        news=news,
        now=now,
    )
    horizon = NewsTimeHorizon.MEDIUM_TERM if abs(pair_score) >= 0.6 else NewsTimeHorizon.INTRADAY

    return PairMacroBias(
        symbol=sym,
        direction=direction,
        confidence=round(confidence, 1),
        horizon=horizon,
        drivers=drivers[:8],
        counter_drivers=counter[:8],
        horizons=horizons,
        as_of_utc=now.isoformat(),
    )


def currency_sentiments_for_symbol(
    symbol: str,
    *,
    events: list[EconomicEvent],
    news: list[NormalizedNewsItem],
    now: datetime | None = None,
) -> dict[str, CurrencySentiment]:
    base, quote = parse_symbol_legs(symbol)
    now = now or datetime.now(timezone.utc)
    return {
        base: build_currency_sentiment(base, events=events, news=news, now=now),
        quote: build_currency_sentiment(quote, events=events, news=news, now=now),
    }
