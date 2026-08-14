"""CSV / JSON replay for H4→M15 FVG backtests (closed-bar only)."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.analysis.h4_m15_fvg.engine import H4M15Engine
from app.analysis.h4_m15_fvg.explain import setup_to_json
from app.analysis.h4_m15_fvg.service import analyze_h4_m15_fvg
from app.analysis.h4_m15_fvg.store import reset_state_tracking, setup_state_changed
from app.analysis.h4_m15_fvg.types import DEFAULT_H4_M15_CONFIG, H4M15FvgConfig, H4M15SetupState
from app.market_structure import atr, candles_from_payload, htf_bias, validate_candles
from app.market_structure.types import Candle


def _norm_col(name: str) -> str:
    return (name or "").strip().lower().replace(" ", "_")


def _parse_time(raw: str) -> int:
    s = (raw or "").strip()
    if not s:
        return 0
    if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
        return int(s)
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
                return int(dt.timestamp())
            except ValueError:
                continue
    return 0


def _row_to_candle(row: dict[str, str]) -> Candle | None:
    keys = {_norm_col(k): v for k, v in row.items()}
    t = _parse_time(keys.get("time") or keys.get("timestamp") or keys.get("datetime") or keys.get("date") or "")
    try:
        o = float(keys.get("open") or keys.get("o") or 0)
        h = float(keys.get("high") or keys.get("h") or 0)
        l = float(keys.get("low") or keys.get("l") or 0)
        c = float(keys.get("close") or keys.get("c") or 0)
        v = float(keys.get("volume") or keys.get("tick_volume") or keys.get("v") or 0)
    except (TypeError, ValueError):
        return None
    if t <= 0 or o <= 0 or c <= 0:
        return None
    return Candle(time=t, open=o, high=h, low=l, close=c, volume=v)


def load_ohlc_csv(path: str | Path) -> list[Candle]:
    """Load OHLC rows from CSV (oldest first)."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(p))
    out: list[Candle] = []
    with p.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            c = _row_to_candle(row)
            if c:
                out.append(c)
    out.sort(key=lambda x: x.time)
    err = validate_candles(out) if out else "Empty CSV"
    if err:
        raise ValueError(f"{p.name}: {err}")
    return out


def load_candles_json(path: str | Path) -> dict[str, list[Candle]]:
    """Load {\"H4\": [...], \"M15\": [...]} candle dict from JSON file."""
    p = Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("JSON root must be an object with timeframe keys")
    out: dict[str, list[Candle]] = {}
    for tf, rows in raw.items():
        if isinstance(rows, list):
            candles = candles_from_payload(rows)
            err = validate_candles(candles) if candles else f"Empty {tf}"
            if err:
                raise ValueError(f"{p.name} [{tf}]: {err}")
            out[str(tf).upper()] = candles
    return out


def replay_incremental(
    *,
    symbol: str,
    candles_h4: list[Candle],
    candles_m15: list[Candle],
    cfg: H4M15FvgConfig | None = None,
) -> dict[str, Any]:
    """Bar-by-bar replay; returns final setups plus transition log (no lookahead)."""
    st = cfg or DEFAULT_H4_M15_CONFIG
    reset_state_tracking()
    engine = H4M15Engine(st)
    engine.bootstrap_h4(symbol.upper(), candles_h4, atr(candles_h4))

    transitions: list[dict[str, Any]] = []
    prev_states: dict[str, str] = {}

    for i, bar in enumerate(candles_m15):
        hist = candles_m15[: i + 1]
        for s in engine.all_setups():
            prev_states.setdefault(s.setup_id, s.state.value)
        engine.process_m15_bar(
            bar,
            hist,
            atr(hist),
            htf_bias=htf_bias(candles_h4),
            dealing_high=max(c.high for c in candles_h4[-50:]),
            dealing_low=min(c.low for c in candles_h4[-50:]),
        )
        for s in engine.all_setups():
            old = prev_states.get(s.setup_id, "")
            new = s.state.value
            if new != old:
                transitions.append(
                    {
                        "bar_index": i,
                        "bar_time": bar.time,
                        "setup_id": s.setup_id,
                        "old_state": old,
                        "new_state": new,
                        "reason": s.transition_log[-1].reason if s.transition_log else "",
                    }
                )
                prev_states[s.setup_id] = new

    setups = engine.all_setups()
    rows = []
    for s in setups:
        row = setup_to_json(s)
        row["state_changed"] = setup_state_changed(s.setup_id, s.state.value)
        rows.append(row)

    entry_ready = [r for r in rows if r.get("state") == H4M15SetupState.ENTRY_READY.value]
    return {
        "module": "h4_m15_fvg",
        "symbol": symbol.upper(),
        "valid": True,
        "mode": "incremental_replay",
        "advisory_only": True,
        "bar_count_m15": len(candles_m15),
        "transition_count": len(transitions),
        "transitions": transitions,
        "setups": rows,
        "entry_ready_count": len(entry_ready),
        "decision": "ENTRY_READY" if entry_ready else "MONITOR",
        "primary": entry_ready[-1] if entry_ready else (rows[-1] if rows else None),
    }


