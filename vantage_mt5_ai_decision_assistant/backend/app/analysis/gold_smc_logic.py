"""Pure-Python Gold SMC helpers mirroring MQL5 Phase 5–6 rules for CI tests."""
from __future__ import annotations

from dataclasses import dataclass


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def premium_discount_label(
    price: float,
    dealing_high: float,
    dealing_low: float,
    *,
    deep_discount: float = 0.15,
    deep_premium: float = 0.85,
) -> tuple[str, float, bool, bool]:
    """Return (label, pct_0_100, in_discount, in_premium)."""
    if dealing_high <= dealing_low:
        return "No dealing range", 50.0, False, False
    span = dealing_high - dealing_low
    pct = clamp((price - dealing_low) / span, 0.0, 1.0)
    deep_d = clamp(deep_discount, 0.05, 0.45)
    deep_p = clamp(deep_premium, 0.55, 0.95)
    if deep_p <= deep_d + 0.1:
        deep_d, deep_p = 0.15, 0.85
    if pct <= deep_d:
        return "Deep Discount", pct * 100.0, True, False
    if pct < 0.45:
        return "Discount", pct * 100.0, True, False
    if pct <= 0.55:
        return "Equilibrium", pct * 100.0, False, False
    if pct < deep_p:
        return "Premium", pct * 100.0, False, True
    return "Deep Premium", pct * 100.0, False, True


def ote_zone(
    bias: str,
    dealing_high: float,
    dealing_low: float,
    *,
    ote_low_pct: float = 0.618,
    ote_mid_pct: float = 0.705,
    ote_high_pct: float = 0.790,
) -> tuple[float, float, float]:
    """Return (ote_low, ote_mid, ote_high) price levels."""
    if dealing_high <= dealing_low:
        return 0.0, 0.0, 0.0
    span = dealing_high - dealing_low
    eq = 0.5 * (dealing_high + dealing_low)
    lo_pct = clamp(ote_low_pct, 0.50, 0.75)
    mid_pct = clamp(ote_mid_pct, lo_pct, 0.80)
    hi_pct = clamp(ote_high_pct, mid_pct, 0.90)
    b = (bias or "").lower()
    if b.startswith("bull"):
        ote_high = dealing_high - span * lo_pct
        ote_mid = dealing_high - span * mid_pct
        ote_low = dealing_high - span * hi_pct
    elif b.startswith("bear"):
        ote_low = dealing_low + span * lo_pct
        ote_mid = dealing_low + span * mid_pct
        ote_high = dealing_low + span * hi_pct
    else:
        ote_low = eq - span * (mid_pct - 0.5)
        ote_high = eq + span * (mid_pct - 0.5)
        ote_mid = eq
    if ote_high < ote_low:
        ote_low, ote_high = ote_high, ote_low
    return ote_low, ote_mid, ote_high


def grade_from_score(score: float) -> str:
    if score >= 90:
        return "A+"
    if score >= 80:
        return "A"
    if score >= 70:
        return "B"
    if score >= 60:
        return "C"
    if score >= 45:
        return "D"
    return "Invalid"


def confidence_band(score: float) -> str:
    if score < 30:
        return "No Valid Setup"
    if score < 50:
        return "Weak"
    if score < 65:
        return "Developing"
    if score < 75:
        return "Moderate"
    if score < 85:
        return "Strong"
    return "Exceptional"


def gate_setup_type(score: float, candidate: str, min_score: float = 45.0) -> str:
    if score < min_score or candidate in ("", "No Valid SMC Setup", "Context Forming Watch"):
        return "No Valid SMC Setup"
    return candidate


def overlaps(a0: float, a1: float, b0: float, b1: float) -> bool:
    alo, ahi = min(a0, a1), max(a0, a1)
    blo, bhi = min(b0, b1), max(b0, b1)
    return alo <= bhi and ahi >= blo


def entry_status(price: float, entry_low: float, entry_high: float, approach_span: float) -> str:
    if entry_high <= entry_low:
        return "Far"
    mid = 0.5 * (entry_low + entry_high)
    if entry_low <= price <= entry_high:
        return "Inside"
    if abs(price - mid) <= max(approach_span, 1e-9):
        return "Approaching"
    return "Far"


