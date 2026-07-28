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
    base = (settings.public_base_url or "http://187.77.142.118:8000").rstrip("/")
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        advisory_only=True,
        version="1.2.0",
        monitor_url=f"{base}/monitor",
    )


@router.post("/api/v1/heartbeat", response_model=HeartbeatResponse)
def heartbeat(
    req: HeartbeatRequest,
    _: None = Depends(require_bearer),
) -> HeartbeatResponse:
    monitor_store.record_heartbeat(req.model_dump())
    from app.signal_ledger import maybe_accept_from_monitor
    from app.ws_hub import push_monitor_update

    accepted = None
    try:
        mode = monitor_store.analyzer_mode()
        accepted = maybe_accept_from_monitor(monitor_store.status(), mode=mode)
    except Exception as exc:  # never fail EA heartbeat on ledger issues
        monitor_store.add_log("ERROR", "signals", f"Ledger accept failed: {exc}")
    push_monitor_update("heartbeat")
    if accepted:
        monitor_store.add_log(
            "INFO",
            "signals",
            f"Accepted {accepted.get('side')} {accepted.get('symbol')} score={accepted.get('score')}",
            signal_id=accepted.get("id"),
        )
        push_monitor_update("signal")
    cy, cm = monitor_store.calendar_request()
    # Default request to whatever month EA just sent if UI has not chosen yet
    if cy <= 0 and req.pl_calendar and req.pl_calendar.get("year") and req.pl_calendar.get("month"):
        cy = int(req.pl_calendar["year"])
        cm = int(req.pl_calendar["month"])
        monitor_store.set_calendar_month(cy, cm)
    settings = get_settings()
    base = (settings.public_base_url or "http://187.77.142.118:8000").rstrip("/")
    return HeartbeatResponse(
        status="ok",
        received_utc=datetime.now(timezone.utc).isoformat(),
        monitor_url=f"{base}/monitor",
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
    if req.pending_orders is not None:
        monitor_store.update_pending_orders(
            req.symbol.name,
            req.pending_orders.model_dump(),
            bid=req.prices.bid,
            ask=req.prices.ask,
            trend=req.structure.trend,
            position_count=req.positions.count,
            total_buy_volume=req.positions.total_buy_volume,
            total_sell_volume=req.positions.total_sell_volume,
            max_position_risk_pct=(req.extra or {}).get("max_position_risk_pct"),
        )
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


@router.get("/api/v1/orders/pending")
def pending_orders_status() -> dict:
    """MT5 pending-order advisory desk — risk, trend, suggestions (no order mutations)."""
    from app.analysis.pending_orders import build_pending_orders_status

    return build_pending_orders_status(monitor_store.status())


@router.get("/api/v1/pullback/status")
def pullback_status() -> dict:
    """Pullback Probability Analyzer — EA-computed advisory blob (passthrough)."""
    st = monitor_store.status()
    ea = st.get("vantage_ea") or {}
    link = st.get("link_health") or {}
    pb = ea.get("pullback")
    selected = str(st.get("selected_symbol") or ea.get("symbol") or "").upper()
    return {
        "advisory_only": True,
        "caption": "Advisory only — never places, modifies, or cancels MT5 orders.",
        "ea_online": bool(link.get("ea_online") or ea.get("connected")),
        "pullback_supported": bool(ea.get("pullback_supported")),
        "selected_symbol": selected,
        "symbol": str(ea.get("symbol") or selected).upper(),
        "available_symbols": list(st.get("available_symbols") or []),
        "symbols": list(st.get("symbols") or []),
        "digits": int(ea.get("digits") or 5) or 5,
        "bid": ea.get("bid"),
        "ask": ea.get("ask"),
        "pullback": pb,
        "links": {"pullback": "/pullback", "analyzer": "/analyzer", "monitor": "/monitor"},
    }


@router.get("/api/v1/signals")
def list_accepted_signals(
    limit: int = Query(default=50, ge=1, le=200),
    symbol: str | None = Query(default=None),
) -> dict:
    """Accepted Signal Ledger — advisory BUY/SELL history from M5 desk."""
    from app.signal_ledger import list_signals

    items = list_signals(limit=limit, symbol=(symbol.strip().upper() if symbol else None))
    return {
        "advisory_only": True,
        "count": len(items),
        "items": items,
    }


@router.get("/api/v1/analyzer/status")
def analyzer_status(
    mode: str = Query(default="STANDARD"),
    timeframe: str | None = Query(default=None),
) -> dict:
    """Smart Analyzer composite — desk + active signal + votes (advisory)."""
    from app.signal_ledger import build_analyzer_status

    monitor_store.set_analyzer_mode(mode)
    return build_analyzer_status(monitor_store.status(), mode=mode, timeframe=timeframe)


@router.post("/api/v1/signals/{signal_id}/decision")
def signal_decision(signal_id: str, body: dict) -> dict:
    """Record TAKE or IGNORE — does not send any MT5 order."""
    from app.signal_ledger import record_decision
    from app.ws_hub import push_monitor_update

    decision = str((body or {}).get("decision") or "").upper()
    try:
        updated = record_decision(signal_id, decision)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not updated:
        raise HTTPException(status_code=404, detail="Signal not found")
    monitor_store.add_log(
        "INFO",
        "signals",
        f"User {decision} on {updated.get('side')} {updated.get('symbol')}",
        signal_id=signal_id,
    )
    push_monitor_update("signal_decision")
    return {
        "advisory_only": True,
        "ok": True,
        "caption": "Records your decision only — no MT5 order is sent.",
        "signal": updated,
    }


@router.get("/api/v1/patterns/status")
def patterns_status() -> dict:
    from app.strategy_workspace import build_patterns

    return build_patterns(monitor_store.status())


@router.get("/api/v1/scanner/status")
def scanner_status() -> dict:
    from app.strategy_workspace import build_scanner

    base = monitor_store.status()
    return build_scanner(base, monitor_store.pair_statuses())


@router.get("/api/v1/lab/status")
def lab_status() -> dict:
    from app.strategy_workspace import build_lab

    return build_lab(monitor_store.status())


@router.post("/api/v1/lab/simulate")
def lab_simulate(body: dict | None = None) -> dict:
    """What-if evaluation without saving session overrides."""
    from app.strategy_workspace import build_lab, sanitize_lab_overrides

    trial = sanitize_lab_overrides(body or {})
    return build_lab(monitor_store.status(), trial_overrides=trial)


@router.post("/api/v1/lab/apply")
def lab_apply(body: dict | None = None) -> dict:
    """Persist Strategy Lab overrides for this backend session."""
    from app.strategy_workspace import build_lab, sanitize_lab_overrides
    from app.ws_hub import push_monitor_update

    overrides = sanitize_lab_overrides(body or {})
    monitor_store.set_lab_overrides(overrides)
    monitor_store.add_log("INFO", "lab", f"Session overrides applied: {overrides or '{}'}")
    push_monitor_update("lab")
    return build_lab(monitor_store.status())


@router.post("/api/v1/lab/reset")
def lab_reset() -> dict:
    from app.strategy_workspace import build_lab
    from app.ws_hub import push_monitor_update

    monitor_store.clear_lab_overrides()
    monitor_store.add_log("INFO", "lab", "Session overrides reset to playbook defaults")
    push_monitor_update("lab")
    return build_lab(monitor_store.status())


@router.get("/api/v1/monitor/logs")
def monitor_logs(limit: int = Query(default=100, ge=1, le=300)) -> dict:
    return {"items": monitor_store.logs(limit)}
