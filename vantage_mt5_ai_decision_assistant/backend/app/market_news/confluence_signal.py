"""Normalize macro intelligence into a confluence StrategySignal."""
from __future__ import annotations

import time
from typing import Any

from app.analysis.confluence.types import ConfluenceConfig, Direction, StrategySignal
from app.analysis.confluence.weights import DEFAULT_STRATEGY_WEIGHTS
from app.market_news.types import MacroBiasDirection, normalize_bias


def _macro_direction_to_confluence(bias: MacroBiasDirection) -> Direction:
    if bias in {
        MacroBiasDirection.STRONGLY_BULLISH,
        MacroBiasDirection.BULLISH,
        MacroBiasDirection.MILD_BULLISH,
    }:
        return "LONG"
    if bias in {
        MacroBiasDirection.STRONGLY_BEARISH,
        MacroBiasDirection.BEARISH,
        MacroBiasDirection.MILD_BEARISH,
    }:
        return "SHORT"
    if bias == MacroBiasDirection.NEUTRAL:
        return "NEUTRAL"
    return "NO_SETUP"


def normalize_macro_signal(
    ea: dict[str, Any],
    cfg: ConfluenceConfig,
    *,
    macro_status: dict[str, Any] | None = None,
) -> StrategySignal | None:
    """
    Map pair macro bias to a weighted MACRO strategy signal.
    Requires MARKET_NEWS_ENABLED; inactive when macro data unavailable.
    """
    from app.config import get_settings

    settings = get_settings()
    if not settings.market_news_enabled or not cfg.macro_enabled:
        return None

    if macro_status is None:
        from app.market_news.service import build_symbol_status

        from app.market_news.pair_bias import normalize_symbol

        symbol = normalize_symbol(str(ea.get("symbol") or ea.get("broker_symbol") or "XAUUSD"))
        macro_status = build_symbol_status(symbol, settings, ea_snapshot=ea)

    bias = macro_status.get("macro_bias") if isinstance(macro_status.get("macro_bias"), dict) else {}
    direction = _macro_direction_to_confluence(normalize_bias(bias.get("direction")))
    confidence = float(bias.get("confidence") or 0.0)
    if direction == "NO_SETUP" or confidence <= 0:
        return None

    alignment = macro_status.get("technical_alignment") if isinstance(macro_status.get("technical_alignment"), dict) else {}
    status = str(alignment.get("status") or "NEUTRAL").upper()
    evidence: list[str] = []
    for d in macro_status.get("drivers") or []:
        if d:
            evidence.append(str(d))
    if alignment.get("reason"):
        evidence.append(str(alignment["reason"]))
    event_risk = macro_status.get("event_risk") if isinstance(macro_status.get("event_risk"), dict) else {}
    if event_risk.get("blocked") and event_risk.get("message"):
        evidence.append(str(event_risk["message"]))

    weight = float(cfg.strategy_weights.get("MACRO", DEFAULT_STRATEGY_WEIGHTS.get("MACRO", 0.35)))

    return StrategySignal(
        strategy="MACRO",
        direction=direction,
        confidence=max(0.0, min(100.0, confidence)),
        status=status,
        evidence=evidence[:6],
        invalidation=[],
        timestamp=int(ea.get("server_time") or time.time()),
        freshness_sec=0.0,
        weight=weight,
        active=True,
    )
