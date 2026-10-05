"""
Backtest evidence for live signals.

Reads ``strategy_scorecard.json`` produced offline by ``python -m app.research.cli``
and answers, for a strategy + confidence score: how did signals like this
actually perform on history? With ``EVIDENCE_GATE_ENABLED=true`` actionable
alerts from strategies without demonstrated edge are suppressed.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.paths import data_dir

SCORECARD_FILENAME = "strategy_scorecard.json"
MIN_BUCKET_TRADES = 10

_lock = threading.Lock()
_cache: dict[str, Any] = {"path": None, "mtime": None, "data": None}


def scorecard_path(settings: Settings | None = None) -> Path:
    st = settings or get_settings()
    raw = (st.strategy_scorecard_path or "").strip()
    return Path(raw) if raw else data_dir() / SCORECARD_FILENAME


def load_scorecard(settings: Settings | None = None) -> dict[str, Any] | None:
    """Parsed scorecard, re-read only when the file changes. None when absent/invalid."""
    path = scorecard_path(settings)
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    with _lock:
        if _cache["path"] == str(path) and _cache["mtime"] == mtime:
            return _cache["data"]
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = None
        if not isinstance(data, dict) or not isinstance(data.get("strategies"), dict):
            data = None
        _cache.update(path=str(path), mtime=mtime, data=data)
        return data


def _bucket_for(buckets: list[dict[str, Any]], confidence: float) -> dict[str, Any] | None:
    for b in buckets or []:
        lo, hi = float(b.get("lo", 0)), float(b.get("hi", 0))
        if lo <= confidence < hi or (hi >= 100 and confidence >= 100):
            return b if int(b.get("n", 0)) >= MIN_BUCKET_TRADES else None
    return None


def strategy_evidence(strategy: str, confidence: float, settings: Settings | None = None) -> dict[str, Any]:
    """
    Evidence for one signal. ``allowed`` applies the gate rules:

      EDGE              → allowed (above the out-of-sample confirmed floor, if one exists)
      INCONCLUSIVE /
      NO_EDGE           → allowed only above a confidence floor confirmed out of sample
      INSUFFICIENT_DATA /
      not in scorecard  → allowed, flagged unmeasured
    """
    sc = load_scorecard(settings)
    base: dict[str, Any] = {"strategy": strategy, "confidence": round(float(confidence or 0), 1)}
    res = (sc or {}).get("strategies", {}).get(strategy)
    if not isinstance(res, dict):
        return {**base, "measured": False, "allowed": True, "reason": "no_scorecard" if sc is None else "not_in_scorecard"}

    overall = res.get("overall") or {}
    th = res.get("threshold") or {}
    floor = th.get("min_confidence") if th.get("confirmed") else None
    verdict = str(res.get("verdict") or "INSUFFICIENT_DATA")
    above_floor = floor is not None and confidence >= float(floor)

    if verdict == "EDGE":
        allowed = floor is None or above_floor
        reason = "edge" if allowed else "below_confirmed_floor"
    elif verdict in ("INCONCLUSIVE", "NO_EDGE"):
        allowed = above_floor
        reason = "above_confirmed_floor" if allowed else verdict.lower()
    else:
        allowed, reason = True, "insufficient_data"

    return {
        **base,
        "measured": verdict != "INSUFFICIENT_DATA",
        "allowed": allowed,
        "reason": reason,
        "verdict": verdict,
        "sample_size": int(overall.get("n", 0)),
        "win_rate": overall.get("win_rate"),
        "avg_r": overall.get("avg_r"),
        "profit_factor": overall.get("profit_factor"),
        "confirmed_min_confidence": floor,
        "bucket": _bucket_for(res.get("confidence_buckets") or [], float(confidence or 0)),
        "scorecard_generated_utc": (sc or {}).get("generated_utc"),
        "data_range": f"{(sc or {}).get('data', {}).get('from', '?')} → {(sc or {}).get('data', {}).get('to', '?')}",
    }


def gate(strategy: str, confidence: float, settings: Settings | None = None) -> tuple[bool, dict[str, Any]]:
    """(send?, evidence). The gate only blocks when EVIDENCE_GATE_ENABLED is true."""
    st = settings or get_settings()
    ev = strategy_evidence(strategy, confidence, st)
    return (ev["allowed"] or not st.evidence_gate_enabled), ev


def evidence_text(ev: dict[str, Any]) -> str:
    if not ev.get("measured"):
        if ev.get("reason") == "insufficient_data":
            return f"Not enough backtest trades yet ({ev.get('sample_size', 0)})."
        return "Not measured — run `python -m app.research.cli` and install strategy_scorecard.json."
    headline = f"{ev['verdict']} · {ev['sample_size']} trades"
    if ev.get("win_rate") is not None:
        headline += f" · {ev['win_rate'] * 100:.0f}% win · {ev.get('avg_r') or 0:+.2f}R avg"
    parts = [headline]
    b = ev.get("bucket")
    if b:
        parts.append(f"Confidence {b['lo']}–{b['hi']}: {b['n']} trades, {b.get('avg_r', 0):+.2f}R avg")
    if ev.get("confirmed_min_confidence") is not None:
        parts.append(f"Out-of-sample floor: {ev['confirmed_min_confidence']:.0f}")
    return "\n".join(parts)


def evidence_field(ev: dict[str, Any]) -> dict[str, Any]:
    return {"name": "Backtest evidence", "value": evidence_text(ev), "inline": False}


def scorecard_summary(settings: Settings | None = None) -> dict[str, Any]:
    st = settings or get_settings()
    sc = load_scorecard(st)
    if sc is None:
        return {"available": False, "path": str(scorecard_path(st)), "gate_enabled": st.evidence_gate_enabled}
    return {
        "available": True,
        "gate_enabled": st.evidence_gate_enabled,
        "generated_utc": sc.get("generated_utc"),
        "data": sc.get("data"),
        "assumptions": sc.get("assumptions"),
        "strategies": {
            name: {
                "verdict": res.get("verdict"),
                "overall": res.get("overall"),
                "threshold": {
                    k: (res.get("threshold") or {}).get(k) for k in ("min_confidence", "confirmed")
                },
                "confidence_buckets": res.get("confidence_buckets"),
            }
            for name, res in sc["strategies"].items()
            if isinstance(res, dict)
        },
    }
