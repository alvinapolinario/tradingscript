"""AI news interpretation — structured macro analysis with DB cache (Step 11)."""
from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.analysis.openai_client import llm_status
from app.config import Settings, get_settings
from app.market_news.pair_bias import build_pair_macro_bias, currency_sentiments_for_symbol, normalize_symbol, parse_symbol_legs
from app.market_news.providers.registry import get_registry
from app.market_news.service import build_symbol_status
from app.market_news.store import get_news_analysis, save_news_analysis
from app.market_news.surprise import interpret_surprise
from app.market_news.types import (
    NewsAnalysisRecord,
    NewsCategory,
    NewsTimeHorizon,
    _stable_json,
    content_hash,
    normalize_category,
    normalize_horizon,
)
from app.schemas import MarketNewsAiAnalysisOut, MarketNewsCurrencyBiasOut

SYSTEM_PROMPT = """You are a macro news interpreter for a trading advisory desk.
Return ONLY valid JSON matching this schema — no markdown fences:
{
  "headline": "short summary headline",
  "category": "CPI_INFLATION | EMPLOYMENT | CENTRAL_BANK | GDP | ...",
  "time_horizon": "INTRADAY | SHORT_TERM | MEDIUM_TERM | LONG_TERM",
  "currencies": {"USD": {"direction": "BULLISH|BEARISH|NEUTRAL", "confidence": 0-100, "horizon": "INTRADAY|..."}},
  "symbols": {"XAUUSD": {"direction": "...", "confidence": 0-100, "horizon": "..."}},
  "drivers": ["bullet reasons supporting bias"],
  "counter_drivers": ["risk factors or opposing forces"]
}
Rules:
- Interpret ONLY from the supplied facts — never invent economic release numbers.
- If actual/forecast/previous values are absent in the facts, do not quote numeric releases.
- Keep drivers factual and concise (max 8 each).
"""


def analysis_input_hash(payload: dict[str, Any]) -> str:
    return content_hash(_stable_json(_stable_facts_for_hash(payload)))


