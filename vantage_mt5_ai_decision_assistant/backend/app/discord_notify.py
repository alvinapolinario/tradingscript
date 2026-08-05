"""Discord webhook alerts — backend only; webhook URL stays in .env."""
from __future__ import annotations

import threading
import time
from typing import Any

import httpx

from app.config import Settings, get_settings

_lock = threading.Lock()
_last_state: dict[str, str] = {}
_last_sent_at: dict[str, float] = {}


def _normalize_webhook_url(url: str) -> str:
    u = (url or "").strip()
    if u.startswith("https://discordapp.com/api/webhooks/"):
        return "https://discord.com/api/webhooks/" + u.removeprefix("https://discordapp.com/api/webhooks/")
    return u


def discord_configured(settings: Settings | None = None) -> bool:
    st = settings or get_settings()
    url = _normalize_webhook_url(st.discord_webhook_url or "")
    return bool(st.discord_enabled and url.startswith("https://discord.com/api/webhooks/"))


def discord_status(settings: Settings | None = None) -> dict[str, Any]:
    st = settings or get_settings()
    return {
        "enabled": st.discord_enabled,
        "configured": discord_configured(st),
        "cooldown_sec": st.discord_cooldown_sec,
        "webhook_set": bool((st.discord_webhook_url or "").strip()),
        "trades_only": st.discord_trades_only,
        "trades_min_amd_ifvg_conf": st.discord_trades_min_amd_ifvg_conf,
    }


def _send_raw(message: str, *, color: int | None = None) -> tuple[bool, str]:
    st = get_settings()
    if not discord_configured(st):
        return False, "Discord not configured"
    url = _normalize_webhook_url(st.discord_webhook_url or "")
    payload: dict[str, Any] = {
        "username": "Vantage AI",
        "content": message[:2000],
    }
    if color is not None:
        payload["embeds"] = [{"description": message[:4096], "color": color}]
        payload.pop("content", None)
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=payload)
        if resp.status_code in (200, 204):
            return True, "sent"
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as exc:
        return False, str(exc)


def send_test_message() -> tuple[bool, str]:
    st = get_settings()
    base = (st.public_base_url or "").rstrip("/")
    msg = (
        "✅ **Vantage AI Discord test**\n"
        f"Monitor: {base}/monitor\n"
        "Advisory only — no auto-trades."
    )
    return _send_raw(msg, color=3066993)


def _dedupe_send(event_key: str, message: str, cooldown_sec: int | None = None, *, color: int | None = None) -> bool:
    st = get_settings()
    if not discord_configured(st):
        return False
    cd = st.discord_cooldown_sec if cooldown_sec is None else cooldown_sec
    now = time.time()
    with _lock:
        last = _last_sent_at.get(event_key, 0.0)
        if now - last < cd:
            return False
        _last_sent_at[event_key] = now
    ok, detail = _send_raw(message, color=color)
    if not ok:
        with _lock:
            _last_sent_at.pop(event_key, None)
        try:
            from app.monitor_state import monitor_store

            monitor_store.add_log("WARN", "discord", f"Send failed: {detail}", key=event_key)
        except Exception:
            pass
    return ok


def _state_changed(scope: str, value: str) -> bool:
    with _lock:
        prev = _last_state.get(scope)
        if prev == value:
            return False
        _last_state[scope] = value
        return True


def _fmt_header(title: str, symbol: str) -> str:
    return f"**{title} · {symbol}**"


def notify_accepted_signal(signal: dict[str, Any]) -> None:
    if not get_settings().telegram_alert_signals:
        return
    sym = str(signal.get("symbol") or "XAUUSD").upper()
    side = str(signal.get("side") or "?")
    score = signal.get("score")
    entry = signal.get("entry_lo") or signal.get("entry")
    sl = signal.get("stop_loss") or signal.get("sl")
    st = get_settings()
    base = st.public_base_url.rstrip("/")
    msg = (
        f"{_fmt_header('Accepted signal', sym)}\n"
        f"Side: **{side}** · Score: `{score}`\n"
        f"Entry: `{entry}` · SL: `{sl}`\n"
        f"[Signals ledger]({base}/signals)"
    )
    _dedupe_send(f"signal|{signal.get('id') or sym}|{side}", msg, cooldown_sec=60, color=3447003)


