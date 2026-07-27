"""Static audits: no trade execution in EA; no cloud keys in MQL5."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MQL5 = ROOT / "MQL5"


FORBIDDEN_PATTERNS = [
    r"\bCTrade\b",
    r"\bOrderSend\b",
    r"\bPositionClose\b",
    r"\bPositionModify\b",
    r"\bOrderSendAsync\b",
    r"#include\s*<Trade/Trade\.mqh>",
]

CLOUD_KEY_PATTERNS = [
    r"sk-[A-Za-z0-9]{10,}",
    r"OPENAI_API_KEY\s*=",
    r"api[_-]?key\s*=\s*\"sk-",
]


def _iter_mq_files():
    for p in MQL5.rglob("*"):
        if p.suffix.lower() in {".mq5", ".mqh"}:
            yield p


def test_no_trade_execution_symbols_in_mql5():
    offenders = []
    for path in _iter_mq_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pat in FORBIDDEN_PATTERNS:
            for i, line in enumerate(text.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
                    continue
                # Allow documentary string literals in Print/SetLabel
                if ("Print(" in stripped or "SetLabel(" in stripped or "Alert(" in stripped) and (
                    "OrderSend" in stripped or "CTrade" in stripped or "PositionClose" in stripped
                ):
                    continue
                if re.search(pat, line):
                    offenders.append(f"{path.name}:{i}: {stripped[:120]}")
    assert not offenders, "Trade execution symbols found:\n" + "\n".join(offenders)


def test_no_cloud_provider_keys_in_mql5():
    offenders = []
    for path in _iter_mq_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pat in CLOUD_KEY_PATTERNS:
            if re.search(pat, text):
                offenders.append(f"{path}: matched {pat}")
    assert not offenders


def test_login_not_in_payload_builder():
    ea = (MQL5 / "Experts" / "VantageMT5AIDecisionAssistant.mq5").read_text(encoding="utf-8")
    # Must send masked only
    assert "account_login_masked" in ea
    assert "IntegerToString(g_acct.login)" not in ea or "login_masked" in ea
    # Ensure raw login field name not serialized
    assert "\"login\":" not in ea
    assert "ACCOUNT_LOGIN" not in ea.split("BuildAnalyzePayload")[1].split("//+------------------------------------------------------------------+")[0]


def test_webrequest_guidance_present():
    backend = (MQL5 / "Include" / "VantageAI" / "VantageBackend.mqh").read_text(encoding="utf-8")
    assert "Allow WebRequest" in backend
    assert "127.0.0.1:8000" in backend
