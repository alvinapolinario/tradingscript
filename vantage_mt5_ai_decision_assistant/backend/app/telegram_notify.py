"""Telegram Bot alerts — backend only; secrets stay in .env."""
from __future__ import annotations

import re
import threading
import time
from typing import Any

import httpx

from app.config import Settings, get_settings

_lock = threading.Lock()
_last_state: dict[str, str] = {}
_last_sent_at: dict[str, float] = {}


def telegram_configured(settings: Settings | None = None) -> bool:
    st = settings or get_settings()
    return bool(
        st.telegram_enabled
        and st.telegram_bot_token
        and st.telegram_chat_id
    )


def telegram_status(settings: Settings | None = None) -> dict[str, Any]:
    st = settings or get_settings()
    ready = telegram_configured(st)
    return {
        "enabled": st.telegram_enabled,
        "configured": ready,
        "cooldown_sec": st.telegram_cooldown_sec,
        "chat_id_set": bool(st.telegram_chat_id),
    }


def _escape_md(text: str) -> str:
    """Minimal escape for Telegram MarkdownV2."""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!\\])", r"\\\1", str(text or ""))


def _send_raw(message: str, *, parse_mode: str = "MarkdownV2") -> tuple[bool, str]:
    st = get_settings()
    if not telegram_configured(st):
        return False, "Telegram not configured"
    token = st.telegram_bot_token.strip()
    chat_id = st.telegram_chat_id.strip()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": message[:4096],
        "disable_web_page_preview": True,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=payload)
        if resp.status_code == 200 and resp.json().get("ok"):
            return True, "sent"
        # Fallback plain text if Markdown rejected
        if parse_mode and resp.status_code == 400:
            plain = re.sub(r"\\([_*\[\]()~`>#+\-=|{}.!\\])", r"\1", message)
            plain = plain.replace("*", "").replace("`", "")
            with httpx.Client(timeout=10.0) as client:
                resp2 = client.post(
                    url,
                    json={
                        "chat_id": chat_id,
                        "text": plain[:4096],
                        "disable_web_page_preview": True,
                    },
                )
            if resp2.status_code == 200 and resp2.json().get("ok"):
                return True, "sent_plain"
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as exc:
        return False, str(exc)


def send_test_message() -> tuple[bool, str]:
    st = get_settings()
    base = (st.public_base_url or "").rstrip("/")
    msg = (
        "✅ *Vantage AI Telegram test*\n"
        f"Monitor: `{_escape_md(base + '/monitor')}`\n"
        "Advisory only — no auto\\-trades\\."
    )
    return _send_raw(msg)


def _dedupe_send(event_key: str, message: str, cooldown_sec: int | None = None) -> bool:
    st = get_settings()
    if not telegram_configured(st):
        return False
    cd = st.telegram_cooldown_sec if cooldown_sec is None else cooldown_sec
    now = time.time()
    with _lock:
        last = _last_sent_at.get(event_key, 0.0)
        if now - last < cd:
            return False
        _last_sent_at[event_key] = now
    ok, detail = _send_raw(message)
    if not ok:
        with _lock:
            _last_sent_at.pop(event_key, None)
        try:
            from app.monitor_state import monitor_store

            monitor_store.add_log("WARN", "telegram", f"Send failed: {detail}", key=event_key)
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
    return f"*{_escape_md(title)}* · `{_escape_md(symbol)}`"


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
        f"Side: *{_escape_md(side)}* · Score: `{_escape_md(str(score))}`\n"
        f"Entry: `{_escape_md(str(entry))}` · SL: `{_escape_md(str(sl))}`\n"
        f"[Signals ledger]({_escape_md(base + '/signals')})"
    )
    _dedupe_send(f"signal|{signal.get('id') or sym}|{side}", msg, cooldown_sec=60)


def notify_execution_ack(signal: dict[str, Any], status: str) -> None:
    if not get_settings().telegram_alert_execution:
        return
    sym = str(signal.get("symbol") or "XAUUSD").upper()
    side = str(signal.get("side") or "?")
    msg = (
        f"{_fmt_header(f'Demo exec {status}', sym)}\n"
        f"Side: `{_escape_md(side)}` · Signal: `{_escape_md(str(signal.get('id', '')))}`"
    )
    ticket = signal.get("ticket")
    if ticket:
        msg += f"\nTicket: `{_escape_md(str(ticket))}`"
    _dedupe_send(f"exec|{signal.get('id')}|{status}", msg, cooldown_sec=30)


