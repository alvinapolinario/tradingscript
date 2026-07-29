"""Market State Engine v2 — static advisory audits."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MQL5 = ROOT / "MQL5"
INC = MQL5 / "Include" / "VantageAI"

REQUIRED = ["VantageMarketStateTypes.mqh", "VantageMarketStateManager.mqh"]
FORBIDDEN = [r"\bCTrade\b", r"\bOrderSend\b"]


def test_market_state_modules_present():
    missing = [n for n in REQUIRED if not (INC / n).exists()]
    assert not missing


def test_market_state_no_trade_execution():
    offenders = []
    for name in REQUIRED:
        text = (INC / name).read_text(encoding="utf-8", errors="ignore")
        for pat in FORBIDDEN:
            for i, line in enumerate(text.splitlines(), 1):
                if line.strip().startswith("//"):
                    continue
                if re.search(pat, line):
                    offenders.append(f"{name}:{i}")
    assert not offenders


def test_market_state_closed_bars():
    text = (INC / "VantageMarketStateManager.mqh").read_text(encoding="utf-8")
    assert "CopyRates(m_symbol, PERIOD_M5, 1, 120, m_cache.m5)" in text
    assert "m_last_m5_bar" in text


def test_market_state_lifecycle_labels():
    text = (INC / "VantageMarketStateManager.mqh").read_text(encoding="utf-8")
    assert "horizontal_breakout = \"Waiting\"" in text
    assert "retest_status = \"Waiting\"" in text


def test_ea_wires_market_state():
    ea = (MQL5 / "Experts" / "VantageMT5AIDecisionAssistant.mq5").read_text(encoding="utf-8")
    assert "InpMseEnable" in ea
    assert "market_state_engine" in ea
    assert "CMarketStateManager" in ea
