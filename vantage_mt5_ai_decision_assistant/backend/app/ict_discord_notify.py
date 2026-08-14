"""ICT Strategy Discord alerts — dedicated webhook (analysis only, state-change)."""
from __future__ import annotations

import logging
import threading
import time
from typing import Any

import httpx

from app.config import Settings, get_settings

_log = logging.getLogger(__name__)
_lock = threading.Lock()
_sent_ids: set[str] = set()
_last_sent_at: dict[str, float] = {}

DEFAULT_ICT_DISCORD_EVENTS = frozenset(
    {
        "LIQUIDITY_SWEPT",
        "DISPLACEMENT_CONFIRMED",
        "MSS_CONFIRMED",
        "EXECUTION_FVG_FOUND",
        "FVG_TOUCHED",
        "ENTRY_ZONE_ACTIVE",
        "ENTRY_READY",
        "TRIGGERED",
        "INVALIDATED",
        "TARGET_REACHED",
    }
)

_TERMINAL_LOW_CONF_OK = frozenset({"INVALIDATED", "TARGET_REACHED", "EXPIRED"})


def _normalize_webhook_url(url: str) -> str:
    u = (url or "").strip()
    if u.startswith("https://discordapp.com/api/webhooks/"):
        return "https://discord.com/api/webhooks/" + u.removeprefix("https://discordapp.com/api/webhooks/")
    return u


def ict_discord_configured(settings: Settings | None = None) -> bool:
    st = settings or get_settings()
    url = _normalize_webhook_url(st.discord_ict_webhook_url or "")
    return bool(st.discord_ict_alerts_enabled and url.startswith("https://discord.com/api/webhooks/"))


def _allowed_events(st: Settings) -> frozenset[str]:
    raw = (st.discord_ict_alert_events or "").strip()
    if not raw:
        return DEFAULT_ICT_DISCORD_EVENTS
    return frozenset(e.strip().upper() for e in raw.split(",") if e.strip())


