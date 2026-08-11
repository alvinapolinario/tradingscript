"""Health, analyze, heartbeat, and monitor API routes."""
from __future__ import annotations

import json
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
    MarketNewsAnalyzeRequest,
    MarketNewsIngestRequest,
    Mt5CalendarIngestRequest,
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
    from app.discord_notify import discord_status
    from app.telegram_notify import telegram_status

    base = (settings.public_base_url or "http://187.77.142.118:8000").rstrip("/")
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        advisory_only=True,
        version="1.2.0",
        monitor_url=f"{base}/monitor",
        telegram=telegram_status(settings),
        discord=discord_status(settings),
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
    try:
        from app.alert_notify import process_heartbeat

        process_heartbeat(req.model_dump(), accepted)
    except Exception as exc:
        monitor_store.add_log("WARN", "alerts", f"Heartbeat notify failed: {exc}")
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
    from app.analysis.ai_brief import build_ai_brief_payload

    status = monitor_store.status()
    brief = build_ai_brief_payload(status, extra_question=extra_question or None)
    return {
        "status": "ok",
        "symbol": status.get("selected_symbol") or "",
        "markdown": brief["markdown"],
        "structured_context": brief["structured_context"],
        "llm": _llm_public(),
    }


@router.post("/api/v1/monitor/ai-analyze")
def ai_analyze(req: AiAnalyzeRequest) -> dict:
    """Server-side OpenAI analysis of the current monitor snapshot."""
    from app.analysis.ai_brief import build_ai_brief_payload
    from app.analysis.openai_client import analyze_with_openai, llm_status

    settings = get_settings()
    st = llm_status(settings)
    if not st.ready:
        raise HTTPException(status_code=400, detail=st.detail)

    if req.symbol.strip():
        monitor_store.select_symbol(req.symbol.strip())

    status = monitor_store.status()
    symbol = status.get("selected_symbol") or ""
    brief = build_ai_brief_payload(status, extra_question=req.extra_question or None)
    snapshot = brief["markdown"]
    structured_context = brief["structured_context"]
    try:
        result = analyze_with_openai(
            snapshot,
            symbol=symbol,
            extra_question=req.extra_question or "",
            settings=settings,
            bypass_cache=req.bypass_cache,
            structured_context=structured_context,
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


_monitor_alert_test_at: dict[str, float] = {}


def _monitor_alert_test_cooldown(channel: str, *, sec: float = 30.0) -> None:
    import time

    now = time.time()
    last = _monitor_alert_test_at.get(channel, 0.0)
    if now - last < sec:
        raise HTTPException(status_code=429, detail=f"Wait {int(sec)}s between {channel} tests")
    _monitor_alert_test_at[channel] = now


@router.post("/api/v1/monitor/discord/test")
def monitor_discord_test() -> dict:
    """Send Discord test from monitor UI (no Bearer — same as other /monitor routes)."""
    from app.discord_notify import discord_status, send_test_message

    _monitor_alert_test_cooldown("discord")
    ok, detail = send_test_message()
    if not ok:
        raise HTTPException(status_code=400, detail=detail or "Discord send failed")
    return {"ok": True, "detail": detail, "discord": discord_status()}


@router.post("/api/v1/monitor/telegram/test")
def monitor_telegram_test() -> dict:
    """Send Telegram test from monitor UI (no Bearer — same as other /monitor routes)."""
    from app.telegram_notify import send_test_message, telegram_status

    _monitor_alert_test_cooldown("telegram")
    ok, detail = send_test_message()
    if not ok:
        raise HTTPException(status_code=400, detail=detail or "Telegram send failed")
    return {"ok": True, "detail": detail, "telegram": telegram_status()}


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


@router.get("/api/v1/gold-smc/status")
def gold_smc_status() -> dict:
    """Gold SMC Intelligence — EA-computed advisory blob (passthrough; Gold-only)."""
    st = monitor_store.status()
    ea = st.get("vantage_ea") or {}
    link = st.get("link_health") or {}
    blob = ea.get("gold_smc")
    selected = str(st.get("selected_symbol") or ea.get("symbol") or "").upper()
    return {
        "advisory_only": True,
        "caption": "Advisory only — never places, modifies, or cancels MT5 orders. Gold / XAUUSD only.",
        "ea_online": bool(link.get("ea_online") or ea.get("connected")),
        "gold_smc_supported": bool(ea.get("gold_smc_supported")),
        "selected_symbol": selected,
        "symbol": str(ea.get("symbol") or selected).upper(),
        "available_symbols": list(st.get("available_symbols") or []),
        "symbols": list(st.get("symbols") or []),
        "digits": int(ea.get("digits") or 5) or 5,
        "bid": ea.get("bid"),
        "ask": ea.get("ask"),
        "gold_smc": blob,
        "links": {"gold_smc": "/gold-smc", "pullback": "/pullback", "analyzer": "/analyzer", "monitor": "/monitor"},
    }


@router.get("/api/v1/liquidity-grab/status")
def liquidity_grab_status() -> dict:
    """Liquidity Grab Monitor — EA-computed advisory blob (passthrough; Gold-only)."""
    st = monitor_store.status()
    ea = st.get("vantage_ea") or {}
    link = st.get("link_health") or {}
    blob = ea.get("liquidity_grab")
    selected = str(st.get("selected_symbol") or ea.get("symbol") or "").upper()
    return {
        "advisory_only": True,
        "caption": "Advisory only — never places, modifies, or cancels MT5 orders. Gold / XAUUSD only.",
        "ea_online": bool(link.get("ea_online") or ea.get("connected")),
        "liquidity_grab_supported": bool(ea.get("liquidity_grab_supported")),
        "selected_symbol": selected,
        "symbol": str(ea.get("symbol") or selected).upper(),
        "available_symbols": list(st.get("available_symbols") or []),
        "symbols": list(st.get("symbols") or []),
        "digits": int(ea.get("digits") or 5) or 5,
        "bid": ea.get("bid"),
        "ask": ea.get("ask"),
        "liquidity_grab": blob,
        "links": {
            "liquidity_grab": "/liquidity-grab",
            "gold_smc": "/gold-smc",
            "pullback": "/pullback",
            "analyzer": "/analyzer",
            "monitor": "/monitor",
        },
    }


@router.get("/api/v1/breakout-structure/status")
def breakout_structure_status() -> dict:
    """Breakout Structure Intelligence — EA-computed advisory blob (passthrough; Gold-only)."""
    st = monitor_store.status()
    ea = st.get("vantage_ea") or {}
    link = st.get("link_health") or {}
    blob = ea.get("breakout_structure")
    selected = str(st.get("selected_symbol") or ea.get("symbol") or "").upper()
    return {
        "advisory_only": True,
        "caption": "Advisory only — never places, modifies, or cancels MT5 orders. Gold / XAUUSD only.",
        "ea_online": bool(link.get("ea_online") or ea.get("connected")),
        "breakout_structure_supported": bool(ea.get("breakout_structure_supported")),
        "selected_symbol": selected,
        "symbol": str(ea.get("symbol") or selected).upper(),
        "available_symbols": list(st.get("available_symbols") or []),
        "symbols": list(st.get("symbols") or []),
        "digits": int(ea.get("digits") or 5) or 5,
        "bid": ea.get("bid"),
        "ask": ea.get("ask"),
        "breakout_structure": blob,
        "links": {
            "breakout_structure": "/breakout-structure",
            "liquidity_grab": "/liquidity-grab",
            "gold_smc": "/gold-smc",
            "pullback": "/pullback",
            "analyzer": "/analyzer",
            "monitor": "/monitor",
        },
    }


@router.get("/api/v1/market-state/status")
def market_state_status() -> dict:
    """Institutional Market State Engine v2 — EA-computed lifecycle blob (passthrough; Gold-only)."""
    st = monitor_store.status()
    ea = st.get("vantage_ea") or {}
    link = st.get("link_health") or {}
    blob = ea.get("market_state_engine")
    selected = str(st.get("selected_symbol") or ea.get("symbol") or "").upper()
    return {
        "advisory_only": True,
        "caption": "Advisory only — never places, modifies, or cancels MT5 orders. Gold / XAUUSD only.",
        "ea_online": bool(link.get("ea_online") or ea.get("connected")),
        "market_state_engine_supported": bool(ea.get("market_state_engine_supported")),
        "selected_symbol": selected,
        "symbol": str(ea.get("symbol") or selected).upper(),
        "available_symbols": list(st.get("available_symbols") or []),
        "symbols": list(st.get("symbols") or []),
        "digits": int(ea.get("digits") or 5) or 5,
        "bid": ea.get("bid"),
        "ask": ea.get("ask"),
        "market_state_engine": blob,
        "links": {
            "market_state": "/market-state",
            "breakout_structure": "/breakout-structure",
            "liquidity_grab": "/liquidity-grab",
            "gold_smc": "/gold-smc",
            "pullback": "/pullback",
            "analyzer": "/analyzer",
            "monitor": "/monitor",
        },
    }


@router.get("/api/v1/swing-strategy/status")
def swing_strategy_status() -> dict:
    """Swing Strategy Engine — EA-computed advisory blob (passthrough; Gold-only)."""
    st = monitor_store.status()
    ea = st.get("vantage_ea") or {}
    link = st.get("link_health") or {}
    blob = ea.get("swing_strategy")
    selected = str(st.get("selected_symbol") or ea.get("symbol") or "").upper()
    return {
        "advisory_only": True,
        "caption": "Advisory only — never places, modifies, or cancels MT5 orders. Gold / XAUUSD only.",
        "ea_online": bool(link.get("ea_online") or ea.get("connected")),
        "swing_strategy_supported": bool(ea.get("swing_strategy_supported")),
        "selected_symbol": selected,
        "symbol": str(ea.get("symbol") or selected).upper(),
        "available_symbols": list(st.get("available_symbols") or []),
        "symbols": list(st.get("symbols") or []),
        "digits": int(ea.get("digits") or 5) or 5,
        "bid": ea.get("bid"),
        "ask": ea.get("ask"),
        "swing_strategy": blob,
        "links": {
            "swing_strategy": "/swing-strategy",
            "market_state": "/market-state",
            "breakout_structure": "/breakout-structure",
            "gold_smc": "/gold-smc",
            "pullback": "/pullback",
            "analyzer": "/analyzer",
            "monitor": "/monitor",
        },
    }


@router.get("/api/v1/amd-ifvg/status")
def amd_ifvg_status() -> dict:
    """AMD + iFVG Strategy — EA-computed advisory blob (passthrough; Gold-only)."""
    st = monitor_store.status()
    ea = st.get("vantage_ea") or {}
    link = st.get("link_health") or {}
    blob = ea.get("amd_ifvg")
    selected = str(st.get("selected_symbol") or ea.get("symbol") or "").upper()
    return {
        "advisory_only": True,
        "caption": "Advisory only — never places, modifies, or cancels MT5 orders. Gold / XAUUSD only.",
        "ea_online": bool(link.get("ea_online") or ea.get("connected")),
        "amd_ifvg_supported": bool(ea.get("amd_ifvg_supported")),
        "selected_symbol": selected,
        "symbol": str(ea.get("symbol") or selected).upper(),
        "available_symbols": list(st.get("available_symbols") or []),
        "symbols": list(st.get("symbols") or []),
        "digits": int(ea.get("digits") or 5) or 5,
        "bid": ea.get("bid"),
        "ask": ea.get("ask"),
        "amd_ifvg": blob,
        "links": {
            "amd_ifvg": "/amd-ifvg",
            "liquidity_grab": "/liquidity-grab",
            "gold_smc": "/gold-smc",
            "swing_strategy": "/swing-strategy",
            "pullback": "/pullback",
            "analyzer": "/analyzer",
            "monitor": "/monitor",
        },
    }


@router.post("/api/v1/amd-ifvg/analyze")
def amd_ifvg_analyze(body: dict) -> dict:
    """Offline AMD + iFVG analysis from supplied closed candles (no look-ahead)."""
    from app.analysis.amd_ifvg_logic import analyze_amd_ifvg, candles_from_payload

    payload = body or {}
    symbol = str(payload.get("symbol") or payload.get("broker_symbol") or "XAUUSD").upper()
    candles_raw = payload.get("candles") if isinstance(payload.get("candles"), dict) else {}
    market = payload.get("market") if isinstance(payload.get("market"), dict) else {}

    setup_rows = candles_raw.get("M15") or candles_raw.get("setup") or []
    entry_rows = candles_raw.get("M5") or candles_raw.get("entry") or setup_rows
    bias_rows = candles_raw.get("H1") or candles_raw.get("bias") or setup_rows

    candles_setup = candles_from_payload(setup_rows if isinstance(setup_rows, list) else [])
    candles_entry = candles_from_payload(entry_rows if isinstance(entry_rows, list) else [])
    candles_bias = candles_from_payload(bias_rows if isinstance(bias_rows, list) else [])

    bid = float(market.get("bid") or 0)
    ask = float(market.get("ask") or 0)
    spread = float(market.get("spread_points") or market.get("spread") or 0)

    return analyze_amd_ifvg(
        symbol=symbol,
        candles_setup=candles_setup,
        candles_entry=candles_entry,
        candles_bias=candles_bias,
        bid=bid,
        ask=ask,
        spread_points=spread,
    )


@router.get("/api/v1/box-theory/status")
def box_theory_status() -> dict:
    """Box Theory Strategy — EA-computed or backend-analyzed advisory blob (Gold-only)."""
    st = monitor_store.status()
    ea = st.get("vantage_ea") or {}
    link = st.get("link_health") or {}
    blob = ea.get("box_theory")
    selected = str(st.get("selected_symbol") or ea.get("symbol") or "").upper()
    return {
        "advisory_only": True,
        "caption": "Advisory only — never places, modifies, or cancels MT5 orders. Gold / XAUUSD only.",
        "ea_online": bool(link.get("ea_online") or ea.get("connected")),
        "box_theory_supported": bool(ea.get("box_theory_supported")),
        "selected_symbol": selected,
        "symbol": str(ea.get("symbol") or selected).upper(),
        "available_symbols": list(st.get("available_symbols") or []),
        "digits": int(ea.get("digits") or 5) or 5,
        "bid": ea.get("bid"),
        "ask": ea.get("ask"),
        "modules_detected": {
            "amd_ifvg": bool(ea.get("amd_ifvg_supported")),
            "liquidity_grab": bool(ea.get("liquidity_grab_supported")),
            "swing_strategy": bool(ea.get("swing_strategy_supported")),
            "box_theory": bool(ea.get("box_theory_supported")),
        },
        "box_theory": blob,
        "links": {
            "box_theory": "/box-theory",
            "amd_ifvg": "/amd-ifvg",
            "liquidity_grab": "/liquidity-grab",
            "gold_smc": "/gold-smc",
            "swing_strategy": "/swing-strategy",
            "pullback": "/pullback",
            "analyzer": "/analyzer",
            "monitor": "/monitor",
        },
    }


@router.post("/api/v1/box-theory/analyze")
def box_theory_analyze(body: dict) -> dict:
    """Offline Box Theory analysis from supplied closed candles (no look-ahead)."""
    from app.analysis.box_theory import analyze_box_strategy, candles_from_payload
    from app.analysis.box_theory.history import record_box_result
    from app.analysis.box_theory.types import BoxStrategyConfig
    from app.box_discord_notify import maybe_box_theory_alert

    payload = body or {}
    symbol = str(payload.get("symbol") or payload.get("broker_symbol") or "XAUUSD").upper()
    candles_raw = payload.get("candles") if isinstance(payload.get("candles"), dict) else {}
    market = payload.get("market") if isinstance(payload.get("market"), dict) else {}
    cfg_raw = payload.get("config") if isinstance(payload.get("config"), dict) else {}

    box_rows = candles_raw.get("M15") or candles_raw.get("box") or []
    entry_rows = candles_raw.get("M5") or candles_raw.get("entry") or box_rows
    struct_rows = candles_raw.get("H1") or candles_raw.get("structure") or box_rows

    candles_box = candles_from_payload(box_rows if isinstance(box_rows, list) else [])
    candles_entry = candles_from_payload(entry_rows if isinstance(entry_rows, list) else [])
    candles_structure = candles_from_payload(struct_rows if isinstance(struct_rows, list) else [])

    cfg = BoxStrategyConfig(**{k: v for k, v in cfg_raw.items() if hasattr(BoxStrategyConfig, k)})
    bid = float(market.get("bid") or 0)

    result = analyze_box_strategy(
        symbol=symbol,
        candles_box=candles_box,
        candles_entry=candles_entry,
        candles_structure=candles_structure,
        bid=bid,
        cfg=cfg,
    )
    record_box_result(symbol, result)
    maybe_box_theory_alert({"box_theory": result})
    return result


@router.get("/api/v1/strategies/box/{symbol}")
def box_strategy_summary(symbol: str) -> dict:
    """Compact Box Theory status for a symbol."""
    sym = symbol.strip().upper()
    st = monitor_store.status()
    ea = st.get("vantage_ea") or {}
    blob = ea.get("box_theory") if isinstance(ea.get("box_theory"), dict) else {}
    if str(blob.get("symbol") or "").upper() not in ("", sym):
        blob = {}
    return {
        "success": True,
        "strategy": "BOX_THEORY",
        "symbol": sym,
        "box_status": blob.get("box_status") or blob.get("status") or "FORMING",
        "signal": blob.get("signal") or "WAIT",
        "confidence": blob.get("confidence_score") or blob.get("confidence") or 0,
        "advisory_only": True,
    }


@router.get("/api/v1/strategies/box/{symbol}/history")
def box_strategy_history(symbol: str, limit: int = Query(default=20, ge=1, le=100)) -> dict:
    """Historical Box Theory snapshots recorded on this backend instance."""
    from app.analysis.box_theory.history import list_box_history

    sym = symbol.strip().upper()
    items = list_box_history(sym, limit=limit)
    return {"success": True, "symbol": sym, "count": len(items), "items": items}


@router.get("/api/v1/ict/status")
def ict_status() -> dict:
    """ICT Strategy — EA-computed or backend-analyzed advisory blob (Gold-only)."""
    from app.analysis.ict.history import list_ict_history
    from app.analysis.ict.state_store import get_active_setup, record_to_dict

    st = monitor_store.status()
    ea = st.get("vantage_ea") or {}
    link = st.get("link_health") or {}
    selected = str(st.get("selected_symbol") or ea.get("symbol") or "").upper()
    blob = ea.get("ict") if isinstance(ea.get("ict"), dict) else None
    backend_active = False

    if not blob and selected:
        active = get_active_setup(selected, "M15")
        if active:
            backend_active = True
            hist = list_ict_history(selected, limit=1)
            blob = hist[0] if hist else None
            if not blob:
                blob = {
                    "strategy": "ICT",
                    "setup_record": record_to_dict(active),
                    "status": active.state.value,
                }

    return {
        "advisory_only": True,
        "caption": "Advisory only — never places, modifies, or cancels MT5 orders. Gold / XAUUSD only.",
        "ea_online": bool(link.get("ea_online") or ea.get("connected")),
        "ict_supported": bool(ea.get("ict_supported")) or backend_active,
        "backend_engine_available": True,
        "selected_symbol": selected,
        "symbol": str(ea.get("symbol") or selected).upper(),
        "available_symbols": list(st.get("available_symbols") or []),
        "symbols": list(st.get("symbols") or []),
        "digits": int(ea.get("digits") or 5) or 5,
        "bid": ea.get("bid"),
        "ask": ea.get("ask"),
        "modules_detected": {
            "amd_ifvg": bool(ea.get("amd_ifvg_supported")),
            "box_theory": bool(ea.get("box_theory_supported")),
            "liquidity_grab": bool(ea.get("liquidity_grab_supported")),
            "swing_strategy": bool(ea.get("swing_strategy_supported")),
            "ict": bool(ea.get("ict_supported")),
        },
        "ict": blob,
        "links": {
            "ict": "/ict",
            "box_theory": "/box-theory",
            "amd_ifvg": "/amd-ifvg",
            "gold_smc": "/gold-smc",
            "liquidity_grab": "/liquidity-grab",
            "swing_strategy": "/swing-strategy",
            "pullback": "/pullback",
            "analyzer": "/analyzer",
            "monitor": "/monitor",
        },
    }


def _ict_candles_from_request(candles_raw: dict) -> tuple[dict, list, list]:
    """Parse multi-TF candle payload → (by_timeframe, setup, execution)."""
    from app.analysis.ict import candles_from_payload

    by_tf: dict = {}
    for key, rows in candles_raw.items():
        if isinstance(rows, list):
            by_tf[str(key).upper()] = candles_from_payload(rows)

    setup = (
        by_tf.get("M15")
        or by_tf.get("SETUP")
        or by_tf.get("H1")
        or next(iter(by_tf.values()), [])
    )
    execution = by_tf.get("M5") or by_tf.get("ENTRY") or setup
    return by_tf, setup, execution


@router.post("/api/v1/ict/analyze")
@router.post("/api/v1/strategy/ict/analyze")
def ict_analyze(body: dict) -> dict:
    """Offline ICT analysis from supplied closed candles (no look-ahead)."""
    from app.analysis.ict import analyze_ict_strategy
    from app.analysis.ict.types import IctConfig

    payload = body or {}
    symbol = str(payload.get("symbol") or payload.get("broker_symbol") or "XAUUSD").upper()
    timeframe = str(payload.get("timeframe") or "M15").upper()
    candles_raw = payload.get("candles") if isinstance(payload.get("candles"), dict) else {}
    market = payload.get("market") if isinstance(payload.get("market"), dict) else {}
    cfg_raw = payload.get("config") if isinstance(payload.get("config"), dict) else {}

    by_tf, setup, execution = _ict_candles_from_request(candles_raw)
    cfg_kwargs = {k: v for k, v in cfg_raw.items() if hasattr(IctConfig, k)}
    cfg = IctConfig(**cfg_kwargs)
    if timeframe and timeframe != cfg.primary_setup_timeframe:
        from dataclasses import replace

        cfg = replace(cfg, primary_setup_timeframe=timeframe)

    bid = float(market.get("bid") or 0)
    spread = float(market.get("spread_points") or market.get("spread") or 0)

    result = analyze_ict_strategy(
        symbol=symbol,
        candles_by_timeframe=by_tf or None,
        candles_setup=setup,
        candles_execution=execution,
        bid=bid,
        spread_points=spread,
        cfg=cfg,
    )
    try:
        from app.ict_discord_notify import maybe_ict_alert

        maybe_ict_alert({"ict": result})
    except Exception:
        pass
    return result


@router.get("/api/v1/strategies/ict/{symbol}")
def ict_strategy_summary(symbol: str) -> dict:
    """Compact ICT status for a symbol."""
    from app.analysis.ict.history import list_ict_history

    sym = symbol.strip().upper()
    st = monitor_store.status()
    ea = st.get("vantage_ea") or {}
    blob = ea.get("ict") if isinstance(ea.get("ict"), dict) else {}
    if str(blob.get("symbol") or "").upper() not in ("", sym):
        blob = {}
    if not blob:
        hist = list_ict_history(sym, limit=1)
        blob = hist[0] if hist else {}
    return {
        "success": True,
        "strategy": "ICT",
        "symbol": sym,
        "status": blob.get("status") or blob.get("setup_state") or "WAITING_FOR_LIQUIDITY",
        "decision": blob.get("decision") or "WAIT",
        "confidence": blob.get("confidence_score") or blob.get("confidence") or 0,
        "setup_id": blob.get("setup_id") or "",
        "advisory_only": True,
    }


@router.get("/api/v1/strategies/ict/{symbol}/history")
def ict_strategy_history(symbol: str, limit: int = Query(default=20, ge=1, le=100)) -> dict:
    """Historical ICT snapshots recorded on this backend instance."""
    from app.analysis.ict.history import list_ict_history

    sym = symbol.strip().upper()
    items = list_ict_history(sym, limit=limit)
    return {"success": True, "symbol": sym, "count": len(items), "items": items}


@router.post("/api/v1/confluence/analyze")
def confluence_analyze(body: dict) -> dict:
    """Multi-strategy confluence from a heartbeat-like EA payload."""
    from app.analysis.confluence import compute_confluence_from_ea, confluence_config_from_settings

    payload = body or {}
    ea = payload.get("ea") if isinstance(payload.get("ea"), dict) else payload
    ea = dict(ea)
    ea.setdefault("connected", True)
    cfg = confluence_config_from_settings()
    cfg.enabled = True
    out = compute_confluence_from_ea(ea, cfg)
    out["advisory_only"] = True
    return out


@router.get("/api/v1/confluence/status")
def confluence_status() -> dict:
    """Live confluence from current monitor store + master verdict."""
    from app.analysis.confluence import compute_confluence_from_ea, confluence_config_from_settings
    from app.analysis.master_verdict import build_master_verdict

    st = monitor_store.status()
    ea = dict(st.get("vantage_ea") or {})
    link = st.get("link_health") or {}
    ea["connected"] = bool(link.get("ea_online") or ea.get("connected"))
    cfg = confluence_config_from_settings()
    conf = compute_confluence_from_ea(ea, cfg)
    mv = build_master_verdict(ea)
    return {
        "advisory_only": True,
        "confluence_enabled": cfg.enabled,
        "confluence": conf,
        "master_verdict": mv,
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


@router.post("/api/v1/signals/clear")
def clear_accepted_signals(body: dict | None = None) -> dict:
    """Clear Signal Center history — advisory ledger only."""
    from app.signal_ledger import clear_signals
    from app.ws_hub import push_monitor_update

    payload = body or {}
    scope = str(payload.get("scope") or "all").lower()
    symbol = payload.get("symbol")
    try:
        deleted = clear_signals(scope=scope, symbol=(str(symbol).strip() if symbol else None))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    monitor_store.add_log(
        "INFO",
        "signals",
        f"Cleared {deleted} signal(s) · scope={scope}"
        + (f" · symbol={str(symbol).upper()}" if symbol else ""),
    )
    push_monitor_update("signals_cleared")
    return {
        "advisory_only": True,
        "ok": True,
        "deleted": deleted,
        "scope": scope,
        "symbol": str(symbol).upper() if symbol else None,
    }


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


@router.post("/api/v1/market-news/mt5-calendar")
def ingest_mt5_calendar(
    req: Mt5CalendarIngestRequest,
    _: None = Depends(require_bearer),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Ingest normalized economic calendar rows from MT5 bridge EA."""
    if not settings.market_news_enabled:
        raise HTTPException(status_code=503, detail="Market news module disabled")
    from app.market_news.ingest import ingest_mt5_calendar as run_ingest

    result = run_ingest(req)
    monitor_store.add_log(
        "INFO",
        "market_news",
        f"MT5 calendar ingest · received={result.get('received')} "
        f"inserted={result.get('inserted')} updated={result.get('updated')}",
    )
    return result


@router.get("/api/v1/market-news/calendar")
def market_news_calendar(
    limit: int = Query(default=100, ge=1, le=500),
    currency: str | None = Query(default=None),
    from_utc: str | None = Query(default=None),
    to_utc: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> dict:
    """List persisted economic calendar events (newest scheduled first)."""
    if not settings.market_news_enabled:
        return {"advisory_only": True, "enabled": False, "count": 0, "items": []}
    from app.market_news.providers.registry import get_registry
    from app.market_news.types import parse_utc

    registry = get_registry()
    start = parse_utc(from_utc) if from_utc else None
    end = parse_utc(to_utc) if to_utc else None
    currencies = [currency.strip().upper()] if currency else None
    events, _providers = registry.fetch_calendar(
        from_utc=start,
        to_utc=end,
        currencies=currencies,
        limit=limit,
        unbounded=not from_utc and not to_utc,
    )
    items = [ev.to_dict() for ev in events]
    return {
        "advisory_only": True,
        "enabled": True,
        "provider": "mt5_calendar",
        "count": len(items),
        "items": items,
    }


@router.get("/api/v1/market-news/latest")
def market_news_latest(
    limit: int = Query(default=50, ge=1, le=200),
    source: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Recent normalized news headlines from registered providers."""
    if not settings.market_news_enabled:
        return {"advisory_only": True, "enabled": False, "count": 0, "items": []}
    from app.market_news.providers.registry import get_registry

    registry = get_registry()
    provider_names = None
    if source:
        provider_names = [source.strip().lower()]
    items, provider_results = registry.fetch_latest(limit=limit, providers=provider_names)
    return {
        "advisory_only": True,
        "enabled": True,
        "count": len(items),
        "items": [item.to_dict() for item in items],
        "providers": [r.to_dict() for r in provider_results],
    }


@router.get("/api/v1/market-news/providers")
def market_news_providers(settings: Settings = Depends(get_settings)) -> dict:
    """List registered news/calendar provider adapters (Step 5)."""
    if not settings.market_news_enabled:
        return {"advisory_only": True, "enabled": False, "providers": []}
    from app.market_news.providers.registry import get_registry

    registry = get_registry()
    return {
        "advisory_only": True,
        "enabled": True,
        "providers": registry.describe(),
    }


@router.post("/api/v1/market-news/ingest")
def ingest_market_news(
    req: MarketNewsIngestRequest,
    _: None = Depends(require_bearer),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Manual / provider bulk news ingest (textual headlines)."""
    if not settings.market_news_enabled:
        raise HTTPException(status_code=503, detail="Market news module disabled")
    from app.market_news.ingest import ingest_news_items as run_ingest

    result = run_ingest(req)
    monitor_store.add_log(
        "INFO",
        "market_news",
        f"News ingest · received={result.get('received')} "
        f"inserted={result.get('inserted')} updated={result.get('updated')}",
    )
    return result


@router.get("/api/v1/market-news/currency/{ccy}")
def market_news_currency(
    ccy: str,
    settings: Settings = Depends(get_settings),
) -> dict:
    """Currency macro sentiment, event risk, and timeline."""
    if not settings.market_news_enabled:
        return {"advisory_only": True, "enabled": False, "currency": ccy.upper()}
    from app.market_news.service import build_currency_status

    try:
        return build_currency_status(ccy, settings)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/v1/market-news/symbol/{symbol}")
def market_news_symbol(
    symbol: str,
    settings: Settings = Depends(get_settings),
) -> dict:
    """Pair macro bias, horizons, event risk, and technical alignment."""
    if not settings.market_news_enabled:
        return {"advisory_only": True, "enabled": False, "symbol": symbol.upper()}
    from app.market_news.service import build_symbol_status

    ea = monitor_store.status().get("ea") or {}
    return build_symbol_status(symbol, settings, ea_snapshot=ea)


@router.get("/api/v1/market-news/status")
def market_news_status(
    symbol: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Desk-style composite macro status (default symbol XAUUSD)."""
    if not settings.market_news_enabled:
        return {"advisory_only": True, "enabled": False, "module": "market_news"}
    from app.market_news.service import build_macro_desk_status

    ea = monitor_store.status().get("ea") or {}
    return build_macro_desk_status(settings, symbol=symbol, ea_snapshot=ea)


@router.post("/api/v1/market-news/analyze")
def market_news_analyze(
    req: MarketNewsAnalyzeRequest,
    settings: Settings = Depends(get_settings),
) -> dict:
    """Structured macro/news interpretation — rule-based or LLM when enabled."""
    if not settings.market_news_enabled:
        return {"advisory_only": True, "enabled": False, "status": "disabled"}
    from app.market_news.ai_interpret import interpret_macro

    ea = monitor_store.status().get("ea") or {}
    try:
        return interpret_macro(
            symbol=req.symbol,
            headline=req.headline,
            settings=settings,
            ea_snapshot=ea,
            force=req.force,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid AI response: {exc}") from exc


@router.post("/api/v1/market-news/fetch")
def fetch_external_market_news(
    _: None = Depends(require_bearer),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=100),
) -> dict:
    """Pull RSS / licensed API headlines and upsert into market_news.db (Step 13)."""
    if not settings.market_news_enabled:
        raise HTTPException(status_code=503, detail="Market news module disabled")
    from app.market_news.external_fetch import fetch_and_persist_external_news

    result = fetch_and_persist_external_news(settings, limit=limit)
    monitor_store.add_log(
        "INFO",
        "market_news",
        f"External fetch · received={result.get('received')} "
        f"inserted={result.get('inserted')} updated={result.get('updated')}",
    )
    return result


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


@router.get("/api/v1/execution/next")
def execution_next(
    symbol: str = Query(default="XAUUSD"),
    mode: str = Query(default="SWING"),
    account_mode: str = Query(default="DEMO"),
    min_confidence: float | None = Query(default=None, ge=0, le=100),
    max_m5_bars: int | None = Query(default=None, ge=1, le=10),
    tp_level: str = Query(default="TP1"),
    _: None = Depends(require_bearer),
) -> dict:
    """Executor poll — reserve one Swing or Scalping order spec (demo default; live opt-in)."""
    from app.config import get_settings
    from app.execution_queue import reserve_next

    st = get_settings()
    acct = str(account_mode or "DEMO").upper()
    if acct == "LIVE" and not st.execution_allow_live:
        return {
            "has_signal": False,
            "demo_execution": False,
            "live_execution": True,
            "live_blocked": True,
            "account_mode": acct,
            "reason": "backend_live_disabled",
            "caption": "Live execution blocked — set EXECUTION_ALLOW_LIVE=true on server .env",
        }

    result = reserve_next(
        monitor_store.status(),
        symbol=symbol,
        mode=mode,
        min_confidence=min_confidence,
        max_m5_bars=max_m5_bars,
        tp_level=tp_level,
    )
    result["account_mode"] = acct
    result["live_execution"] = acct == "LIVE"
    result["demo_execution"] = acct != "LIVE"
    return result


@router.post("/api/v1/execution/ack")
def execution_ack(
    body: dict,
    _: None = Depends(require_bearer),
) -> dict:
    """Demo executor ack — FILLED / REJECTED / SKIPPED."""
    from app.execution_queue import ack_execution
    from app.ws_hub import push_monitor_update

    signal_id = str((body or {}).get("signal_id") or "").strip()
    status = str((body or {}).get("status") or "").upper()
    ticket = (body or {}).get("ticket")
    reason = str((body or {}).get("reason") or "")
    fill_price = (body or {}).get("fill_price")
    volume = (body or {}).get("volume")
    if not signal_id:
        raise HTTPException(status_code=400, detail="signal_id required")
    try:
        updated = ack_execution(
            signal_id,
            status,
            ticket=int(ticket) if ticket is not None else None,
            reason=reason or None,
            fill_price=float(fill_price) if fill_price is not None else None,
            volume=float(volume) if volume is not None else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not updated:
        raise HTTPException(status_code=404, detail="Signal not found")
    acct = str((body or {}).get("account_mode") or "DEMO").upper()
    exec_label = "Live exec" if acct == "LIVE" else "Demo exec"
    monitor_store.add_log(
        "INFO",
        "execution",
        f"{exec_label} {status} {updated.get('side')} {updated.get('symbol')}",
        signal_id=signal_id,
    )
    push_monitor_update("execution_ack")
    try:
        from app.alert_notify import notify_execution_ack

        notify_execution_ack(updated, status, account_mode=acct)
    except Exception as exc:
        monitor_store.add_log("WARN", "alerts", f"Execution notify failed: {exc}")
    return {
        "demo_execution": True,
        "ok": True,
        "signal": updated,
    }


@router.get("/api/v1/execution/history")
def execution_history(
    limit: int = Query(default=50, ge=1, le=200),
    symbol: str | None = Query(default=None),
    mode: str | None = Query(default=None),
) -> dict:
    """Execution journal (demo default; live when enabled)."""
    from app.config import get_settings
    from app.execution_queue import execution_summary, list_history

    st = get_settings()
    items = list_history(
        limit=limit,
        symbol=(symbol.strip().upper() if symbol else None),
        mode=(mode.strip().upper() if mode else None),
    )
    summary = execution_summary(monitor_store.status())
    return {
        "demo_execution": not st.execution_allow_live,
        "live_execution_allowed": st.execution_allow_live,
        "count": len(items),
        "items": items,
        "summary": summary,
    }


@router.get("/api/v1/monitor/logs")
def monitor_logs(limit: int = Query(default=100, ge=1, le=300)) -> dict:
    return {"items": monitor_store.logs(limit)}


@router.post("/api/v1/telegram/test")
def telegram_test(_: None = Depends(require_bearer)) -> dict:
    """Send a test message using TELEGRAM_* settings in .env."""
    from app.telegram_notify import send_test_message, telegram_status

    ok, detail = send_test_message()
    if not ok:
        raise HTTPException(status_code=400, detail=detail or "Telegram send failed")
    return {"ok": True, "detail": detail, "telegram": telegram_status()}


@router.post("/api/v1/discord/test")
def discord_test(_: None = Depends(require_bearer)) -> dict:
    """Send a test message using DISCORD_* settings in .env."""
    from app.discord_notify import discord_status, send_test_message

    ok, detail = send_test_message()
    if not ok:
        raise HTTPException(status_code=400, detail=detail or "Discord send failed")
    return {"ok": True, "detail": detail, "discord": discord_status()}
