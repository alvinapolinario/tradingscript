"""OpenAI Chat Completions client (httpx). Key stays server-side only."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.analysis.ai_brief import SYSTEM_PROMPT
from app.config import Settings, get_settings

# Simple in-process cache: (symbol, question_hash) -> (expires, payload)
_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_TTL_SEC = 60.0


@dataclass
class LlmStatus:
    enabled: bool
    configured: bool
    model: str
    ready: bool
    detail: str


def llm_status(settings: Settings | None = None) -> LlmStatus:
    s = settings or get_settings()
    key = (s.openai_api_key or "").strip()
    configured = bool(key)
    enabled = bool(s.use_llm)
    ready = enabled and configured
    if not enabled:
        detail = "USE_LLM=false — enable in backend .env"
    elif not configured:
        detail = "OPENAI_API_KEY missing — set in backend .env (never in the EA)"
    else:
        detail = f"Ready ({s.openai_model})"
    return LlmStatus(
        enabled=enabled,
        configured=configured,
        model=s.openai_model,
        ready=ready,
        detail=detail,
    )


def _cache_key(symbol: str, question: str) -> str:
    return f"{symbol}|{hash(question)}"


def analyze_with_openai(
    snapshot_markdown: str,
    *,
    symbol: str = "",
    extra_question: str = "",
    settings: Settings | None = None,
    bypass_cache: bool = False,
    structured_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    s = settings or get_settings()
    status = llm_status(s)
    if not status.ready:
        raise RuntimeError(status.detail)

    q = (extra_question or "").strip()
    ck = _cache_key(symbol or "?", q or snapshot_markdown[:200])
    now = time.time()
    if not bypass_cache and ck in _cache:
        exp, payload = _cache[ck]
        if exp > now:
            return {**payload, "cached": True}

    user_content = snapshot_markdown
    if q:
        user_content += f"\n\n## Trader follow-up\n{q}\n"

    headers = {
        "Authorization": f"Bearer {s.openai_api_key.strip()}",
        "Content-Type": "application/json",
    }
    body = {
        "model": s.openai_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    }
    # GPT-5.6 family only allows default temperature; older models can tune it
    model_l = (s.openai_model or "").lower()
    if not model_l.startswith("gpt-5.6"):
        body["temperature"] = 0.3

    with httpx.Client(timeout=60.0) as client:
        r = client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body)
        if r.status_code >= 400:
            detail = r.text[:500]
            raise RuntimeError(f"OpenAI HTTP {r.status_code}: {detail}")
        data = r.json()

    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("OpenAI response missing message content") from exc

    usage = data.get("usage") or {}
    validation: dict[str, Any] | None = None
    if structured_context:
        from app.analysis.ai_validation import validate_ai_response

        validation = validate_ai_response(structured_context, text.strip())

    payload = {
        "status": "ok",
        "model": data.get("model") or s.openai_model,
        "analysis_markdown": text.strip(),
        "symbol": symbol,
        "cached": False,
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        },
    }
    if structured_context is not None:
        payload["structured_context"] = structured_context
    if validation is not None:
        payload["ai_validation"] = validation
    _cache[ck] = (now + _CACHE_TTL_SEC, payload)
    return payload
