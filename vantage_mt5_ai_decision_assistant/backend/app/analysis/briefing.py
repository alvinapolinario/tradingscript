"""Human-readable decision briefing for the monitor UI (advisory only)."""
from __future__ import annotations

from typing import Any


def _f(v: Any, digits: int = 2) -> str:
    try:
        return f"{float(v):.{digits}f}"
    except (TypeError, ValueError):
        return "—"


def build_decision_brief(ea: dict[str, Any], stats: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Build analysis + recommendations from the latest EA/analyze snapshot.
    Returns structured sections for the monitor (not raw logs).
    """
    stats = stats or {}
    connected = bool(ea.get("connected"))
    positions = int(ea.get("position_count") or 0)
    trend = (ea.get("trend") or "—").upper()
    market = (ea.get("market_state") or "—").upper()
    new_entry = (ea.get("new_entry_decision") or "—").upper()
    existing = (ea.get("existing_position_decision") or "—").upper()
    risk = (ea.get("risk_status") or "—").upper()
    equity = ea.get("equity_risk_pct")
    sl_loss = ea.get("estimated_sl_loss")
    entry = ea.get("entry")
    sl = ea.get("sl")
    float_pl = ea.get("floating_pl")
    float_pct = ea.get("floating_pl_pct_of_equity")
    equity_bal = ea.get("equity")
    float_target = float(ea.get("float_profit_target_pct") or 10.0)
    float_hit = bool(ea.get("float_profit_target_hit"))
    if float_pct is None and equity_bal and float(equity_bal) > 0 and float_pl is not None:
        float_pct = (float(float_pl) / float(equity_bal)) * 100.0
    if float_pct is not None and float(float_pct) >= float_target > 0 and int(ea.get("position_count") or 0) > 0:
        float_hit = True
    support = ea.get("nearest_support") or "—"
    resist = ea.get("nearest_resistance") or "—"
    recovery_1 = ea.get("recovery_level_1") or resist
    recovery_2 = ea.get("recovery_level_2") or "—"
    bullish = ea.get("bullish_confirmation") or "—"
    invalidation = ea.get("technical_invalidation") or "—"
    warning = ea.get("risk_warning") or ea.get("note") or ""
    high_spread = bool(ea.get("high_spread"))
    add_ok = bool(ea.get("add_position_allowed"))
    new_ok = bool(ea.get("new_position_allowed"))
    exceeds = bool(ea.get("exceeds_max_position_risk"))

    severity = "info"
    if not connected:
        severity = "warn"
    if risk in ("HIGH", "VERY_HIGH") or high_spread:
        severity = "warn"
    if float_hit and severity == "info":
        severity = "warn"
    if risk == "CRITICAL" or exceeds or existing == "CRITICAL_RISK":
        severity = "critical"

    # --- Headline ---
    if not connected:
        headline = "Waiting for EA heartbeat — analysis will appear once the chart EA is linked."
    elif positions > 0 and risk == "CRITICAL":
        headline = (
            f"Open position under CRITICAL equity risk ({_f(equity)}%). "
            "Protect capital: do not average down or widen the stop."
        )
    elif positions > 0 and existing == "HOLD_WITH_CAUTION":
        headline = (
            f"Hold the open position with caution. Equity risk {_f(equity)}% at SL "
            f"(~{_f(sl_loss)} USD). Prefer defense over adding size."
        )
    elif positions > 0 and existing == "PROTECT_PROFIT":
        headline = "Open trade is profitable into adverse structure — consider protecting gains manually."
    elif positions > 0 and existing == "EXIT_WARNING":
        headline = "Open trade is underwater with adverse structure — review exit manually (advisory only)."
    elif float_hit:
        headline = (
            f"Floating profit hit {_f(float_pct)}% of equity (target {float_target:.0f}%). "
            "Consider limiting/taking profit — do not let a winner become a give-back."
        )
    elif new_entry in ("BUY_ALLOWED", "SELL_ALLOWED"):
        headline = f"New-entry watch: {new_entry.replace('_', ' ')} — still advisory; confirm structure on M30."
    elif new_entry == "WAIT":
        headline = "Wait for retest / pullback — do not chase impulse."
    elif high_spread:
        headline = "High spread environment — suppress fresh entries until spread normalizes."
    else:
        headline = f"Flat / no fresh edge. Trend={trend}, market={market}. Stand aside unless conditions improve."

    # --- Situation bullets ---
    situation: list[str] = []
    if connected:
        situation.append(f"Symbol {ea.get('symbol') or '—'} · Trend {trend} · Market {market}")
        bull_pct = ea.get("bullish_pct")
        bear_pct = ea.get("bearish_pct")
        lookback = ea.get("bias_lookback") or 20
        if bull_pct is not None or bear_pct is not None:
            situation.append(
                f"Chart bias ({lookback} bars): Bullish {_f(bull_pct, 1)}% · Bearish {_f(bear_pct, 1)}%"
                + (f" · Flat {_f(ea.get('neutral_pct'), 1)}%" if float(ea.get("neutral_pct") or 0) > 0.05 else "")
            )
            situation.append(
                f"Indicator bias: Bullish {_f(ea.get('indicator_bullish_pct'), 1)}% · "
                f"Bearish {_f(ea.get('indicator_bearish_pct'), 1)}%"
            )
        situation.append(
            f"New entry: {new_entry} · Existing position: {existing} · Risk: {risk}"
        )
        if positions > 0:
            situation.append(
                f"Open positions: {positions} · Float P/L {_f(float_pl)} "
                f"({_f(float_pct)}% of equity {_f(equity_bal)}) · Entry {_f(entry)} · SL {_f(sl)}"
            )
            situation.append(
                f"If SL hits: estimated loss ~{_f(sl_loss)} USD ({_f(equity)}% of equity)"
            )
            situation.append(
                f"Float profit target: {float_target:.1f}% of equity — "
                + ("HIT" if float_hit else "not yet")
            )
        else:
            situation.append("No open position — new-entry rules apply.")
        if high_spread:
            situation.append(f"Spread elevated ({ea.get('spread_points')} pts) — entry quality degraded.")
        situation.append(f"Key support {support} · Recovery {recovery_1} / {recovery_2} · Bullish conf {bullish}")
        if invalidation and invalidation != "—":
            situation.append(f"Technical invalidation: {invalidation}")
    else:
        situation.append(
            "Attach EA to the chart for the selected pair (e.g. XAUUSD or BTCUSD M30), "
            "allow WebRequest for http://127.0.0.1:8000, enable Algo Trading."
        )

    # --- Actionable recommendations ---
    recommendations: list[dict[str, str]] = []

    def rec(priority: str, title: str, detail: str) -> None:
        recommendations.append({"priority": priority, "title": title, "detail": detail})

    if not connected:
        rec("high", "Restore EA link", "Until heartbeat resumes, treat any prior state as stale.")
    elif positions > 0 and (risk == "CRITICAL" or exceeds):
        rec(
            "critical",
            "Do not add exposure",
            "Equity risk exceeds configured maximum. No averaging-down, no new lots, no widening SL.",
        )
        rec(
            "high",
            "Decide management plan manually",
            "Advisory only — choose hold-with-plan, partial reduce, or exit yourself. The EA will not close the trade.",
        )
        if float_pl is not None and float(float_pl) > 0:
            rec(
                "medium",
                "Protect floating profit",
                f"Price is above entry while risk-at-SL remains large. Trail/lock gains only if your plan allows — current SL {_f(sl)}.",
            )
        else:
            rec(
                "high",
                "Respect invalidation",
                invalidation or f"A sustained break through SL {_f(sl)} ends the thesis for this entry.",
            )
        rec(
            "medium",
            "Watch recovery map",
            f"Support {support}. Recovery L1 {recovery_1}, L2 {recovery_2}. Bullish confirmation {bullish} would challenge the bearish bias.",
        )
    elif positions > 0:
        rec(
            "high",
            f"Manage open trade: {existing.replace('_', ' ')}",
            f"Primary focus is the existing position, not a new entry ({new_entry}).",
        )
        if not add_ok:
            rec("medium", "No add-on", "Add-position is blocked while an open trade is active / risk elevated.")
        rec(
            "medium",
            "Map levels before acting",
            f"Support {support} · Recovery {recovery_1}/{recovery_2} · Confirmation {bullish}.",
        )
    else:
        if new_ok:
            rec(
                "medium",
                f"New entry watch: {new_entry.replace('_', ' ')}",
                "Confirm closed M30 structure, spread, and risk size before any manual order.",
            )
        elif new_entry == "WAIT":
            rec("medium", "Wait for retest", "Impulse without pullback — patience improves R:R.")
        elif new_entry == "HIGH_SPREAD":
            rec("high", "Stand aside on spread", "Fresh entries blocked until spread is back under your limit.")
        else:
            rec("low", "No new trade", "Conditions do not justify a fresh entry. Preserve cash and wait for structure.")
        rec(
            "low",
            "Pre-trade checklist",
            "Define entry, SL, size so equity risk ≤ your max (default 2%), and invalidation before clicking Buy/Sell.",
        )

    if float_hit:
        rec(
            "high",
            "Take-profit discipline",
            f"Floating P/L is {_f(float_pct)}% of equity (≥ {float_target:.0f}% target). "
            "Consider locking gains or reducing size manually — EA will not close for you.",
        )

    if warning:
        rec("critical" if severity == "critical" else "high", "System warning", warning)

    # --- Checklist ---
    checklist: list[dict[str, Any]] = [
        {"label": "EA connected", "ok": connected},
        {"label": "Spread acceptable", "ok": connected and not high_spread},
        {"label": "New position allowed", "ok": new_ok},
        {"label": "Add position allowed", "ok": add_ok},
        {
            "label": "Position risk within max",
            "ok": connected and (positions == 0 or (not exceeds and risk != "CRITICAL")),
        },
        {
            "label": "Float profit under target",
            "ok": connected and (positions == 0 or not float_hit),
        },
        {
            "label": "Invalidation defined",
            "ok": bool(invalidation and invalidation != "—") or positions == 0,
        },
    ]

    # --- What would improve the next decision ---
    improvements = [
        "Size so estimated SL loss stays under your max equity risk (default 2%) before entry.",
        f"When floating profit reaches {float_target:.0f}% of equity, take partial or full profit — do not widen targets emotionally.",
        "Require a closed M30 confirmation candle at recovery levels before reversing a losing BUY.",
        "If risk is CRITICAL, only two manual choices: hold with a written plan, or reduce/exit — never widen SL.",
        "Treat BEARISH_EXHAUSTED as ‘no chase’: wait for reclaim of recovery L1/L2 before considering long adds.",
        "Log your own decision (hold / cut / trail) when risk or float-profit state changes — one deliberate action beats tick noise.",
    ]

    last_analyze = stats.get("last_analyze_utc")
    analyze_age = stats.get("seconds_since_analyze")

    return {
        "severity": severity,
        "headline": headline,
        "situation": situation,
        "recommendations": recommendations,
        "checklist": checklist,
        "improvements": improvements,
        "levels": {
            "support": support,
            "recovery_1": recovery_1,
            "recovery_2": recovery_2,
            "bullish_confirmation": bullish,
            "invalidation": invalidation,
            "entry": entry,
            "sl": sl,
            "source": ea.get("level_source") or "",
            "symbol": ea.get("symbol") or "",
        },
        "meta": {
            "last_analyze_utc": last_analyze,
            "seconds_since_analyze": analyze_age,
            "analyze_count": stats.get("analyze_count"),
            "advisory_only": True,
        },
        "equity_pie": {
            "equity": float(equity_bal or 0),
            "floating_pl": float(float_pl or 0),
            "floating_pl_pct": float(float_pct or 0),
            "target_pct": float_target,
            "target_hit": float_hit,
            "currency": ea.get("currency") or "USD",
        },
        "chart_bias": {
            "bullish_pct": float(ea.get("bullish_pct") or 0),
            "bearish_pct": float(ea.get("bearish_pct") or 0),
            "neutral_pct": float(ea.get("neutral_pct") or 0),
            "lookback": int(ea.get("bias_lookback") or 20),
            "indicator_bullish_pct": float(ea.get("indicator_bullish_pct") or 0),
            "indicator_bearish_pct": float(ea.get("indicator_bearish_pct") or 0),
            "trend": trend,
        },
    }
