"""Chronological ICT replay harness — one closed bar at a time, no look-ahead."""
from __future__ import annotations

from typing import Any

from app.analysis.ict import analyze_ict_strategy
from app.analysis.ict.types import DEFAULT_ICT_CONFIG, IctConfig
from app.market_structure.types import Candle


def replay_ict_sequence(
    *,
    symbol: str,
    setup_candles: list[Candle],
    execution_candles: list[Candle] | None = None,
    bids: list[float] | None = None,
    cfg: IctConfig | None = None,
) -> list[dict[str, Any]]:
    """
    Feed setup candles incrementally; at step N only bars[:N] are visible.
    Optional ``bids`` aligned to setup steps for touch simulation.
    """
    st = cfg or DEFAULT_ICT_CONFIG
    min_n = max(st.min_candles, 3)
    steps: list[dict[str, Any]] = []
    exec_all = execution_candles or setup_candles

    for n in range(min_n, len(setup_candles) + 1):
        partial_setup = setup_candles[:n]
        last_t = partial_setup[-1].time
        partial_exec = [c for c in exec_all if c.time <= last_t]
        bid = bids[n - min_n] if bids and len(bids) > n - min_n else partial_setup[-1].close
        result = analyze_ict_strategy(
            symbol=symbol,
            candles_setup=partial_setup,
            candles_execution=partial_exec if partial_exec else partial_setup,
            bid=bid,
            cfg=st,
        )
        steps.append(
            {
                "step": n,
                "eval_bar_time": last_t,
                "state": result.get("state") or result.get("status"),
                "decision": result.get("decision"),
                "causality_valid": result.get("causality_valid"),
                "causality_errors": result.get("causality_errors"),
                "setup_id": result.get("setup_id"),
                "liquidity_event": result.get("liquidity_event"),
                "displacement_event": result.get("displacement_event"),
                "mss_event": result.get("mss_event"),
                "execution_fvg": result.get("execution_fvg"),
                "entry_ready": result.get("entry_ready"),
            }
        )
    return steps
