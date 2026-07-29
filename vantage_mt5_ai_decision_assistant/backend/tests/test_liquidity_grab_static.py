"""Liquidity Grab — static advisory / module presence audits."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MQL5 = ROOT / "MQL5"
INC = MQL5 / "Include" / "VantageAI"

REQUIRED = [
    "VantageLiquidityGrabTypes.mqh",
    "VantageLiquidityGrab.mqh",
]

FORBIDDEN = [
    r"\bCTrade\b",
    r"\bOrderSend\b",
    r"\bPositionClose\b",
    r"\bPositionModify\b",
]


def test_liquidity_grab_modules_present():
    missing = [n for n in REQUIRED if not (INC / n).exists()]
    assert not missing, f"Missing: {missing}"


def test_liquidity_grab_no_trade_execution():
    offenders = []
    for name in REQUIRED:
        text = (INC / name).read_text(encoding="utf-8", errors="ignore")
        for pat in FORBIDDEN:
            for i, line in enumerate(text.splitlines(), 1):
                s = line.strip()
                if s.startswith("//"):
                    continue
                if re.search(pat, line):
                    offenders.append(f"{name}:{i}: {s[:100]}")
    assert not offenders, "\n".join(offenders)


def test_liquidity_grab_uses_closed_bars():
    text = (INC / "VantageLiquidityGrab.mqh").read_text(encoding="utf-8")
    assert "CopyRates(m_symbol, tf, 1, 1, rates)" in text
    assert "CopyRates(m_symbol, tf, 1, count, rates)" in text
    assert "m_last_m5_bar" in text


def test_liquidity_grab_state_machine_present():
    text = (INC / "VantageLiquidityGrab.mqh").read_text(encoding="utf-8")
    for st in ("LG_STATE_SWEPT", "LG_STATE_REJECTED", "LG_STATE_DISPLACEMENT", "LG_STATE_MSS", "LG_STATE_BREAKOUT"):
        assert st in text


def test_ea_wires_liquidity_grab():
    ea = (MQL5 / "Experts" / "VantageMT5AIDecisionAssistant.mq5").read_text(encoding="utf-8")
    assert "InpLiqGrabEnable" in ea
    assert "liquidity_grab" in ea
    assert "CVantageLiquidityGrab" in ea
    assert "MaybeEvalLiquidityGrab" in ea
    assert 'input group "U. Liquidity Grab' in ea
