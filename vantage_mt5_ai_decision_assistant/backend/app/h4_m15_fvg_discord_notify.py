"""H4→M15 FVG Discord alerts — ENTRY_READY and terminal setup states."""
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

DEFAULT_H4_M15_DISCORD_EVENTS = frozenset(
    {
        "ENTRY_READY",
        "SETUP_INVALIDATED",
        "SETUP_EXPIRED",
    }
)

_TERMINAL_LOW_SCORE_OK = frozenset({"SETUP_INVALIDATED", "SETUP_EXPIRED"})


def _normalize_webhook_url(url: str) -> str:
    u = (url or "").strip()
    if u.startswith("https://discordapp.com/api/webhooks/"):
        return "https://discord.com/api/webhooks/" + u.removeprefix("https://discordapp.com/api/webhooks/")
    return u


def h4_m15_fvg_discord_configured(settings: Settings | None = None) -> bool:
    st = settings or get_settings()
    url = _normalize_webhook_url(st.discord_h4_m15_fvg_webhook_url or "")
    return bool(st.discord_h4_m15_fvg_alerts_enabled and url.startswith("https://discord.com/api/webhooks/"))


def _allowed_events(st: Settings) -> frozenset[str]:
    raw = (st.discord_h4_m15_fvg_alert_events or "").strip()
    if not raw:
        return DEFAULT_H4_M15_DISCORD_EVENTS
    return frozenset(e.strip().upper() for e in raw.split(",") if e.strip())


def _send_embed(*, title: str, description: str, fields: list[dict[str, Any]], color: int) -> tuple[bool, str]:
    st = get_settings()
    if not h4_m15_fvg_discord_configured(st):
        return False, "H4→M15 FVG Discord not configured"
    url = _normalize_webhook_url(st.discord_h4_m15_fvg_webhook_url or "")
    payload = {
        "username": "H4→M15 FVG",
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
    if not h4_m15_fvg_discord_configured(st):
        return False
    now = time.time()
    cooldown = max(0, int(st.discord_h4_m15_fvg_cooldown_sec))
    with _lock:
        if signal_id in _sent_ids:
            _log.info("[DISCORD] Duplicate H4→M15 FVG notification prevented signal_id=%s", signal_id)
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
        _log.info("[DISCORD] H4→M15 FVG alert sent signal_id=%s", signal_id)
        try:
            from app.monitor_state import monitor_store

            monitor_store.add_log("INFO", "discord", f"[DISCORD] H4→M15 FVG: {signal_id}", key=signal_id)
        except Exception:
            pass
    else:
        with _lock:
            _sent_ids.discard(signal_id)
            _last_sent_at.pop(signal_id, None)
        _log.warning("[DISCORD] H4→M15 FVG send failed signal_id=%s detail=%s", signal_id, detail)
    return ok


def _state_color(state: str) -> int:
    if state == "ENTRY_READY":
        return 3066993
    if state == "SETUP_INVALIDATED":
        return 15105570
    if state == "SETUP_EXPIRED":
        return 9807270
    return 3447003


def _fmt_setup_alert(setup: dict[str, Any], module: dict[str, Any]) -> tuple[str, str, list[dict[str, Any]], int]:
    sym = str(setup.get("symbol") or module.get("symbol") or "XAUUSD").upper()
    state = str(setup.get("state") or setup.get("decision") or "—").upper()
    direction = str(setup.get("direction") or "—").upper()
    htf = setup.get("htf_location") if isinstance(setup.get("htf_location"), dict) else {}
    liq = setup.get("liquidity") if isinstance(setup.get("liquidity"), dict) else {}
    disp = setup.get("displacement") if isinstance(setup.get("displacement"), dict) else {}
    struct = setup.get("structure") if isinstance(setup.get("structure"), dict) else {}
    ef = setup.get("entry_fvg") if isinstance(setup.get("entry_fvg"), dict) else {}

    emoji = {"ENTRY_READY": "🎯", "SETUP_INVALIDATED": "⛔", "SETUP_EXPIRED": "⌛"}.get(state, "📊")
    title = f"{emoji} H4→M15 FVG — {state.replace('_', ' ')}"
    if state == "ENTRY_READY":
        title = f"{emoji} H4→M15 FVG — {direction} ENTRY READY"

    desc = "\n".join(
        [
            f"**Symbol:** {sym}",
            f"**Setup ID:** `{setup.get('setup_id') or '—'}`",
            f"**Grade:** {setup.get('grade') or '—'} · **Score:** {setup.get('score') or 0}/100",
        ]
    )
    fields = [
        {"name": "Direction", "value": direction},
        {"name": "H4 FVG", "value": f"{htf.get('lower', '—')} – {htf.get('upper', '—')}"},
        {"name": "Mitigation", "value": f"{htf.get('mitigation_percent', 0)}%"},
        {"name": "Liquidity", "value": liq.get("type") or ("YES" if liq.get("sweep_detected") else "NO")},
        {"name": "Displacement", "value": disp.get("score") or "—"},
        {"name": "MSS", "value": struct.get("broken_level") or "—"},
        {"name": "Execution FVG", "value": f"{ef.get('lower', '—')} – {ef.get('upper', '—')}"},
        {"name": "Entry", "value": setup.get("entry_price") or "—"},
        {"name": "Stop", "value": setup.get("structural_stop") or "—"},
    ]
    if setup.get("invalidation_reason"):
        fields.append({"name": "Invalidation", "value": setup["invalidation_reason"], "inline": False})
    if setup.get("expiration_reason"):
        fields.append({"name": "Expiration", "value": setup["expiration_reason"], "inline": False})

    return title, desc, fields, _state_color(state)


def maybe_h4_m15_fvg_alert(payload: dict[str, Any]) -> None:
    """Evaluate h4_m15_fvg blob from heartbeat or analyze. Never raises."""
    st = get_settings()
    if not h4_m15_fvg_discord_configured(st):
        return

    blob = payload.get("h4_m15_fvg")
    if not isinstance(blob, dict) or not blob.get("valid"):
        return

    allowed = _allowed_events(st)
    min_score = float(st.discord_h4_m15_fvg_min_score)

    candidates: list[dict[str, Any]] = []
    primary = blob.get("primary")
    if isinstance(primary, dict):
        candidates.append(primary)
    for row in blob.get("setups") or []:
        if isinstance(row, dict) and row not in candidates:
            candidates.append(row)

    for setup in candidates:
        state = str(setup.get("state") or setup.get("decision") or "").upper()
        if not state or state not in allowed:
            continue
        if setup.get("state_changed") is False:
            continue
        score = float(setup.get("score") or 0)
        if score < min_score and state not in _TERMINAL_LOW_SCORE_OK:
            continue

        setup_id = str(setup.get("setup_id") or "")
        sym = str(setup.get("symbol") or blob.get("symbol") or "XAUUSD").upper()
        if not setup_id:
            setup_id = f"{sym}|{state}|{setup.get('entry_ready_time') or ''}"

        signal_id = f"{setup_id}|{state}"
        title, desc, fields, color = _fmt_setup_alert(setup, blob)
        _dedupe_send(signal_id, title=title, description=desc, fields=fields, color=color)


def reset_state_for_tests() -> None:
    with _lock:
        _sent_ids.clear()
        _last_sent_at.clear()
