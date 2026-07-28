"""Gold SMC — symbol validator + heartbeat passthrough (Phase 6 sample)."""
from fastapi.testclient import TestClient

from app.analysis.gold_symbol_validator import is_approved_gold_symbol
from app.config import get_settings
from app.main import app
from app.monitor_state import monitor_store


def test_gold_symbol_validator_matrix():
    cases = [
        ("XAUUSD", True),
        ("XAUUSD.a", True),
        ("XAUUSDm", True),
        ("m.XAUUSD", True),
        ("GOLD", True),
        ("GOLD.pro", True),
        ("EURUSD", False),
        ("XAGUSD", False),
        ("XAUEUR", False),
        ("BTCUSD", False),
        ("US30", False),
        ("OIL", False),
        ("GOLDENCOIN", False),
        ("xauusd", True),
        ("Gold.a", True),
    ]
    for sym, expect in cases:
        ok, base = is_approved_gold_symbol(sym)
        assert ok is expect, f"{sym}: expected {expect}, got {ok} base={base}"
        if expect:
            assert base in ("XAUUSD", "GOLD")


SAMPLE_GOLD_SMC = {
    "version": "1.0",
    "engine_phase": 8,
    "advisory_only": True,
    "valid": True,
    "gold_symbol_valid": True,
    "engine_enabled": True,
    "analysis_active": True,
    "symbol": "XAUUSD",
    "base_symbol": "XAUUSD",
    "status_line": "ACTIVE – GOLD ONLY (Phase 8)",
    "disable_reason": "",
    "macro_bias": "Bearish",
    "h4_bias": "Bearish",
    "h1_bias": "Bearish",
    "m15_bias": "Bullish",
    "m5_bias": "Bullish",
    "structure_status": "H4 Ext Bearish | H1 Ext Bearish | M15 Int Bullish | M5 Int Bullish",
    "m5_context": "Bearish retracement — internal bullish correction (M5 does not override H1)",
    "latest_structure_event": "CHoCH Bullish",
    "displacement_status": "Strong displacement (78)",
    "session_name": "London–New York Overlap",
    "liquidity_draw": "Sell-Side",
    "draw_distance_atr": 0.72,
    "nearest_bsl": 4085.0,
    "nearest_ssl": 4050.0,
    "nearest_bsl_label": "PDH",
    "nearest_ssl_label": "PDL",
    "pdh": 4085.0,
    "pdl": 4050.0,
    "sweep_class": "Valid sweep",
    "latest_liquidity_event": "Buy-Side swept (4085.00) — Valid sweep",
    "primary_poi_type": "Fair Value Gap",
    "primary_poi_dir": "Bearish",
    "primary_poi_status": "Fresh",
    "poi_upper": 4086.2,
    "poi_lower": 4082.5,
    "poi_quality": 72.0,
    "poi_mitigation_pct": 0.0,
    "premium_discount": "Premium",
    "dealing_high": 4100.0,
    "dealing_low": 4040.0,
    "dealing_eq": 4070.0,
    "dealing_pct": 72.0,
    "in_discount": False,
    "in_premium": True,
    "ote_enabled": True,
    "ote_low": 4077.0,
    "ote_mid": 4082.0,
    "ote_high": 4087.0,
    "price_in_ote": True,
    "poi_overlaps_ote": True,
    "inducement_status": "Confirmed inducement sweep",
    "po3_status": "Manipulation confirmed",
    "po3_bias": "Bearish",
    "setup_direction": "Bearish",
    "setup_type": "OTE Confluence Setup",
    "setup_candidate": "OTE Confluence Setup",
    "setup_phase": "Price Inside Entry Zone",
    "confidence_score": 78.0,
    "confidence_band": "Strong",
    "quality_grade": "B",
    "score_breakdown": "HTF 100 (H4+H1 aligned); Liq 80 (Valid liquidity sweep); OTE 100 (Price+POI in OTE)",
    "entry_zone": "4082.50-4086.20",
    "entry_low": 4082.5,
    "entry_high": 4086.2,
    "preferred_entry": 4084.0,
    "entry_status": "Inside",
    "zone_source": "Fair Value Gap + OTE",
    "invalidation": "M15 close above 4086.20 (entry-zone / POI extreme)",
    "invalidation_price": 4086.2,
    "target_1": 4050.0,
    "target_2": 4040.0,
    "target_3": 4020.0,
    "targets": "T1 4050.00 | T2 4040.00 | T3 4020.00",
    "estimated_rr": 2.1,
    "recommendation": "WATCH — price inside entry zone (4082.50-4086.20).",
    "technical_narrative": "Gold SMC score 78/100 (B, Strong). Direction: Bearish.",
    "reasons_for": "Approved Gold symbol;HTF alignment;Liquidity event;OTE confluence;",
    "reasons_against": "",
    "last_alert": "Price inside Fair Value Gap + OTE 4082.50-4086.20",
    "last_alert_time": 1753680000,
    "chart_objects_active": True,
}


