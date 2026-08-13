"""H4 → M15 FVG strategy — analysis service entry point."""
from __future__ import annotations

from typing import Any

from app.analysis.desk_symbol_validator import desk_disable_message, is_approved_desk_symbol
from app.analysis.h4_m15_fvg.engine import H4M15Engine
from app.analysis.h4_m15_fvg.explain import setup_to_json, setup_to_text
from app.analysis.h4_m15_fvg.store import save_setup_snapshot
from app.analysis.h4_m15_fvg.types import DEFAULT_H4_M15_CONFIG, H4M15FvgConfig, H4M15SetupState
from app.market_structure import atr, candles_from_payload, htf_bias, validate_candles
from app.market_structure.types import Candle


def _dealing_range(candles: list[Candle]) -> tuple[float, float]:
    if not candles:
        return 0.0, 0.0
    look = candles[-min(50, len(candles)) :]
    return max(c.high for c in look), min(c.low for c in look)


def analyze_h4_m15_fvg(
    *,
    symbol: str,
    candles_h4: list[Candle] | None = None,
    candles_m15: list[Candle] | None = None,
    candles_by_timeframe: dict[str, list[Candle]] | None = None,
    cfg: H4M15FvgConfig | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Run H4→M15 FVG orchestration on closed OHLC only. No trade execution."""
    st = cfg or DEFAULT_H4_M15_CONFIG
    sym = (symbol or "XAUUSD").upper()
    desk_ok, _ = is_approved_desk_symbol(sym)
    if not desk_ok:
        return {
            "module": "h4_m15_fvg",
            "symbol": sym,
            "valid": False,
            "reason": desk_disable_message("H4→M15 FVG Engine"),
            "setups": [],
        }

    tf_map = dict(candles_by_timeframe or {})
    h4 = candles_h4 or tf_map.get(st.htf_timeframe) or tf_map.get("H4") or []
    m15 = candles_m15 or tf_map.get(st.execution_timeframe) or tf_map.get("M15") or []

    err = validate_candles(h4) if h4 else "Missing H4 candles"
    if h4 and not err:
        err = validate_candles(m15) if m15 else "Missing M15 candles"
    if err or not h4 or not m15:
        return {
            "module": "h4_m15_fvg",
            "symbol": sym,
            "valid": False,
            "reason": err or "Insufficient candle data",
            "setups": [],
        }

    if len(h4) < 5 or len(m15) < st.pivot_left + st.pivot_right + 5:
        return {
            "module": "h4_m15_fvg",
            "symbol": sym,
            "valid": False,
            "reason": "Need more closed H4/M15 history",
            "setups": [],
        }

    atr_h4 = atr(h4)
    atr_m15 = atr(m15)
    bias = htf_bias(h4)
    d_hi, d_lo = _dealing_range(h4)

    engine = H4M15Engine(st)
    engine.bootstrap_h4(sym, h4, atr_h4)

    for i in range(len(m15)):
        hist = m15[: i + 1]
        engine.process_m15_bar(
            m15[i],
            hist,
            atr_m15,
            htf_bias=bias,
            dealing_high=d_hi,
            dealing_low=d_lo,
        )

    setups = engine.all_setups()
    if persist:
        for s in setups:
            save_setup_snapshot(s)

    active = [s for s in setups if s.state not in (
        H4M15SetupState.SETUP_INVALIDATED,
        H4M15SetupState.SETUP_EXPIRED,
    )]
    entry_ready = [s for s in setups if s.state == H4M15SetupState.ENTRY_READY]

    return {
        "module": "h4_m15_fvg",
        "symbol": sym,
        "valid": True,
        "advisory_only": True,
        "decision": "ENTRY_READY" if entry_ready else "MONITOR",
        "active_setup_count": len(active),
        "entry_ready_count": len(entry_ready),
        "setups": [setup_to_json(s) for s in setups],
        "primary": setup_to_json(entry_ready[-1]) if entry_ready else (setup_to_json(active[-1]) if active else None),
        "explanation_text": setup_to_text(entry_ready[-1]) if entry_ready else (
            setup_to_text(active[-1]) if active else f"{sym}: No active H4→M15 FVG setup."
        ),
        "config": {
            "htf_timeframe": st.htf_timeframe,
            "execution_timeframe": st.execution_timeframe,
            "min_h4_fvg_atr": st.min_h4_fvg_atr,
            "min_m15_fvg_atr": st.min_m15_fvg_atr,
        },
    }


def candles_from_request(raw: dict) -> dict[str, list[Candle]]:
    out: dict[str, list[Candle]] = {}
    for tf, rows in (raw or {}).items():
        if isinstance(rows, list):
            out[str(tf).upper()] = candles_from_payload(rows)
    return out