def run_replay(
    *,
    symbol: str,
    candles_h4: list[Candle],
    candles_m15: list[Candle],
    cfg: H4M15FvgConfig | None = None,
    persist: bool = True,
    incremental: bool = False,
) -> dict[str, Any]:
    if incremental:
        return replay_incremental(
            symbol=symbol,
            candles_h4=candles_h4,
            candles_m15=candles_m15,
            cfg=cfg,
        )
    return analyze_h4_m15_fvg(
        symbol=symbol,
        candles_h4=candles_h4,
        candles_m15=candles_m15,
        cfg=cfg,
        persist=persist,
    )


def _load_config(path: str | None) -> H4M15FvgConfig | None:
    if not path:
        return None
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Config JSON must be an object")
    kwargs = {k: v for k, v in raw.items() if hasattr(H4M15FvgConfig, k)}
    return H4M15FvgConfig(**kwargs) if kwargs else H4M15FvgConfig()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Replay H4→M15 FVG strategy on closed OHLC CSV/JSON (no live trading)."
    )
    parser.add_argument("--symbol", default="XAUUSD", help="Symbol label (default: XAUUSD)")
    parser.add_argument("--h4-csv", help="H4 OHLC CSV path")
    parser.add_argument("--m15-csv", help="M15 OHLC CSV path")
    parser.add_argument("--candles-json", help="JSON file with H4/M15 candle arrays")
    parser.add_argument("--config-json", help="Optional H4M15FvgConfig overrides JSON")
    parser.add_argument("--out", help="Write full result JSON to this path")
    parser.add_argument("--jsonl", help="Write incremental transitions JSONL to this path")
    parser.add_argument("--incremental", action="store_true", help="Bar-by-bar replay with transition log")
    parser.add_argument("--no-persist", action="store_true", help="Skip SQLite persistence")
    args = parser.parse_args(argv)

    cfg = _load_config(args.config_json)
    h4: list[Candle] = []
    m15: list[Candle] = []

    if args.candles_json:
        by_tf = load_candles_json(args.candles_json)
        h4 = by_tf.get("H4") or []
        m15 = by_tf.get("M15") or []
    else:
        if not args.h4_csv or not args.m15_csv:
            parser.error("Provide --candles-json or both --h4-csv and --m15-csv")
        h4 = load_ohlc_csv(args.h4_csv)
        m15 = load_ohlc_csv(args.m15_csv)

    result = run_replay(
        symbol=args.symbol,
        candles_h4=h4,
        candles_m15=m15,
        cfg=cfg,
        persist=not args.no_persist,
        incremental=args.incremental,
    )
    text = json.dumps(result, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        print(text)

    if args.jsonl and args.incremental:
        p = Path(args.jsonl)
        with p.open("w", encoding="utf-8") as fh:
            for row in result.get("transitions") or []:
                fh.write(json.dumps(row) + "\n")

    return 0 if result.get("valid") else 1


if __name__ == "__main__":
    sys.exit(main())
