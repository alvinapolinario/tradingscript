"""Unified alert dispatch — Telegram + Discord."""
from __future__ import annotations

from typing import Any, Callable


def _safe(module: str, fn: Callable[..., None], *args: Any, **kwargs: Any) -> None:
    try:
        fn(*args, **kwargs)
    except Exception as exc:
        try:
            from app.monitor_state import monitor_store

            monitor_store.add_log("WARN", module, f"Notify failed: {exc}")
        except Exception:
            pass


def process_heartbeat(payload: dict[str, Any], accepted: dict[str, Any] | None = None) -> None:
    from app.discord_notify import process_heartbeat as discord_hb
    from app.telegram_notify import process_heartbeat as telegram_hb

    _safe("telegram", telegram_hb, payload, accepted)
    _safe("discord", discord_hb, payload, accepted)


def notify_execution_ack(signal: dict[str, Any], status: str) -> None:
    from app.discord_notify import notify_execution_ack as discord_ack
    from app.telegram_notify import notify_execution_ack as telegram_ack

    _safe("telegram", telegram_ack, signal, status)
    _safe("discord", discord_ack, signal, status)
