"""
Pattern Strategy · Strategy Scanner · Strategy Lab helpers.

Advisory-only views over the M5 Alignment Desk feed.
"""
from __future__ import annotations

from typing import Any, Optional

from app.strategy_desk import (
    STRATEGY_SPEC,
    _ea_blob,
    build_dashboard,
    evaluate_gates,
    playbook_spec,
    summarize_verdict,
)

PATTERN_CATALOG: list[dict[str, Any]] = [
    {
        "id": "h1_m15_align",
        "name": "H1 + M15 Alignment",
        "family": "Structure",
        "gate": "alignment",
        "description": "Trade only when H1 bias and M15 structure agree (BUY or SELL).",
        "rules": ["H1 bias ∈ {BULLISH, BEARISH}", "M15 structure matches H1", "Direction locked to alignment"],
    },
    {
        "id": "ema_stack",
        "name": "M5 EMA Stack",
        "family": "Momentum",
        "gate": "ema",
        "description": "M5 EMA 20/50/200 stack agrees with the aligned direction.",
        "rules": ["EMA20 vs EMA50 vs EMA200 stacked with bias", "M5 trigger confirms H1"],
    },
    {
        "id": "adx_trend",
        "name": "ADX Trend Strength",
        "family": "Momentum",
        "gate": "adx",
        "description": "ADX(14) above playbook minimum — avoid flat regimes.",
        "rules": ["ADX period 14", "Min ADX from Strategy Lab / playbook"],
    },
    {
        "id": "rr_geometry",
        "name": "Reward:Risk Geometry",
        "family": "Risk",
        "gate": "rr",
        "description": "Planned entry → stop → target meets minimum R:R.",
        "rules": ["Min R:R from playbook", "ATR-based stop / target from EA desk"],
    },
    {
        "id": "risk_cap",
        "name": "Equity Risk Cap",
        "family": "Risk",
        "gate": "risk_pct",
        "description": "Planned size stays within playbook equity risk %.",
        "rules": ["Default 0.50% of equity", "Override via Strategy Lab session"],
    },
    {
        "id": "spread_filter",
        "name": "Pair Spread Filter",
        "family": "Execution",
        "gate": "spread",
        "description": "Spread within pair-specific max points.",
        "rules": ["XAUUSD / GOLD · BTCUSD tables", "EA high-spread flag respected"],
    },
    {
        "id": "news_window",
        "name": "News Blackout",
        "family": "Execution",
        "gate": "news",
        "description": "Stand aside around high-impact calendar events.",
        "rules": ["30m before / 15m after (playbook)", "Broker calendar when available"],
    },
    {
        "id": "setup_fresh",
        "name": "Fresh Setup Age",
        "family": "Timing",
        "gate": "setup_age",
        "description": "Setup still within max completed M5 bars after signal.",
        "rules": ["Max age from playbook (default 3)", "Candle-close confirmation required"],
    },
    {
        "id": "m5_close",
        "name": "M5 Close Confirm",
        "family": "Timing",
        "gate": "close_confirm",
        "description": "Wait for confirmed M5 close before acting on advice.",
        "rules": ["No mid-candle chase", "EA m5_closed_confirmed flag"],
    },
]


