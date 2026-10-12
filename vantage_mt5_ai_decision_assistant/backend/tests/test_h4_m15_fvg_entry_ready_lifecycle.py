"""ENTRY_READY must stay live: later closes through the sweep invalidate it, and it expires.

Regression: ENTRY_READY used to be TERMINAL, so a setup kept showing ENTRY_READY after
price had closed through its stop (seen live on XAUUSD: bearish ENTRY_READY with exec FVG
4191.53–4195.12 while price traded 4210, above the 4202.80 sweep high).
"""
from __future__ import annotations

from dataclasses import replace

from app.analysis.h4_m15_fvg.service import analyze_h4_m15_fvg
from app.analysis.h4_m15_fvg.store import clear_store
from app.analysis.h4_m15_fvg.types import DEFAULT_H4_M15_CONFIG, H4M15SetupState
from app.market_structure.types import Candle

from test_h4_m15_fvg_integration import build_bullish_entry_ready_fixture

STEP = 900
FIXTURE_SETUP_ID = "H4M15-EURUSD-B-572800"


def _run(extra: list[tuple[float, float, float, float]], **cfg_overrides):
    clear_store()
    h4, m15 = build_bullish_entry_ready_fixture()
    t = m15[-1].time
    for i, (o, h, l, c) in enumerate(extra, 1):
        m15.append(Candle(time=t + i * STEP, open=o, high=h, low=l, close=c))
    cfg = replace(DEFAULT_H4_M15_CONFIG, **cfg_overrides) if cfg_overrides else None
    out = analyze_h4_m15_fvg(symbol="EURUSD", candles_h4=h4, candles_m15=m15, cfg=cfg, persist=False)
    assert out["valid"] is True
    return out, _bullish_setup(out)


def _bullish_setup(out: dict) -> dict:
    rows = [s for s in out["setups"] if s["setup_id"] == FIXTURE_SETUP_ID]
    assert rows, "fixture should produce the bullish H4 FVG setup"
    return rows[0]


QUIET = (1.08500, 1.08510, 1.08490, 1.08500)  # well above the 1.08418 sweep low


def test_fixture_baseline_is_entry_ready():
    out, setup = _run([])
    assert setup["state"] == H4M15SetupState.ENTRY_READY.value
    assert out["decision"] == "ENTRY_READY"


def test_entry_ready_survives_bars_that_respect_the_stop():
    out, setup = _run([QUIET] * 3)
    assert setup["state"] == H4M15SetupState.ENTRY_READY.value
    assert out["decision"] == "ENTRY_READY"


def test_close_through_sweep_after_entry_ready_invalidates():
    # Disable the H4 close-break rule so this exercises the sweep (stop) rule on its own.
    out, setup = _run([QUIET, (1.08500, 1.08505, 1.08370, 1.08380)], invalidate_htf_on_close_break=False)
    assert setup["state"] == H4M15SetupState.SETUP_INVALIDATED.value
    assert "sweep low" in setup["invalidation_reason"]
    assert out["decision"] == "MONITOR"
    assert out["entry_ready_count"] == 0
    states = [t["new_state"] for t in setup["transition_log"]]
    assert states.index("ENTRY_READY") < states.index("SETUP_INVALIDATED")


def test_h4_fvg_close_break_after_entry_ready_invalidates():
    out, setup = _run([QUIET, (1.08500, 1.08505, 1.08370, 1.08380)])
    assert setup["state"] == H4M15SetupState.SETUP_INVALIDATED.value
    assert out["decision"] == "MONITOR"


def test_wick_through_sweep_without_close_does_not_invalidate():
    out, setup = _run([(1.08500, 1.08505, 1.08380, 1.08470)])
    assert setup["state"] == H4M15SetupState.ENTRY_READY.value


def test_entry_ready_expires_after_max_bars():
    # Bars already elapsed inside the fixture after ENTRY_READY count toward the limit.
    _, base = _run([])
    _, m15 = build_bullish_entry_ready_fixture()
    already = sum(1 for c in m15 if c.time > base["entry_ready_time"])
    limit = already + 2

    _, still = _run([QUIET] * 2, max_entry_ready_m15_bars=limit)
    assert still["state"] == H4M15SetupState.ENTRY_READY.value

    out, setup = _run([QUIET] * 3, max_entry_ready_m15_bars=limit)
    assert setup["state"] == H4M15SetupState.SETUP_EXPIRED.value
    assert "ENTRY_READY not acted on" in setup["expiration_reason"]
    assert out["decision"] == "MONITOR"
