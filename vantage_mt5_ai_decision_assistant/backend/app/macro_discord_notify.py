"""Macro / news Discord alerts — dedicated webhook (Step 12)."""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.market_news.surprise import interpret_surprise
from app.market_news.types import EconomicEvent, MacroConflictStatus, NewsImportance, parse_utc

_log = logging.getLogger(__name__)
_lock = threading.Lock()
_sent_ids: set[str] = set()
_last_sent_at: dict[str, float] = {}
_last_alignment: dict[str, str] = {}

_HIGH_IMPORTANCE = frozenset({NewsImportance.HIGH, NewsImportance.CRITICAL})
_ICT_CONFIRM_STATES = frozenset(
    {"MSS_CONFIRMED", "ENTRY_ZONE_ACTIVE", "TRIGGERED", "LIQUIDITY_SWEPT"}
)


def _normalize_webhook_url(url: str) -> str:
    u = (url or "").strip()
    if u.startswith("https://discordapp.com/api/webhooks/"):
        return "https://discord.com/api/webhooks/" + u.removeprefix("https://discordapp.com/api/webhooks/")
    return u


def macro_discord_configured(settings: Settings | None = None) -> bool:
    st = settings or get_settings()
    url = _normalize_webhook_url(st.discord_macro_webhook_url or "")
    return bool(st.discord_macro_alerts_enabled and url.startswith("https://discord.com/api/webhooks/"))


def macro_discord_status(settings: Settings | None = None) -> dict[str, Any]:
    st = settings or get_settings()
    return {
        "enabled": st.discord_macro_alerts_enabled,
        "configured": macro_discord_configured(st),
        "cooldown_sec": st.discord_macro_cooldown_sec,
        "approach_minutes": _approach_minutes(st),
        "webhook_set": bool((st.discord_macro_webhook_url or "").strip()),
    }


def _approach_minutes(st: Settings) -> list[int]:
    raw = (st.discord_macro_approach_minutes or "15,30").strip()
    out: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            val = int(part)
        except ValueError:
            continue
        if val > 0:
            out.append(val)
    return sorted(set(out)) or [15, 30]


