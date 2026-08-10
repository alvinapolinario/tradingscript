"""AMD + iFVG — static advisory / module presence audits."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MQL5 = ROOT / "MQL5"
INC = MQL5 / "Include" / "VantageAI"

REQUIRED = [
    "VantageAmdIfvgTypes.mqh",
    "VantageAmdIfvg.mqh",
]

FORBIDDEN = [
    r"\bCTrade\b",
    r"\bOrderSend\b",
    r"\bPositionClose\b",
    r"\bPositionModify\b",
]


def test_amd_ifvg_modules_present():
    missing = [n for n in REQUIRED if not (INC / n).exists()]
    assert not missing, f"Missing: {missing}"


def test_amd_ifvg_no_trade_execution():
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


def test_amd_ifvg_uses_closed_bars():
    text = (INC / "VantageAmdIfvg.mqh").read_text(encoding="utf-8")
    assert "CopyRates(m_symbol, tf, 1, count, rates)" in text
    assert "m_last_m5_bar" in text


def test_amd_ifvg_pipeline_mss_before_ifvg():
    text = (INC / "VantageAmdIfvg.mqh").read_text(encoding="utf-8")
    mss_pos = text.find("out.mss_detected = true")
    ifvg_pos = text.find("// iFVG scan on M5")
    assert mss_pos > 0 and ifvg_pos > mss_pos
    assert "ifvg_max_retests" in text
    assert "chase_max_atr" in text
    assert "min_rr" in text


def test_ea_wires_amd_ifvg():
    ea = (MQL5 / "Experts" / "VantageMT5AIDecisionAssistant.mq5").read_text(encoding="utf-8")
    assert "InpAmdIfvgEnable" in ea
    assert "amd_ifvg" in ea
    assert "CVantageAmdIfvg" in ea
    assert "MaybeEvalAmdIfvg" in ea
    assert 'input group "AP. AMD + iFVG' in ea
