# Strategy research — measuring real edge

The desks produce confidence scores (72, 75, 85 …) that were tuned by hand. This
workflow replays the Python-canonical engines over gold history, simulates every
signal with real spread, and writes a **scorecard** that says which strategies
actually made money and at which confidence levels. The live backend reads that
scorecard to annotate (and optionally filter) alerts.

| Engine | Adapter | Entry | Stop / target used |
|---|---|---|---|
| ICT | `ict` | market, next M5 open | engine stop · TP from `--tp-level` |
| H4→M15 FVG | `h4_m15_fvg` | market, next M5 open | structural stop · `--default-rr` (engine has no target) |
| Box Theory | `box_theory` | market, next M5 open | engine stop · tp1/tp2/tp3 |
| AMD + iFVG | `amd_ifvg` | limit at preferred entry (market when already inside the iFVG) | engine stop · TP from `--tp-level` |

The MQL5-only strategies (Swing / Scalping that feed the executor, Gold SMC,
Liquidity Grab, Breakout, Pullback) are not covered — they need the MT5 Strategy
Tester or a Python port. The executor journal is their forward test.

## 1. Export history from MT5

1. Tools → Options → Charts → **Max bars in chart = Unlimited**, restart MT5.
2. Open an XAUUSD+ M5 chart and scroll back so history downloads.
3. Copy `MQL5/Scripts/VantageExportHistory.mq5` into your terminal's `MQL5/Scripts`,
   compile, drag it onto the chart. Set `InpFrom` (e.g. 2023.01.01).
4. The CSV lands in `<Data Folder>/MQL5/Files/XAUUSD+_M5.csv` (File → Open Data Folder).

Columns: `time` (server epoch), `open, high, low, close, tick_volume, spread` (points),
`spread_price` (price units). Any CSV with `time/open/high/low/close` works; spread
falls back to `--default-spread`.

## 2. Run the scorecard

```bash
cd vantage_mt5_ai_decision_assistant/backend
pip install -r requirements-dev.txt
python -m app.research.cli --csv "XAUUSD+_M5.csv" --server-utc-offset 3 --out ../../research_out/xau
```

| Option | Default | Meaning |
|---|---|---|
| `--strategies` | all four | comma list |
| `--cadence` | `M5` | how often engines are evaluated (`M15` is ~3× faster) |
| `--tp-level` | `TP2` | engine target to use |
| `--default-rr` | `2.0` | target for engines without one |
| `--max-hold-bars` | `48` | time stop in M5 bars |
| `--server-utc-offset` | `0` | broker server time − UTC in hours (Vantage: 2 winter / 3 summer) — used for session stats |
| `--default-spread` | `0.30` | spread when the CSV has none |
| `--commission` | `0` | round-trip cost in price units |
| `--start` / `--end` | full file | `YYYY-MM-DD` |
| `--workers` | up to 4 | strategies run in parallel processes |

Two years of M5 takes roughly an hour (ICT is the slowest engine). Engine setup
state goes to a temporary data directory, never to the live SQLite files.

Outputs in `--out`:

* `report.md` — summary table, then per strategy: confidence buckets, side, session (UTC), year, time folds
* `strategy_scorecard.json` — machine-readable, consumed by the live API
* `trades.csv` — every signal and its simulated outcome

## 3. Reading the verdicts

| Verdict | Rule |
|---|---|
| **EDGE** | ≥ 30 trades, average R > 0, t-stat ≥ 2, positive in ≥ 3 of 4 chronological folds |
| **INCONCLUSIVE** | positive but not strong or not stable enough |
| **NO_EDGE** | average R ≤ 0 or t-stat < 1 |
| **INSUFFICIENT_DATA** | fewer than 30 closed trades |

**Confidence floor:** fitted on the first 70 % of trades (best t-stat with ≥ 20 trades),
then checked on the last 30 %. Only a floor that is still profitable out of sample is
marked `confirmed` and used by the live gate. Treat everything else as in-sample.

Simulation is deliberately conservative: buys pay the spread at entry, sells exit
on the ask, and when stop and target fall in the same M5 bar the stop wins.

## 4. Use the scorecard live

Copy `strategy_scorecard.json` into the backend data directory (Docker volume
`/app/data`), e.g. on the VPS:

```bash
docker cp strategy_scorecard.json vantage-mt5-ai-api:/app/data/strategy_scorecard.json
```

* Actionable ICT, H4→M15 FVG, Box Theory and AMD+iFVG alerts gain a
  **Backtest evidence** line (verdict, trades, win %, avg R, the alert's confidence bucket).
* `GET /api/v1/evidence/scorecard` returns the summary.
* `EVIDENCE_GATE_ENABLED=true` suppresses actionable alerts when the strategy is
  `NO_EDGE`/`INCONCLUSIVE` (unless above a confirmed floor) or below a confirmed
  floor of an `EDGE` strategy. Unmeasured strategies are never blocked.

Re-run the scorecard every month or two; the file is re-read automatically when it changes.
