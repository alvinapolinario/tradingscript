"""Offline research harness — data, simulator, metrics, adapters, CLI."""
from __future__ import annotations

import csv
import json
import random
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.market_structure.types import Candle
from app.research import metrics, signals
from app.research.data import History, load_m5_csv, resample
from app.research.signals import Signal
from app.research.simulate import SimConfig, Trade, simulate, simulate_signal

T0 = int(datetime(2025, 3, 3, tzinfo=timezone.utc).timestamp())  # Monday 00:00 UTC


def _hist(rows: list[tuple[float, float, float, float]], spread: float = 0.2) -> History:
    m5 = [Candle(time=T0 + i * 300, open=o, high=h, low=l, close=c) for i, (o, h, l, c) in enumerate(rows)]
    return History(symbol="XAUUSD", m5=m5, spread=[spread] * len(m5))


def _sig(side: str = "BUY", sl: float = 99.0, tp: float = 102.0, **kw) -> Signal:
    return Signal(strategy="test", time=T0, side=side, stop_loss=sl, take_profit=tp, confidence=70, setup_id="s1", **kw)


# --- data -------------------------------------------------------------------------


def test_load_m5_csv_spread_columns_sorting_and_dedupe(tmp_path: Path):
    p = tmp_path / "m5.csv"
    p.write_text(
        "time,open,high,low,close,tick_volume,spread\n"
        "2025-03-03 00:05:00,2,3,1,2,10,25\n"
        "2025-03-03 00:00:00,1,2,0.5,1.5,10,0\n"
        "2025-03-03 00:05:00,2,3,1,2,10,25\n",
        encoding="utf-8",
    )
    h = load_m5_csv(p, point=0.01, default_spread=0.3)
    assert [c.time for c in h.m5] == [T0, T0 + 300]
    assert h.spread == [0.3, 0.25]  # zero spread → default; 25 points × 0.01

    p2 = tmp_path / "m5b.csv"
    p2.write_text("time,open,high,low,close,spread_price\n2025-03-03 00:00:00,1,2,0.5,1.5,0.42\n", encoding="utf-8")
    assert load_m5_csv(p2).spread == [0.42]


def test_resample_and_closed_never_returns_a_forming_bar():
    rows = [(10 + i, 11 + i, 9 + i, 10.5 + i) for i in range(6)]  # 30 minutes of M5
    h = _hist(rows)
    m15 = resample(h.m5, 900)
    assert [c.time for c in m15] == [T0, T0 + 900]
    assert m15[0].open == 10 and m15[0].close == 12.5 and m15[0].high == 13 and m15[0].low == 9

    # At 00:10 the first M15 bar (00:00–00:15) is still forming.
    assert h.closed("M15", T0 + 600, 10) == []
    assert [c.time for c in h.closed("M15", T0 + 900, 10)] == [T0]
    assert [c.time for c in h.closed("M5", T0 + 600, 10)] == [T0, T0 + 300]


# --- simulator ----------------------------------------------------------------------


def test_market_buy_hits_target_and_pays_spread():
    h = _hist([(100, 100.5, 99.8, 100.2), (100.2, 102.5, 100.1, 102.4)], spread=0.2)
    t = simulate_signal(h, _sig(sl=99.0, tp=102.0), SimConfig())
    assert t.status == "CLOSED" and t.exit_reason == "TP"
    assert t.entry == pytest.approx(100.2)  # open 100.0 + spread
    assert t.r == pytest.approx((102.0 - 100.2) / (100.2 - 99.0), abs=1e-4)


def test_stop_wins_when_stop_and_target_share_a_bar():
    h = _hist([(100, 103, 98, 101)])
    t = simulate_signal(h, _sig(sl=99.0, tp=102.0), SimConfig())
    assert t.exit_reason == "SL" and t.r == -1.0  # risk is measured from the spread-paid entry


def test_sell_exits_on_ask():
    # Bid low 98.85 + spread 0.2 = 99.05 never reaches the 99.0 target.
    h = _hist([(100, 100.1, 98.85, 99.0)], spread=0.2)
    t = simulate_signal(h, _sig(side="SELL", sl=101.0, tp=99.0), SimConfig(max_hold_bars=0))
    assert t.exit_reason == "TIME"
    h2 = _hist([(100, 100.1, 98.7, 99.0)], spread=0.2)
    assert simulate_signal(h2, _sig(side="SELL", sl=101.0, tp=99.0), SimConfig()).exit_reason == "TP"


def test_default_rr_target_time_exit_and_invalid_levels():
    h = _hist([(100, 100.4, 99.9, 100.1)] * 3, spread=0.0)
    t = simulate_signal(h, _sig(sl=99.0, tp=0.0), SimConfig(default_rr=2.0, max_hold_bars=2))
    assert t.take_profit == pytest.approx(102.0) and t.exit_reason == "TIME"
    bad = simulate_signal(h, _sig(sl=101.0, tp=103.0), SimConfig())
    assert bad.status == "INVALID_LEVELS"


def test_limit_entry_fills_or_expires():
    h = _hist([(100, 100.5, 99.6, 100.2), (100.2, 100.3, 99.4, 99.6), (99.6, 101.5, 99.5, 101.4)], spread=0.1)
    filled = simulate_signal(h, _sig(sl=99.0, tp=101.0, entry_type="LIMIT", entry_price=99.5), SimConfig())
    assert filled.status == "CLOSED" and filled.entry == 99.5 and filled.exit_reason == "TP"
    missed = simulate_signal(h, _sig(sl=98.0, tp=101.0, entry_type="LIMIT", entry_price=99.0), SimConfig())
    assert missed.status == "NOT_FILLED"


