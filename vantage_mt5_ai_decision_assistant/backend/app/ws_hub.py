"""WebSocket broadcast hub for the monitor UI."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import WebSocket


class MonitorHub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue: asyncio.Queue[dict[str, Any]] | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._queue = asyncio.Queue()

    async def register(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients.add(websocket)

    async def unregister(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)

    async def send_json(self, websocket: WebSocket, payload: dict[str, Any]) -> None:
        await websocket.send_text(json.dumps(payload, default=str))

    async def broadcast(self, payload: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        async with self._lock:
            clients = list(self._clients)
        text = json.dumps(payload, default=str)
        for ws in clients:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)

    def publish(self, payload: dict[str, Any]) -> None:
        """Thread-safe publish from sync FastAPI route handlers."""
        if self._loop is None or self._queue is None:
            return
        try:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, payload)
        except Exception:
            pass

    async def runner(self) -> None:
        assert self._queue is not None
        while True:
            payload = await self._queue.get()
            await self.broadcast(payload)


monitor_hub = MonitorHub()


def push_monitor_update(event: str = "update") -> None:
    from app.monitor_state import monitor_store

    monitor_hub.publish(
        {
            "type": event,
            "status": monitor_store.status(),
        }
    )
