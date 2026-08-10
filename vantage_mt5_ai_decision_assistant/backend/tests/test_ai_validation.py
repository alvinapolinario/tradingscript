"""AI structured validation tests."""
import json

from app.analysis.ai_brief import SYSTEM_PROMPT, build_ai_brief_markdown
from app.analysis.ai_validation import (
    build_strategy_validation_context,
    extract_ai_validation_block,
    validate_ai_response,
)
from fastapi.testclient import TestClient

from app.main import app
from app.monitor_state import monitor_store


def _status_with_ict():
    monitor_store.record_heartbeat(
        {
            "symbol": "XAUUSD",
            "connected": True,
            "bid": 3400.0,
            "ict": {
                "valid": True,
                "analysis_active": True,
                "decision": "SELL",
                "confidence_score": 84,
                "setup_state": "ENTRY_ZONE_ACTIVE",
                "score_components": {"liquidity": 20, "mss": 18},
                "score_gates": {"liquidity_sweep": True, "mss": True},
                "reasons": ["Bearish MSS after buy-side sweep"],
                "invalidations": ["Close above 4015 invalidates"],
                "htf_bias": {"direction": "BEARISH", "confidence": 78},
            },
            "amd_ifvg": {
                "valid": True,
                "analysis_active": True,
                "decision": "SELL",
                "confidence": 76,
                "setup_state": "WAITING_FOR_RETRACE",
            },
        }
    )
    monitor_store.select_symbol("XAUUSD")
    return monitor_store.status()


def test_build_strategy_validation_context_includes_ict():
    ctx = build_strategy_validation_context(_status_with_ict())
    assert "ICT" in ctx["strategies"]
    ict = ctx["strategies"]["ICT"]
    assert ict["backend_signal"] == "SELL"
    assert ict["confidence"] == 84
    assert ict["state"] == "ENTRY_ZONE_ACTIVE"
    assert ict["score_components"]["liquidity"] == 20
    assert len(ict["evidence"]) >= 1
    assert ctx["backend_authoritative"] is True


def test_ai_brief_markdown_includes_structured_section():
    md = build_ai_brief_markdown(_status_with_ict())
    assert "## 9. Backend strategy signals" in md
    assert "AUTHORITATIVE" in md
    assert "ENTRY_ZONE_ACTIVE" in md
    assert "ai_assessment" in md


def test_system_prompt_forbids_score_override():
    assert "AUTHORITATIVE" in SYSTEM_PROMPT or "authoritative" in SYSTEM_PROMPT.lower()
    assert "CAUTION" in SYSTEM_PROMPT


def test_extract_ai_validation_block():
    text = """Some analysis here.

```json
{"ai_assessment": "CAUTION", "assessment_reason": "Spread elevated", "backend_signals_acknowledged": ["ICT"]}
```"""
    block = extract_ai_validation_block(text)
    assert block is not None
    assert block["ai_assessment"] == "CAUTION"


def test_validate_ai_response_caution():
    ctx = build_strategy_validation_context(_status_with_ict())
    ai_text = (
        "Backend SELL is noted but timing is poor.\n\n"
        "```json\n"
        + json.dumps(
            {
                "ai_assessment": "CAUTION",
                "assessment_reason": "Wait for retrace confirmation",
                "backend_signals_acknowledged": ["ICT", "AMD_IFVG"],
                "agrees_with_primary_signal": True,
            }
        )
        + "\n```"
    )
    v = validate_ai_response(ctx, ai_text)
    assert v["ai_assessment"] == "CAUTION"
    assert v["valid"] is True
    assert v["backend_authoritative"] is True


def test_validate_ai_response_missing_footer():
    ctx = build_strategy_validation_context(_status_with_ict())
    v = validate_ai_response(ctx, "Analysis without JSON footer.")
    assert v["ai_assessment"] == "UNKNOWN"
    assert v["valid"] is False
    assert any("Missing" in d for d in v["disagreements"])


def test_ai_brief_api_returns_structured_context():
    _status_with_ict()
    r = TestClient(app).get("/api/v1/monitor/ai-brief")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "structured_context" in body
    assert "ICT" in body["structured_context"]["strategies"]