def test_one_position_per_strategy():
    h = _hist([(100, 100.5, 99.9, 100.2)] * 10, spread=0.0)
    first = _sig(sl=99.0, tp=105.0)
    second = Signal("test", T0 + 600, "BUY", 99.0, 105.0, 70, "s2")
    trades = simulate(h, [first, second], SimConfig(max_hold_bars=5))
    assert [t.status for t in trades] == ["CLOSED", "SKIPPED_BUSY"]


# --- metrics ------------------------------------------------------------------------


def _trades(rs: list[float], conf: list[float] | None = None) -> list[Trade]:
    conf = conf or [60.0] * len(rs)
    return [Trade("x", T0 + i * 3600, "BUY", c, f"s{i}", "CLOSED", r=r) for i, (r, c) in enumerate(zip(rs, conf))]


def test_basic_stats_and_drawdown():
    st = metrics.basic_stats(_trades([1, -1, -1, 2]))
    assert st["n"] == 4 and st["win_rate"] == 0.5 and st["total_r"] == 1
    assert st["profit_factor"] == 1.5 and st["max_drawdown_r"] == 2


def test_verdicts():
    assert metrics.evaluate_strategy(_trades([1.0] * 10))["verdict"] == "INSUFFICIENT_DATA"
    assert metrics.evaluate_strategy(_trades([-1.0, 0.5] * 30))["verdict"] == "NO_EDGE"
    rng = random.Random(1)
    edge = [2.0 if rng.random() < 0.5 else -1.0 for _ in range(200)]
    assert metrics.evaluate_strategy(_trades(edge))["verdict"] == "EDGE"


def test_threshold_is_fitted_in_sample_and_checked_out_of_sample():
    # High-confidence trades win, low-confidence lose — in both halves of the data.
    rs, conf = [], []
    for i in range(200):
        hi = i % 2 == 0
        rs.append(1.5 if hi else -1.0)
        conf.append(85.0 if hi else 55.0)
    res = metrics.evaluate_strategy(_trades(rs, conf))
    th = res["threshold"]
    assert th["min_confidence"] is not None and 55 < th["min_confidence"] <= 85
    assert th["confirmed"] is True
    assert th["out_of_sample_filtered"]["avg_r"] == pytest.approx(1.5)


# --- adapters -----------------------------------------------------------------------


def _frames(n: int = 120) -> dict[str, list[Candle]]:
    bars = [Candle(time=T0 + i * 900, open=100, high=101, low=99, close=100) for i in range(n)]
    return {"M5": bars, "M15": bars, "H1": bars, "H4": bars, "D1": bars}


def test_ict_adapter_emits_once_per_setup(monkeypatch):
    import app.analysis.ict as ict

    result = {
        "decision": "BUY",
        "setup_id": "ict-1",
        "entry_event_id": "e1",
        "confidence": 81,
        "stop_loss": {"price": 95.0},
        "targets": [{"name": "TP1", "price": 105.0}, {"name": "TP2", "price": 110.0}],
    }
    monkeypatch.setattr(ict, "analyze_ict_strategy", lambda **_: result)
    a = signals.IctAdapter("XAUUSD", tp_level="TP2")
    s = a.evaluate(_frames(), T0)
    assert s and s.side == "BUY" and s.stop_loss == 95.0 and s.take_profit == 110.0 and s.confidence == 81
    assert a.evaluate(_frames(), T0 + 300) is None  # same setup → no duplicate


def test_box_and_amd_adapters(monkeypatch):
    import app.analysis.amd_ifvg_logic as amd
    import app.analysis.box_theory as box

    monkeypatch.setattr(
        box, "analyze_box_strategy",
        lambda **_: {"signal": "SELL", "signal_id": "b1", "stop_loss": 105, "tp1": 98, "tp2": 96, "confidence": 66},
    )
    s = signals.BoxTheoryAdapter("XAUUSD", tp_level="TP2").evaluate(_frames(), T0)
    assert s and s.side == "SELL" and s.take_profit == 96

    monkeypatch.setattr(
        amd, "analyze_amd_ifvg",
        lambda **_: {
            "decision": "BUY",
            "confidence": 77,
            "ifvg": {"lower_boundary": 99, "upper_boundary": 100},
            "entry": {"preferred_entry": 99.5, "current_price_inside_zone": False},
            "risk": {"stop_loss": 98},
            "targets": [{"name": "TP1", "price": 101}, {"name": "TP2", "price": 103}],
        },
    )
    s = signals.AmdIfvgAdapter("XAUUSD").evaluate(_frames(), T0)
    assert s and s.entry_type == "LIMIT" and s.entry_price == 99.5 and s.take_profit == 103


# --- CLI end to end -----------------------------------------------------------------


def test_cli_writes_scorecard(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("VANTAGE_DATA_DIR", str(tmp_path / "data"))
    rng = random.Random(3)
    csv_path = tmp_path / "m5.csv"
    px, t = 2650.0, T0
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["time", "open", "high", "low", "close", "spread"])
        for _ in range(288 * 12):
            o, c = px, px + rng.gauss(0, 1.0)
            w.writerow([t, o, max(o, c) + 0.3, min(o, c) - 0.3, c, 25])
            px, t = c, t + 300

    from app.research.cli import main

    out = tmp_path / "out"
    assert main(["--csv", str(csv_path), "--out", str(out), "--strategies", "amd_ifvg", "--workers", "1"]) == 0
    sc = json.loads((out / "strategy_scorecard.json").read_text(encoding="utf-8"))
    assert sc["schema"] == "vantage.strategy_scorecard.v1"
    assert sc["data"]["m5_bars"] == 288 * 12
    assert "amd_ifvg" in sc["strategies"] and "verdict" in sc["strategies"]["amd_ifvg"]
    assert (out / "report.md").exists() and (out / "trades.csv").exists()
