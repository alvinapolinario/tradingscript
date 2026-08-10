"""Box Theory Discord alerts — dedicated webhook (analysis only)."""
from __future__ import annotations

import logging
import threading
import time
from typing import Any

import httpx

from app.analysis.box_theory.types import DEFAULT_DISCORD_EVENTS
from app.config import Settings, get_settings

_log = logging.getLogger(__name__)
_lock = threading.Lock()
_sent_ids: set[str] = set()
_last_sent_at: dict[str, float] = {}


def _normalize_webhook_url(url: str) -> str:
    u = (url or "").strip()
    if u.startswith("https://discordapp.com/api/webhooks/"):
        return "https://discord.com/api/webhooks/" + u.removeprefix("https://discordapp.com/api/webhooks/")
    return u


def box_discord_configured(settings: Settings | None = None) -> bool:
    st = settings or get_settings()
    url = _normalize_webhook_url(st.discord_box_webhook_url or "")
    return bool(st.discord_box_alerts_enabled and url.startswith("https://discord.com/api/webhooks/"))


def _allowed_events(st: Settings) -> frozenset[str]:
    raw = (st.discord_box_alert_events or "").strip()
    if not raw:
        return DEFAULT_DISCORD_EVENTS
    return frozenset(e.strip().upper() for e in raw.split(",") if e.strip())


def _send_embed(*, title: str, description: str, fields: list[dict[str, Any]], color: int) -> tuple[bool, str]:
    st = get_settings()
    if not box_discord_configured(st):
        return False, "Box Discord not configured"
    url = _normalize_webhook_url(st.discord_box_webhook_url or "")
    payload = {
        "username": "Box Theory",
        "embeds": [
            {
                "title": title[:256],
                "description": description[:4096],
                "color": color,
                "fields": [{"name": f["name"][:256], "value": str(f["value"])[:1024], "inline": f.get("inline", True)} for f in fields[:25]],
                "footer": {"text": "ANALYSIS ONLY — NO AUTO TRADE"},
            }
        ],
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=payload)
        if resp.status_code in (200, 204):
            return True, "sent"
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as exc:
        return False, str(exc)


def _dedupe_send(signal_id: str, *, title: str, description: str, fields: list[dict[str, Any]], color: int) -> bool:
    st = get_settings()
    if not box_discord_configured(st):
        return False
    now = time.time()
    with _lock:
        if signal_id in _sent_ids:
            _log.info("[DISCORD] Duplicate notification prevented signal_id=%s", signal_id)
            return False
        last = _last_sent_at.get(signal_id, 0.0)
        if now - last < st.discord_cooldown_sec:
            return False
        _sent_ids.add(signal_id)
        _last_sent_at[signal_id] = now
        if len(_sent_ids) > 5000:
            _sent_ids.clear()
            _last_sent_at.clear()

    ok, detail = _send_embed(title=title, description=description, fields=fields, color=color)
    if ok:
        _log.info("[DISCORD] Signal sent signal_id=%s", signal_id)
        try:
            from app.monitor_state import monitor_store

            monitor_store.add_log("INFO", "discord", f"[DISCORD] Box signal sent: {signal_id}", key=signal_id)
        except Exception:
            pass
    else:
        with _lock:
            _sent_ids.discard(signal_id)
            _last_sent_at.pop(signal_id, None)
        _log.warning("[DISCORD] Send failed signal_id=%s detail=%s", signal_id, detail)
    return ok


