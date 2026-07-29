# Breakout Structure Intelligence Engine

Rule-based **swing structure, trendline breakout, retest, SBR/RBS**, and **explainable ML-style validation** for **XAUUSD / Gold** — advisory only.

## Features

| # | Feature | Implementation |
|---|---------|----------------|
| 1 | Swing detection | HH/HL/LH/LL on H4/H1/M15 closed bars |
| 2 | Market structure | BOS/CHoCH with body-close + ATR gates |
| 3 | Trendlines | Auto HL/LH lines, min 3 touches |
| 4 | Trendline breakout | Weak / Strong / Fake / Institutional |
| 5 | Retest | Pending / Success / Failed |
| 6 | SBR | PDH/PDL flip heuristics on M5 |
| 7 | RBS | Inverse of SBR |
| 8 | ML validation | Weighted feature logistic (explainable, not opaque) |
| 9 | Scoring | 100-pt weighted grade A–Institutional |
| 10 | Dashboard | HUD `tbs0`–`tbs7` + `/breakout-structure` web desk |

## EA inputs

Groups **AA–AF** in `VantageMT5AIDecisionAssistant.mq5`.

Heartbeat key: `breakout_structure`

## Grading

| Score | Grade |
|-------|-------|
| 95–100 | Institutional Grade |
| 90–94 | A+ |
| 85–89 | A |
| 80–84 | B+ |
| 75–79 | B |
| &lt;75 | Reject |

## Tests

```bash
cd backend
pytest tests/test_breakout_structure_status.py tests/test_breakout_structure_static.py -q
```

## Known limitations (v1)

- ML layer is **explainable weighted scoring**, not a trained external model
- M1 entry validation uses M5 proxy in primary eval loop
- FVG/OB confluence weights are placeholders until cross-module feed is wired

No trade execution — ever.
