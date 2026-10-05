"""
Strategy adapters — turn each Python-canonical engine into a stream of trade signals.

Each adapter is called once per closed bar with only the bars that had closed
at that moment (``History.closed``), mirroring what the live heartbeat sees.
An adapter emits a signal the first time a setup becomes tradable and never
again for the same setup id.
"""
from __future__ import annotations

import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

from app.market_structure.types import Candle
from app.research.data import History

WINDOW = {"M5": 300, "M15": 300, "H1": 300, "H4": 200, "D1": 60}


@dataclass
class Signal:
    strategy: str
    time: int  # decision time (close of the evaluated bar, epoch seconds)
    side: str  # BUY | SELL
    stop_loss: float
    take_profit: float  # 0 → simulator applies default_rr
    confidence: float
    setup_id: str
    entry_type: str = "MARKET"  # MARKET | LIMIT
    entry_price: float = 0.0  # LIMIT price
    meta: dict[str, Any] = field(default_factory=dict)


def _pick_target(targets: Any, level: str) -> float:
    if not isinstance(targets, list) or not targets:
        return 0.0
    by_name = {str(t.get("name") or "").upper(): t for t in targets if isinstance(t, dict)}
    chosen = by_name.get(level.upper()) or targets[-1 if level.upper() != "TP1" else 0]
    try:
        return float(chosen.get("price") or 0)
    except (AttributeError, TypeError, ValueError):
        return 0.0


def _side(raw: Any) -> str:
    u = str(raw or "").upper()
    return "BUY" if u in ("BUY", "BULLISH") else "SELL" if u in ("SELL", "BEARISH") else ""


class Adapter:
    name = ""

    def __init__(self, symbol: str, tp_level: str = "TP2") -> None:
        self.symbol = symbol
        self.tp_level = tp_level
        self._seen: set[str] = set()

    def _once(self, key: str) -> bool:
        if not key or key in self._seen:
            return False
        self._seen.add(key)
        return True

    def evaluate(self, frames: dict[str, list[Candle]], at: int) -> Signal | None:
        raise NotImplementedError


class IctAdapter(Adapter):
    name = "ict"

    def evaluate(self, frames: dict[str, list[Candle]], at: int) -> Signal | None:
        from app.analysis.ict import analyze_ict_strategy

        res = analyze_ict_strategy(
            symbol=self.symbol,
            candles_by_timeframe={k: v for k, v in frames.items() if v},
            candles_setup=frames["M15"],
            candles_execution=frames["M5"],
            bid=frames["M5"][-1].close,
        )
        side = _side(res.get("decision"))
        if not side:
            return None
        key = f"{res.get('setup_id')}|{res.get('entry_event_id') or ''}"
        if not self._once(key):
            return None
        sl = res.get("stop_loss") or {}
        return Signal(
            strategy=self.name,
            time=at,
            side=side,
            stop_loss=float(sl.get("price") if isinstance(sl, dict) else sl or 0),
            take_profit=_pick_target(res.get("targets"), self.tp_level),
            confidence=float(res.get("confidence") or 0),
            setup_id=str(res.get("setup_id") or key),
            meta={"state": res.get("setup_state"), "rr": res.get("risk_reward")},
        )


class H4M15FvgAdapter(Adapter):
    """
    Drives one long-lived ``H4M15Engine`` bar by bar.

    The live service rebuilds the engine from its whole candle window on every
    call (O(window) per call); feeding each newly closed M15 bar once gives the
    same state machine at O(1) per bar and only ever uses data closed at that time.
    """

    name = "h4_m15_fvg"

    def __init__(self, symbol: str, tp_level: str = "TP2") -> None:
        super().__init__(symbol, tp_level)
        from app.analysis.h4_m15_fvg.engine import H4M15Engine

        self.engine = H4M15Engine()
        self._last_m15 = 0
        self._last_h4 = 0

    def evaluate(self, frames: dict[str, list[Candle]], at: int) -> Signal | None:
        from app.analysis.h4_m15_fvg.service import _dealing_range
        from app.analysis.h4_m15_fvg.types import H4M15SetupState
        from app.market_structure import atr, htf_bias

        h4, m15 = frames["H4"], frames["M15"]
        if not h4 or not m15 or m15[-1].time == self._last_m15:
            return None
        if h4[-1].time != self._last_h4:
            self.engine.bootstrap_h4(self.symbol, h4, atr(h4))
            self._last_h4 = h4[-1].time
        d_hi, d_lo = _dealing_range(h4)
        self.engine.process_m15_bar(
            m15[-1], m15, atr(m15), htf_bias=htf_bias(h4), dealing_high=d_hi, dealing_low=d_lo
        )
        self._last_m15 = m15[-1].time

        for setup in self.engine.all_setups():
            if setup.state != H4M15SetupState.ENTRY_READY or not self._once(setup.setup_id):
                continue
            side = _side(setup.direction)
            if not side:
                continue
            return Signal(
                strategy=self.name,
                time=at,
                side=side,
                stop_loss=float(setup.structural_stop or 0),
                take_profit=0.0,  # engine publishes no target → default_rr
                confidence=float(setup.setup_score or 0),
                setup_id=setup.setup_id,
                meta={"grade": setup.setup_grade},
            )
        return None


