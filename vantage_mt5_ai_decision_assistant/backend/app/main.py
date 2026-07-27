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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1", "http://localhost", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


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