def _send_embed(*, title: str, description: str, fields: list[dict[str, Any]], color: int) -> tuple[bool, str]:
    st = get_settings()
    if not macro_discord_configured(st):
        return False, "Macro Discord not configured"
    url = _normalize_webhook_url(st.discord_macro_webhook_url or "")
    payload = {
        "username": "Macro Intelligence",
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
    if not macro_discord_configured(st):
        return False
    now = time.time()
    cooldown = max(0, int(st.discord_macro_cooldown_sec))
    with _lock:
        if signal_id in _sent_ids:
            _log.info("[DISCORD] Duplicate macro notification prevented signal_id=%s", signal_id)
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
        _log.info("[DISCORD] Macro signal sent signal_id=%s", signal_id)
        try:
            from app.monitor_state import monitor_store

            monitor_store.add_log("INFO", "discord", f"[DISCORD] Macro alert sent: {signal_id}", key=signal_id)
        except Exception:
            pass
    else:
        with _lock:
            _sent_ids.discard(signal_id)
            _last_sent_at.pop(signal_id, None)
        _log.warning("[DISCORD] Macro send failed signal_id=%s detail=%s", signal_id, detail)
    return ok


def _fmt_num(val: float | None) -> str:
    if val is None:
        return "—"
    return f"{val:.3g}"


def _event_fingerprint(event: EconomicEvent) -> str:
    ext = event.external_event_id or event.event_id
    dt = parse_utc(event.scheduled_at)
    sched = dt.isoformat() if dt else event.scheduled_at
    return f"{ext}:{sched}"


def _fmt_high_impact_release(event: EconomicEvent) -> tuple[str, str, list[dict[str, Any]], int]:
    surprise = interpret_surprise(event)
    title = f"📊 HIGH IMPACT — {event.event}"
    desc_lines = [
        f"**Currency:** {event.currency}",
        f"**Category:** {event.category.value}",
        f"**Scheduled:** {event.scheduled_at}",
    ]
    fields = [
        {"name": "Previous", "value": _fmt_num(event.previous)},
        {"name": "Forecast", "value": _fmt_num(event.forecast)},
        {"name": "Actual", "value": _fmt_num(event.actual)},
        {"name": "Importance", "value": event.importance.value},
        {"name": "Status", "value": event.status.value},
    ]
    color = 15844367
    if surprise:
        fields.extend(
            [
                {"name": "Surprise", "value": f"{surprise.surprise:+.3g}"},
                {"name": "Read", "value": f"{surprise.label} · {surprise.direction.value}"},
                {"name": "Confidence", "value": f"{surprise.confidence:.0f}%"},
            ]
        )
        desc_lines.append(f"**Surprise:** {surprise.driver}")
        if surprise.direction.value.endswith("BULLISH") or surprise.direction.value == "BULLISH":
            color = 3066993
        elif surprise.direction.value.endswith("BEARISH") or surprise.direction.value == "BEARISH":
            color = 15158332
    return title, "\n".join(desc_lines), fields, color


def maybe_alert_released_events(events: list[EconomicEvent]) -> None:
    """Alert when high-impact events release with actual values (ingest hook)."""
    st = get_settings()
    if not macro_discord_configured(st) or not st.market_news_enabled:
        return
    for event in events:
        if event.importance not in _HIGH_IMPORTANCE:
            continue
        if event.actual is None:
            continue
        if event.status.value not in {"RELEASED", "REVISED"}:
            continue
        signal_id = f"{_event_fingerprint(event)}:{event.status.value}"
        title, desc, fields, color = _fmt_high_impact_release(event)
        _dedupe_send(signal_id, title=title, description=desc, fields=fields, color=color)


def _minutes_until(scheduled_at: str, now: datetime) -> int | None:
    dt = parse_utc(scheduled_at)
    if dt is None:
        return None
    return int((dt - now).total_seconds() / 60)


def _maybe_approaching_alerts(desk: dict[str, Any], st: Settings) -> None:
    thresholds = _approach_minutes(st)
    if not thresholds:
        return
    now = datetime.now(timezone.utc)
    rows = desk.get("high_impact_upcoming") or desk.get("calendar_table") or desk.get("upcoming_events") or []
    for row in rows:
        if not isinstance(row, dict):
            continue
        importance = str(row.get("importance") or "").upper()
        if importance not in {"HIGH", "CRITICAL"}:
            continue
        mins = _minutes_until(str(row.get("scheduled_at") or ""), now)
        if mins is None or mins < 0:
            continue
        for threshold in thresholds:
            if mins is None or mins < 0:
                continue
            if mins > threshold or mins < threshold - 2:
                continue
            ext = str(row.get("external_event_id") or row.get("event_id") or row.get("event") or "event")
            sched = str(row.get("scheduled_at") or "")
            signal_id = f"{ext}:{sched}:APPROACH:{threshold}m"
            title = f"⏰ EVENT APPROACHING — {row.get('event') or 'High impact'}"
            desc = (
                f"**Currency:** {row.get('currency') or '—'}\n"
                f"**In ~{mins} minutes** · threshold {threshold}m\n"
                f"**Scheduled:** {sched}"
            )
            fields = [
                {"name": "Importance", "value": importance},
                {"name": "Forecast", "value": _fmt_num(row.get("forecast"))},
                {"name": "Previous", "value": _fmt_num(row.get("previous"))},
            ]
            _dedupe_send(signal_id, title=title, description=desc, fields=fields, color=10181046)


def _technical_confirmation(payload: dict[str, Any]) -> str:
    ict = payload.get("ict") if isinstance(payload.get("ict"), dict) else {}
    if ict.get("valid") or ict.get("analysis_active"):
        state = str(ict.get("setup_state") or ict.get("status") or "").upper()
        if state in _ICT_CONFIRM_STATES:
            return f"ICT {state.replace('_', ' ')}"
    swing = payload.get("swing_strategy") if isinstance(payload.get("swing_strategy"), dict) else {}
    if swing.get("valid"):
        sig = str(swing.get("signal") or "").upper()
        if "BUY" in sig or "SELL" in sig:
            return f"Swing {sig}"
    amd = payload.get("amd_ifvg") if isinstance(payload.get("amd_ifvg"), dict) else {}
    if amd.get("valid") or amd.get("analysis_active"):
        decision = str(amd.get("decision") or "").upper()
        if decision in {"BUY", "SELL"}:
            return f"AMD {decision}"
    return ""


def _alignment_became_aligned(symbol: str, status: str) -> bool:
    with _lock:
        prev = _last_alignment.get(symbol)
        _last_alignment[symbol] = status
    return status == MacroConflictStatus.ALIGNED.value and prev != MacroConflictStatus.ALIGNED.value


def _maybe_alignment_alert(symbol: str, desk: dict[str, Any], payload: dict[str, Any], st: Settings) -> None:
    alignment = desk.get("technical_alignment") if isinstance(desk.get("technical_alignment"), dict) else {}
    status = str(alignment.get("status") or "")
    if not _alignment_became_aligned(symbol, status):
        return

    macro = desk.get("macro_bias") if isinstance(desk.get("macro_bias"), dict) else {}
    conf = float(macro.get("confidence") or 0)
    if conf < st.discord_macro_alignment_min_confidence:
        return

    tech_dir = str(alignment.get("technical_direction") or "")
    macro_dir = str(alignment.get("macro_direction") or macro.get("direction") or "")
    if tech_dir == "NEUTRAL" or macro_dir == "NEUTRAL":
        return

    tech_note = _technical_confirmation(payload)
    if not tech_note:
        return

    signal_id = f"{symbol}:ALIGNED:{macro_dir}:{tech_dir}:{tech_note.replace(' ', '_')}"
    title = f"🤝 MACRO + TECHNICAL ALIGNMENT — {symbol}"
    desc = (
        f"**Macro:** {macro_dir} ({conf:.0f}%)\n"
        f"**Technical:** {tech_dir}\n"
        f"**Confirmation:** {tech_note}\n"
        f"{alignment.get('reason') or ''}"
    )
    base = (st.public_base_url or "").rstrip("/")
    if base:
        desc += f"\n[News / Macro desk]({base}/market-news)"
    fields = [
        {"name": "Horizon", "value": macro.get("horizon") or "—"},
        {"name": "Recommendation", "value": alignment.get("recommendation") or "CONFIRM"},
    ]
    drivers = desk.get("drivers") or []
    if drivers:
        fields.append({"name": "Drivers", "value": "\n".join(f"• {d}" for d in drivers[:5]), "inline": False})
    color = 3066993 if macro_dir == "BULLISH" else (15158332 if macro_dir == "BEARISH" else 3447003)
    _dedupe_send(signal_id, title=title, description=desc, fields=fields, color=color)


def maybe_macro_alert(payload: dict[str, Any]) -> None:
    """Evaluate macro approaching + alignment alerts on EA heartbeat. Never raises."""
    st = get_settings()
    if not macro_discord_configured(st) or not st.market_news_enabled:
        return

    sym = str(payload.get("symbol") or "XAUUSD").upper()
    try:
        from app.market_news.service import build_symbol_status

        desk = build_symbol_status(sym, st, ea_snapshot=payload)
    except Exception:
        return

    _maybe_approaching_alerts(desk, st)
    _maybe_alignment_alert(sym, desk, payload, st)


def reset_state_for_tests() -> None:
    with _lock:
        _sent_ids.clear()
        _last_sent_at.clear()
        _last_alignment.clear()
