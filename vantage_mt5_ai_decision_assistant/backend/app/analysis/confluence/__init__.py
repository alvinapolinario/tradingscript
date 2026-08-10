"""Multi-strategy confluence engine."""
from app.analysis.confluence.engine import (
    compute_confluence,
    compute_confluence_from_ea,
    confluence_config_from_settings,
    verdict_from_confluence,
)
from app.analysis.confluence.normalize import normalize_ea_signals
from app.analysis.confluence.types import ConfluenceConfig, ConfluenceResult, StrategySignal
from app.analysis.confluence.weights import DEFAULT_STRATEGY_WEIGHTS

__all__ = [
    "ConfluenceConfig",
    "ConfluenceResult",
    "StrategySignal",
    "DEFAULT_STRATEGY_WEIGHTS",
    "compute_confluence",
    "compute_confluence_from_ea",
    "confluence_config_from_settings",
    "normalize_ea_signals",
    "verdict_from_confluence",
]