def process_heartbeat(payload: dict[str, Any], accepted: dict[str, Any] | None = None) -> None:
    """Evaluate heartbeat payload and send Telegram alerts. Never raises."""
    st = get_settings()
    if not telegram_configured(st):
        return

    sym = str(payload.get("symbol") or "XAUUSD").upper()

    if accepted:
        notify_accepted_signal(accepted)

    if st.telegram_alert_risk:
        risk = str(payload.get("risk_status") or "")
        critical = risk == "CRITICAL" or bool(payload.get("exceeds_max_position_risk"))
        if critical and _state_changed(f"{sym}|risk", risk):
            eq_risk = payload.get("equity_risk_pct")
            msg = (
                f"{_fmt_header('CRITICAL RISK', sym)}\n"
                f"Status: `{_escape_md(risk)}` · Equity at SL: `{_escape_md(str(eq_risk))}%`\n"
                f"Action: `{_escape_md(str(payload.get('primary_action') or payload.get('action') or ''))}`"
            )
            _dedupe_send(f"{sym}|critical", msg)

        if st.telegram_alert_float_target and bool(payload.get("float_profit_target_hit")):
            if _state_changed(f"{sym}|float_hit", "1"):
                fpct = payload.get("floating_pl_pct_of_equity")
                msg = (
                    f"{_fmt_header('Float profit target', sym)}\n"
                    f"Floating P/L: `{_escape_md(str(fpct))}%` of equity\n"
                    "Consider taking partial profit manually\\."
                )
                _dedupe_send(f"{sym}|float_target", msg)

    if st.telegram_alert_entry:
        entry = str(payload.get("new_entry_decision") or "")
        if entry in ("BUY_ALLOWED", "SELL_ALLOWED") and _state_changed(f"{sym}|entry", entry):
            bid = payload.get("bid")
            trend = payload.get("trend") or payload.get("market_state")
            base = st.public_base_url.rstrip("/")
            msg = (
                f"{_fmt_header('New entry watch', sym)}\n"
                f"Decision: *{_escape_md(entry)}* · Trend: `{_escape_md(str(trend))}`\n"
                f"Bid: `{_escape_md(str(bid))}`\n"
                f"[Monitor]({_escape_md(base + '/monitor')})"
            )
            _dedupe_send(f"{sym}|entry|{entry}", msg)

    if st.telegram_alert_swing:
        swing = payload.get("swing_strategy")
        if isinstance(swing, dict) and swing.get("valid"):
            signal = str(swing.get("signal") or "")
            conf = float(swing.get("confidence") or 0)
            if "STRONG" in signal.upper() and conf >= 85.0:
                key = f"{sym}|swing|{signal}|{int(conf)}"
                if _state_changed(key, key):
                    msg = (
                        f"{_fmt_header('Swing STRONG', sym)}\n"
                        f"Signal: `{_escape_md(signal)}` · Conf: `{conf:.1f}`\n"
                        f"Quality: `{_escape_md(str(swing.get('entry_quality') or ''))}`"
                    )
                    _dedupe_send(key, msg)

    if st.telegram_alert_liquidity_grab:
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
                        f"Status: `{_escape_md(status)}` · Score: `{_escape_md(str(score))}`"
                    )
                    _dedupe_send(key, msg)

    if st.telegram_alert_gold_smc:
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
                        f"Setup: `{_escape_md(setup)}` · Score: `{score:.0f}`\n"
                        f"[Gold SMC desk]({_escape_md(base + '/gold-smc')})"
                    )
                    _dedupe_send(key, msg)

    if st.telegram_enabled:
        try:
            from app.analysis.master_verdict import build_master_verdict

            mv = build_master_verdict({**payload, "connected": True})
            verdict = str(mv.get("verdict") or "")
            if verdict in ("STRONG", "CRITICAL") and _state_changed(f"{sym}|master|{verdict}", verdict):
                side = mv.get("side") or "—"
                base = st.public_base_url.rstrip("/")
                msg = (
                    f"{_fmt_header(f'Master {verdict}', sym)}\n"
                    f"Side: `{_escape_md(str(side))}` · Score: `{mv.get('score')}`\n"
                    f"{_escape_md(str(mv.get('summary') or ''))}\n"
                    f"[Monitor]({_escape_md(base + '/monitor')})"
                )
                _dedupe_send(f"{sym}|master|{verdict}|{side}", msg, cooldown_sec=max(st.telegram_cooldown_sec, 600))
        except Exception:
            pass


def reset_state_for_tests() -> None:
    with _lock:
        _last_state.clear()
        _last_sent_at.clear()
