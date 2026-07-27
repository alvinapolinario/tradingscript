"""M5 Alignment Desk gate evaluation."""
from app.strategy_desk import build_dashboard, evaluate_gates, summarize_verdict


def _status(strategy=None, connected=True, spread=20, high_spread=False, symbol="XAUUSD"):
    # Shape matches monitor_store.status() (vantage_ea + link_health)
    return {
        "selected_symbol": symbol,
        "available_symbols": ["XAUUSD", "BTCUSD"],
        "link_health": {
            "api_online": True,
            "ea_online": connected,
            "any_ea_online": connected,
            "overall": "CONNECTED" if connected else "WAITING_FOR_EA",
        },
        "vantage_ea": {
            "connected": connected,
            "seconds_since_seen": 5 if connected else None,
            "symbol": symbol,
            "spread_points": spread,
            "high_spread": high_spread,
            "bid": 3300.0,
            "ask": 3300.2,
            "strategy": strategy,
        },
    }


def test_reads_monitor_store_shape():
    d = build_dashboard(_status(connected=True, symbol="AUDUSD"))
    assert d["connection"]["ea_connected"] is True
    assert d["market"]["symbol"] == "AUDUSD"
    assert {g["key"]: g["status"] for g in d["gates"]}["ea_feed"] == "pass"


def test_offline_ea_awaiting():
    d = build_dashboard(_status(connected=False))
    assert d["verdict"]["verdict"] == "AWAITING_FEED"


def test_full_strategy_pass():
    strategy = {
        "h1_bias": "BEARISH",
        "m15_structure": "BEARISH",
        "h1_m15_aligned": True,
        "adx14": 24.0,
        "reward_risk_ratio": 2.0,
        "planned_equity_risk_pct": 0.50,
        "max_spread_points": 50,
        "news_available": True,
        "news_blocked": False,
        "minutes_to_high_impact": 120,
        "setup_age_m5": 1,
        "m5_closed_confirmed": True,
        "ema_stack_ok": True,
        "m5_trigger": "BEARISH",
    }
    gates = evaluate_gates(_status(strategy=strategy))
    by_key = {g["key"]: g for g in gates}
    assert by_key["ea_feed"]["status"] == "pass"
    assert by_key["alignment"]["status"] == "pass"
    assert by_key["adx"]["status"] == "pass"
    assert by_key["rr"]["status"] == "pass"
    assert by_key["risk_pct"]["status"] == "pass"
    assert by_key["spread"]["status"] == "pass"
    assert by_key["news"]["status"] == "pass"
    assert by_key["setup_age"]["status"] == "pass"
    assert by_key["close_confirm"]["status"] == "pass"
    v = summarize_verdict(gates)
    assert v["verdict"] == "SETUP_OK"


def test_misaligned_blocks():
    strategy = {
        "h1_bias": "BULLISH",
        "m15_structure": "BEARISH",
        "h1_m15_aligned": False,
        "adx14": 30.0,
        "reward_risk_ratio": 2.5,
        "planned_equity_risk_pct": 0.5,
        "max_spread_points": 50,
        "news_available": True,
        "news_blocked": False,
        "setup_age_m5": 0,
        "m5_closed_confirmed": True,
        "ema_stack_ok": False,
    }
    gates = evaluate_gates(_status(strategy=strategy))
    by_key = {g["key"]: g for g in gates}
    assert by_key["alignment"]["status"] == "fail"
    assert by_key["setup_age"]["status"] == "pass"
    assert summarize_verdict(gates)["verdict"] == "NO_TRADE"