def test_gold_smc_status_passthrough():
    monitor_store.record_heartbeat(
        {
            "symbol": "XAUUSD",
            "bid": 3325.5,
            "ask": 3325.8,
            "digits": 2,
            "gold_smc": SAMPLE_GOLD_SMC,
        }
    )
    monitor_store.select_symbol("XAUUSD")
    client = TestClient(app)
    body = client.get("/api/v1/gold-smc/status").json()
    assert body["advisory_only"] is True
    assert body["gold_smc_supported"] is True
    assert body["gold_smc"]["gold_symbol_valid"] is True
    assert body["gold_smc"]["engine_phase"] == 8
    assert body["gold_smc"]["analysis_active"] is True
    assert body["gold_smc"]["setup_type"] == "OTE Confluence Setup"
    assert body["gold_smc"]["confidence_score"] == 78.0
    assert body["gold_smc"]["quality_grade"] == "B"
    assert body["gold_smc"]["price_in_ote"] is True
    assert body["gold_smc"]["estimated_rr"] == 2.1
    assert body["gold_smc"]["chart_objects_active"] is True
    assert "Fair Value Gap" in body["gold_smc"]["last_alert"]
    assert "does not override" in body["gold_smc"]["m5_context"]
    assert "gold_smc" in body["links"]


def test_gold_smc_disabled_blob():
    monitor_store.record_heartbeat(
        {
            "symbol": "BTCUSD",
            "bid": 70000.0,
            "ask": 70010.0,
            "digits": 2,
            "gold_smc": {
                **SAMPLE_GOLD_SMC,
                "symbol": "BTCUSD",
                "base_symbol": "",
                "gold_symbol_valid": False,
                "status_line": "DISABLED — GOLD ONLY",
                "disable_reason": (
                    "Gold SMC Intelligence Engine is disabled. "
                    "This module supports XAUUSD/Gold only."
                ),
            },
        }
    )
    monitor_store.select_symbol("BTCUSD")
    body = TestClient(app).get("/api/v1/gold-smc/status").json()
    assert body["gold_smc"]["gold_symbol_valid"] is False
    assert "XAUUSD/Gold only" in body["gold_smc"]["disable_reason"]


def test_gold_smc_page_and_heartbeat_field():
    token = get_settings().local_api_token
    client = TestClient(app)
    page = client.get("/gold-smc")
    assert page.status_code == 200
    assert "Gold SMC Intelligence" in page.text
    assert 'id="symbolSelect"' in page.text

    r = client.post(
        "/api/v1/heartbeat",
        json={"symbol": "XAUUSD", "bid": 1.0, "ask": 1.1, "digits": 2, "gold_smc": SAMPLE_GOLD_SMC},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    monitor_store.select_symbol("XAUUSD")
    st = client.get("/api/v1/gold-smc/status").json()
    assert st["gold_smc_supported"] is True
