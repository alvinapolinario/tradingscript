"""
Advisory analysis for MT5 pending orders.

Never cancels or modifies orders — suggestions only.
"""
from __future__ import annotations

from typing import Any

from app.config import get_settings


_BUY_TYPES = {"BUY_LIMIT", "BUY_STOP", "BUY_STOP_LIMIT"}
_SELL_TYPES = {"SELL_LIMIT", "SELL_STOP", "SELL_STOP_LIMIT"}
_LIMIT_TYPES = {"BUY_LIMIT", "SELL_LIMIT"}


def _f(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _side_from_type(order_type: str) -> str:
    t = (order_type or "").upper()
    if t in _BUY_TYPES:
        return "BUY"
    if t in _SELL_TYPES:
        return "SELL"
    return ""


def _is_stale(order_type: str, price_open: float, bid: float, ask: float) -> bool:
    """True when a stop/limit has already been traded through relative to bid/ask."""
    t = (order_type or "").upper()
    if price_open <= 0 or bid <= 0 or ask <= 0:
        return False
    if t == "BUY_STOP" or t == "BUY_STOP_LIMIT":
        return price_open <= ask
    if t == "SELL_STOP" or t == "SELL_STOP_LIMIT":
        return price_open >= bid
    if t == "BUY_LIMIT":
        return price_open >= ask
    if t == "SELL_LIMIT":
        return price_open <= bid
    return False


def _trend_alignment(
    side: str,
    chart_trend: str,
    h1: str,
    m15: str,
    m5: str,
) -> dict[str, Any]:
    want = "BULLISH" if side == "BUY" else ("BEARISH" if side == "SELL" else "")
    biases = [
        ("chart", (chart_trend or "").upper()),
        ("h1", (h1 or "").upper()),
        ("m15", (m15 or "").upper()),
        ("m5", (m5 or "").upper()),
    ]
    aligned = 0
    opposed = 0
    details: list[dict[str, str]] = []
    for name, b in biases:
        if not want or not b or b == "NEUTRAL":
            details.append({"tf": name, "bias": b or "—", "vs": "neutral"})
            continue
        if b == want:
            aligned += 1
            details.append({"tf": name, "bias": b, "vs": "with"})
        else:
            opposed += 1
            details.append({"tf": name, "bias": b, "vs": "against"})

    if not want:
        label = "MIXED"
    elif opposed == 0 and aligned >= 2:
        label = "WITH_TREND"
    elif opposed >= 2 and aligned == 0:
        label = "COUNTER_TREND"
    elif opposed > aligned:
        label = "COUNTER_TREND"
    elif aligned > opposed:
        label = "WITH_TREND"
    else:
        label = "MIXED"

    return {
        "label": label,
        "aligned": aligned,
        "opposed": opposed,
        "want": want,
        "details": details,
    }


def _risk_label(equity_pct: float | None, available: bool, max_pct: float) -> str:
    if not available or equity_pct is None:
        return "UNKNOWN"
    pct = float(equity_pct)
    if pct >= max_pct:
        return "OVERSIZE"
    if pct >= max_pct * 0.75:
        return "HIGH"
    if pct >= max_pct * 0.4:
        return "MODERATE"
    return "LOW"


def analyze_pending_order(
    raw: dict[str, Any],
    *,
    bid: float,
    ask: float,
    atr: float | None,
    chart_trend: str,
    strategy: dict[str, Any],
    max_position_risk_pct: float,
    open_buy_volume: float = 0.0,
    open_sell_volume: float = 0.0,
) -> dict[str, Any]:
    order_type = str(raw.get("type") or "").upper()
    side = _side_from_type(order_type)
    price_open = _f(raw.get("price_open"))
    sl = _f(raw.get("sl"))
    tp = _f(raw.get("tp"))
    volume = _f(raw.get("volume"))
    dist_price = _f(raw.get("distance_price"))
    dist_pts = _f(raw.get("distance_points"))
    risk_available = bool(raw.get("risk_available"))
    equity_pct = _f(raw.get("equity_risk_pct")) if risk_available else None
    money = _f(raw.get("money_at_risk")) if risk_available else None
    rr = _f(raw.get("reward_risk_ratio")) if risk_available else None

    mid = (bid + ask) / 2.0 if bid > 0 and ask > 0 else bid or ask
    if dist_price <= 0 and price_open > 0 and mid > 0:
        dist_price = abs(price_open - mid)

    h1 = str(strategy.get("h1_bias") or "")
    m15 = str(strategy.get("m15_structure") or "")
    m5 = str(strategy.get("m5_trigger") or "")
    adx = strategy.get("adx14")
    ema_ok = strategy.get("ema_stack_ok")

    trend = _trend_alignment(side, chart_trend, h1, m15, m5)
    stale = _is_stale(order_type, price_open, bid, ask)
    missing_sl = sl <= 0

    far_limit = False
    if atr and atr > 0 and order_type in _LIMIT_TYPES and dist_price > 1.5 * atr:
        far_limit = True

    stacked_same_side = False
    if side == "BUY" and open_buy_volume > 0:
        stacked_same_side = True
    if side == "SELL" and open_sell_volume > 0:
        stacked_same_side = True

    suggestions: list[str] = []
    if missing_sl:
        suggestions.append("ADD_OR_TIGHTEN_SL")
    if stale:
        suggestions.append("STALE_OR_INVALID")
    if risk_available and equity_pct is not None and equity_pct >= max_position_risk_pct:
        suggestions.append("SIZE_TOO_LARGE")
        suggestions.append("CONSIDER_CANCEL")
    h1u = (h1 or "").upper()
    against_h1 = bool(
        side
        and h1u in {"BULLISH", "BEARISH"}
        and ((side == "BUY" and h1u == "BEARISH") or (side == "SELL" and h1u == "BULLISH"))
    )
    if against_h1:
        suggestions.append("AGAINST_H1_BIAS")
        if far_limit or trend["opposed"] >= 2:
            suggestions.append("CONSIDER_CANCEL")
    elif trend["label"] == "COUNTER_TREND":
        suggestions.append("AGAINST_TREND")
    if far_limit and "CONSIDER_CANCEL" not in suggestions:
        suggestions.append("WAIT_FOR_FILL")
    if stacked_same_side and "SIZE_TOO_LARGE" not in suggestions:
        suggestions.append("STACKED_WITH_OPEN_POSITION")
    if not suggestions:
        suggestions.append("KEEP_WATCH")

    # Cap to 3, keep highest priority first
    priority = [
        "STALE_OR_INVALID",
        "ADD_OR_TIGHTEN_SL",
        "SIZE_TOO_LARGE",
        "CONSIDER_CANCEL",
        "AGAINST_H1_BIAS",
        "AGAINST_TREND",
        "STACKED_WITH_OPEN_POSITION",
        "WAIT_FOR_FILL",
        "KEEP_WATCH",
    ]
    ordered = [s for s in priority if s in suggestions][:3]

    risk_block = {
        "label": _risk_label(equity_pct, risk_available and not missing_sl, max_position_risk_pct),
        "missing_sl": missing_sl,
        "risk_available": risk_available and not missing_sl,
        "equity_risk_pct": equity_pct,
        "money_at_risk": money,
        "reward_risk_ratio": rr if rr and rr > 0 else None,
        "distance_price": dist_price,
        "distance_points": dist_pts,
        "stale_or_invalid": stale,
        "stacked_with_open": stacked_same_side,
        "max_position_risk_pct": max_position_risk_pct,
    }

    return {
        "ticket": int(raw.get("ticket") or 0),
        "type": order_type,
        "side": side,
        "volume": volume,
        "price_open": price_open,
        "sl": sl if sl > 0 else None,
        "tp": tp if tp > 0 else None,
        "time_setup": raw.get("time_setup") or "",
        "comment": raw.get("comment") or "",
        "magic": int(raw.get("magic") or 0),
        "suggestions": ordered,
        "risk": risk_block,
        "trend": {
            **trend,
            "adx14": _f(adx) if adx is not None else None,
            "ema_stack_ok": bool(ema_ok) if ema_ok is not None else None,
            "chart_trend": (chart_trend or "").upper() or None,
        },
        "advisory_only": True,
    }


def build_pending_orders_status(monitor_status: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    ea = monitor_status.get("vantage_ea") or {}
    link = monitor_status.get("link_health") or {}
    strategy = ea.get("strategy") or {}
    raw_po = ea.get("pending_orders") or {}
    items_raw = raw_po.get("items") if isinstance(raw_po, dict) else []
    if not isinstance(items_raw, list):
        items_raw = []

    bid = _f(ea.get("bid"))
    ask = _f(ea.get("ask"))
    atr = strategy.get("atr14")
    try:
        atr_f = float(atr) if atr is not None else None
    except (TypeError, ValueError):
        atr_f = None

    max_risk = ea.get("max_position_risk_pct")
    if max_risk is None:
        max_risk = settings.max_position_risk_pct
    try:
        max_risk_f = float(max_risk)
    except (TypeError, ValueError):
        max_risk_f = float(settings.max_position_risk_pct)

    open_buy = _f(ea.get("total_buy_volume"))
    open_sell = _f(ea.get("total_sell_volume"))
    pos_count = int(ea.get("position_count") or 0)

    analyzed = [
        analyze_pending_order(
            item if isinstance(item, dict) else {},
            bid=bid,
            ask=ask,
            atr=atr_f,
            chart_trend=str(ea.get("trend") or ""),
            strategy=strategy if isinstance(strategy, dict) else {},
            max_position_risk_pct=max_risk_f,
            open_buy_volume=open_buy,
            open_sell_volume=open_sell,
        )
        for item in items_raw
    ]

    with_trend = sum(1 for a in analyzed if a["trend"]["label"] == "WITH_TREND")
    counter = sum(1 for a in analyzed if a["trend"]["label"] == "COUNTER_TREND")
    missing_sl_n = sum(1 for a in analyzed if a["risk"]["missing_sl"])
    oversize_n = sum(1 for a in analyzed if a["risk"]["label"] == "OVERSIZE")

    ea_online = bool(link.get("ea_online") or ea.get("connected"))
    symbol = str(ea.get("symbol") or monitor_status.get("selected_symbol") or "").upper()

    return {
        "advisory_only": True,
        "caption": "Advisory only — never places, modifies, or cancels MT5 pending orders.",
        "ea_online": ea_online,
        "symbol": symbol,
        "bid": bid,
        "ask": ask,
        "digits": int(ea.get("digits") or 5) or 5,
        "open_position_count": pos_count,
        "count": len(analyzed),
        "items": analyzed,
        "summary": {
            "with_trend": with_trend,
            "counter_trend": counter,
            "missing_sl": missing_sl_n,
            "oversize": oversize_n,
        },
        "links": {
            "orders": "/orders",
            "monitor": "/monitor",
            "analyzer": "/analyzer",
        },
    }
