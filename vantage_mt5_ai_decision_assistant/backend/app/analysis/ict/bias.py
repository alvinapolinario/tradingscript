"""Multi-timeframe ICT bias engine."""
from __future__ import annotations

from app.analysis.ict.types import IctConfig
from app.market_structure.bias import htf_bias
from app.market_structure.types import Candle


def compute_htf_bias(
    candles_by_tf: dict[str, list[Candle]],
    cfg: IctConfig,
) -> tuple[str, float, list[str]]:
    """
    Weighted HTF bias from configured higher timeframes.
    Returns (direction, confidence 0-100, evidence list).
    """
    weights = {"D1": 3.0, "H4": 2.5, "H1": 2.0, "M15": 1.0, "M5": 0.5}
    bull = bear = neutral = 0.0
    evidence: list[str] = []

    for tf in cfg.higher_timeframes:
        candles = candles_by_tf.get(tf) or []
        if len(candles) < 20:
            continue
        b = htf_bias(candles)
        w = weights.get(tf, 1.0)
        if b == "BULLISH":
            bull += w
            evidence.append(f"{tf} bullish structure")
        elif b == "BEARISH":
            bear += w
            evidence.append(f"{tf} bearish structure")
        else:
            neutral += w

    total = bull + bear + neutral
    if total <= 0:
        return "NEUTRAL", 40.0, evidence or ["Insufficient HTF data"]

    if bull > bear * 1.2:
        conf = min(100.0, 50.0 + (bull / total) * 50.0)
        return "BULLISH", conf, evidence
    if bear > bull * 1.2:
        conf = min(100.0, 50.0 + (bear / total) * 50.0)
        return "BEARISH", conf, evidence
    return "NEUTRAL", 45.0, evidence or ["Mixed HTF structure"]