def _stable_facts_for_hash(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove time-volatile fields so cache keys stay stable between polls."""

    def _scrub(obj: Any) -> Any:
        if isinstance(obj, dict):
            out: dict[str, Any] = {}
            for key, val in obj.items():
                if key in {"as_of_utc", "analyzed_at", "minutes_to_next_high_impact"}:
                    continue
                out[key] = _scrub(val)
            return out
        if isinstance(obj, list):
            return [_scrub(x) for x in obj]
        return obj

    return _scrub(payload)


def _extract_known_numbers(facts: dict[str, Any]) -> set[str]:
    known: set[str] = set()

    def _add(val: Any) -> None:
        if val is None:
            return
        try:
            num = float(val)
        except (TypeError, ValueError):
            return
        known.add(f"{num:.6g}")

    for event in facts.get("events") or []:
        if not isinstance(event, dict):
            continue
        for key in ("previous", "forecast", "actual"):
            _add(event.get(key))
    return known


def validate_no_hallucinated_numbers(parsed: dict[str, Any], facts: dict[str, Any]) -> list[str]:
    """Flag numeric literals in LLM output that are not present in source facts."""
    known = _extract_known_numbers(facts)
    blob = json.dumps(parsed)
    issues: list[str] = []
    for match in re.finditer(r"-?\d+(?:\.\d+)?", blob):
        token = match.group(0)
        try:
            normalized = f"{float(token):.6g}"
        except ValueError:
            continue
        if normalized in known:
            continue
        # Allow common non-economic integers (confidence scores, years in categories)
        if re.fullmatch(r"\d{1,2}", token):
            val = int(token)
            if 0 <= val <= 100:
                continue
        if re.fullmatch(r"20\d{2}", token):
            continue
        issues.append(f"Unexpected numeric literal in AI output: {token}")
    return issues[:6]


def _parse_llm_json(text: str) -> dict[str, Any]:
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("AI response must be a JSON object")
    return data


def _coerce_bias_map(raw: Any) -> dict[str, MarketNewsCurrencyBiasOut]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, MarketNewsCurrencyBiasOut] = {}
    for key, val in raw.items():
        if not isinstance(val, dict):
            continue
        direction = str(val.get("direction") or "NEUTRAL").upper()
        if direction not in {"BULLISH", "BEARISH", "NEUTRAL"}:
            direction = "NEUTRAL"
        try:
            confidence = float(val.get("confidence") or 0)
        except (TypeError, ValueError):
            confidence = 0.0
        horizon = str(val.get("horizon") or "INTRADAY").upper()
        out[str(key).upper()] = MarketNewsCurrencyBiasOut(
            direction=direction,
            confidence=max(0.0, min(100.0, confidence)),
            horizon=horizon,
        )
    return out


def _validate_output(parsed: dict[str, Any]) -> MarketNewsAiAnalysisOut:
    currencies = _coerce_bias_map(parsed.get("currencies"))
    symbols = _coerce_bias_map(parsed.get("symbols"))
    drivers = [str(x) for x in (parsed.get("drivers") or []) if x][:8]
    counter = [str(x) for x in (parsed.get("counter_drivers") or []) if x][:8]
    category = normalize_category(parsed.get("category")).value
    horizon = normalize_horizon(parsed.get("time_horizon")).value
    return MarketNewsAiAnalysisOut(
        headline=str(parsed.get("headline") or "Macro interpretation"),
        category=category,
        time_horizon=horizon,
        currencies=currencies,
        symbols=symbols,
        drivers=drivers,
        counter_drivers=counter,
    )


def build_analysis_facts(
    *,
    symbol: str,
    settings: Settings,
    ea_snapshot: dict[str, Any] | None = None,
    headline: str | None = None,
) -> dict[str, Any]:
    sym = normalize_symbol(symbol)
    base, quote = parse_symbol_legs(sym)
    registry = get_registry()
    events, _ = registry.fetch_calendar(unbounded=True, limit=500)
    news, _ = registry.fetch_latest(limit=100)
    desk = build_symbol_status(sym, settings, ea_snapshot=ea_snapshot)
    pair_bias = build_pair_macro_bias(sym, events=events, news=news)
    ccy_map = currency_sentiments_for_symbol(sym, events=events, news=news)

    relevant_events = []
    for event in events:
        if event.currency not in {base, quote}:
            continue
        row = event.to_dict()
        surprise = interpret_surprise(event)
        if surprise:
            row["surprise_label"] = surprise.label
            row["surprise_direction"] = surprise.direction.value
        relevant_events.append(row)

    relevant_news = []
    for item in news:
        if headline and item.headline.strip() == headline.strip():
            relevant_news.append(item.to_dict())
            continue
        if set(item.currencies) & {base, quote}:
            relevant_news.append(item.to_dict())
        if len(relevant_news) >= 12:
            break

    return {
        "symbol": sym,
        "headline_focus": headline or "",
        "macro_bias": desk.get("macro_bias"),
        "horizons": desk.get("horizons"),
        "currency_bias": desk.get("currency_bias"),
        "event_risk": desk.get("event_risk"),
        "technical_alignment": desk.get("technical_alignment"),
        "drivers": desk.get("drivers"),
        "counter_drivers": desk.get("counter_drivers"),
        "pair_bias": pair_bias.to_dict(),
        "currency_sentiments": {k: v.to_dict() for k, v in ccy_map.items()},
        "events": relevant_events[:20],
        "news": relevant_news[:12],
    }


def rule_based_analysis(facts: dict[str, Any]) -> NewsAnalysisRecord:
    sym = facts.get("symbol") or "XAUUSD"
    pair = facts.get("pair_bias") or {}
    macro = facts.get("macro_bias") or {}
    currencies_raw = facts.get("currency_sentiments") or {}
    currencies = {
        k: v
        for k, v in currencies_raw.items()
        if isinstance(v, dict)
    }
    symbols = {
        sym: {
            "direction": pair.get("direction") or macro.get("direction") or "NEUTRAL",
            "confidence": pair.get("confidence") or macro.get("confidence") or 0,
            "horizon": pair.get("horizon") or macro.get("horizon") or "INTRADAY",
        }
    }
    from app.market_news.types import CurrencySentiment, MacroBiasDirection, PairMacroBias

    ccy_objs: dict[str, CurrencySentiment] = {}
    for ccy, row in currencies.items():
        if not isinstance(row, dict):
            continue
        try:
            direction = MacroBiasDirection(str(row.get("direction") or "NEUTRAL").upper())
        except ValueError:
            direction = MacroBiasDirection.NEUTRAL
        ccy_objs[ccy] = CurrencySentiment(
            currency=ccy,
            direction=direction,
            confidence=float(row.get("confidence") or 0),
            horizon=normalize_horizon(row.get("horizon")),
            drivers=list(row.get("drivers") or [])[:8],
        )

    try:
        pair_dir = MacroBiasDirection(str(pair.get("direction") or macro.get("direction") or "NEUTRAL").upper())
    except ValueError:
        pair_dir = MacroBiasDirection.NEUTRAL

    symbol_obj = PairMacroBias(
        symbol=sym,
        direction=pair_dir,
        confidence=float(pair.get("confidence") or macro.get("confidence") or 0),
        horizon=normalize_horizon(pair.get("horizon") or macro.get("horizon")),
        drivers=list(facts.get("drivers") or pair.get("drivers") or [])[:8],
        counter_drivers=list(facts.get("counter_drivers") or pair.get("counter_drivers") or [])[:8],
    )

    headline = str(facts.get("headline_focus") or "").strip()
    if not headline:
        headline = f"Macro desk — {sym} {pair_dir.value} ({symbol_obj.confidence:.0f}%)"

    record = NewsAnalysisRecord(
        headline=headline,
        category=NewsCategory.OTHER,
        time_horizon=normalize_horizon(pair.get("horizon") or macro.get("horizon")),
        currencies=ccy_objs,
        symbols={sym: symbol_obj},
        drivers=symbol_obj.drivers,
        counter_drivers=symbol_obj.counter_drivers,
        ai_model="rule_based",
        source_refs=[f"symbol:{sym}"],
    )
    record.analysis_hash = analysis_input_hash(facts)
    return record


def _call_openai_json(user_content: str, settings: Settings) -> tuple[str, dict[str, Any]]:
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key.strip()}",
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "response_format": {"type": "json_object"},
    }
    model_l = (settings.openai_model or "").lower()
    if not model_l.startswith("gpt-5.6"):
        body["temperature"] = 0.2

    with httpx.Client(timeout=60.0) as client:
        r = client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body)
        if r.status_code >= 400:
            raise RuntimeError(f"OpenAI HTTP {r.status_code}: {r.text[:500]}")
        data = r.json()

    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("OpenAI response missing message content") from exc

    usage = data.get("usage") or {}
    return text.strip(), {
        "model": data.get("model") or settings.openai_model,
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        },
    }


def interpret_macro(
    *,
    symbol: str = "XAUUSD",
    headline: str | None = None,
    settings: Settings | None = None,
    ea_snapshot: dict[str, Any] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Run rule-based or LLM macro interpretation with DB cache."""
    s = settings or get_settings()
    if not s.market_news_enabled:
        return {"advisory_only": True, "enabled": False, "status": "disabled"}

    facts = build_analysis_facts(
        symbol=symbol,
        settings=s,
        ea_snapshot=ea_snapshot,
        headline=headline,
    )
    digest = analysis_input_hash(facts)
    if not force:
        cached = get_news_analysis(digest)
        if cached:
            cached["status"] = "ok"
            cached["mode"] = cached.get("ai_model") or "cached"
            cached["symbol"] = normalize_symbol(symbol)
            return cached

    ai_ready = bool(s.market_news_ai_enabled) and llm_status(s).ready
    if not ai_ready:
        record = rule_based_analysis(facts)
        payload = record.to_dict()
        payload["status"] = "ok"
        payload["mode"] = "rule_based"
        payload["symbol"] = normalize_symbol(symbol)
        payload["cached"] = False
        payload["validation"] = {"hallucination_issues": [], "source": "deterministic_engine"}
        save_news_analysis(record)
        return payload

    user_blob = json.dumps(facts, indent=2, default=str)
    prompt = f"Interpret the macro context below for trading advisory purposes.\n\n{user_blob}"
    text, meta = _call_openai_json(prompt, s)
    parsed = _parse_llm_json(text)
    validated = _validate_output(parsed)
    issues = validate_no_hallucinated_numbers(parsed, facts)

    from app.market_news.types import CurrencySentiment, MacroBiasDirection, PairMacroBias

    ccy_objs: dict[str, CurrencySentiment] = {}
    for ccy, bias in validated.currencies.items():
        try:
            direction = MacroBiasDirection(bias.direction.upper())
        except ValueError:
            direction = MacroBiasDirection.NEUTRAL
        ccy_objs[ccy] = CurrencySentiment(
            currency=ccy,
            direction=direction,
            confidence=bias.confidence,
            horizon=normalize_horizon(bias.horizon),
        )

    sym = normalize_symbol(symbol)
    sym_objs: dict[str, PairMacroBias] = {}
    sym_bias = validated.symbols.get(sym) or next(iter(validated.symbols.values()), None)
    if sym_bias:
        try:
            direction = MacroBiasDirection(sym_bias.direction.upper())
        except ValueError:
            direction = MacroBiasDirection.NEUTRAL
        sym_objs[sym] = PairMacroBias(
            symbol=sym,
            direction=direction,
            confidence=sym_bias.confidence,
            horizon=normalize_horizon(sym_bias.horizon),
            drivers=validated.drivers,
            counter_drivers=validated.counter_drivers,
        )
    else:
        fallback = rule_based_analysis(facts)
        sym_objs = fallback.symbols

    record = NewsAnalysisRecord(
        headline=validated.headline,
        category=normalize_category(validated.category),
        time_horizon=normalize_horizon(validated.time_horizon),
        currencies=ccy_objs,
        symbols=sym_objs,
        drivers=validated.drivers,
        counter_drivers=validated.counter_drivers,
        ai_model=str(meta.get("model") or s.openai_model),
        analysis_hash=digest,
        source_refs=[f"symbol:{sym}"],
    )
    save_news_analysis(record)
    payload = record.to_dict()
    payload["status"] = "ok"
    payload["mode"] = "llm"
    payload["symbol"] = sym
    payload["cached"] = False
    payload["usage"] = meta.get("usage")
    payload["validation"] = {"hallucination_issues": issues, "source": "openai_json"}
    return payload
