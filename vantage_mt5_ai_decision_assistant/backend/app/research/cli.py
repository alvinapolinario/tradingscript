"""
Strategy scorecard — replay every Python-canonical engine over M5 history.

    cd backend
    python -m app.research.cli --csv XAUUSD_M5.csv --out research_out

Writes ``trades.csv``, ``strategy_scorecard.json`` and ``report.md`` to ``--out``.
Copy ``strategy_scorecard.json`` to the backend data directory to let the live
API attach evidence to signals (see ``app/evidence.py``).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ALL_STRATEGIES = ("ict", "h4_m15_fvg", "box_theory", "amd_ifvg")


def _date(s: str) -> int:
    return int(datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()) if s else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv", required=True, help="M5 history CSV (VantageExportHistory.mq5 output)")
    p.add_argument("--out", default="research_out")
    p.add_argument("--symbol", default="XAUUSD")
    p.add_argument("--strategies", default=",".join(ALL_STRATEGIES))
    p.add_argument("--cadence", default="M5", choices=("M5", "M15"), help="how often engines are evaluated")
    p.add_argument("--tp-level", default="TP2", choices=("TP1", "TP2", "TP3"))
    p.add_argument("--point", type=float, default=0.01, help="price per MT5 point (for a 'spread' column in points)")
    p.add_argument("--default-spread", type=float, default=0.30, help="spread in price units when the CSV has none")
    p.add_argument("--server-utc-offset", type=float, default=0.0, help="broker server time minus UTC, hours")
    p.add_argument("--start", default="", help="YYYY-MM-DD")
    p.add_argument("--end", default="", help="YYYY-MM-DD")
    p.add_argument("--max-hold-bars", type=int, default=48)
    p.add_argument("--default-rr", type=float, default=2.0)
    p.add_argument("--commission", type=float, default=0.0, help="round-trip cost in price units")
    p.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1), help="parallel strategy processes")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # Engines persist setup state in SQLite — never let a backtest touch live data.
    os.environ.setdefault("VANTAGE_DATA_DIR", tempfile.mkdtemp(prefix="vantage_research_"))

    from app.research.data import load_m5_csv
    from app.research.metrics import evaluate_strategy
    from app.research.signals import generate_signals
    from app.research.simulate import SimConfig, simulate

    strategies = [s.strip() for s in args.strategies.split(",") if s.strip()]
    unknown = set(strategies) - set(ALL_STRATEGIES)
    if unknown:
        print(f"Unknown strategies: {', '.join(sorted(unknown))}", file=sys.stderr)
        return 2

    hist = load_m5_csv(args.csv, symbol=args.symbol, point=args.point, default_spread=args.default_spread)
    first, last = hist.m5[0].time, hist.m5[-1].time
    print(f"Loaded {len(hist.m5):,} M5 bars {_iso(first)} -> {_iso(last)}")

    t0 = time.time()
    signals = generate_signals(
        hist,
        strategies,
        cadence=args.cadence,
        tp_level=args.tp_level,
        start=_date(args.start),
        end=_date(args.end),
        workers=args.workers,
        verbose=True,
    )
    cfg = SimConfig(max_hold_bars=args.max_hold_bars, default_rr=args.default_rr, commission=args.commission)
    trades = simulate(hist, signals, cfg)

    results = {
        name: evaluate_strategy([t for t in trades if t.strategy == name], utc_offset_hours=args.server_utc_offset)
        for name in strategies
    }
    scorecard = {
        "schema": "vantage.strategy_scorecard.v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "data": {
            "symbol": hist.symbol,
            "csv": Path(args.csv).name,
            "from": _iso(first),
            "to": _iso(last),
            "m5_bars": len(hist.m5),
        },
        "assumptions": {
            "cadence": args.cadence,
            "tp_level": args.tp_level,
            "max_hold_bars_m5": args.max_hold_bars,
            "default_rr": args.default_rr,
            "commission": args.commission,
            "default_spread": args.default_spread,
            "server_utc_offset_hours": args.server_utc_offset,
            "fills": "market at next M5 open (buy at ask); stop wins when SL and TP share a bar",
        },
        "strategies": results,
    }

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    _write_trades(out / "trades.csv", trades)
    (out / "strategy_scorecard.json").write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
    (out / "report.md").write_text(render_report(scorecard), encoding="utf-8")
    print(render_summary(results))
    print(f"\nWrote {out / 'strategy_scorecard.json'}, report.md, trades.csv in {time.time() - t0:.0f}s")
    return 0


def _iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


def _write_trades(path: Path, trades) -> None:
    rows = [t.to_dict() for t in trades]
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def _fmt(st: dict, key: str, pct: bool = False, missing: str = "—") -> str:
    v = st.get(key)
    if v is None:
        return missing
    return f"{v * 100:.1f}%" if pct else f"{v}"


def render_summary(results: dict) -> str:
    lines = [f"\n{'strategy':<12} {'verdict':<18} {'trades':>6} {'win%':>7} {'avgR':>7} {'PF':>6} {'t':>6} {'maxDD':>6}"]
    for name, res in results.items():
        o = res["overall"]
        cells = [_fmt(o, k, k == "win_rate", "-") for k in ("win_rate", "avg_r", "profit_factor", "t_stat", "max_drawdown_r")]
        lines.append(
            f"{name:<12} {res['verdict']:<18} {o.get('n', 0):>6} "
            f"{cells[0]:>7} {cells[1]:>7} {cells[2]:>6} {cells[3]:>6} {cells[4]:>6}"
        )
    return "\n".join(lines)


def render_report(sc: dict) -> str:
    d, a = sc["data"], sc["assumptions"]
    md = [
        "# Strategy scorecard",
        "",
        f"{d['symbol']} M5 · {d['from']} → {d['to']} UTC · {d['m5_bars']:,} bars · generated {sc['generated_utc'][:16]}",
        "",
        f"Assumptions: evaluated every {a['cadence']} close, target {a['tp_level']} (engines without a target use "
        f"{a['default_rr']}R), max hold {a['max_hold_bars_m5']} M5 bars, real per-bar spread "
        f"(fallback {a['default_spread']}), commission {a['commission']}. {a['fills']}.",
        "",
        "Verdicts: **EDGE** = avg R > 0, t ≥ 2 and positive in ≥ 3 of 4 time folds · **NO_EDGE** = avg R ≤ 0 or t < 1 · "
        "**INCONCLUSIVE** = in between · **INSUFFICIENT_DATA** = fewer than 30 trades.",
        "",
        "| Strategy | Verdict | Trades | Win % | Avg R | PF | t | Max DD (R) | OOS floor | OOS avg R |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, res in sc["strategies"].items():
        o, th = res["overall"], res["threshold"]
        oos = th["out_of_sample_filtered"]
        md.append(
            f"| {name} | {res['verdict']} | {o.get('n', 0)} | {_fmt(o, 'win_rate', True)} | {_fmt(o, 'avg_r')} | "
            f"{_fmt(o, 'profit_factor')} | {_fmt(o, 't_stat')} | {_fmt(o, 'max_drawdown_r')} | "
            f"{th['min_confidence'] if th['min_confidence'] is not None else '—'} | {_fmt(oos, 'avg_r')} |"
        )
    for name, res in sc["strategies"].items():
        md += ["", f"## {name}", "", f"Signal outcomes: {res['signals']} · exits: {res['exit_reasons']}", ""]
        md += _table("Confidence bucket", [(f"{b['lo']}–{b['hi']}", b) for b in res["confidence_buckets"]])
        md += _table("Side", list(res["by_side"].items()))
        md += _table("Session (UTC)", list(res["by_session"].items()))
        md += _table("Year", list(res["by_year"].items()))
        md += _table("Time fold", [(f"#{f['fold']}", f) for f in res["folds"]])
    return "\n".join(md) + "\n"


def _table(title: str, rows: list) -> list[str]:
    if not rows:
        return []
    out = ["", f"| {title} | Trades | Win % | Avg R | PF |", "|---|---:|---:|---:|---:|"]
    for label, st in rows:
        cells = [_fmt(st, "win_rate", True), _fmt(st, "avg_r"), _fmt(st, "profit_factor")]
        out.append(f"| {label} | {st.get('n', 0)} | " + " | ".join(cells) + " |")
    return out


if __name__ == "__main__":
    raise SystemExit(main())
