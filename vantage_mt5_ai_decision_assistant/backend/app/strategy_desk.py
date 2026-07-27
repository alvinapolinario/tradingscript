"""
M5 Alignment Desk — separate strategy playbook for the multi-TF dashboard.

Analysis M5 · Structure M15 · Bias H1.
Advisory-only; does not execute trades.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Optional


# Fixed playbook (source of truth for /dashboard)
STRATEGY_SPEC: dict[str, Any] = {
    "id": "m5_alignment_desk",
    "name": "M5 Alignment Desk",
    "version": "1.0.0",
    "advisory_only": True,
    "timeframes": {
        "analysis": "M5",
        "structure": "M15",
        "bias": "H1",
    },
    "indicators": {
        "ema_fast": 20,
        "ema_medium": 50,
        "ema_trend": 200,
        "atr_period": 14,
        "adx_period": 14,
        "min_adx": 20.0,
    },
    "risk": {
        "min_reward_risk": 2.0,
        "risk_pct": 0.50,
        "max_spread": "pair_specific",
    },
    "news_block": {
        "high_impact_only": True,
        "minutes_before": 30,
        "minutes_after": 15,
    },
    "setup": {
        "max_age_completed_m5": 3,
        "confirmation": "candle_close_required",
        "allowed_direction": "only_with_h1_and_m15_alignment",
    },
    # Desk defaults when EA does not report a pair limit (points)
    "max_spread_points_by_symbol": {
        "XAUUSD": 50,
        "GOLD": 50,
        "BTCUSD": 1500,
        "BITCOIN": 1500,
    },
}


def _sym_key(symbol: str) -> str:
    s = (symbol or "").upper().replace(".", "").replace("#", "")
    for key in STRATEGY_SPEC["max_spread_points_by_symbol"]:
        if key in s or s.endswith(key) or s.startswith(key):
            return key
    return s


def playbook_spec(monitor_status: dict[str, Any] | None = None) -> dict[str, Any]:
    """Base STRATEGY_SPEC merged with optional session lab_overrides."""
    spec = deepcopy(STRATEGY_SPEC)
    ov = (monitor_status or {}).get("lab_overrides") or {}
    try:
        if ov.get("min_adx") is not None:
            spec["indicators"]["min_adx"] = float(ov["min_adx"])
        if ov.get("min_reward_risk") is not None:
            spec["risk"]["min_reward_risk"] = float(ov["min_reward_risk"])
        if ov.get("risk_pct") is not None:
            spec["risk"]["risk_pct"] = float(ov["risk_pct"])
        if ov.get("max_age_completed_m5") is not None:
            spec["setup"]["max_age_completed_m5"] = int(ov["max_age_completed_m5"])
        if ov.get("news_before") is not None:
            spec["news_block"]["minutes_before"] = int(ov["news_before"])
        if ov.get("news_after") is not None:
            spec["news_block"]["minutes_after"] = int(ov["news_after"])
    except (TypeError, ValueError):
        pass
    return spec


def max_spread_for_symbol(symbol: str) -> Optional[int]:
    table = STRATEGY_SPEC["max_spread_points_by_symbol"]
    key = _sym_key(symbol)
    if key in table:
        return int(table[key])
    # fallback fuzzy
    for k, v in table.items():
        if k in key:
            return int(v)
    return None


def _gate(
    key: str,
    label: str,
    status: str,
    detail: str,
    required: bool = True,
) -> dict[str, Any]:
    """status: pass | fail | unknown | warn"""
    return {
        "key": key,
        "label": label,
        "status": status,
        "detail": detail,
        "required": required,
    }


def _extra_strategy(ea: dict[str, Any]) -> dict[str, Any]:
    """Optional EA fields under strategy / m5_desk / extra."""
    for k in ("strategy", "m5_desk", "alignment_desk"):
        v = ea.get(k)
        if isinstance(v, dict):
            return v
    extra = ea.get("extra")
    if isinstance(extra, dict):
        for k in ("strategy", "m5_desk", "alignment_desk"):
            v = extra.get(k)
            if isinstance(v, dict):
                return v
    return {}


def _ea_blob(monitor_status: dict[str, Any]) -> dict[str, Any]:
    """Normalize monitor_store.status() → EA snapshot dict."""
    ea = monitor_status.get("vantage_ea") or monitor_status.get("ea") or {}
    return ea if isinstance(ea, dict) else {}


def _ea_is_connected(monitor_status: dict[str, Any], ea: dict[str, Any]) -> bool:
    link = monitor_status.get("link_health") or {}
    if isinstance(link, dict) and "ea_online" in link:
        return bool(link.get("ea_online"))
    if "ea_connected" in monitor_status:
        return bool(monitor_status.get("ea_connected"))
    if "connected" in ea:
        return bool(ea.get("connected"))
    return False


def _seconds_since_heartbeat(monitor_status: dict[str, Any], ea: dict[str, Any]) -> Any:
    if monitor_status.get("seconds_since_heartbeat") is not None:
        return monitor_status.get("seconds_since_heartbeat")
    if ea.get("seconds_since_seen") is not None:
        return ea.get("seconds_since_seen")
    link = monitor_status.get("link_health") or {}
    return link.get("seconds_since_heartbeat") if isinstance(link, dict) else None


def evaluate_gates(monitor_status: dict[str, Any]) -> list[dict[str, Any]]:
    ea = _ea_blob(monitor_status)
    connected = _ea_is_connected(monitor_status, ea)
    st = _extra_strategy(ea)
    spec = playbook_spec(monitor_status)
    symbol = str(ea.get("symbol") or monitor_status.get("selected_symbol") or "")
    spread = int(ea.get("spread_points") or 0)
    high_spread = bool(ea.get("high_spread"))
    max_spread = st.get("max_spread_points")
    if max_spread is None:
        max_spread = max_spread_for_symbol(symbol)

    gates: list[dict[str, Any]] = []
    min_adx = float(spec["indicators"]["min_adx"])
    min_rr = float(spec["risk"]["min_reward_risk"])
    risk_pct = float(spec["risk"]["risk_pct"])
    adx_label = f"ADX ≥ {min_adx:.0f}"
    rr_label = f"Reward:risk ≥ {min_rr:.1f}"
    risk_label = f"Risk ≤ {risk_pct:.2f}%"

    # 1) Live feed
    if not connected:
        gates.append(_gate("ea_feed", "EA feed", "fail", "Waiting for EA heartbeat on selected pair"))
    else:
        gates.append(_gate("ea_feed", "EA feed", "pass", f"Live · {symbol or '—'}"))

    # 2) H1 + M15 alignment
    h1 = st.get("h1_bias") or st.get("bias_h1")
    m15 = st.get("m15_structure") or st.get("structure_m15")
    aligned = st.get("h1_m15_aligned")
    if aligned is None and h1 and m15:
        aligned = str(h1).upper() == str(m15).upper() and str(h1).upper() in {"BULLISH", "BEARISH", "BUY", "SELL"}
    if aligned is True:
        gates.append(
            _gate(
                "alignment",
                "H1 + M15 alignment",
                "pass",
                f"Aligned · H1={h1 or '—'} · M15={m15 or '—'}",
            )
        )
    elif aligned is False:
        gates.append(
            _gate(
                "alignment",
                "H1 + M15 alignment",
                "fail",
                f"Not aligned · H1={h1 or '—'} · M15={m15 or '—'} · direction blocked",
            )
        )
    else:
        gates.append(
            _gate(
                "alignment",
                "H1 + M15 alignment",
                "unknown",
                "Requires strategy feed (H1 bias + M15 structure). Direction only when both agree.",
            )
        )

    # 3) ADX
    adx = st.get("adx14")
    if adx is None:
        gates.append(_gate("adx", adx_label, "unknown", f"ADX({spec['indicators']['adx_period']}) pending strategy feed"))
    else:
        try:
            adx_f = float(adx)
            ok = adx_f >= min_adx
            gates.append(
                _gate(
                    "adx",
                    adx_label,
                    "pass" if ok else "fail",
                    f"ADX={adx_f:.1f} (min {min_adx:.0f})",
                )
            )
        except (TypeError, ValueError):
            gates.append(_gate("adx", adx_label, "unknown", "Invalid ADX value"))

    # 4) R:R
    rr = st.get("reward_risk_ratio")
    if rr is None:
        rr = (ea.get("risk") or {}).get("reward_risk_ratio") if isinstance(ea.get("risk"), dict) else None
    # sometimes flat on decision
    if rr is None:
        rr = ea.get("reward_risk_ratio")
    if rr is None:
        gates.append(_gate("rr", rr_label, "unknown", f"Min R:R {min_rr:.1f} · awaiting setup levels"))
    else:
        try:
            rr_f = float(rr)
            ok = rr_f >= min_rr
            gates.append(
                _gate(
                    "rr",
                    rr_label,
                    "pass" if ok else "fail",
                    f"R:R={rr_f:.2f} (min {min_rr:.1f})",
                )
            )
        except (TypeError, ValueError):
            gates.append(_gate("rr", rr_label, "unknown", "Invalid R:R"))

    # 5) Risk % — prefer desk planned size, then open-position equity risk
    equity_risk = st.get("planned_equity_risk_pct")
    if equity_risk is None:
        equity_risk = ea.get("equity_risk_pct")
    if equity_risk is None:
        gates.append(
            _gate(
                "risk_pct",
                risk_label,
                "warn",
                f"Playbook risk {risk_pct:.2f}% of equity · size manually to this cap",
            )
        )
    else:
        try:
            er = float(equity_risk)
            if er <= 0.0 and st.get("planned_equity_risk_pct") is None:
                gates.append(
                    _gate(
                        "risk_pct",
                        risk_label,
                        "warn",
                        f"Playbook risk {risk_pct:.2f}% of equity · size manually to this cap",
                    )
                )
            else:
                # planned 0.50 from desk, or open risk under cap
                ok = er <= risk_pct + 0.05
                gates.append(
                    _gate(
                        "risk_pct",
                        risk_label,
                        "pass" if ok else "fail",
                        f"Equity risk {er:.2f}% (cap {risk_pct:.2f}%)",
                    )
                )
        except (TypeError, ValueError):
            gates.append(_gate("risk_pct", risk_label, "warn", f"Cap {risk_pct:.2f}%"))

    # 6) Spread
    if max_spread is None:
        if high_spread:
            gates.append(_gate("spread", "Max spread (pair)", "fail", f"{spread} pts · EA flagged HIGH_SPREAD"))
        elif connected:
            gates.append(
                _gate(
                    "spread",
                    "Max spread (pair)",
                    "warn",
                    f"{spread} pts · pair limit not mapped — use EA InpMaxSpreadPoints",
                )
            )
        else:
            gates.append(_gate("spread", "Max spread (pair)", "unknown", "Pair-specific limit"))
    else:
        ok = (not high_spread) and spread <= int(max_spread)
        gates.append(
            _gate(
                "spread",
                "Max spread (pair)",
                "pass" if ok else "fail",
                f"{spread} pts · limit {max_spread} ({_sym_key(symbol) or 'pair'})",
            )
        )

    # 7) News block
    news_blocked = st.get("news_blocked")
    mins_to = st.get("minutes_to_high_impact")
    news_available = st.get("news_available")
    if news_available is False:
        gates.append(
            _gate(
                "news",
                "High-impact news window",
                "warn",
                f"Broker calendar unavailable — check manually · "
                f"{spec['news_block']['minutes_before']}m before / "
                f"{spec['news_block']['minutes_after']}m after",
            )
        )
    elif news_blocked is True:
        gates.append(
            _gate(
                "news",
                "High-impact news window",
                "fail",
                f"Blocked · {spec['news_block']['minutes_before']}m before / "
                f"{spec['news_block']['minutes_after']}m after",
            )
        )
    elif news_blocked is False:
        detail = "Clear of high-impact window"
        if mins_to is not None and int(mins_to) >= 0:
            detail += f" · next in ~{mins_to}m"
        gates.append(_gate("news", "High-impact news window", "pass", detail))
    else:
        gates.append(
            _gate(
                "news",
                "High-impact news window",
                "unknown",
                f"Block {spec['news_block']['minutes_before']}m before / "
                f"{spec['news_block']['minutes_after']}m after high-impact · check calendar manually",
            )
        )

    # 8) Setup age
    age = st.get("setup_age_m5")
    max_age = int(spec["setup"]["max_age_completed_m5"])
    aligned = st.get("h1_m15_aligned")
    if age is None:
        gates.append(
            _gate(
                "setup_age",
                "Setup age ≤ 3 M5",
                "unknown",
                f"Max {max_age} completed M5 candles after signal",
            )
        )
    elif aligned is not True:
        gates.append(
            _gate(
                "setup_age",
                "Setup age ≤ 3 M5",
                "pass",
                "No active aligned setup",
            )
        )
    else:
        try:
            age_i = int(age)
            ok = age_i <= max_age
            gates.append(
                _gate(
                    "setup_age",
                    "Setup age ≤ 3 M5",
                    "pass" if ok else "fail",
                    f"Age={age_i} completed M5 (max {max_age})",
                )
            )
        except (TypeError, ValueError):
            gates.append(_gate("setup_age", "Setup age ≤ 3 M5", "unknown", f"Max {max_age}"))

    # 9) Candle close confirmation
    close_ok = st.get("m5_closed_confirmed")
    if close_ok is None:
        candle_status = str(ea.get("candle_status") or "")
        if "CLOSED" in candle_status.upper() or "CONFIRMED" in candle_status.upper():
            # Existing EA reports M30 close — mark warn that desk needs M5 close
            gates.append(
                _gate(
                    "close_confirm",
                    "M5 candle close",
                    "warn",
                    f"EA candle={candle_status or '—'} · desk requires completed M5 close",
                )
            )
        else:
            gates.append(
                _gate(
                    "close_confirm",
                    "M5 candle close",
                    "unknown",
                    "Confirmation requires completed M5 candle close",
                )
            )
    elif close_ok:
        gates.append(_gate("close_confirm", "M5 candle close", "pass", "M5 close confirmed"))
    else:
        gates.append(_gate("close_confirm", "M5 candle close", "fail", "Wait for M5 candle close"))

    # 10) EMA stack (optional informational)
    ema_ok = st.get("ema_stack_ok")
    if ema_ok is True:
        gates.append(
            _gate(
                "ema",
                "EMA 20 / 50 / 200",
                "pass",
                "Stack agrees with allowed direction",
                required=False,
            )
        )
    elif ema_ok is False:
        gates.append(
            _gate(
                "ema",
                "EMA 20 / 50 / 200",
                "fail",
                "EMA stack disagrees with direction",
                required=False,
            )
        )
    else:
        gates.append(
            _gate(
                "ema",
                "EMA 20 / 50 / 200",
                "unknown",
                "Fast 20 · Medium 50 · Trend 200 on analysis TF",
                required=False,
            )
        )

    return gates


def summarize_verdict(gates: list[dict[str, Any]]) -> dict[str, Any]:
    required = [g for g in gates if g.get("required", True)]
    fails = [g for g in required if g["status"] == "fail"]
    unknowns = [g for g in required if g["status"] == "unknown"]
    warns = [g for g in required if g["status"] == "warn"]

    if fails:
        fail_keys = [g["key"] for g in fails]
        # Offline EA alone is "waiting", not a failed setup
        if fail_keys == ["ea_feed"]:
            return {
                "verdict": "AWAITING_FEED",
                "tone": "warn",
                "headline": "Playbook active — waiting for EA on selected pair",
                "blocked_by": fail_keys,
            }
        return {
            "verdict": "NO_TRADE",
            "tone": "bad",
            "headline": "Stand aside — required gate failed",
            "blocked_by": fail_keys,
        }
    if unknowns:
        return {
            "verdict": "AWAITING_FEED",
            "tone": "warn",
            "headline": "Playbook active — waiting for M5 strategy feed",
            "blocked_by": [g["key"] for g in unknowns],
        }
    if warns:
        return {
            "verdict": "CHECK_MANUAL",
            "tone": "warn",
            "headline": "Gates soft-pass — confirm remaining warnings",
            "blocked_by": [g["key"] for g in warns],
        }
    return {
        "verdict": "SETUP_OK",
        "tone": "ok",
        "headline": "All required gates passed — advisory setup OK",
        "blocked_by": [],
    }


def build_dashboard(monitor_status: dict[str, Any]) -> dict[str, Any]:
    ea = _ea_blob(monitor_status)
    connected = _ea_is_connected(monitor_status, ea)
    gates = evaluate_gates(monitor_status)
    verdict = summarize_verdict(gates)
    symbol = str(ea.get("symbol") or monitor_status.get("selected_symbol") or "")
    st = _extra_strategy(ea)
    link = monitor_status.get("link_health") or {}
    overall = link.get("overall") if isinstance(link, dict) else monitor_status.get("overall")

    return {
        "spec": STRATEGY_SPEC,
        "verdict": verdict,
        "gates": gates,
        "market": {
            "symbol": symbol,
            "bid": ea.get("bid"),
            "ask": ea.get("ask"),
            "spread_points": ea.get("spread_points"),
            "max_spread_points": st.get("max_spread_points") or max_spread_for_symbol(symbol),
            "trend": ea.get("trend"),
            "market_state": ea.get("market_state"),
            "new_entry_decision": ea.get("new_entry_decision"),
            "existing_position_decision": ea.get("existing_position_decision"),
            "risk_status": ea.get("risk_status"),
            "equity_risk_pct": ea.get("equity_risk_pct"),
            "h1_bias": st.get("h1_bias") or st.get("bias_h1"),
            "m15_structure": st.get("m15_structure") or st.get("structure_m15"),
            "m5_trigger": st.get("m5_trigger") or st.get("analysis_m5"),
            "adx14": st.get("adx14"),
            "atr14": st.get("atr14") or st.get("atr"),
            "setup_age_m5": st.get("setup_age_m5"),
            "reward_risk_ratio": st.get("reward_risk_ratio") or ea.get("reward_risk_ratio"),
        },
        "connection": {
            "ea_connected": connected,
            "overall": overall,
            "selected_symbol": monitor_status.get("selected_symbol"),
            "available_symbols": monitor_status.get("available_symbols") or [],
            "seconds_since_heartbeat": _seconds_since_heartbeat(monitor_status, ea),
        },
        "links": {
            "m30_cockpit": "/monitor",
            "dashboard": "/dashboard",
        },
        "note": (
            "This desk is separate from the M30 advisory cockpit. "
            "Multi-TF gates light up when the EA posts strategy={...} on heartbeat; "
            "until then the playbook and pair feed still display."
        ),
    }
