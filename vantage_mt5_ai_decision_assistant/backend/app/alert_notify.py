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


def execution_signal_ref(signal: dict[str, Any]) -> str:
    """Human-readable signal reference for execution alerts."""
    sid = str(signal.get("signal_id") or signal.get("id") or "").strip()
    label = str(signal.get("signal_label") or "").strip()
    if label and sid:
        short = sid if len(sid) <= 12 else sid[:8] + "…"
        return f"{label} · {short}"
    if label:
        return label
    return sid or "—"


def format_execution_ack_message(
    signal: dict[str, Any],
    status: str,
    *,
    account_mode: str = "DEMO",
) -> str:
    sym = str(signal.get("symbol") or "XAUUSD").upper()
    side = str(signal.get("side") or "?").upper()
    acct = str(account_mode or "DEMO").upper()
    exec_label = "Live exec" if acct == "LIVE" else "Demo exec"
    ref = execution_signal_ref(signal)
    mode = str(signal.get("trade_mode") or "—")
    conf = signal.get("confidence")
    sl = signal.get("stop_loss")
    tp = signal.get("take_profit")
    ticket = signal.get("ticket")
    fill_price = signal.get("fill_price") or signal.get("planned_entry")
    volume = signal.get("volume")
    reason = str(signal.get("reason") or "").strip()

    lines = [
        f"**{exec_label} {status} · {sym}**",
        f"Side: **{side}** · Signal: {ref}",
        f"Mode: `{mode}`" + (f" · Conf: `{conf}`" if conf is not None else ""),
    ]
    entry_parts: list[str] = []
    if fill_price is not None:
        entry_parts.append(f"Entry: `{fill_price}`")
    if volume is not None:
        entry_parts.append(f"Lot: `{volume}`")
    if entry_parts:
        lines.append(" · ".join(entry_parts))
    if sl is not None or tp is not None:
        detail = []
        if sl is not None:
            detail.append(f"SL: `{sl}`")
        if tp is not None:
            detail.append(f"TP: `{tp}`")
        lines.append(" · ".join(detail))
    if ticket is not None:
        lines.append(f"Ticket: **{ticket}**")
    if reason and status != "FILLED":
        lines.append(f"Reason: `{reason}`")
    return "\n".join(lines)


def process_heartbeat(payload: dict[str, Any], accepted: dict[str, Any] | None = None) -> None:
    from app.discord_notify import process_heartbeat as discord_hb
    from app.telegram_notify import process_heartbeat as telegram_hb

    _safe("telegram", telegram_hb, payload, accepted)
    _safe("discord", discord_hb, payload, accepted)


def notify_execution_ack(
    signal: dict[str, Any],
    status: str,
    *,
    account_mode: str = "DEMO",
) -> None:
    from app.discord_notify import notify_execution_ack as discord_ack
    from app.telegram_notify import notify_execution_ack as telegram_ack

    _safe("telegram", telegram_ack, signal, status, account_mode=account_mode)
    _safe("discord", discord_ack, signal, status, account_mode=account_mode)