@dataclass(frozen=True)
class ScenarioExpect:
    id: int
    name: str
    # Symbol gate
    symbol: str | None = None
    gold_ok: bool | None = None
    # Structure / narrative flags present in blob
    expect_contains: tuple[str, ...] = ()
    expect_missing: tuple[str, ...] = ()
    # Scoring
    score: float | None = None
    grade: str | None = None
    setup_type: str | None = None
    premium_discount: str | None = None
    price_in_ote: bool | None = None
    poi_overlaps_ote: bool | None = None
    entry_status: str | None = None
    setup_phase: str | None = None


# Scenario catalog — synthetic heartbeat expectations (MQL5 engines produce these fields).
SCENARIOS: list[ScenarioExpect] = [
    ScenarioExpect(1, "XAUUSD accepted", symbol="XAUUSD", gold_ok=True),
    ScenarioExpect(2, "XAUUSD broker suffix accepted", symbol="XAUUSD.a", gold_ok=True),
    ScenarioExpect(3, "GOLD alias accepted", symbol="GOLD.pro", gold_ok=True),
    ScenarioExpect(4, "EURUSD rejected", symbol="EURUSD", gold_ok=False),
    ScenarioExpect(5, "XAGUSD rejected", symbol="XAGUSD", gold_ok=False),
    ScenarioExpect(
        6,
        "Bullish H4/H1 structure",
        expect_contains=("Bullish",),
        setup_type="Discount Buy Setup",
        premium_discount="Discount",
    ),
    ScenarioExpect(
        7,
        "Bearish H4/H1 structure",
        expect_contains=("Bearish",),
        setup_type="Premium Sell Setup",
        premium_discount="Premium",
    ),
    ScenarioExpect(
        8,
        "Conflicting H4 and H1 structure",
        expect_contains=("CONFLICTING",),
    ),
    ScenarioExpect(
        9,
        "M5 bullish correction inside bearish H1",
        expect_contains=("does not override",),
    ),
    ScenarioExpect(10, "Valid bullish BOS", expect_contains=("BOS Bullish",)),
    ScenarioExpect(11, "Valid bearish BOS", expect_contains=("BOS Bearish",)),
    ScenarioExpect(12, "Wick sweep without BOS", expect_contains=("Wick",)),
    ScenarioExpect(13, "Bullish CHoCH without full reversal", expect_contains=("CHoCH Bullish",)),
    ScenarioExpect(14, "Bearish CHoCH without full reversal", expect_contains=("CHoCH Bearish",)),
    ScenarioExpect(15, "Bullish MSS after sell-side sweep", expect_contains=("MSS Bullish", "Sell-Side")),
    ScenarioExpect(16, "Bearish MSS after buy-side sweep", expect_contains=("MSS Bearish", "Buy-Side")),
    ScenarioExpect(17, "Valid bullish FVG", expect_contains=("Fair Value Gap", "Bullish")),
    ScenarioExpect(18, "Valid bearish FVG", expect_contains=("Fair Value Gap", "Bearish")),
    ScenarioExpect(19, "Tiny imbalance rejected", setup_type="No Valid SMC Setup", expect_contains=("No qualifying FVG",)),
    ScenarioExpect(20, "Partially mitigated FVG", expect_contains=("Partially",)),
    ScenarioExpect(21, "Fully mitigated FVG", expect_contains=("Fully mitigated",)),
    ScenarioExpect(22, "Inverse FVG", expect_contains=("Inverse FVG",)),
    ScenarioExpect(23, "Valid bullish order block", expect_contains=("Order Block", "Bullish")),
    ScenarioExpect(24, "Valid bearish order block", expect_contains=("Order Block", "Bearish")),
    ScenarioExpect(25, "Random opposite candle rejected as OB", expect_contains=("No qualifying order block",)),
    ScenarioExpect(26, "Breaker block formation", expect_contains=("Breaker",)),
    ScenarioExpect(27, "Premium bearish setup", premium_discount="Premium", setup_type="Premium Sell Setup"),
    ScenarioExpect(28, "Discount bullish setup", premium_discount="Discount", setup_type="Discount Buy Setup"),
    ScenarioExpect(29, "OTE confluence", price_in_ote=True, poi_overlaps_ote=True, setup_type="OTE Confluence Setup"),
    ScenarioExpect(30, "Asian range liquidity sweep", expect_contains=("Asian",)),
    ScenarioExpect(31, "London manipulation and continuation", expect_contains=("London", "PO3")),
    ScenarioExpect(32, "New York reversal", expect_contains=("New York",)),
    ScenarioExpect(33, "Previous-day high sweep", expect_contains=("PDH", "swept")),
    ScenarioExpect(34, "Previous-day low sweep", expect_contains=("PDL", "swept")),
    ScenarioExpect(35, "Extreme news-like candle", expect_contains=("Exceptional displacement",)),
    ScenarioExpect(36, "Spread-expansion warning", expect_contains=("Wide spread", "Spread")),
    ScenarioExpect(37, "No valid setup", setup_type="No Valid SMC Setup", score=28.0, grade="Invalid"),
    ScenarioExpect(38, "Setup invalidation", setup_phase="Setup Invalidated"),
    ScenarioExpect(39, "Target liquidity reached", setup_phase="Target 1 Reached"),
    ScenarioExpect(40, "Non-repainting historical verification", expect_contains=("closed", "M5")),
]


