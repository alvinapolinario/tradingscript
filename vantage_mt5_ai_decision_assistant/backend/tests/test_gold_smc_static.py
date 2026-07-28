"""Gold SMC Phase 8 — static non-repaint / advisory / module presence audits."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MQL5 = ROOT / "MQL5"
GSMC = MQL5 / "Include" / "VantageAI"

REQUIRED_MODULES = [
    "VantageGoldSMC.mqh",
    "VantageGoldSMCTypes.mqh",
    "VantageGoldSMCValidator.mqh",
    "VantageGoldSMCCore.mqh",
    "VantageGoldSMCLiquidity.mqh",
    "VantageGoldSMCZones.mqh",
    "VantageGoldSMCContext.mqh",
    "VantageGoldSMCSetup.mqh",
    "VantageGoldSMCChart.mqh",
    "VantageGoldSMCAlert.mqh",
]

FORBIDDEN = [
    r"\bCTrade\b",
    r"\bOrderSend\b",
    r"\bPositionClose\b",
    r"\bPositionModify\b",
]


def test_all_gold_smc_modules_present():
    missing = [n for n in REQUIRED_MODULES if not (GSMC / n).exists()]
    assert not missing, f"Missing modules: {missing}"


def test_gold_smc_no_trade_execution():
    offenders = []
    for name in REQUIRED_MODULES:
        text = (GSMC / name).read_text(encoding="utf-8", errors="ignore")
        for pat in FORBIDDEN:
            for i, line in enumerate(text.splitlines(), 1):
                s = line.strip()
                if s.startswith("//"):
                    continue
                if re.search(pat, line):
                    offenders.append(f"{name}:{i}: {s[:100]}")
    assert not offenders, "\n".join(offenders)


def test_structure_and_zones_use_closed_bars():
    """CopyRates for analysis must start at shift 1 (closed), not forming bar 0."""
    core = (GSMC / "VantageGoldSMCCore.mqh").read_text(encoding="utf-8")
    zones = (GSMC / "VantageGoldSMCZones.mqh").read_text(encoding="utf-8")
    facade = (GSMC / "VantageGoldSMC.mqh").read_text(encoding="utf-8")
    assert "CopyRates(m_symbol, tf, 1," in core
    assert "ArraySetAsSeries(rates, true)" in core
    assert "CopyRates(m_symbol, m_cfg.tf_confirm, 1," in zones
    assert "CopyRates(m_symbol, m_cfg.tf_exec, 1, 1, rb)" in facade
    # Cache on closed M5 bar
    assert "m_last_m5_bar" in facade
    assert "m5_bar == m_last_m5_bar" in facade


def test_swing_confirmation_requires_right_bars():
    core = (GSMC / "VantageGoldSMCCore.mqh").read_text(encoding="utf-8")
    assert "swing_right_ext" in core
    assert "swing_right_int" in core
    assert "LightRefreshLive" in (GSMC / "VantageGoldSMC.mqh").read_text(encoding="utf-8")


def test_ea_wires_gold_smc_groups_and_heartbeat():
    ea = (MQL5 / "Experts" / "VantageMT5AIDecisionAssistant.mq5").read_text(encoding="utf-8")
    assert "InpGoldSmcEnable" in ea
    assert "InpGoldSmcShowChartObj" in ea
    assert "InpGoldSmcAlertEnable" in ea
    assert "InpGoldSmcDebug" in ea
    assert "gold_smc" in ea
    assert "CVantageGoldSMC" in ea


def test_docs_and_disclaimer_present():
    docs = (ROOT / "docs" / "GOLD_SMC.md").read_text(encoding="utf-8")
    assert "Smart Money Concepts are interpretive" in docs
    assert "Phase 8" in docs
    assert "Non-repaint" in docs or "closed bars" in docs.lower()
    assert "Troubleshooting" in docs
