"""Structured strategy context + AI response validation (Step 12)."""
from __future__ import annotations

import json
import re
from typing import Any, Literal

AiAssessment = Literal["ALIGNED", "CAUTION", "DISAGREE", "UNKNOWN"]

AI_VALIDATION_SCHEMA = {
    "ai_assessment": "ALIGNED | CAUTION | DISAGREE",
    "assessment_reason": "string — why aligned, cautious, or disagreeing",
    "backend_signals_acknowledged": ["list of strategy keys referenced, e.g. ICT"],
    "agrees_with_primary_signal": "boolean — narrative aligns with backend primary direction",
}


def _pick_blob(ea: dict[str, Any], key: str) -> dict[str, Any]:
    val = ea.get(key)
    return val if isinstance(val, dict) else {}


def _list(val: Any, limit: int = 8) -> list[str]:
    if not isinstance(val, list):
        return []
    return [str(x) for x in val[:limit] if x]


def _ict_context(blob: dict[str, Any]) -> dict[str, Any] | None:
    if not (blob.get("valid") or blob.get("analysis_active")):
        return None
    htf = blob.get("htf_bias") if isinstance(blob.get("htf_bias"), dict) else {}
    return {
        "backend_signal": str(blob.get("decision") or "NO_TRADE"),
        "confidence": float(blob.get("confidence_score") or blob.get("confidence") or 0),
        "score_components": blob.get("score_components") if isinstance(blob.get("score_components"), dict) else {},
        "score_gates": blob.get("score_gates") if isinstance(blob.get("score_gates"), dict) else {},
        "state": str(blob.get("setup_state") or blob.get("status") or ""),
        "htf_bias": str(htf.get("direction") or ""),
        "setup_id": str(blob.get("setup_id") or ""),
        "evidence": _list(blob.get("reasons")),
        "invalidations": _list(blob.get("invalidations")),
    }


def _amd_context(blob: dict[str, Any]) -> dict[str, Any] | None:
    if not (blob.get("valid") or blob.get("analysis_active")):
        return None
    inv = blob.get("invalidation")
    inv_list: list[str] = []
    if isinstance(inv, dict):
        if inv.get("reason"):
            inv_list.append(str(inv["reason"]))
        if inv.get("price"):
            inv_list.append(f"invalidation @ {inv['price']}")
    elif inv:
        inv_list = _list(inv, limit=3)
    return {
        "backend_signal": str(blob.get("decision") or "NO_TRADE"),
        "confidence": float(blob.get("confidence") or 0),
        "state": str(blob.get("setup_state") or blob.get("amd_phase") or ""),
        "htf_bias": str(blob.get("higher_timeframe_bias") or ""),
        "evidence": _list(blob.get("reasoning")),
        "invalidations": inv_list,
    }


def _box_context(blob: dict[str, Any]) -> dict[str, Any] | None:
    if not (blob.get("valid") or blob.get("analysis_active")):
        return None
    return {
        "backend_signal": str(blob.get("signal") or "WAIT"),
        "confidence": float(blob.get("confidence_score") or blob.get("confidence") or 0),
        "state": str(blob.get("box_status") or ""),
        "htf_bias": str(blob.get("htf_bias") or ""),
        "evidence": _list(blob.get("reasons")),
        "invalidations": [],
    }


def build_strategy_validation_context(status: dict[str, Any]) -> dict[str, Any]:
    """Extract authoritative backend strategy signals for AI validation."""
    ea = status.get("vantage_ea") if isinstance(status.get("vantage_ea"), dict) else {}
    brief = status.get("decision_brief") if isinstance(status.get("decision_brief"), dict) else {}
    symbol = str(status.get("selected_symbol") or ea.get("symbol") or "—")

    from app.analysis.master_verdict import build_master_verdict

    ea_connected = dict(ea)
    ea_connected["connected"] = bool(ea.get("connected") or status.get("link_health", {}).get("ea_online"))
    master = brief.get("master_verdict") if isinstance(brief.get("master_verdict"), dict) else build_master_verdict(ea_connected)

    strategies: dict[str, Any] = {}
    ict = _ict_context(_pick_blob(ea, "ict"))
    if ict:
        strategies["ICT"] = ict
    amd = _amd_context(_pick_blob(ea, "amd_ifvg"))
    if amd:
        strategies["AMD_IFVG"] = amd
    box = _box_context(_pick_blob(ea, "box_theory"))
    if box:
        strategies["BOX_THEORY"] = box

    confluence = master.get("confluence") if isinstance(master.get("confluence"), dict) else None
    if confluence is None:
        try:
            from app.analysis.confluence import compute_confluence_from_ea, confluence_config_from_settings

            conf_out = compute_confluence_from_ea(ea_connected, confluence_config_from_settings())
            confluence = {
                "overall_direction": conf_out.get("overall_direction"),
                "confidence": conf_out.get("confidence"),
                "agreement": conf_out.get("agreement"),
                "conflicting_strategies": conf_out.get("conflicting_strategies"),
                "strongest_strategy": conf_out.get("strongest_strategy"),
            }
        except Exception:
            confluence = None

    primary = "—"
    primary_conf = 0.0
    if confluence and confluence.get("overall_direction") in ("LONG", "SHORT"):
        primary = "BUY" if confluence["overall_direction"] == "LONG" else "SELL"
        primary_conf = float(confluence.get("confidence") or 0)
    elif master.get("side") in ("BUY", "SELL"):
        primary = str(master.get("side"))
        primary_conf = float(master.get("score") or 0)
    elif ict and ict.get("backend_signal") in ("BUY", "SELL"):
        primary = ict["backend_signal"]
        primary_conf = float(ict.get("confidence") or 0)

    return {
        "symbol": symbol,
        "advisory_only": True,
        "backend_authoritative": True,
        "primary_signal": primary,
        "primary_confidence": primary_conf,
        "master_verdict": {
            "verdict": master.get("verdict"),
            "side": master.get("side"),
            "score": master.get("score"),
            "summary": master.get("summary"),
            "blocks": master.get("blocks") or [],
        },
        "confluence": confluence,
        "strategies": strategies,
        "validation_rules": {
            "do_not_override_scores": True,
            "do_not_invent_prices": True,
            "allowed_assessments": ["ALIGNED", "CAUTION", "DISAGREE"],
        },
    }