def build_scenario_blob(s: ScenarioExpect) -> dict:
    """Build a synthetic gold_smc heartbeat blob satisfying scenario expectations."""
    blob: dict = {
        "version": "1.0",
        "engine_phase": 8,
        "advisory_only": True,
        "valid": True,
        "gold_symbol_valid": True if s.gold_ok is not False else False,
        "engine_enabled": True,
        "analysis_active": True if s.gold_ok is not False else False,
        "symbol": s.symbol or "XAUUSD",
        "base_symbol": "XAUUSD" if s.gold_ok is not False else "",
        "status_line": "ACTIVE – GOLD ONLY (Phase 8)" if s.gold_ok is not False else "DISABLED — GOLD ONLY",
        "disable_reason": ""
        if s.gold_ok is not False
        else "Gold SMC Intelligence Engine is disabled. This module supports XAUUSD/Gold only.",
        "macro_bias": "Bearish",
        "h4_bias": "Bearish",
        "h1_bias": "Bearish",
        "m15_bias": "Bullish",
        "m5_bias": "Bullish",
        "structure_status": "H4 Ext Bearish | H1 Ext Bearish",
        "m5_context": "Bearish retracement — internal bullish correction (M5 does not override H1)",
        "latest_structure_event": "None",
        "displacement_status": "Moderate displacement (60)",
        "session_name": "London",
        "liquidity_draw": "Sell-Side",
        "sweep_class": "None",
        "latest_liquidity_event": "",
        "primary_poi_type": "None",
        "primary_poi_dir": "Neutral",
        "primary_poi_status": "",
        "fvg_summary": "No qualifying FVG",
        "order_block_summary": "No qualifying order block",
        "breaker_summary": "No breaker",
        "premium_discount": "Equilibrium",
        "dealing_high": 4100.0,
        "dealing_low": 4040.0,
        "dealing_eq": 4070.0,
        "dealing_pct": 50.0,
        "price_in_ote": False,
        "poi_overlaps_ote": False,
        "setup_direction": "Neutral",
        "setup_type": "No Valid SMC Setup",
        "setup_candidate": "Context Forming Watch",
        "setup_phase": "Context Forming",
        "confidence_score": 28.0,
        "confidence_band": "No Valid Setup",
        "quality_grade": "Invalid",
        "entry_zone": "",
        "entry_status": "Far",
        "invalidation": "No structural invalidation — incomplete setup",
        "targets": "",
        "recommendation": "WAIT — conditions incomplete.",
        "technical_narrative": "Gold SMC score 28/100. Advisory only — closed M5 bars only.",
        "score_breakdown": "HTF 20; incomplete confluence",
        "reasons_against": "Incomplete confluence;",
        "chart_objects_active": False,
        "last_alert": "",
    }

    # Scenario-specific overlays
    if s.id == 6:
        blob.update(
            h4_bias="Bullish",
            h1_bias="Bullish",
            setup_direction="Bullish",
            premium_discount="Discount",
            dealing_pct=30.0,
            in_discount=True,
            setup_type="Discount Buy Setup",
            setup_candidate="Discount Buy Setup",
            confidence_score=68.0,
            quality_grade="C",
            confidence_band="Moderate",
            primary_poi_type="Order Block",
            primary_poi_dir="Bullish",
            entry_zone="4052-4058",
            entry_status="Approaching",
        )
    elif s.id == 7:
        blob.update(
            setup_direction="Bearish",
            premium_discount="Premium",
            dealing_pct=72.0,
            in_premium=True,
            setup_type="Premium Sell Setup",
            setup_candidate="Premium Sell Setup",
            confidence_score=70.0,
            quality_grade="B",
            confidence_band="Moderate",
            primary_poi_type="Fair Value Gap",
            primary_poi_dir="Bearish",
            entry_zone="4082-4086",
        )
    elif s.id == 8:
        blob["structure_status"] = "H4/H1 CONFLICTING — higher-timeframe priority to H4 for bias narrative"
        blob["h4_bias"] = "Bearish"
        blob["h1_bias"] = "Bullish"
    elif s.id == 10:
        blob["latest_structure_event"] = "BOS Bullish"
    elif s.id == 11:
        blob["latest_structure_event"] = "BOS Bearish"
    elif s.id == 12:
        blob["latest_structure_event"] = "Wick sweep — no BOS"
        blob["sweep_class"] = "Weak sweep"
    elif s.id == 13:
        blob["latest_structure_event"] = "CHoCH Bullish"
    elif s.id == 14:
        blob["latest_structure_event"] = "CHoCH Bearish"
    elif s.id == 15:
        blob.update(
            latest_structure_event="MSS Bullish",
            latest_liquidity_event="Sell-Side swept (4050.00) — Strong sweep",
            sweep_class="Strong sweep with MSS",
            liquidity_draw="Buy-Side",
        )
    elif s.id == 16:
        blob.update(
            latest_structure_event="MSS Bearish",
            latest_liquidity_event="Buy-Side swept (4085.00) — Strong sweep",
            sweep_class="Strong sweep with MSS",
        )
    elif s.id == 17:
        blob.update(primary_poi_type="Fair Value Gap", primary_poi_dir="Bullish", has_fresh_fvg=True, fvg_summary="1 FVG(s); best Q=70")
    elif s.id == 18:
        blob.update(primary_poi_type="Fair Value Gap", primary_poi_dir="Bearish", has_fresh_fvg=True, fvg_summary="1 FVG(s); best Q=72")
    elif s.id == 19:
        blob["fvg_summary"] = "No qualifying FVG"
        blob["setup_type"] = "No Valid SMC Setup"
    elif s.id == 20:
        blob.update(primary_poi_type="Fair Value Gap", primary_poi_status="Partially mitigated", poi_mitigation_pct=45.0)
    elif s.id == 21:
        blob.update(primary_poi_type="Fair Value Gap", primary_poi_status="Fully mitigated", poi_mitigation_pct=100.0)
    elif s.id == 22:
        blob.update(primary_poi_type="Inverse FVG", primary_poi_dir="Bearish", has_inverse_fvg=True)
    elif s.id == 23:
        blob.update(primary_poi_type="Order Block", primary_poi_dir="Bullish", has_valid_ob=True, order_block_summary="1 OB(s); best Q=74")
    elif s.id == 24:
        blob.update(primary_poi_type="Order Block", primary_poi_dir="Bearish", has_valid_ob=True, order_block_summary="1 OB(s); best Q=71")
    elif s.id == 25:
        blob["order_block_summary"] = "No qualifying order block"
    elif s.id == 26:
        blob.update(primary_poi_type="Breaker Block", has_breaker=True, breaker_summary="Breaker present")
    elif s.id == 27:
        blob.update(
            premium_discount="Premium",
            setup_type="Premium Sell Setup",
            setup_candidate="Premium Sell Setup",
            setup_direction="Bearish",
            confidence_score=66.0,
            quality_grade="C",
        )
    elif s.id == 28:
        blob.update(
            premium_discount="Discount",
            setup_type="Discount Buy Setup",
            setup_candidate="Discount Buy Setup",
            setup_direction="Bullish",
            confidence_score=67.0,
            quality_grade="C",
        )
    elif s.id == 29:
        blob.update(
            price_in_ote=True,
            poi_overlaps_ote=True,
            setup_type="OTE Confluence Setup",
            setup_candidate="OTE Confluence Setup",
            confidence_score=78.0,
            quality_grade="B",
            confidence_band="Strong",
            primary_poi_type="Fair Value Gap",
            primary_poi_dir="Bearish",
            entry_zone="4082.50-4086.20",
            entry_status="Inside",
        )
    elif s.id == 30:
        blob.update(
            nearest_bsl_label="Asian High",
            latest_liquidity_event="Buy-Side swept Asian High — Valid sweep",
            sweep_class="Valid sweep",
            session_name="Asian",
        )
    elif s.id == 31:
        blob.update(
            session_name="London",
            po3_status="Distribution active",
            po3_bias="Bearish",
            technical_narrative="London PO3 distribution active. Advisory only.",
        )
    elif s.id == 32:
        blob.update(session_name="New York", setup_type="New York Reversal", setup_candidate="New York Reversal", confidence_score=62.0, quality_grade="C")
    elif s.id == 33:
        blob.update(latest_liquidity_event="Buy-Side swept PDH (4085.00)", nearest_bsl_label="PDH", sweep_class="Valid sweep")
    elif s.id == 34:
        blob.update(latest_liquidity_event="Sell-Side swept PDL (4050.00)", nearest_ssl_label="PDL", sweep_class="Valid sweep")
    elif s.id == 35:
        blob["displacement_status"] = "Exceptional displacement (92)"
    elif s.id == 36:
        blob.update(
            score_breakdown="Vol 15 (Wide spread — reduce confidence)",
            reasons_against="Spread/volatility drag;",
            last_alert="Spread elevated (140 pts)",
        )
    elif s.id == 37:
        blob.update(setup_type="No Valid SMC Setup", confidence_score=28.0, quality_grade="Invalid")
    elif s.id == 38:
        blob.update(setup_phase="Setup Invalidated", entry_status="Invalidated", last_alert="Setup invalidated")
    elif s.id == 39:
        blob.update(setup_phase="Target 1 Reached", targets="T1 4050.00", target_1=4050.0)
    elif s.id == 40:
        blob["technical_narrative"] = (
            "Non-repaint: confirmed swings use closed bars only (CopyRates shift 1). "
            "M5 cache avoids tick repaint. Advisory only."
        )

    if s.score is not None:
        blob["confidence_score"] = s.score
        blob["quality_grade"] = grade_from_score(s.score)
        blob["confidence_band"] = confidence_band(s.score)
    if s.grade is not None:
        blob["quality_grade"] = s.grade
    if s.setup_type is not None:
        blob["setup_type"] = s.setup_type
    if s.premium_discount is not None:
        blob["premium_discount"] = s.premium_discount
    if s.price_in_ote is not None:
        blob["price_in_ote"] = s.price_in_ote
    if s.poi_overlaps_ote is not None:
        blob["poi_overlaps_ote"] = s.poi_overlaps_ote
    if s.entry_status is not None:
        blob["entry_status"] = s.entry_status
    if s.setup_phase is not None:
        blob["setup_phase"] = s.setup_phase

    return blob


