"""Replay CLI tests for H4→M15 FVG."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from app.analysis.h4_m15_fvg.replay import load_ohlc_csv, run_replay


def test_load_ohlc_csv_and_replay():
    with tempfile.TemporaryDirectory() as tmp:
        h4_path = Path(tmp) / "h4.csv"
        m15_path = Path(tmp) / "m15.csv"
        h4_path.write_text(
            "time,open,high,low,close\n"
            + "\n".join(f"{40000 + i * 14400},1.086,1.0863,1.0857,1.086" for i in range(38))
            + "\n"
            f"{40000 + 38 * 14400},1.0838,1.0845,1.0837,1.0840\n"
            f"{40000 + 39 * 14400},1.0846,1.0860,1.0846,1.0855\n"
            f"{40000 + 40 * 14400},1.0855,1.0865,1.0850,1.0860\n",
            encoding="utf-8",
        )
        from test_h4_m15_fvg_integration import build_bullish_entry_ready_fixture

        _, m15 = build_bullish_entry_ready_fixture()
        lines = ["time,open,high,low,close"]
        for c in m15:
            lines.append(f"{c.time},{c.open},{c.high},{c.low},{c.close}")
        m15_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        h4 = load_ohlc_csv(h4_path)
        m15_loaded = load_ohlc_csv(m15_path)
        out = run_replay(
            symbol="EURUSD",
            candles_h4=h4,
            candles_m15=m15_loaded,
            persist=False,
            incremental=True,
        )
        assert out["valid"] is True
        assert out["mode"] == "incremental_replay"
        assert out.get("entry_ready_count", 0) >= 1
        assert len(out.get("transitions") or []) > 0


def test_replay_cli_main(tmp_path):
    from test_h4_m15_fvg_integration import build_bullish_entry_ready_fixture
    from app.analysis.h4_m15_fvg.replay import main

    h4, m15 = build_bullish_entry_ready_fixture()
    json_path = tmp_path / "candles.json"
    json_path.write_text(
        json.dumps(
            {
                "H4": [c.__dict__ for c in h4],
                "M15": [c.__dict__ for c in m15],
            }
        ),
        encoding="utf-8",
    )
    out_path = tmp_path / "out.json"
    rc = main(["--symbol", "EURUSD", "--candles-json", str(json_path), "--out", str(out_path), "--no-persist"])
    assert rc == 0
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["valid"] is True
