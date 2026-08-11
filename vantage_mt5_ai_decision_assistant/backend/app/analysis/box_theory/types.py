"""Box Theory — types, enums, configuration."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.market_structure.types import Candle


class BoxStatus(str, Enum):
    FORMING = "FORMING"
    VALID = "VALID"
    BREAKOUT_UP = "BREAKOUT_UP"
    BREAKOUT_DOWN = "BREAKOUT_DOWN"
    RETESTING = "RETESTING"
    CONFIRMED_BULLISH = "CONFIRMED_BULLISH"
    CONFIRMED_BEARISH = "CONFIRMED_BEARISH"
    BULL_TRAP = "BULL_TRAP"
    BEAR_TRAP = "BEAR_TRAP"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"


class SignalDecision(str, Enum):
    WAIT = "WAIT"
    WATCH = "WATCH"
    BUY = "BUY"
    SELL = "SELL"
    INVALID = "INVALID"


class SignalQuality(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class EntryMode(str, Enum):
    BREAKOUT_MODE = "BREAKOUT_MODE"
    BREAKOUT_RETEST_MODE = "BREAKOUT_RETEST_MODE"


class BoxEvent(str, Enum):
    BOX_DETECTED = "BOX_DETECTED"
    BOX_BREAKOUT = "BOX_BREAKOUT"
    BOX_BREAKDOWN = "BOX_BREAKDOWN"
    RETEST_STARTED = "RETEST_STARTED"
    BUY_CONFIRMED = "BUY_CONFIRMED"
    SELL_CONFIRMED = "SELL_CONFIRMED"
    BULL_TRAP = "BULL_TRAP"
    BEAR_TRAP = "BEAR_TRAP"
    BOX_INVALIDATED = "BOX_INVALIDATED"


@dataclass
class BoxRange:
    box_id: str
    high: float
    low: float
    mid: float
    height: float
    start_time: int
    end_time: int
    age_candles: int
    upper_touches: int
    lower_touches: int
    inside_ratio: float
    quality_score: float


@dataclass
class BoxStrategyConfig:
    enabled: bool = True
    allowed_symbols: tuple[str, ...] = ("XAUUSD", "GOLD", "EURUSD", "USDJPY")
    structure_timeframe: str = "H1"
    box_timeframe: str = "M15"
    entry_timeframe: str = "M5"
    lookback_candles: int = 50
    min_box_candles: int = 8
    min_touches: int = 2
    touch_tolerance_atr: float = 0.15
    max_box_height_atr: float = 2.5
    min_box_height_atr: float = 0.35
    min_inside_ratio: float = 0.65
    breakout_buffer_atr: float = 0.15
    min_breakout_body_ratio: float = 0.45
    retest_tolerance_atr: float = 0.25
    max_retest_candles: int = 10
    confirmation_candles: int = 1
    require_retest: bool = True
    entry_mode: str = "BREAKOUT_RETEST_MODE"
    max_box_age_candles: int = 80
    chase_max_atr: float = 0.5
    liquidity_sweep_detection: bool = True
    fvg_confirmation: bool = True
    htf_confirmation: bool = True
    minimum_signal_score: float = 70.0
    block_countertrend: bool = False
    countertrend_penalty: float = 15.0
    sl_mode: str = "RETEST_SWING"  # RETEST_SWING | BOX_MID | BOX_OPPOSITE
    sl_buffer_atr: float = 0.15
    tp_multipliers: tuple[float, ...] = (1.0, 1.5, 2.0)
    discord_default_events: tuple[str, ...] = (
        "BUY_CONFIRMED",
        "SELL_CONFIRMED",
        "BULL_TRAP",
        "BEAR_TRAP",
    )


DEFAULT_BOX_STRATEGY_CONFIG = BoxStrategyConfig()

DEFAULT_DISCORD_EVENTS = frozenset(
    {
        BoxEvent.BUY_CONFIRMED.value,
        BoxEvent.SELL_CONFIRMED.value,
        BoxEvent.BULL_TRAP.value,
        BoxEvent.BEAR_TRAP.value,
    }
)
