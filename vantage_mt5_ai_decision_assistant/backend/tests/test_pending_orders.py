"""Pending MT5 order advisory analysis."""
from app.analysis.pending_orders import analyze_pending_order, build_pending_orders_status


def _base_order(**kw):
    o = {
        "ticket": 1001,
        "type": "BUY_LIMIT",
        "volume": 0.10,
        "price_open": 3200.0,
        "price_current": 3300.0,
        "sl": 3180.0,
        "tp": 3350.0,
        "distance_price": 100.0,
        "distance_points": 10000.0,
        "risk_available": True,
        "equity_risk_pct": 0.8,
        "money_at_risk": 80.0,
        "reward_risk_ratio": 2.5,
    }
    o.update(kw)
    return o


def test_empty_list():
    out = build_pending_orders_status(
        {
            "selected_symbol": "XAUUSD",
            "link_health": {"ea_online": True},
            "vantage_ea": {
                "connected": True,
                "symbol": "XAUUSD",
                "bid": 3300.0,
                "ask": 3300.2,
                "pending_orders": {"count": 0, "items": []},
            },
        }
    )
    assert out["advisory_only"] is True
    assert out["count"] == 0
    assert out["items"] == []


def test_missing_sl_suggests_add_sl():
    card = analyze_pending_order(
        _base_order(sl=0.0, risk_available=False),
        bid=3300.0,
        ask=3300.2,
        atr=12.0,
        chart_trend="BULLISH",
        strategy={"h1_bias": "BULLISH", "m15_structure": "BULLISH", "m5_trigger": "BULLISH"},
        max_position_risk_pct=2.0,
    )
    assert "ADD_OR_TIGHTEN_SL" in card["suggestions"]
    assert card["risk"]["missing_sl"] is True


def test_counter_trend_against_h1():
    card = analyze_pending_order(
        _base_order(type="BUY_LIMIT"),
        bid=3300.0,
        ask=3300.2,
        atr=12.0,
        chart_trend="BEARISH",
        strategy={"h1_bias": "BEARISH", "m15_structure": "BEARISH", "m5_trigger": "BEARISH"},
        max_position_risk_pct=2.0,
    )
    assert card["side"] == "BUY"
    assert card["trend"]["label"] == "COUNTER_TREND"
    assert "AGAINST_H1_BIAS" in card["suggestions"]


def test_oversize_risk():
    card = analyze_pending_order(
        _base_order(equity_risk_pct=3.5, money_at_risk=350.0),
        bid=3300.0,
        ask=3300.2,
        atr=12.0,
        chart_trend="BULLISH",
        strategy={"h1_bias": "BULLISH", "m15_structure": "BULLISH", "m5_trigger": "BULLISH"},
        max_position_risk_pct=2.0,
    )
    assert card["risk"]["label"] == "OVERSIZE"
    assert "SIZE_TOO_LARGE" in card["suggestions"]
    assert "CONSIDER_CANCEL" in card["suggestions"]


def test_far_limit_wait_for_fill():
    card = analyze_pending_order(
        _base_order(distance_price=30.0, equity_risk_pct=0.5),
        bid=3300.0,
        ask=3300.2,
        atr=12.0,
        chart_trend="BULLISH",
        strategy={"h1_bias": "BULLISH", "m15_structure": "BULLISH", "m5_trigger": "BULLISH"},
        max_position_risk_pct=2.0,
    )
    assert "WAIT_FOR_FILL" in card["suggestions"]


def test_stale_buy_stop():
    card = analyze_pending_order(
        _base_order(type="BUY_STOP", price_open=3290.0, distance_price=10.0),
        bid=3300.0,
        ask=3300.2,
        atr=12.0,
        chart_trend="BULLISH",
        strategy={"h1_bias": "BULLISH", "m15_structure": "BULLISH", "m5_trigger": "BULLISH"},
        max_position_risk_pct=2.0,
    )
    assert "STALE_OR_INVALID" in card["suggestions"]
    assert card["risk"]["stale_or_invalid"] is True


def test_keep_watch_aligned():
    card = analyze_pending_order(
        _base_order(distance_price=5.0, equity_risk_pct=0.4),
        bid=3300.0,
        ask=3300.2,
        atr=12.0,
        chart_trend="BULLISH",
        strategy={"h1_bias": "BULLISH", "m15_structure": "BULLISH", "m5_trigger": "BULLISH"},
        max_position_risk_pct=2.0,
    )
    assert card["suggestions"] == ["KEEP_WATCH"]
    assert card["trend"]["label"] == "WITH_TREND"


def test_api_pending_orders():
    from fastapi.testclient import TestClient

    from app.main import app
    from app.monitor_state import monitor_store

    monitor_store.record_heartbeat(
        {
            "symbol": "XAUUSD",
            "bid": 3300.0,
            "ask": 3300.2,
            "digits": 2,
            "trend": "BULLISH",
            "pending_orders": {
                "count": 1,
                "items": [_base_order(sl=0.0, risk_available=False)],
            },
            "strategy": {
                "h1_bias": "BULLISH",
                "m15_structure": "BULLISH",
                "m5_trigger": "BULLISH",
                "atr14": 12.0,
            },
        }
    )
    client = TestClient(app)
    r = client.get("/api/v1/orders/pending")
    assert r.status_code == 200
    body = r.json()
    assert body["advisory_only"] is True
    assert body["count"] == 1
    assert "ADD_OR_TIGHTEN_SL" in body["items"][0]["suggestions"]
    page = client.get("/orders")
    assert page.status_code == 200
    assert "Pending Orders" in page.text
