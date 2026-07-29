"""Breakout Structure — static advisory audits."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MQL5 = ROOT / "MQL5"
INC = MQL5 / "Include" / "VantageAI"

REQUIRED = ["VantageBreakoutStructureTypes.mqh", "VantageBreakoutStructure.mqh"]
FORBIDDEN = [r"\bCTrade\b", r"\bOrderSend\b"]


def test_breakout_modules_present():
    missing = [n for n in REQUIRED if not (INC / n).exists()]
    assert not missing


def test_breakout_no_trade_execution():
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


def test_breakout_closed_bars():
    text = (INC / "VantageBreakoutStructure.mqh").read_text(encoding="utf-8")
    assert "CopyRates(m_symbol, tf, 1, count, rates)" in text
    assert "m_last_m5_bar" in text


def test_ea_wires_breakout():
    ea = (MQL5 / "Experts" / "VantageMT5AIDecisionAssistant.mq5").read_text(encoding="utf-8")
    assert "InpBosEnable" in ea
    assert "breakout_structure" in ea
    assert "CVantageBreakoutStructure" in ea