def notify_execution_ack(signal: dict[str, Any], status: str) -> None:
    if not get_settings().telegram_alert_execution:
        return
    sym = str(signal.get("symbol") or "XAUUSD").upper()
    side = str(signal.get("side") or "?")
    msg = (
        f"{_fmt_header(f'Demo exec {status}', sym)}\n"
        f"Side: `{side}` · Signal: `{signal.get('id', '')}`"
    )
    ticket = signal.get("ticket")
    if ticket:
        msg += f"\nTicket: `{ticket}`"
    color = 3066993 if status == "FILLED" else 15105570
    _dedupe_send(f"exec|{signal.get('id')}|{status}", msg, cooldown_sec=30, color=color)


def _discord_category_enabled(st: Settings, category: str) -> bool:
    """Respect discord_trades_only — skip noisy categories; keep actionable trades + critical risk."""
    if not st.discord_trades_only:
        mapping = {
            "risk": st.telegram_alert_risk,
            "float_target": st.telegram_alert_float_target,
            "entry": st.telegram_alert_entry,
            "signals": st.telegram_alert_signals,
            "swing": st.telegram_alert_swing,
            "liquidity_grab": st.telegram_alert_liquidity_grab,
            "gold_smc": st.telegram_alert_gold_smc,
            "amd_ifvg": st.telegram_alert_amd_ifvg,
            "execution": st.telegram_alert_execution,
        }
        return bool(mapping.get(category, True))
    return category in ("risk", "signals", "swing", "master", "amd_ifvg")


def _maybe_master_verdict_alert(payload: dict[str, Any], sym: str, st: Settings, *, verdicts: tuple[str, ...]) -> None:
    try:
        from app.analysis.master_verdict import build_master_verdict

        mv = build_master_verdict({**payload, "connected": True})
        verdict = str(mv.get("verdict") or "")
        if verdict not in verdicts:
            return
        if not _state_changed(f"{sym}|master|{verdict}", verdict):
            return
        side = mv.get("side") or "—"
        base = st.public_base_url.rstrip("/")
        modules = mv.get("modules") or []
        mod_line = " · ".join(f"{m.get('name')}: {m.get('status')}" for m in modules[:5])
        msg = (
            f"{_fmt_header(f'Master {verdict}', sym)}\n"
            f"Side: `{side}` · Score: `{mv.get('score')}`\n"
            f"{mv.get('summary') or ''}\n"
        )
        if mod_line:
            msg += f"Modules: `{mod_line}`\n"
        msg += f"[Monitor]({base}/monitor)"
        color = 15158332 if verdict == "CRITICAL" else (3066993 if verdict == "STRONG" else 3447003)
        _dedupe_send(
            f"{sym}|master|{verdict}|{side}",
            msg,
            cooldown_sec=max(st.discord_cooldown_sec, 600),
            color=color,
        )
    except Exception:
        pass


def _maybe_swing_trade_alert(payload: dict[str, Any], sym: str, st: Settings) -> None:
    if not _discord_category_enabled(st, "swing"):
        return
    swing = payload.get("swing_strategy")
    if not isinstance(swing, dict) or not swing.get("valid"):
        return
    signal = str(swing.get("signal") or "")
    sig_u = signal.upper()
    conf = float(swing.get("confidence") or 0)
    quality = str(swing.get("entry_quality") or "").upper()
    if quality == "AVOID":
        return
    min_conf = st.discord_trades_min_swing_conf if st.discord_trades_only else 85.0
    strong = "STRONG" in sig_u and conf >= 85.0
    swing_trade = ("SWING BUY" in sig_u or "SWING SELL" in sig_u) and conf >= min_conf
    if st.discord_trades_only and not (strong or swing_trade):
        return
    if not st.discord_trades_only and not strong:
        return
    key = f"{sym}|swing|{signal}|{int(conf)}"
    if not _state_changed(key, key):
        return
    sl = swing.get("stop_loss") or swing.get("sl")
    entry = swing.get("entry") or swing.get("entry_price")
    msg = (
        f"{_fmt_header('Swing trade', sym)}\n"
        f"Signal: `{signal}` · Conf: `{conf:.1f}`\n"
        f"Quality: `{swing.get('entry_quality') or '—'}`"
    )
    if entry:
        msg += f"\nEntry: `{entry}` · SL: `{sl}`"
    _dedupe_send(key, msg, color=3066993)


