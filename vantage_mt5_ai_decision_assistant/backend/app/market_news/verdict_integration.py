"""Step 9 — wire macro intelligence into master verdict, analyzer, and desk gates."""
from __future__ import annotations

from typing import Any


def _module_chip(name: str, status: str, detail: str, tone: str) -> dict[str, str]:
    return {"name": name, "status": status, "detail": detail, "tone": tone}


def load_macro_context(ea: dict[str, Any]) -> dict[str, Any] | None:
    from app.config import get_settings

    settings = get_settings()
    if not settings.market_news_enabled:
        return None
    try:
        from app.market_news.service import build_symbol_status
        from app.market_news.pair_bias import normalize_symbol

        symbol = normalize_symbol(str(ea.get("symbol") or ea.get("broker_symbol") or "XAUUSD"))
        return build_symbol_status(symbol, settings, ea_snapshot=ea)
    except Exception:
        return None


def macro_module_chip(macro_ctx: dict[str, Any] | None) -> dict[str, str] | None:
    if not macro_ctx or not macro_ctx.get("enabled", True):
        return None
    bias = macro_ctx.get("macro_bias") if isinstance(macro_ctx.get("macro_bias"), dict) else {}
    direction = str(bias.get("direction") or "NEUTRAL")
    confidence = float(bias.get("confidence") or 0.0)
    alignment = macro_ctx.get("technical_alignment") if isinstance(macro_ctx.get("technical_alignment"), dict) else {}
    status = str(alignment.get("status") or "NEUTRAL").upper()
    if status == "ALIGNED":
        tone = "ok"
    elif status == "CONFLICT":
        tone = "warn"
    else:
        tone = "muted"
    rec = str(alignment.get("recommendation") or "MONITOR")
    return _module_chip("Macro", direction[:16], f"{confidence:.0f}% · {rec}", tone)


def macro_recommendation_block(macro_ctx: dict[str, Any] | None) -> dict[str, Any]:
    if not macro_ctx:
        return {}
    alignment = macro_ctx.get("technical_alignment") if isinstance(macro_ctx.get("technical_alignment"), dict) else {}
    return {
        "status": alignment.get("status"),
        "recommendation": alignment.get("recommendation"),
        "reason": alignment.get("reason"),
        "macro_direction": alignment.get("macro_direction"),
        "technical_direction": alignment.get("technical_direction"),
    }


def macro_event_risk_block(macro_ctx: dict[str, Any] | None) -> dict[str, Any]:
    if not macro_ctx:
        return {}
    risk = macro_ctx.get("event_risk") if isinstance(macro_ctx.get("event_risk"), dict) else {}
    return {
        "blocked": bool(risk.get("blocked")),
        "minutes_to_next_high_impact": risk.get("minutes_to_next_high_impact"),
        "next_event": risk.get("next_event"),
        "message": risk.get("message"),
    }


def technical_setup_confirmed(ea: dict[str, Any], *, confluence: dict[str, Any] | None = None) -> bool:
    if confluence:
        if confluence.get("agreeing_count", 0) >= 2 and confluence.get("overall_direction") in ("LONG", "SHORT"):
            return True
        if confluence.get("macro_conflict"):
            return False
    for key in ("ict", "amd_ifvg", "swing_strategy", "box_theory"):
        block = ea.get(key) if isinstance(ea.get(key), dict) else {}
        decision = str(block.get("decision") or block.get("signal") or "").upper()
        if decision in ("BUY", "SELL"):
            conf = float(block.get("confidence_score") or block.get("confidence") or 0)
            if conf >= 70:
                return True
    entry = str(ea.get("new_entry_decision") or "").upper()
    return entry in ("BUY_ALLOWED", "SELL_ALLOWED")


def setup_verdict_complete(verdict: str) -> bool:
    return verdict in ("SETUP", "STRONG")


def apply_macro_verdict_rules(
    verdict: str,
    tone: str,
    summary: str,
    macro_ctx: dict[str, Any] | None,
    *,
    ea: dict[str, Any],
    confluence: dict[str, Any] | None = None,
) -> tuple[str, str, str]:
    """Task §18 — macro never trades alone; adjusts verdict when conflict/aligned."""
    if not macro_ctx:
        return verdict, tone, summary

    alignment = macro_ctx.get("technical_alignment") if isinstance(macro_ctx.get("technical_alignment"), dict) else {}
    status = str(alignment.get("status") or "NEUTRAL").upper()
    tech_ok = technical_setup_confirmed(ea, confluence=confluence)
    setup_ok = setup_verdict_complete(verdict)

    event_risk = macro_ctx.get("event_risk") if isinstance(macro_ctx.get("event_risk"), dict) else {}
    if event_risk.get("blocked") and verdict in ("SETUP", "STRONG"):
        return "WATCH", "warn", f"High-impact event window — stand aside. {summary}"

    if status == "CONFLICT" and not tech_ok:
        return "WATCH", "warn", f"Macro conflict — wait for confirmation. {summary}"

    if status == "ALIGNED" and setup_ok and tech_ok and verdict == "SETUP":
        return "SETUP", "ok", f"Macro aligned — setup validated. {summary}"

    if status == "ALIGNED" and setup_ok and tech_ok and verdict == "STRONG":
        return "STRONG", "ok", f"Macro + technical alignment. {summary}"

    return verdict, tone, summary


