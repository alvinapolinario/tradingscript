"""
Vantage MT5 AI Decision Assistant — local FastAPI backend.

Advisory-only. Does not execute trades.
Cloud AI provider keys (if any) stay on this host — never inside the EA.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.monitor_state import monitor_store
from app.routers.api import router
from app.ws_hub import monitor_hub, push_monitor_update

settings = get_settings()
STATIC_DIR = Path(__file__).resolve().parent / "static"


async def _status_ticker() -> None:
    """Keep connected-age / WAITING_FOR_EA fresh without browser polling."""
    while True:
        await asyncio.sleep(5)
        push_monitor_update("tick")


@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()
    monitor_hub.bind_loop(loop)
    runner = asyncio.create_task(monitor_hub.runner())
    ticker = asyncio.create_task(_status_ticker())
    monitor_store.add_log("INFO", "backend", "FastAPI backend started", host=settings.host, port=settings.port)
    push_monitor_update("startup")
    try:
        yield
    finally:
        runner.cancel()
        ticker.cancel()
        await asyncio.gather(runner, ticker, return_exceptions=True)


app = FastAPI(
    title=settings.app_name,
    version="1.2.0",
    description="Local advisory backend for Vantage MT5 AI Decision Assistant",
    lifespan=lifespan,
)

_cors_origins = [
    "http://127.0.0.1",
    "http://localhost",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://187.77.142.118:8000",
    "http://187.77.142.118",
]
_pub = (settings.public_base_url or "").rstrip("/")
if _pub and _pub not in _cors_origins:
    _cors_origins.append(_pub)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def root():
    return RedirectResponse(url="/monitor")


@app.get("/monitor")
def monitor_page():
    page = STATIC_DIR / "monitor.html"
    if not page.exists():
        return {"error": "monitor.html missing", "path": str(page)}
    return FileResponse(page)


@app.get("/dashboard")
def dashboard_page():
    """Separate M5 / M15 / H1 alignment strategy desk."""
    page = STATIC_DIR / "dashboard.html"
    if not page.exists():
        return {"error": "dashboard.html missing", "path": str(page)}
    return FileResponse(page)


@app.get("/signals")
def signals_page():
    """Accepted Signal Ledger — BUY/SELL history cards."""
    page = STATIC_DIR / "signals.html"
    if not page.exists():
        return {"error": "signals.html missing", "path": str(page)}
    return FileResponse(page)


@app.get("/orders")
def orders_page():
    """Pending Orders desk — advisory risk/trend/suggestions (no order mutations)."""
    page = STATIC_DIR / "orders.html"
    if not page.exists():
        return {"error": "orders.html missing", "path": str(page)}
    return FileResponse(page)


@app.get("/pullback")
def pullback_page():
    """Pullback Probability Analyzer desk — advisory only."""
    page = STATIC_DIR / "pullback.html"
    if not page.exists():
        return {"error": "pullback.html missing", "path": str(page)}
    return FileResponse(page)


@app.get("/gold-smc")
def gold_smc_page():
    """Gold SMC Intelligence desk — advisory only, XAUUSD/Gold."""
    page = STATIC_DIR / "gold-smc.html"
    if not page.exists():
        return {"error": "gold-smc.html missing", "path": str(page)}
    return FileResponse(page)


@app.get("/liquidity-grab")
def liquidity_grab_page():
    """Liquidity Grab Monitor desk — advisory only, XAUUSD/Gold."""
    page = STATIC_DIR / "liquidity-grab.html"
    if not page.exists():
        return {"error": "liquidity-grab.html missing", "path": str(page)}
    return FileResponse(page)


@app.get("/breakout-structure")
def breakout_structure_page():
    """Breakout Structure Intelligence desk — advisory only, XAUUSD/Gold."""
    page = STATIC_DIR / "breakout-structure.html"
    if not page.exists():
        return {"error": "breakout-structure.html missing", "path": str(page)}
    return FileResponse(page)


@app.get("/market-state")
def market_state_page():
    """Institutional Market State Engine v2 desk — advisory only, XAUUSD/Gold."""
    page = STATIC_DIR / "market-state.html"
    if not page.exists():
        return {"error": "market-state.html missing", "path": str(page)}
    return FileResponse(page)


@app.get("/analyzer")
def analyzer_page():
    """Smart Analyzer — advisory decision desk (Take/Ignore, no orders)."""
    page = STATIC_DIR / "analyzer.html"
    if not page.exists():
        return {"error": "analyzer.html missing", "path": str(page)}
    return FileResponse(page)


@app.get("/patterns")
def patterns_page():
    page = STATIC_DIR / "patterns.html"
    if not page.exists():
        return {"error": "patterns.html missing", "path": str(page)}
    return FileResponse(page)


@app.get("/scanner")
def scanner_page():
    page = STATIC_DIR / "scanner.html"
    if not page.exists():
        return {"error": "scanner.html missing", "path": str(page)}
    return FileResponse(page)


@app.get("/lab")
def lab_page():
    page = STATIC_DIR / "lab.html"
    if not page.exists():
        return {"error": "lab.html missing", "path": str(page)}
    return FileResponse(page)


@app.get("/coming-soon")
def coming_soon_page():
    page = STATIC_DIR / "coming-soon.html"
    if not page.exists():
        return {"error": "coming-soon.html missing", "path": str(page)}
    return FileResponse(page)


@app.websocket("/ws/monitor")
async def monitor_ws(websocket: WebSocket):
    await monitor_hub.register(websocket)
    # Initial snapshot
    await monitor_hub.send_json(
        websocket,
        {
            "type": "snapshot",
            "status": monitor_store.status(),
        },
    )
    try:
        while True:
            # Client may send ping/pong text; keep connection alive
            msg = await websocket.receive_text()
            if msg.strip().lower() in {"ping", "\"ping\"", "{\"type\":\"ping\"}"}:
                await monitor_hub.send_json(websocket, {"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        await monitor_hub.unregister(websocket)