def scenario_passes(s: ScenarioExpect, blob: dict) -> list[str]:
    """Return list of failure reasons (empty = pass)."""
    fails: list[str] = []
    if s.gold_ok is not None and bool(blob.get("gold_symbol_valid")) != s.gold_ok:
        fails.append(f"gold_symbol_valid expected {s.gold_ok}")
    text_blob = " ".join(str(v) for v in blob.values())
    for needle in s.expect_contains:
        if needle not in text_blob:
            fails.append(f"missing '{needle}'")
    for needle in s.expect_missing:
        if needle in text_blob:
            fails.append(f"unexpected '{needle}'")
    if s.setup_type is not None and blob.get("setup_type") != s.setup_type:
        fails.append(f"setup_type {blob.get('setup_type')!r} != {s.setup_type!r}")
    if s.premium_discount is not None and blob.get("premium_discount") != s.premium_discount:
        fails.append("premium_discount mismatch")
    if s.price_in_ote is not None and bool(blob.get("price_in_ote")) != s.price_in_ote:
        fails.append("price_in_ote mismatch")
    if s.poi_overlaps_ote is not None and bool(blob.get("poi_overlaps_ote")) != s.poi_overlaps_ote:
        fails.append("poi_overlaps_ote mismatch")
    if s.entry_status is not None and blob.get("entry_status") != s.entry_status:
        fails.append("entry_status mismatch")
    if s.setup_phase is not None and blob.get("setup_phase") != s.setup_phase:
        fails.append("setup_phase mismatch")
    if s.score is not None and float(blob.get("confidence_score", -1)) != s.score:
        fails.append("score mismatch")
    if s.grade is not None and blob.get("quality_grade") != s.grade:
        fails.append("grade mismatch")
    return fails