def _maybe_amd_ifvg_alert(payload: dict[str, Any], sym: str, st: Settings) -> None:
    if not _discord_category_enabled(st, "amd_ifvg"):
        return
    amd = payload.get("amd_ifvg")
    if not isinstance(amd, dict) or not (amd.get("valid") or amd.get("analysis_active")):
        return
    if amd.get("gold_symbol_valid") is False:
        return

    decision = str(amd.get("decision") or "NO_TRADE").upper()
    conf = float(amd.get("confidence") or 0)
    setup_state = str(amd.get("setup_state") or "")
    amd_phase = str(amd.get("amd_phase") or "—")
    min_conf = st.discord_trades_min_amd_ifvg_conf if st.discord_trades_only else 75.0

    trade_signal = decision in ("BUY", "SELL") and conf >= min_conf
    entry_zone = (
        decision == "WAIT"
        and setup_state == "ENTRY_ZONE_ACTIVE"
        and conf >= min_conf
    )
    if not (trade_signal or entry_zone):
        return

    eval_bar = str(amd.get("eval_bar_m5") or amd.get("timestamp") or "")
    key = f"{sym}|amd|{decision}|{setup_state}|{int(conf)}|{eval_bar}"
    if not _state_changed(key, key):
        return

    entry = amd.get("entry") if isinstance(amd.get("entry"), dict) else {}
    risk = amd.get("risk") if isinstance(amd.get("risk"), dict) else {}
    ifvg = amd.get("ifvg") if isinstance(amd.get("ifvg"), dict) else {}
    preferred = entry.get("preferred_entry")
    entry_lo = entry.get("entry_low")
    entry_hi = entry.get("entry_high")
    sl = risk.get("stop_loss")
    htf = amd.get("higher_timeframe_bias") or "—"

    title = "AMD + iFVG trade" if trade_signal else "AMD + iFVG entry zone"
    base = st.public_base_url.rstrip("/")
    msg = (
        f"{_fmt_header(title, sym)}\n"
        f"Decision: **{decision}** · Conf: `{conf:.1f}`\n"
        f"Phase: `{amd_phase}` · State: `{setup_state.replace('_', ' ')}`\n"
        f"HTF bias: `{htf}`"
    )
    if ifvg.get("detected"):
        msg += f"\niFVG: `{ifvg.get('direction')}` ({ifvg.get('lower_boundary')} – {ifvg.get('upper_boundary')})"
    if preferred:
        msg += f"\nPreferred entry: `{preferred}`"
    elif entry_lo and entry_hi:
        msg += f"\nEntry zone: `{entry_lo}` – `{entry_hi}`"
    if sl:
        msg += f" · SL: `{sl}`"
    narrative = amd.get("technical_narrative") or ""
    if narrative:
        msg += f"\n{narrative[:240]}"
    msg += f"\n[AMD + iFVG desk]({base}/amd-ifvg)"

    color = 3066993 if decision == "BUY" else (15158332 if decision == "SELL" else 3447003)
    _dedupe_send(key, msg, color=color)


