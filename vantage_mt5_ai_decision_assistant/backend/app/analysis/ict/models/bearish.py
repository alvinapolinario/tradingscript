"""ICT bearish model — delegates to causal sequence engine."""
from __future__ import annotations

from app.analysis.ict.causal import evaluate_causal_sequence
from app.analysis.ict.types import IctConfig, IctSetupContext, IctSetupState
from app.market_structure.types import Candle


def evaluate_bearish_sequence(
    ctx: IctSetupContext,
    setup_candles: list[Candle],
    exec_candles: list[Candle],
    atr_setup: float,
    atr_exec: float,
    cfg: IctConfig,
    price: float,
    *,
    symbol: str = "",
    prior_state: IctSetupState | None = None,
) -> IctSetupContext:
    if not ctx.sweep or ctx.trade_bias != "BEARISH":
        return ctx
    return evaluate_causal_sequence(
        ctx,
        setup_candles,
        exec_candles,
        atr_setup,
        atr_exec,
        cfg,
        price,
        symbol=symbol,
        prior_state=prior_state,
    )
