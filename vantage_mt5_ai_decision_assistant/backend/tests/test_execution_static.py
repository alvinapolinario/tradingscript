"""Demo execution — static audits."""
from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

ROOT = Path(__file__).resolve().parents[2]
ADVISORY_MQL5 = ROOT / "MQL5"
EXEC_ROOT = ROOT.parent / "vantage_mt5_execution" / "MQL5"
STATIC = ROOT / "backend" / "app" / "static"


def test_execution_page_served():
    r = client.get("/execution")
    assert r.status_code == 200
    assert "Demo Execution" in r.text


def test_shell_has_execution_nav():
    shell = (STATIC / "shell.js").read_text(encoding="utf-8")
    assert 'id: "execution"' in shell
    assert 'href: "/execution"' in shell


def test_execution_package_has_executor():
    ea = EXEC_ROOT / "Experts" / "VantageSwingExecutor.mq5"
    assert ea.exists()
    text = ea.read_text(encoding="utf-8")
    assert "ACCOUNT_TRADE_MODE_DEMO" in text
    assert "EnforceAccountSafety" in text
    assert "InpAllowLiveExecution" in text
    assert "InpLiveConfirmPhrase" in text


def test_advisory_tree_still_no_ctrade():
    offenders = []
    for path in ADVISORY_MQL5.rglob("*"):
        if path.suffix.lower() not in {".mq5", ".mqh"}:
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("//"):
                continue
            if re.search(r"\bCTrade\b", line) and "Print(" not in stripped:
                offenders.append(f"{path.name}:{i}")
    assert not offenders


def test_execution_includes_present():
    inc = EXEC_ROOT / "Include" / "VantageExecution"
    for name in (
        "VantageExecutionTypes.mqh",
        "VantageExecutionClient.mqh",
        "VantageExecutionRisk.mqh",
        "VantageExecutionTrade.mqh",
    ):
        assert (inc / name).exists(), name
