"""ICT Strategy — MQL5 module presence and EA wiring audits."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MQL5 = ROOT / "MQL5"
INC = MQL5 / "Include" / "VantageAI"

REQUIRED = [
    "VantageIctTypes.mqh",
    "VantageIct.mqh",
]

FORBIDDEN = [
    r"\bCTrade\b",
    r"\bOrderSend\b",
    r"\bPositionClose\b",
    r"\bPositionModify\b",
]


def test_ict_modules_present():
    missing = [n for n in REQUIRED if not (INC / n).exists()]
    assert not missing, f"Missing: {missing}"


def test_ict_no_trade_execution():
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


def test_ict_uses_closed_bars():
    text = (INC / "VantageIct.mqh").read_text(encoding="utf-8")
    assert "CopyRates(m_symbol, tf, 1, count, rates)" in text
    assert "m_last_entry_bar" in text


def test_ict_tojson_matches_backend_blob():
    text = (INC / "VantageIct.mqh").read_text(encoding="utf-8")
    for key in (
        '\\"module\\":\\"ict\\"',
        '\\"setup_state\\"',
        '\\"htf_bias\\"',
        '\\"liquidity\\"',
        '\\"structure\\"',
        '\\"fvg\\"',
        '\\"entry\\"',
        '\\"stop_loss\\"',
        '\\"targets\\"',
    ):
        assert key in text


def test_ea_wires_ict():
    ea = (MQL5 / "Experts" / "VantageMT5AIDecisionAssistant.mq5").read_text(encoding="utf-8")
    assert "InpIctEnable" in ea
    assert ',\\"ict\\":' in ea
    assert "CVantageIct" in ea
    assert "MaybeEvalIct" in ea
    assert "FillIctConfig" in ea
    assert 'input group "AX. ICT Strategy — Core"' in ea