def _send_embed(*, title: str, description: str, fields: list[dict[str, Any]], color: int) -> tuple[bool, str]:
    st = get_settings()
    if not ict_discord_configured(st):
        return False, "ICT Discord not configured"
    url = _normalize_webhook_url(st.discord_ict_webhook_url or "")
    payload = {
        "username": "ICT Strategy",
        "embeds": [
            {
                "title": title[:256],
                "description": description[:4096],
                "color": color,
                "fields": [
                    {"name": f["name"][:256], "value": str(f["value"])[:1024], "inline": f.get("inline", True)}
                    for f in fields[:25]
                ],
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
    if not ict_discord_configured(st):
        return False
    now = time.time()
    cooldown = max(0, int(st.discord_ict_cooldown_sec))
    with _lock:
        if signal_id in _sent_ids:
            _log.info("[DISCORD] Duplicate ICT notification prevented signal_id=%s", signal_id)
            return False
        last = _last_sent_at.get(signal_id, 0.0)
        if now - last < cooldown:
            return False
        _sent_ids.add(signal_id)
        _last_sent_at[signal_id] = now
        if len(_sent_ids) > 5000:
            _sent_ids.clear()
            _last_sent_at.clear()

    ok, detail = _send_embed(title=title, description=description, fields=fields, color=color)
    if ok:
        _log.info("[DISCORD] ICT signal sent signal_id=%s", signal_id)
        try:
            from app.monitor_state import monitor_store

            monitor_store.add_log("INFO", "discord", f"[DISCORD] ICT signal sent: {signal_id}", key=signal_id)
        except Exception:
            pass
    else:
        with _lock:
            _sent_ids.discard(signal_id)
            _last_sent_at.pop(signal_id, None)
        _log.warning("[DISCORD] ICT send failed signal_id=%s detail=%s", signal_id, detail)
    return ok


def _state_color(state: str, decision: str) -> int:
    if state == "TARGET_REACHED":
        return 3066993
    if state == "INVALIDATED" or state == "EXPIRED":
        return 15105570
    if state == "TRIGGERED" or state == "ENTRY_READY":
        if decision == "BUY":
            return 3066993
        if decision == "SELL":
            return 15158332
        return 15844367
    if state == "FVG_TOUCHED":
        return 15844367
    if state == "EXECUTION_FVG_FOUND":
        return 10181046
    if state == "ENTRY_ZONE_ACTIVE":
        return 3447003
    if state == "MSS_CONFIRMED":
        return 10181046
    if state == "LIQUIDITY_SWEPT":
        return 7419530
    return 3447003


def _fmt_ict_alert(blob: dict[str, Any]) -> tuple[str, str, list[dict[str, Any]], int]:
    sym = str(blob.get("symbol") or "XAUUSD").upper()
    state = str(blob.get("state") or blob.get("setup_state") or blob.get("status") or "—").upper()
    decision = str(blob.get("decision") or "—").upper()
    conf = float(blob.get("confidence_score") or blob.get("confidence") or 0)
    quality = str(blob.get("signal_quality") or "—")
    setup_id = str(blob.get("setup_id") or "—")

    htf = blob.get("htf_bias") if isinstance(blob.get("htf_bias"), dict) else {}
    liq = blob.get("liquidity") if isinstance(blob.get("liquidity"), dict) else {}
    struct = blob.get("structure") if isinstance(blob.get("structure"), dict) else {}
    fvg = blob.get("fvg") if isinstance(blob.get("fvg"), dict) else {}
    entry = blob.get("entry") if isinstance(blob.get("entry"), dict) else {}
    sl = blob.get("stop_loss") if isinstance(blob.get("stop_loss"), dict) else {}
    targets = blob.get("targets") if isinstance(blob.get("targets"), list) else []
    reasons = blob.get("reasons") if isinstance(blob.get("reasons"), list) else []

    emoji_map = {
        "LIQUIDITY_SWEPT": "💧",
        "DISPLACEMENT_CONFIRMED": "📈",
        "MSS_CONFIRMED": "📐",
        "EXECUTION_FVG_FOUND": "🟦",
        "FVG_TOUCHED": "👆",
        "ENTRY_ZONE_ACTIVE": "🎯",
        "ENTRY_READY": "✅",
        "TRIGGERED": "⚡",
        "INVALIDATED": "⛔",
        "TARGET_REACHED": "🏁",
        "EXPIRED": "⌛",
    }
    emoji = emoji_map.get(state, "📊")
    title = f"{emoji} ICT — {state.replace('_', ' ')}"
    if decision in ("BUY", "SELL") and state in ("TRIGGERED", "ENTRY_READY", "ENTRY_ZONE_ACTIVE"):
        title = f"{emoji} ICT — {decision} · {state.replace('_', ' ')}"

    desc_lines = [
        f"**Symbol:** {sym}",
        f"**Setup TF:** {blob.get('timeframe') or 'M15'} · **Exec TF:** {blob.get('execution_timeframe') or 'M5'}",
        f"**Setup ID:** `{setup_id}`",
    ]
    guidance = blob.get("action_guidance") or blob.get("technical_narrative")
    if guidance:
        desc_lines.append(f"**Note:** {guidance}")

    tp1 = targets[0].get("price") if targets else "—"
    tp2 = targets[1].get("price") if len(targets) > 1 else "—"

    fields = [
        {"name": "Engine", "value": blob.get("engine_source") or "—"},
        {"name": "Decision", "value": decision},
        {"name": "Confidence", "value": f"{conf:.0f}/100 — {quality}"},
        {"name": "HTF Bias", "value": htf.get("direction") or "—"},
        {"name": "Session", "value": blob.get("session") or "—"},
        {"name": "Liquidity Sweep", "value": liq.get("type") or ("YES" if liq.get("sweep_detected") else "NO")},
        {"name": "Sweep Level", "value": liq.get("level") or liq.get("sweep_price") or "—"},
        {"name": "MSS", "value": struct.get("mss") or "—"},
        {"name": "Displacement", "value": struct.get("displacement_score") or "—"},
        {"name": "FVG Zone", "value": f"{fvg.get('low') or '—'} – {fvg.get('high') or '—'}"},
        {"name": "Entry Zone", "value": f"{entry.get('zone_low') or '—'} – {entry.get('zone_high') or '—'}"},
        {"name": "Stop Loss", "value": sl.get("price") or "—"},
        {"name": "TP1 / TP2", "value": f"{tp1} / {tp2}"},
        {"name": "R:R", "value": f"1:{blob.get('risk_reward') or '—'}"},
        {"name": "Premium / Discount", "value": blob.get("premium_discount_zone") or "—"},
    ]
    if reasons:
        bullet = "\n".join(f"• {r}" for r in reasons[:8])
        fields.append({"name": "Reasons", "value": bullet, "inline": False})

    color = _state_color(state, decision)
    return title, "\n".join(desc_lines), fields, color


def maybe_ict_alert(payload: dict[str, Any]) -> None:
    """Evaluate ict blob from heartbeat or analyze response. Never raises."""
    st = get_settings()
    if not ict_discord_configured(st):
        return

    blob = payload.get("ict")
    if not isinstance(blob, dict) or not (blob.get("valid") or blob.get("analysis_active")):
        return
    if str(blob.get("engine_source") or "").upper() == "MQL5_LEGACY":
        return
    if blob.get("gold_symbol_valid") is False:
        return

    state = str(blob.get("state") or blob.get("setup_state") or blob.get("status") or "").upper()
    if not state or state not in _allowed_events(st):
        return

    if blob.get("state_changed") is False:
        return

    conf = float(blob.get("confidence_score") or blob.get("confidence") or 0)
    if conf < st.discord_ict_min_confidence and state not in _TERMINAL_LOW_CONF_OK:
        return

    setup_id = str(blob.get("setup_id") or "")
    entry_event_id = str(blob.get("entry_event_id") or "")
    if state == "ENTRY_READY" and entry_event_id:
        signal_id = entry_event_id
    elif setup_id:
        signal_id = f"{setup_id}|{state}"
    else:
        sym = str(blob.get("symbol") or "XAUUSD").upper()
        signal_id = f"{sym}|{state}|{blob.get('eval_bar_time') or blob.get('timestamp') or ''}"
    title, desc, fields, color = _fmt_ict_alert(blob)
    _dedupe_send(signal_id, title=title, description=desc, fields=fields, color=color)


def reset_state_for_tests() -> None:
    with _lock:
        _sent_ids.clear()
        _last_sent_at.clear()
