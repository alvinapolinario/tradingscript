"""Health, analyze, heartbeat, and monitor API routes."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.analysis.decision import decide
from app.analysis.technical import validate_symbol_sanity
from app.config import Settings, get_settings
from app.monitor_state import monitor_store
from app.schemas import (
    AiAnalyzeRequest,
    AnalyzeRequest,
    AnalyzeResponse,
    CalendarMonthRequest,
    HealthResponse,
    HeartbeatRequest,
    HeartbeatResponse,
    SelectSymbolRequest,
)

router = APIRouter()


def require_bearer(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if token != settings.local_api_token:
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    monitor_store.add_log("INFO", "health", "Health check OK")
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        advisory_only=True,
        version="1.0.0",
        monitor_url="http://127.0.0.1:8000/monitor",
    )


@router.post("/api/v1/heartbeat", response_model=HeartbeatResponse)
def heartbeat(
    req: HeartbeatRequest,
    _: None = Depends(require_bearer),
) -> HeartbeatResponse:
    monitor_store.record_heartbeat(req.model_dump())
    from app.ws_hub import push_monitor_update

    push_monitor_update("heartbeat")
    cy, cm = monitor_store.calendar_request()
    # Default request to whatever month EA just sent if UI has not chosen yet
    if cy <= 0 and req.pl_calendar and req.pl_calendar.get("year") and req.pl_calendar.get("month"):
        cy = int(req.pl_calendar["year"])
        cm = int(req.pl_calendar["month"])
        monitor_store.set_calendar_month(cy, cm)
    return HeartbeatResponse(
        status="ok",
        received_utc=datetime.now(timezone.utc).isoformat(),
        monitor_url="http://127.0.0.1:8000/monitor",
        calendar_year=cy,
        calendar_month=cm,
    )


@router.post("/api/v1/monitor/calendar-month")
def set_calendar_month(req: CalendarMonthRequest) -> dict:
    try:
        out = monitor_store.set_calendar_month(req.year, req.month)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    from app.ws_hub import push_monitor_update

    push_monitor_update("calendar")
    return {"status": "ok", **out}


@router.post("/api/v1/monitor/select-symbol")
def select_monitor_symbol(req: SelectSymbolRequest) -> dict:
    symbol = (req.symbol or "").strip()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required")
    out = monitor_store.select_symbol(symbol)
    from app.ws_hub import push_monitor_update

    push_monitor_update("select_symbol")
    return {"status": "ok", **out, **monitor_store.status()}


@router.get("/api/v1/monitor/ai-brief")
def get_ai_brief(extra_question: str = Query(default="")) -> dict:
    """Markdown snapshot for Copy / paste into ChatGPT."""
    from app.analysis.ai_brief import build_ai_brief_markdown

    status = monitor_store.status()
    md = build_ai_brief_markdown(status, extra_question=extra_question or None)
    return {
        "status": "ok",
        "symbol": status.get("selected_symbol") or "",
        "markdown": md,
        "llm": _llm_public(),
    }


@router.post("/api/v1/monitor/ai-analyze")
def ai_analyze(req: AiAnalyzeRequest) -> dict:
    """Server-side OpenAI analysis of the current monitor snapshot."""
    from app.analysis.ai_brief import build_ai_brief_markdown
    from app.analysis.openai_client import analyze_with_openai, llm_status

    settings = get_settings()
    st = llm_status(settings)
    if not st.ready:
        raise HTTPException(status_code=400, detail=st.detail)

    if req.symbol.strip():
        monitor_store.select_symbol(req.symbol.strip())

    status = monitor_store.status()
    symbol = status.get("selected_symbol") or ""
    snapshot = build_ai_brief_markdown(status, extra_question=req.extra_question or None)
    try:
        result = analyze_with_openai(
            snapshot,
            symbol=symbol,
            extra_question=req.extra_question or "",
            settings=settings,
            bypass_cache=req.bypass_cache,
        )
    except RuntimeError as exc:
        monitor_store.add_log("ERROR", "llm", str(exc))
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    monitor_store.add_log(
        "INFO",
        "llm",
        f"OpenAI analyze {symbol} model={result.get('model')} cached={result.get('cached')}",
    )
    return {
        **result,
        "snapshot_markdown": snapshot,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "llm": _llm_public(),
    }


@router.get("/api/v1/monitor/llm-status")
def get_llm_status() -> dict:
    return {"status": "ok", "llm": _llm_public()}


def _llm_public() -> dict:
    from app.analysis.openai_client import llm_status

    st = llm_status(get_settings())
    return {
        "enabled": st.enabled,
        "configured": st.configured,
        "ready": st.ready,
        "model": st.model,
        "detail": st.detail,
    }


@router.post("/api/v1/analyze", response_model=AnalyzeResponse)
def analyze(
    req: AnalyzeRequest,
    _: None = Depends(require_bearer),
) -> AnalyzeResponse:
    dumped = req.model_dump()
    broker = dumped.get("broker") or {}
    for forbidden in ("login", "account_login", "account_number", "ACCOUNT_LOGIN"):
        if forbidden in dumped or forbidden in broker:
            raise HTTPException(status_code=400, detail=f"Forbidden field in payload: {forbidden}")

    if req.mode != "advisory_only":
        raise HTTPException(status_code=400, detail="Only advisory_only mode is accepted")

    validate_symbol_sanity(req)
    resp = decide(req)
    monitor_store.record_analyze(
        {
            "symbol": req.symbol.name,
            "trend": req.structure.trend,
            "environment": req.environment,
            "spread_points": req.prices.spread_points,
            "positions": req.positions.count,
            "action": resp.action.value,
            "new_entry_decision": resp.new_entry_decision.value,
            "existing_position_decision": resp.existing_position_decision.value,
            "risk_status": resp.risk_status.value,
            "market_state": resp.market_state,
            "equity_risk_pct": resp.equity_risk_pct,
        },
        resp.action.value,
    )
    from app.ws_hub import push_monitor_update

    push_monitor_update("analyze")
    return resp


@router.get("/api/v1/monitor/status")
def monitor_status() -> dict:
    return monitor_store.status()


@router.get("/api/v1/dashboard/status")
def dashboard_status() -> dict:
    """M5 Alignment Desk — separate from the M30 advisory cockpit."""
    from app.strategy_desk import build_dashboard

    return build_dashboard(monitor_store.status())


@router.get("/api/v1/monitor/logs")
def monitor_logs(limit: int = Query(default=100, ge=1, le=300)) -> dict:
    return {"items": monitor_store.logs(limit)}