def _fmt_box_alert(box: dict[str, Any], blob: dict[str, Any]) -> tuple[str, str, list[dict[str, Any]], int]:
    direction = str(blob.get("direction") or "—").upper()
    signal = str(blob.get("signal") or "").upper()
    sym = str(blob.get("symbol") or "XAUUSD").upper()
    conf = float(blob.get("confidence_score") or blob.get("confidence") or 0)
    quality = str(blob.get("signal_quality") or "—")
    htf = str(blob.get("htf_bias") or "—")
    sweep = blob.get("liquidity_sweep") if isinstance(blob.get("liquidity_sweep"), dict) else {}
    fvg = bool(blob.get("fvg_confirmation"))
    reasons = blob.get("reasons") if isinstance(blob.get("reasons"), list) else []
    breakout = blob.get("breakout") if isinstance(blob.get("breakout"), dict) else {}
    retest = blob.get("retest") if isinstance(blob.get("retest"), dict) else {}

    is_buy = signal == "BUY" or direction == "BUY"
    is_sell = signal == "SELL" or direction == "SELL"
    is_trap = str(blob.get("box_status") or "").upper() in ("BULL_TRAP", "BEAR_TRAP")

    if is_trap:
        trap = str(blob.get("box_status") or "").upper()
        emoji = "⚠️"
        title = f"{emoji} BOX THEORY — {trap.replace('_', ' ')}"
        color = 15105570
    elif is_buy:
        title = "🟢 BOX THEORY — BUY SIGNAL"
        color = 3066993
    elif is_sell:
        title = "🔴 BOX THEORY — SELL SIGNAL"
        color = 15158332
    else:
        title = f"📦 BOX THEORY — {signal or 'UPDATE'}"
        color = 3447003

    desc_lines = [
        f"**Symbol:** {sym}",
        f"**Box TF:** {blob.get('timeframe') or 'M15'} · **Entry TF:** {blob.get('entry_timeframe') or 'M5'}",
    ]
    if is_trap:
        desc_lines.append(f"**Trap:** {blob.get('box_status')}")

    fields = [
        {"name": "Box High", "value": box.get("high", "—")},
        {"name": "Box Low", "value": box.get("low", "—")},
        {"name": "Breakout", "value": breakout.get("price") or "—"},
        {"name": "Retest", "value": retest.get("price") if retest.get("detected") else "—"},
        {"name": "Entry", "value": blob.get("entry") or "—"},
        {"name": "Stop Loss", "value": blob.get("stop_loss") or "—"},
        {"name": "TP1", "value": blob.get("tp1") or "—"},
        {"name": "TP2", "value": blob.get("tp2") or "—"},
        {"name": "TP3", "value": blob.get("tp3") or "—"},
        {"name": "RR", "value": f"1:{blob.get('risk_reward') or '—'}"},
        {"name": "Confidence", "value": f"{conf:.0f}/100 — {quality}"},
        {"name": "HTF Bias", "value": htf},
        {"name": "Liquidity Sweep", "value": "YES" if sweep.get("detected") else "NO"},
        {"name": "FVG/iFVG", "value": "YES" if fvg else "NO"},
    ]
    if reasons:
        bullet = "\n".join(f"✅ {r}" for r in reasons[:8])
        fields.append({"name": "Reasons", "value": bullet, "inline": False})
    return title, "\n".join(desc_lines), fields, color


def maybe_box_theory_alert(payload: dict[str, Any]) -> None:
    """Evaluate box_theory blob from heartbeat or analyze response. Never raises."""
    st = get_settings()
    if not box_discord_configured(st):
        return

    blob = payload.get("box_theory")
    if not isinstance(blob, dict) or not (blob.get("valid") or blob.get("analysis_active")):
        return
    if blob.get("gold_symbol_valid") is False:
        return

    events = blob.get("events") if isinstance(blob.get("events"), list) else []
    allowed = _allowed_events(st)
    event = next((e for e in reversed(events) if str(e).upper() in allowed), None)
    if not event:
        return

    signal_id = str(blob.get("signal_id") or "")
    if not signal_id:
        sym = str(blob.get("symbol") or "XAUUSD").upper()
        box = blob.get("box") if isinstance(blob.get("box"), dict) else {}
        signal_id = f"{sym}|{box.get('start_time')}|{box.get('end_time')}|{blob.get('direction')}|{event}"

    box = blob.get("box") if isinstance(blob.get("box"), dict) else {}
    title, desc, fields, color = _fmt_box_alert(box, blob)
    _dedupe_send(signal_id, title=title, description=desc, fields=fields, color=color)
