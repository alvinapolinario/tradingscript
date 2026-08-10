"""Synthesize module feeds into one master trading verdict for the monitor."""
from __future__ import annotations

from typing import Any


def _u(val: Any) -> str:
    return str(val or "").strip().upper()


def _f(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _module_chip(name: str, status: str, detail: str, tone: str) -> dict[str, str]:
    return {"name": name, "status": status, "detail": detail, "tone": tone}


def build_master_verdict(ea: dict[str, Any]) -> dict[str, Any]:
    """
    One-line verdict for traders: OFFLINE | CRITICAL | NO TRADE | WATCH | SETUP | STRONG.
    Advisory only — never implies auto-execution.
    """
    connected = bool(ea.get("connected"))
    sym = str(ea.get("symbol") or ea.get("broker_symbol") or "—")
    modules: list[dict[str, str]] = []
    blocks: list[str] = []
    boosts: list[str] = []

    if not connected:
        return {
            "verdict": "OFFLINE",
            "tone": "warn",
            "score": 0,
            "side": "—",
            "summary": "Waiting for EA heartbeat on this pair.",
            "blocks": ["EA not connected"],
            "boosts": [],
            "modules": [
                _module_chip("EA", "OFFLINE", "Attach EA + enable Algo Trading", "warn"),
            ],
        }

    risk = _u(ea.get("risk_status"))
    new_entry = _u(ea.get("new_entry_decision"))
    high_spread = bool(ea.get("high_spread"))
    exceeds = bool(ea.get("exceeds_max_position_risk"))
    float_hit = bool(ea.get("float_profit_target_hit"))
    positions = int(ea.get("position_count") or 0)

    swing = ea.get("swing_strategy") if isinstance(ea.get("swing_strategy"), dict) else {}
    lg = ea.get("liquidity_grab") if isinstance(ea.get("liquidity_grab"), dict) else {}
    gsm = ea.get("gold_smc") if isinstance(ea.get("gold_smc"), dict) else {}
    bos = ea.get("breakout_structure") if isinstance(ea.get("breakout_structure"), dict) else {}
    mse = ea.get("market_state_engine") if isinstance(ea.get("market_state_engine"), dict) else {}
    amd = ea.get("amd_ifvg") if isinstance(ea.get("amd_ifvg"), dict) else {}
    box = ea.get("box_theory") if isinstance(ea.get("box_theory"), dict) else {}

    # --- Module chips ---
    if swing.get("valid"):
        sig = str(swing.get("signal") or "—")
        conf = _f(swing.get("confidence"))
        tone = "ok" if "STRONG" in _u(sig) and conf >= 85 else ("warn" if conf >= 65 else "muted")
        modules.append(_module_chip("Swing", sig, f"{conf:.0f}% · {swing.get('entry_quality') or '—'}", tone))

    if lg.get("valid"):
        st = str(lg.get("status") or lg.get("status_line") or "—")
        sc = lg.get("confidence_score") or lg.get("confidence")
        tone = "ok" if "CONFIRMED" in _u(st) or "HIGH_CONF" in _u(st) else "warn"
        modules.append(_module_chip("Liq grab", st[:28], f"score {sc}", tone))

    if gsm.get("analysis_active") or gsm.get("valid"):
        setup = str(gsm.get("setup_type") or "—")
        gsc = _f(gsm.get("setup_score") or gsm.get("confidence_score"))
        tone = "ok" if gsc >= 75 and "NO VALID" not in _u(setup) else "muted"
        modules.append(_module_chip("Gold SMC", setup[:24], f"score {gsc:.0f}", tone))

    if bos.get("valid"):
        grade = str(bos.get("grade_label") or "—")
        bsc = _f(bos.get("confidence_score"))
        tone = "ok" if grade not in ("Reject", "REJECT") and bsc >= 75 else "warn"
        modules.append(_module_chip("Breakout", grade, f"{bsc:.0f}", tone))

    if mse.get("valid"):
        state = str(mse.get("market_state") or mse.get("state_label") or "—")
        modules.append(_module_chip("Mkt state", state[:20], str(mse.get("advice") or "")[:40], "muted"))

    if amd.get("valid") or amd.get("analysis_active"):
        dec = str(amd.get("decision") or "—")
        aconf = _f(amd.get("confidence"))
        st = str(amd.get("setup_state") or "—").replace("_", " ")[:24]
        tone = "ok" if dec in ("BUY", "SELL") and aconf >= 75 else ("warn" if dec == "WAIT" else "muted")
        modules.append(_module_chip("AMD+iFVG", dec, f"{aconf:.0f}% · {st}", tone))

    if box.get("valid") or box.get("analysis_active"):
        sig = str(box.get("signal") or "—")
        bconf = _f(box.get("confidence_score") or box.get("confidence"))
        bst = str(box.get("box_status") or "—").replace("_", " ")[:20]
        tone = "ok" if sig in ("BUY", "SELL") and bconf >= 70 else ("warn" if sig == "WATCH" else "muted")
        modules.append(_module_chip("Box", sig, f"{bconf:.0f}% · {bst}", tone))

    modules.append(
        _module_chip(
            "M30 core",
            new_entry or "—",
            _u(ea.get("trend") or ea.get("market_state") or "—"),
            "ok" if new_entry in ("BUY_ALLOWED", "SELL_ALLOWED") else "muted",
        )
    )

    # --- Hard blocks ---
    if risk == "CRITICAL" or exceeds:
        return {
            "verdict": "CRITICAL",
            "tone": "critical",
            "score": 100,
            "side": "—",
            "summary": f"Critical equity risk ({_f(ea.get('equity_risk_pct')):.1f}% at SL). No new exposure.",
            "blocks": ["Critical / over-max position risk"],
            "boosts": boosts,
            "modules": modules,
        }

    if high_spread:
        blocks.append("High spread")
    if new_entry in ("HIGH_SPREAD", "RISK_BLOCKED"):
        blocks.append(new_entry.replace("_", " ").title())
    if float_hit and positions > 0:
        blocks.append("Float profit target hit — manage manually")

    swing_sig = _u(swing.get("signal"))
    swing_conf = _f(swing.get("confidence"))
    swing_quality = _u(swing.get("entry_quality"))
    swing_strong = swing.get("valid") and "STRONG" in swing_sig and swing_conf >= 85.0
    swing_side = "BUY" if "BUY" in swing_sig else ("SELL" if "SELL" in swing_sig else "—")

    lg_status = _u(lg.get("status") or lg.get("status_line"))
    lg_confirmed = lg.get("valid") and (
        "GRAB_CONFIRMED" in lg_status or "HIGH_CONFIDENCE" in lg_status
    )
    lg_unconfirmed = lg.get("valid") and "UNCONFIRMED" in lg_status

    gsm_setup = str(gsm.get("setup_type") or "")
    gsm_score = _f(gsm.get("setup_score") or gsm.get("confidence_score"))
    gsm_valid = gsm.get("analysis_active") and gsm_setup and "NO VALID" not in _u(gsm_setup)

    bos_grade = str(bos.get("grade_label") or "")
    bos_reject = bos.get("valid") and _u(bos_grade) == "REJECT"

    if lg_unconfirmed:
        blocks.append("Liquidity sweep unconfirmed")
    if bos_reject:
        blocks.append(f"Breakout rejected ({_f(bos.get('confidence_score')):.0f})")

    if new_entry in ("BUY_ALLOWED", "SELL_ALLOWED"):
        boosts.append(f"M30 {new_entry.replace('_', ' ')}")
    if lg_confirmed:
        boosts.append("Liquidity grab confirmed")
    if gsm_valid and gsm_score >= 75:
        boosts.append(f"Gold SMC {gsm_setup}")
    if swing_strong:
        boosts.append(f"Swing {swing_sig}")

    # --- Score ---
    score = 25.0
    if new_entry in ("BUY_ALLOWED", "SELL_ALLOWED"):
        score += 20.0
    if swing_strong:
        score += 35.0
    elif swing_conf >= 72:
        score += 12.0
    if lg_confirmed:
        score += 18.0
    elif lg_unconfirmed:
        score += 5.0
    if gsm_valid:
        score += min(20.0, gsm_score / 5.0)
    if bos.get("valid") and _u(bos_grade) != "REJECT":
        score += min(10.0, _f(bos.get("confidence_score")) / 10.0)
    score -= 12.0 * len(blocks)
    score = max(0.0, min(100.0, score))

    side = "—"
    if swing_side in ("BUY", "SELL"):
        side = swing_side
    elif new_entry == "BUY_ALLOWED":
        side = "BUY"
    elif new_entry == "SELL_ALLOWED":
        side = "SELL"

    # --- Verdict label ---
    if swing_strong and swing_quality in ("GOOD", "EXCELLENT") and not blocks:
        verdict = "STRONG"
        tone = "ok"
        summary = f"Strong confluence — {swing_sig} ({swing_conf:.0f}%, {swing_quality.title()})."
    elif score >= 68 and boosts and len(blocks) <= 1:
        verdict = "SETUP"
        tone = "ok"
        summary = "Actionable setup forming — confirm on closed candles before manual entry."
    elif boosts or lg_unconfirmed or new_entry == "WAIT" or score >= 38:
        verdict = "WATCH"
        tone = "warn"
        summary = "Mixed signals — monitor levels; do not chase until confirmation."
    else:
        verdict = "NO TRADE"
        tone = "muted"
        summary = "No actionable edge — stand aside."

    if blocks and verdict in ("SETUP", "WATCH"):
        summary += " Caution: " + "; ".join(blocks[:2]) + "."

    return {
        "verdict": verdict,
        "tone": tone,
        "score": round(score, 1),
        "side": side,
        "summary": summary,
        "blocks": blocks,
        "boosts": boosts,
        "modules": modules,
    }
