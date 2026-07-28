"""Gold SMC Phase 8 — scenario catalog, logic helpers, API passthrough."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.analysis.gold_smc_logic import (
    SCENARIOS,
    build_scenario_blob,
    confidence_band,
    entry_status,
    gate_setup_type,
    grade_from_score,
    ote_zone,
    overlaps,
    premium_discount_label,
    scenario_passes,
)
from app.analysis.gold_symbol_validator import is_approved_gold_symbol
from app.main import app
from app.monitor_state import monitor_store


def test_scenario_catalog_has_forty():
    assert len(SCENARIOS) == 40
    ids = [s.id for s in SCENARIOS]
    assert ids == list(range(1, 41))


def test_all_scenarios_self_consistent():
    failures = []
    for s in SCENARIOS:
        blob = build_scenario_blob(s)
        fails = scenario_passes(s, blob)
        if fails:
            failures.append(f"#{s.id} {s.name}: {fails}")
    assert not failures, "\n".join(failures)


def test_symbol_scenarios_1_to_5():
    for s in SCENARIOS[:5]:
        assert s.symbol and s.gold_ok is not None
        ok, _ = is_approved_gold_symbol(s.symbol)
        assert ok is s.gold_ok, s.name


def test_premium_discount_and_ote_helpers():
    label, pct, disc, prem = premium_discount_label(4045.0, 4100.0, 4040.0)
    assert label == "Deep Discount" and disc and not prem and pct < 20

    label, pct, disc, prem = premium_discount_label(4095.0, 4100.0, 4040.0)
    assert label == "Deep Premium" and prem

    label, _, disc, prem = premium_discount_label(4070.0, 4100.0, 4040.0)
    assert label == "Equilibrium" and not disc and not prem

    lo, mid, hi = ote_zone("Bearish", 4100.0, 4040.0)
    assert lo < mid < hi
    assert lo > 4040.0 and hi < 4100.0
    # Bullish OTE is discount-side retracement from high
    blo, bmid, bhi = ote_zone("Bullish", 4100.0, 4040.0)
    assert blo < bmid < bhi
    assert bhi < 4100.0


def test_grade_band_and_gate():
    assert grade_from_score(92) == "A+"
    assert grade_from_score(81) == "A"
    assert grade_from_score(72) == "B"
    assert grade_from_score(61) == "C"
    assert grade_from_score(50) == "D"
    assert grade_from_score(40) == "Invalid"
    assert confidence_band(20) == "No Valid Setup"
    assert confidence_band(78) == "Strong"
    assert gate_setup_type(78, "OTE Confluence Setup") == "OTE Confluence Setup"
    assert gate_setup_type(40, "OTE Confluence Setup") == "No Valid SMC Setup"
    assert gate_setup_type(80, "Context Forming Watch") == "No Valid SMC Setup"


def test_ote_poi_overlap_and_entry_status():
    assert overlaps(4082, 4086, 4077, 4087) is True
    assert overlaps(4000, 4010, 4020, 4030) is False
    assert entry_status(4084, 4082, 4086, 2.0) == "Inside"
    assert entry_status(4088, 4082, 4086, 5.0) == "Approaching"
    assert entry_status(4200, 4082, 4086, 2.0) == "Far"


def test_scenario_api_passthrough_sample():
    """Heartbeat a few high-value scenarios through /gold-smc/status."""
    client = TestClient(app)
    for sid in (1, 9, 29, 37, 38, 40):
        s = next(x for x in SCENARIOS if x.id == sid)
        blob = build_scenario_blob(s)
        monitor_store.record_heartbeat(
            {"symbol": blob["symbol"], "bid": 1.0, "ask": 1.1, "digits": 2, "gold_smc": blob}
        )
        monitor_store.select_symbol(blob["symbol"])
        body = client.get("/api/v1/gold-smc/status").json()
        assert body["gold_smc_supported"] is True
        fails = scenario_passes(s, body["gold_smc"])
        assert not fails, f"scenario {sid}: {fails}"