def format_structured_context_section(ctx: dict[str, Any]) -> str:
    """Markdown section with authoritative JSON for the LLM."""
    payload = json.dumps(ctx, indent=2, default=str)
    return (
        "## 9. Backend strategy signals (AUTHORITATIVE — do not override)\n"
        "The JSON below is computed deterministically by the backend. "
        "Explain and contextualize it — never invent scores, states, or prices.\n\n"
        f"```json\n{payload}\n```\n"
    )


def validation_response_instructions() -> str:
    return (
        "## Required AI validation footer\n"
        "End your response with a fenced JSON block exactly matching this schema:\n"
        f"```json\n{json.dumps(AI_VALIDATION_SCHEMA, indent=2)}\n```\n"
        "Rules:\n"
        "- Use `ALIGNED` when your narrative agrees with backend signals.\n"
        "- Use `CAUTION` when you warn about timing, risk, or incomplete confluence despite backend signals.\n"
        "- Use `DISAGREE` only when you explicitly disagree with backend direction — explain why in assessment_reason.\n"
        "- Never change backend confidence numbers in prose; reference them verbatim if cited.\n"
    )


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", re.IGNORECASE)


def extract_ai_validation_block(text: str) -> dict[str, Any] | None:
    """Parse the last JSON validation block from an LLM response."""
    if not text:
        return None
    matches = _JSON_BLOCK_RE.findall(text)
    for raw in reversed(matches):
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "ai_assessment" in obj:
            return obj
    return None


def _normalize_assessment(val: Any) -> AiAssessment:
    u = str(val or "").strip().upper()
    if u in ("ALIGNED", "CAUTION", "DISAGREE"):
        return u  # type: ignore[return-value]
    return "UNKNOWN"


def validate_ai_response(ctx: dict[str, Any], ai_text: str) -> dict[str, Any]:
    """Compare LLM validation footer against authoritative backend context."""
    parsed = extract_ai_validation_block(ai_text) or {}
    assessment = _normalize_assessment(parsed.get("ai_assessment"))
    reason = str(parsed.get("assessment_reason") or "").strip()

    disagreements: list[str] = []
    primary = str(ctx.get("primary_signal") or "—")
    agrees_flag = parsed.get("agrees_with_primary_signal")

    if assessment == "UNKNOWN":
        disagreements.append("Missing or invalid ai_assessment JSON footer")

    if agrees_flag is False and assessment == "ALIGNED":
        disagreements.append("Footer claims alignment but agrees_with_primary_signal is false")
        assessment = "CAUTION"

    # Narrative keywords vs backend — lightweight sanity check
    text_u = (ai_text or "").upper()
    if primary == "BUY" and assessment == "DISAGREE":
        if any(p in text_u for p in ("STRONG SELL", "FAVOR SHORT", "BIAS BEARISH", "GO SHORT")):
            disagreements.append("Narrative language conflicts with backend BUY primary signal")
    if primary == "SELL" and assessment == "DISAGREE":
        if any(p in text_u for p in ("STRONG BUY", "FAVOR LONG", "BIAS BULLISH", "GO LONG")):
            disagreements.append("Narrative language conflicts with backend SELL primary signal")

    conf = ctx.get("confluence") if isinstance(ctx.get("confluence"), dict) else {}
    conflicts = conf.get("conflicting_strategies") if isinstance(conf.get("conflicting_strategies"), list) else []
    if conflicts and assessment == "ALIGNED" and not reason:
        assessment = "CAUTION"
        reason = reason or f"Backend reports conflicting strategies: {', '.join(conflicts)}"

    valid = assessment in ("ALIGNED", "CAUTION", "DISAGREE")

    return {
        "valid": valid,
        "ai_assessment": assessment,
        "assessment_reason": reason or None,
        "backend_authoritative": True,
        "primary_signal": primary,
        "disagreements": disagreements,
        "parsed_footer": parsed or None,
        "strategies_present": list((ctx.get("strategies") or {}).keys()),
    }