def macro_blocks_and_boosts(
    macro_ctx: dict[str, Any] | None,
    alignment: dict[str, Any] | None = None,
) -> tuple[list[str], list[str]]:
    blocks: list[str] = []
    boosts: list[str] = []
    if not macro_ctx:
        return blocks, boosts

    risk = macro_ctx.get("event_risk") if isinstance(macro_ctx.get("event_risk"), dict) else {}
    if risk.get("blocked"):
        msg = str(risk.get("message") or "High-impact news window")
        blocks.append(msg[:80])

    alignment = alignment or macro_recommendation_block(macro_ctx)
    if str(alignment.get("status") or "").upper() == "ALIGNED":
        macro_dir = str(alignment.get("macro_direction") or "NEUTRAL")
        boosts.append(f"Macro aligned ({macro_dir.lower()})")
    elif str(alignment.get("status") or "").upper() == "CONFLICT":
        blocks.append(str(alignment.get("reason") or "Macro vs technical conflict")[:80])

    return blocks, boosts


def build_news_gate(
    *,
    symbol: str,
    spec: dict[str, Any],
    st: dict[str, Any],
    ea: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Upgraded news gate — merges EA M5 desk feed with backend calendar when enabled.
    Returns gate dict or None to fall back to legacy-only path.
    """
    from app.config import get_settings
    from app.strategy_desk import _gate

    settings = get_settings()
    if not settings.market_news_enabled:
        return None

    macro_ctx = load_macro_context({**ea, "symbol": symbol or ea.get("symbol")})
    if not macro_ctx:
        return None

    before = int(spec["news_block"]["minutes_before"])
    after = int(spec["news_block"]["minutes_after"])
    risk = macro_event_risk_block(macro_ctx)
    ea_blocked = st.get("news_blocked")
    ea_available = st.get("news_available")
    ea_mins = st.get("minutes_to_high_impact")

    backend_blocked = bool(risk.get("blocked"))
    blocked = bool(ea_blocked) or backend_blocked

    next_event = risk.get("next_event") if isinstance(risk.get("next_event"), dict) else None
    mins = risk.get("minutes_to_next_high_impact")
    if mins is None and ea_mins is not None:
        mins = ea_mins

    event_label = ""
    if next_event:
        event_label = f"{next_event.get('event', 'Event')} ({next_event.get('currency', '—')})"

    if blocked:
        if event_label and mins is not None and int(mins) >= 0:
            detail = f"Blocked · {event_label} in ~{int(mins)}m · {before}m before / {after}m after"
        elif event_label:
            detail = f"Blocked · {event_label} · {before}m before / {after}m after"
        else:
            detail = (
                str(risk.get("message") or "")
                or f"Blocked · {before}m before / {after}m after high-impact"
            )
        return _gate("news", "High-impact news window", "fail", detail)

    if ea_available is False and next_event:
        detail = f"Backend calendar · clear · next {event_label}"
        if mins is not None and int(mins) >= 0:
            detail += f" in ~{int(mins)}m"
        return _gate("news", "High-impact news window", "pass", detail)

    if next_event:
        detail = f"Clear · next {event_label}"
        if mins is not None and int(mins) >= 0:
            detail += f" in ~{int(mins)}m"
        else:
            detail += f" · {before}m before / {after}m after"
        return _gate("news", "High-impact news window", "pass", detail)

    if ea_available is False:
        return _gate(
            "news",
            "High-impact news window",
            "warn",
            f"EA calendar unavailable · backend has no upcoming high-impact · "
            f"{before}m before / {after}m after",
        )

    detail = "Clear of high-impact window"
    if mins is not None and int(mins) >= 0:
        detail += f" · next in ~{int(mins)}m"
    return _gate("news", "High-impact news window", "pass", detail)


def analyzer_macro_section(ea: dict[str, Any]) -> dict[str, Any]:
    macro_ctx = load_macro_context(ea)
    if not macro_ctx:
        return {"enabled": False}
    return {
        "enabled": True,
        "macro_bias": macro_ctx.get("macro_bias"),
        "horizons": macro_ctx.get("horizons"),
        "currency_bias": macro_ctx.get("currency_bias"),
        "central_bank": macro_ctx.get("central_bank"),
        "event_risk": macro_event_risk_block(macro_ctx),
        "recommendation": macro_recommendation_block(macro_ctx),
        "upcoming_events": (macro_ctx.get("upcoming_events") or [])[:3],
        "drivers": (macro_ctx.get("drivers") or [])[:4],
    }