class BoxTheoryAdapter(Adapter):
    name = "box_theory"

    def evaluate(self, frames: dict[str, list[Candle]], at: int) -> Signal | None:
        from app.analysis.box_theory import analyze_box_strategy

        res = analyze_box_strategy(
            symbol=self.symbol,
            candles_box=frames["M15"][-120:],
            candles_entry=frames["M5"],
            candles_structure=frames["H1"],
            bid=frames["M5"][-1].close,
        )
        side = _side(res.get("signal"))
        if not side or not self._once(str(res.get("signal_id") or "")):
            return None
        tp = res.get(self.tp_level.lower()) or res.get("tp2") or res.get("tp1") or 0
        return Signal(
            strategy=self.name,
            time=at,
            side=side,
            stop_loss=float(res.get("stop_loss") or 0),
            take_profit=float(tp or 0),
            confidence=float(res.get("confidence") or 0),
            setup_id=str(res.get("signal_id")),
            meta={"events": res.get("events")},
        )


class AmdIfvgAdapter(Adapter):
    name = "amd_ifvg"

    def evaluate(self, frames: dict[str, list[Candle]], at: int) -> Signal | None:
        from app.analysis.amd_ifvg_logic import analyze_amd_ifvg

        res = analyze_amd_ifvg(
            symbol=self.symbol,
            candles_setup=frames["M15"],
            candles_entry=frames["M5"],
            candles_bias=frames["H1"],
            bid=frames["M5"][-1].close,
        )
        side = _side(res.get("decision"))
        if not side:
            return None
        ifvg = res.get("ifvg") or {}
        key = f"{side}|{ifvg.get('lower_boundary')}|{ifvg.get('upper_boundary')}"
        if not self._once(key):
            return None
        entry = res.get("entry") or {}
        risk = res.get("risk") or {}
        inside = bool(entry.get("current_price_inside_zone"))
        return Signal(
            strategy=self.name,
            time=at,
            side=side,
            stop_loss=float(risk.get("stop_loss") or 0),
            take_profit=_pick_target(res.get("targets"), self.tp_level),
            confidence=float(res.get("confidence") or 0),
            setup_id=key,
            entry_type="MARKET" if inside else "LIMIT",
            entry_price=float(entry.get("preferred_entry") or 0),
            meta={"phase": res.get("amd_phase")},
        )


ADAPTERS: dict[str, Callable[..., Adapter]] = {
    a.name: a for a in (IctAdapter, H4M15FvgAdapter, BoxTheoryAdapter, AmdIfvgAdapter)
}


def run_strategy(
    hist: History,
    name: str,
    closes: list[int],
    tp_level: str = "TP2",
    verbose: bool = False,
) -> list[Signal]:
    """Evaluate one strategy at every decision time in ``closes``."""
    adapter = ADAPTERS[name](hist.symbol, tp_level=tp_level)
    started = time.time()
    out: list[Signal] = []
    errors = 0
    for i, at in enumerate(closes):
        frames = {tf: hist.closed(tf, at, n) for tf, n in WINDOW.items()}
        if len(frames["M15"]) < 80 or len(frames["H4"]) < 10:
            continue
        try:
            sig = adapter.evaluate(frames, at)
        except Exception as exc:  # one bad bar must not kill a multi-hour run
            errors += 1
            if verbose and errors <= 5:
                print(f"  {name}: error at {at}: {exc!r}", flush=True)
            continue
        if sig:
            out.append(sig)
        if verbose and i and i % 5000 == 0:
            print(f"  [{time.time() - started:6.0f}s] {name}: {i:,}/{len(closes):,} bars, {len(out)} signals", flush=True)
    if verbose:
        print(f"  {name}: done - {len(out)} signals, {errors} errors, {time.time() - started:.0f}s", flush=True)
    return out


def decision_times(hist: History, cadence: str = "M5", start: int = 0, end: int = 0) -> list[int]:
    from app.research.data import TF_SECONDS

    step = TF_SECONDS[cadence]
    closes = [c.time + step for c in hist.timeframe(cadence)]
    warmup = closes[min(len(closes) - 1, 100)] if closes else 0
    return [t for t in closes if t >= max(start, warmup) and (not end or t <= end)]


def generate_signals(
    hist: History,
    strategies: list[str],
    *,
    cadence: str = "M5",
    tp_level: str = "TP2",
    start: int = 0,
    end: int = 0,
    workers: int = 1,
    verbose: bool = False,
) -> list[Signal]:
    """Walk forward through history and collect signals from each strategy (one process each)."""
    closes = decision_times(hist, cadence, start, end)
    out: list[Signal] = []
    if workers > 1 and len(strategies) > 1:
        with ProcessPoolExecutor(max_workers=min(workers, len(strategies))) as pool:
            futures = [pool.submit(run_strategy, hist, name, closes, tp_level, verbose) for name in strategies]
            for fut in futures:
                out.extend(fut.result())
    else:
        for name in strategies:
            out.extend(run_strategy(hist, name, closes, tp_level, verbose))
    out.sort(key=lambda s: (s.time, s.strategy))
    return out