def apply_lab_overrides_to_status(
    monitor_status: dict[str, Any],
    overrides: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    st = dict(monitor_status)
    base = dict(st.get("lab_overrides") or {})
    if overrides:
        for k, v in overrides.items():
            if v is None or v == "":
                continue
            base[k] = v
    st["lab_overrides"] = base
    return st


def effective_spec(monitor_status: dict[str, Any]) -> dict[str, Any]:
    return playbook_spec(monitor_status)

def build_patterns(monitor_status: dict[str, Any]) -> dict[str, Any]:
    dash = build_dashboard(monitor_status)
    gates = {g["key"]: g for g in (dash.get("gates") or [])}
    market = dash.get("market") or {}
    items = []
    active = 0
    for p in PATTERN_CATALOG:
        g = gates.get(p["gate"]) or {}
        status = g.get("status") or "unknown"
        if status == "pass":
            active += 1
        items.append(
            {
                **p,
                "status": status,
                "detail": g.get("detail") or "Awaiting desk feed",
                "active": status == "pass",
            }
        )
    return {
        "advisory_only": True,
        "symbol": market.get("symbol") or monitor_status.get("selected_symbol"),
        "verdict": dash.get("verdict"),
        "market": {
            "h1_bias": market.get("h1_bias"),
            "m15_structure": market.get("m15_structure"),
            "m5_trigger": market.get("m5_trigger"),
            "adx14": market.get("adx14"),
            "atr14": market.get("atr14"),
            "reward_risk_ratio": market.get("reward_risk_ratio"),
        },
        "active_count": active,
        "total": len(items),
        "items": items,
        "note": "Patterns mirror M5 Alignment Desk gates — advisory only, no orders.",
    }


def _score_row(gates: list[dict[str, Any]], verdict: dict[str, Any]) -> int:
    score = 40
    for g in gates:
        if g.get("status") == "pass":
            score += 6
        elif g.get("status") == "warn":
            score += 2
        elif g.get("status") == "fail":
            score -= 4
    if (verdict or {}).get("verdict") == "SETUP_OK":
        score = max(score, 85)
    return max(0, min(99, score))


def build_scanner(
    base_status: dict[str, Any],
    pair_statuses: list[dict[str, Any]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for ps in pair_statuses:
        symbol = str(ps.get("selected_symbol") or ps.get("symbol") or "")
        status = apply_lab_overrides_to_status(
            {
                **ps,
                "lab_overrides": base_status.get("lab_overrides") or {},
            }
        )
        dash = build_dashboard(status)
        gates = dash.get("gates") or []
        verdict = dash.get("verdict") or {}
        market = dash.get("market") or {}
        conn = dash.get("connection") or {}
        pass_n = sum(1 for g in gates if g.get("status") == "pass")
        fail_n = sum(1 for g in gates if g.get("status") == "fail")
        h1 = str(market.get("h1_bias") or "").upper()
        rows.append(
            {
                "symbol": symbol,
                "connected": bool(conn.get("ea_connected")),
                "verdict": verdict.get("verdict"),
                "tone": verdict.get("tone"),
                "headline": verdict.get("headline"),
                "score": _score_row(gates, verdict),
                "gates_pass": pass_n,
                "gates_fail": fail_n,
                "gates_total": len(gates),
                "side": "BUY" if h1 == "BULLISH" else ("SELL" if h1 == "BEARISH" else "—"),
                "h1_bias": market.get("h1_bias"),
                "m15_structure": market.get("m15_structure"),
                "m5_trigger": market.get("m5_trigger"),
                "adx14": market.get("adx14"),
                "spread_points": market.get("spread_points"),
                "reward_risk_ratio": market.get("reward_risk_ratio"),
                "setup_age_m5": market.get("setup_age_m5"),
            }
        )
    rows.sort(key=lambda r: (0 if r["verdict"] == "SETUP_OK" else 1, -r["score"], r["symbol"]))
    setup_ok = sum(1 for r in rows if r["verdict"] == "SETUP_OK")
    return {
        "advisory_only": True,
        "count": len(rows),
        "setup_ok_count": setup_ok,
        "items": rows,
        "selected_symbol": base_status.get("selected_symbol"),
        "note": "Scanner ranks pairs from live EA strategy heartbeats — advisory only.",
    }


def build_lab(
    monitor_status: dict[str, Any],
    trial_overrides: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    session = dict(monitor_status.get("lab_overrides") or {})
    trial = dict(trial_overrides or {})
    merged = {**session, **trial}
    status = apply_lab_overrides_to_status(monitor_status, merged)
    spec = effective_spec(status)
    gates = evaluate_gates(status)
    verdict = summarize_verdict(gates)
    return {
        "advisory_only": True,
        "spec_base": STRATEGY_SPEC,
        "spec_effective": spec,
        "session_overrides": session,
        "trial_overrides": trial,
        "fields": [
            {
                "key": "min_adx",
                "label": "Min ADX",
                "value": spec["indicators"]["min_adx"],
                "base": STRATEGY_SPEC["indicators"]["min_adx"],
                "hint": "Trend strength floor",
            },
            {
                "key": "min_reward_risk",
                "label": "Min reward:risk",
                "value": spec["risk"]["min_reward_risk"],
                "base": STRATEGY_SPEC["risk"]["min_reward_risk"],
                "hint": "Target distance vs stop",
            },
            {
                "key": "risk_pct",
                "label": "Risk % of equity",
                "value": spec["risk"]["risk_pct"],
                "base": STRATEGY_SPEC["risk"]["risk_pct"],
                "hint": "Planned size cap",
            },
            {
                "key": "max_age_completed_m5",
                "label": "Max setup age (M5)",
                "value": spec["setup"]["max_age_completed_m5"],
                "base": STRATEGY_SPEC["setup"]["max_age_completed_m5"],
                "hint": "Completed M5 bars after signal",
            },
            {
                "key": "news_before",
                "label": "News block before (min)",
                "value": spec["news_block"]["minutes_before"],
                "base": STRATEGY_SPEC["news_block"]["minutes_before"],
                "hint": "High-impact buffer",
            },
            {
                "key": "news_after",
                "label": "News block after (min)",
                "value": spec["news_block"]["minutes_after"],
                "base": STRATEGY_SPEC["news_block"]["minutes_after"],
                "hint": "High-impact buffer",
            },
        ],
        "gates": gates,
        "verdict": verdict,
        "symbol": (_ea_blob(monitor_status).get("symbol") or monitor_status.get("selected_symbol")),
        "note": (
            "Lab what-if is advisory. Apply to session to affect Analyzer / Scanner / Desk gates "
            "on this backend until reset. Does not change the EA binary."
        ),
    }


def sanitize_lab_overrides(body: dict[str, Any] | None) -> dict[str, Any]:
    raw = body or {}
    out: dict[str, Any] = {}
    mapping = {
        "min_adx": float,
        "min_reward_risk": float,
        "risk_pct": float,
        "max_age_completed_m5": int,
        "news_before": int,
        "news_after": int,
    }
    for key, caster in mapping.items():
        if key not in raw or raw[key] is None or raw[key] == "":
            continue
        try:
            out[key] = caster(raw[key])
        except (TypeError, ValueError):
            continue
    return out