def process_heartbeat(payload: dict[str, Any], accepted: dict[str, Any] | None = None) -> None:
    """Evaluate heartbeat payload and send Discord alerts. Never raises."""
    st = get_settings()
    if not discord_configured(st):
        return

    sym = str(payload.get("symbol") or "XAUUSD").upper()
    trades_only = st.discord_trades_only

    if accepted and _discord_category_enabled(st, "signals"):
        notify_accepted_signal(accepted)

    if _discord_category_enabled(st, "risk"):
        risk = str(payload.get("risk_status") or "")
        critical = risk == "CRITICAL" or bool(payload.get("exceeds_max_position_risk"))
        if critical and _state_changed(f"{sym}|risk", risk):
            eq_risk = payload.get("equity_risk_pct")
            msg = (
                f"{_fmt_header('CRITICAL RISK', sym)}\n"
                f"Status: `{risk}` · Equity at SL: `{eq_risk}%`\n"
                f"Action: `{payload.get('primary_action') or payload.get('action') or ''}`"
            )
            _dedupe_send(f"{sym}|critical", msg, color=15158332)

        if not trades_only and st.telegram_alert_float_target and bool(payload.get("float_profit_target_hit")):
            if _state_changed(f"{sym}|float_hit", "1"):
                fpct = payload.get("floating_pl_pct_of_equity")
                msg = (
                    f"{_fmt_header('Float profit target', sym)}\n"
                    f"Floating P/L: `{fpct}%` of equity\n"
                    "Consider taking partial profit manually."
                )
                _dedupe_send(f"{sym}|float_target", msg, color=15844367)

    if not trades_only and st.telegram_alert_entry:
        entry = str(payload.get("new_entry_decision") or "")
        if entry in ("BUY_ALLOWED", "SELL_ALLOWED") and _state_changed(f"{sym}|entry", entry):
            bid = payload.get("bid")
            trend = payload.get("trend") or payload.get("market_state")
            base = st.public_base_url.rstrip("/")
            msg = (
                f"{_fmt_header('New entry watch', sym)}\n"
                f"Decision: **{entry}** · Trend: `{trend}`\n"
                f"Bid: `{bid}`\n"
                f"[Monitor]({base}/monitor)"
            )
            _dedupe_send(f"{sym}|entry|{entry}", msg, color=3447003)

    _maybe_swing_trade_alert(payload, sym, st)
    _maybe_amd_ifvg_alert(payload, sym, st)

    if not trades_only and st.telegram_alert_liquidity_grab:
        lg = payload.get("liquidity_grab")
        if isinstance(lg, dict) and lg.get("valid"):
            status = str(lg.get("status") or lg.get("status_line") or "")
            status_u = status.upper()
            if "GRAB_CONFIRMED" in status_u or "HIGH_CONFIDENCE" in status_u:
                key = f"{sym}|lg|{status}"
                if _state_changed(key, status):
                    score = lg.get("confidence_score") or lg.get("confidence")
                    msg = (
                        f"{_fmt_header('Liquidity grab', sym)}\n"
                        f"Status: `{status}` · Score: `{score}`"
                    )
                    _dedupe_send(key, msg, color=10181046)

    if not trades_only and st.telegram_alert_gold_smc:
        gsm = payload.get("gold_smc")
        if isinstance(gsm, dict) and gsm.get("analysis_active"):
            setup = str(gsm.get("setup_type") or "")
            score = float(gsm.get("setup_score") or gsm.get("confidence_score") or 0)
            min_score = st.telegram_gold_smc_min_score
            if setup and "No Valid" not in setup and score >= min_score:
                key = f"{sym}|gsm|{setup}|{int(score)}"
                if _state_changed(key, key):
                    base = st.public_base_url.rstrip("/")
                    msg = (
                        f"{_fmt_header('Gold SMC setup', sym)}\n"
                        f"Setup: `{setup}` · Score: `{score:.0f}`\n"
                        f"[Gold SMC desk]({base}/gold-smc)"
                    )
                    _dedupe_send(key, msg, color=15844367)

    if st.discord_enabled:
        master_verdicts = ("STRONG", "SETUP", "CRITICAL") if trades_only else ("STRONG", "CRITICAL")
        _maybe_master_verdict_alert(payload, sym, st, verdicts=master_verdicts)


def reset_state_for_tests() -> None:
    with _lock:
        _last_state.clear()
        _last_sent_at.clear()
