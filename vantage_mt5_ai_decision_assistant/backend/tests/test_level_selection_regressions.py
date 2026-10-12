"""Regression audits for stale-level bugs in Swing / Liquidity Grab / Pullback V2 (MQL5).

Swings are stored newest → oldest. Loops that overwrite on every match end up with the
OLDEST pivot, which produced: a buy-side stop above entry (Swing), a bullish MSS below the
sweep low (Liquidity Grab), and an OTE zone outside the dealing range (Pullback V2).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INC = ROOT / "MQL5" / "Include" / "VantageAI"


def _read(name: str) -> str:
    return (INC / name).read_text(encoding="utf-8")


def _body(text: str, signature: str) -> str:
    """Return the brace-balanced body that follows ``signature``."""
    start = text.index(signature)
    open_idx = text.index("{", start)
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[open_idx : i + 1]
    raise AssertionError(f"Unbalanced body for {signature}")


def _strip_comments(src: str) -> str:
    return "\n".join(line.split("//", 1)[0] for line in src.splitlines())


# --- Swing Strategy -----------------------------------------------------------------


def _swing_pipeline() -> str:
    return _strip_comments(_body(_read("VantageSwingStrategy.mqh"), "void RunPipeline("))


def test_swing_keeps_most_recent_swing_not_oldest():
    body = _swing_pipeline()
    # The selection loop must only assign sh/sl on the first (most recent) match.
    assert re.search(r"if\(sh == 0\)\s*\{\s*sh = m_swings\[i\]\.price", body)
    assert re.search(r"if\(sl == 0\)\s*sl = m_swings\[i\]\.price", body)
    # The old overwrite pattern must be gone.
    assert "psh = sh; sh = m_swings[i].price" not in body
    assert "psl = sl; sl = m_swings[i].price" not in body
    # Previous-swing time must come from the matched swing, not a fixed index.
    assert "m_swings[1].time" not in body


def test_swing_structure_uses_latest_high_and_low():
    body = _strip_comments(_body(_read("VantageSwingStrategy.mqh"), "string StructureFromSwings("))
    assert "seen_high" in body and "seen_low" in body
    # Must not OR-accumulate labels across the whole window.
    assert not re.search(r"if\(m_swings\[i\]\.label == SWING_LBL_HH\)\s*hh = true", body)


def test_swing_risk_rejects_stop_on_wrong_side():
    body = _swing_pipeline()
    assert "risk_geometry_ok" in body
    assert re.search(r"bullish_bias && r\.stop_loss > 0 && \(r\.stop_loss >= bid \|\| r\.tp1 <= bid\)", body)
    assert re.search(r"bearish_bias && r\.stop_loss > 0 && \(r\.stop_loss <= bid \|\| r\.tp1 >= bid\)", body)
    # MathAbs hid the inverted stop by producing a plausible positive R:R.
    assert "MathAbs(bid - r.stop_loss)" not in body
    assert "MathAbs(r.tp1 - bid)" not in body


def test_swing_invalid_geometry_zeroes_rr_so_no_entry_signal():
    body = _swing_pipeline()
    guard = body[body.index("if(!risk_geometry_ok)") :]
    guard = guard[: guard.index("}") + 1]
    assert "r.risk_reward = 0" in guard
    # Entry signals still gate on min R:R, so a zeroed R:R can never become a BUY/SELL.
    assert "r.risk_reward >= m_cfg.min_rr" in body
    assert "r.risk_reward >= min_rr_scalp" in body


# --- Liquidity Grab -----------------------------------------------------------------


def test_liquidity_grab_mss_uses_most_recent_pivot_beyond_sweep():
    text = _read("VantageLiquidityGrab.mqh")
    body = _strip_comments(_body(text, "bool DetectMSS("))
    sig = text[text.index("bool DetectMSS(") : text.index("{", text.index("bool DetectMSS("))]
    assert "sweep_price" in sig
    # Bullish MSS pivot must be above the sweep low; bearish must be below the sweep high.
    assert "rates[i].high > sweep_price" in body
    assert "rates[i].low < sweep_price" in body
    # First qualifying pivot wins (break), instead of the loop overwriting to the oldest.
    assert body.count("break;") >= 2


def test_liquidity_grab_passes_sweep_price_to_mss():
    text = _strip_comments(_read("VantageLiquidityGrab.mqh"))
    assert "DetectMSS(rates, n, bsl, c.sweep_price, mss_lvl, mt)" in text


# --- Pullback V2 --------------------------------------------------------------------


def test_pullback_v2_rejects_gold_smc_ote_outside_dealing_range():
    body = _strip_comments(_body(_read("VantagePullbackV2.mqh"), "PbV2OteSnap ResolveOte("))
    assert "gsm_ote_in_range" in body
    assert "PbV2Overlap(dr.range_low, dr.range_high, gsm.ote_low, gsm.ote_high)" in body
    use_gsm = body[body.index("if(m_cfg.prefer_gold_smc_ote") : body.index("MapGoldSmcOte")]
    assert "gsm_ote_in_range" in use_gsm


def test_pullback_v2_checklist_has_no_source_labels_as_positives():
    text = _strip_comments(_read("VantagePullbackV2.mqh"))
    for label in ("Gold SMC OTE;", "Gold SMC POI;", "Liquidity Grab module;", '"Depth from "'):
        assert label not in text, f"source label still emitted as a factor: {label}"


def test_pullback_v2_dealing_range_tick_respects_direction():
    text = _strip_comments(_read("VantagePullbackV2.mqh"))
    assert 'if(dr.valid) pos += "Dealing range "' not in text
    assert re.search(r"pd_fav = CalcPdEntryFavorability\(dom, dr\)", text)
    assert re.search(r'neg \+= "Dealing range " \+ dr\.location \+ " \(against trend entry\);"', text)
