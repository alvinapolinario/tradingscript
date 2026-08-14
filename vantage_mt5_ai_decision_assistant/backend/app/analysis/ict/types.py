"""ICT strategy — types, enums, configuration."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from app.market_structure.types import Candle, FvgZone

if TYPE_CHECKING:
    from app.analysis.ict.poi import OrderBlockZone


class IctSetupState(str, Enum):
    WAITING_FOR_LIQUIDITY = "WAITING_FOR_LIQUIDITY"
    LIQUIDITY_IDENTIFIED = "LIQUIDITY_IDENTIFIED"
    LIQUIDITY_SWEPT = "LIQUIDITY_SWEPT"
    WAITING_FOR_DISPLACEMENT = "WAITING_FOR_DISPLACEMENT"
    DISPLACEMENT_CONFIRMED = "DISPLACEMENT_CONFIRMED"
    WAITING_FOR_MSS = "WAITING_FOR_MSS"
    MSS_CONFIRMED = "MSS_CONFIRMED"
    WAITING_FOR_EXECUTION_FVG = "WAITING_FOR_EXECUTION_FVG"
    EXECUTION_FVG_FOUND = "EXECUTION_FVG_FOUND"
    WAITING_FOR_RETRACE = "WAITING_FOR_RETRACE"
    FVG_TOUCHED = "FVG_TOUCHED"
    ENTRY_ZONE_ACTIVE = "ENTRY_ZONE_ACTIVE"
    ENTRY_READY = "ENTRY_READY"
    TRIGGERED = "TRIGGERED"  # legacy alias — maps to ENTRY_READY in API
    INVALIDATED = "INVALIDATED"
    TARGET_REACHED = "TARGET_REACHED"
    EXPIRED = "EXPIRED"
    NO_SETUP = "NO_SETUP"


class EntryTriggerMode(str, Enum):
    TOUCH = "TOUCH"
    CLOSED_BAR_TOUCH = "CLOSED_BAR_TOUCH"
    CE_TOUCH = "CE_TOUCH"


class IctDecision(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"
    NO_TRADE = "NO_TRADE"
    NO_SETUP = "NO_SETUP"


@dataclass
class IctConfig:
    enabled: bool = True
    allowed_symbols: tuple[str, ...] = ("XAUUSD", "GOLD", "EURUSD", "USDJPY")
    min_candles: int = 60
    higher_timeframes: tuple[str, ...] = ("D1", "H4", "H1")
    setup_timeframes: tuple[str, ...] = ("H1", "M15")
    execution_timeframes: tuple[str, ...] = ("M15", "M5")
    primary_setup_timeframe: str = "M15"
    primary_execution_timeframe: str = "M5"
    min_confidence: float = 70.0
    minimum_rr: float = 2.0
    require_liquidity_sweep: bool = True
    require_displacement: bool = True
    require_mss: bool = True
    require_fvg: bool = True
    use_premium_discount: bool = True
    use_session_filter: bool = False
    pivot_left: int = 2
    pivot_right: int = 2
    swing_min_atr: float = 0.3
    equal_high_low_tolerance_atr: float = 0.10
    sweep_min_penetration_atr: float = 0.05
    sweep_max_penetration_atr: float = 0.75
    sweep_require_reentry: bool = True
    displacement_min_body_atr: float = 0.8
    displacement_min_range_atr: float = 1.0
    displacement_min_body_ratio: float = 0.60
    displacement_min_score: float = 50.0
    max_displacement_bars_after_sweep: int = 4
    max_mss_bars_after_displacement: int = 2
    max_fvg_bars_after_mss: int = 2
    max_bars_sweep_to_displacement: int = 6
    max_bars_displacement_to_mss: int = 4
    max_bars_mss_to_fvg: int = 4
    max_bars_fvg_to_retrace: int = 40
    entry_trigger_mode: EntryTriggerMode = EntryTriggerMode.TOUCH
    enable_ote: bool = True
    enable_order_blocks: bool = True
    enable_breaker: bool = True
    ote_low_pct: float = 0.618
    ote_mid_pct: float = 0.705
    ote_high_pct: float = 0.790
    weight_ote: float = 4.0
    weight_order_block: float = 6.0
    weight_breaker: float = 4.0
    ob_require_sweep_origin: bool = True
    breaker_quality_bonus: float = 8.0
    fvg_min_gap_atr: float = 0.05
    sl_buffer_atr: float = 0.2
    chase_max_atr: float = 0.35
    max_spread_points: float = 80.0
    session_timezone: str = "UTC"
    trading_day_timezone: str = "America/New_York"
    trading_day_reset_hour: int = 17
    weight_htf_alignment: float = 20.0
    weight_liquidity_sweep: float = 20.0
    weight_impulse_quality: float = 40.0  # grouped displacement+MSS+FVG (avoid double count)
    weight_displacement: float = 0.0  # deprecated — use impulse group
    weight_mss: float = 0.0
    weight_fvg: float = 0.0
    weight_premium_discount: float = 10.0
    weight_session: float = 5.0
    weight_risk_reward: float = 5.0
    countertrend_penalty: float = 12.0
    max_setup_age_candles: int = 40
    block_countertrend: bool = False


DEFAULT_ICT_CONFIG = IctConfig()


@dataclass
class LiquidityLevel:
    kind: str  # BSL | SSL | EQH | EQL | PDH | PDL
    price: float
    time: int
    source: str = "SWING"


@dataclass
class LiquiditySweepEvent:
    detected: bool
    sweep_type: str  # BUY_SIDE | SELL_SIDE
    trade_bias: str  # BEARISH | BULLISH
    level: float
    sweep_price: float
    sweep_time: int
    penetration: float
    closed_back_inside: bool
    quality_score: float = 0.0
    event_id: str = ""
    setup_id: str = ""
    liquidity_level_id: str = ""
    liquidity_type: str = ""
    penetration_atr: float = 0.0
    reclaim_confirmed: bool = False


@dataclass
class MssTarget:
    swing_id: str
    swing_type: str
    price: float
    time: int


@dataclass
class DisplacementEvent:
    event_id: str
    setup_id: str
    direction: str
    start_time: int
    end_time: int
    primary_candle_time: int
    open_price: float
    close_price: float
    high: float
    low: float
    body_size: float
    range_size: float
    atr: float
    body_atr_ratio: float
    range_atr_ratio: float
    body_to_range_ratio: float
    close_location: float
    distance_travelled: float
    distance_atr: float
    bars_count: int
    structure_break: bool
    fvg_created: bool
    quality_score: float


@dataclass
class StructureBreakEvent:
    event_id: str
    setup_id: str
    type: str
    direction: str
    broken_swing_id: str
    broken_level: float
    broken_swing_time: int
    confirmation_time: int
    confirmation_price: float
    confirmation_type: str
    source_displacement_event_id: str
    quality_score: float


@dataclass
class EntryZone:
    type: str
    direction: str
    zone_high: float
    zone_low: float
    midpoint: float
    status: str  # DETECTED | ACTIVE | TOUCHED | CONFIRMED


@dataclass
class IctSetupContext:
    trade_bias: str
    state: IctSetupState
    bsl_levels: list[LiquidityLevel] = field(default_factory=list)
    ssl_levels: list[LiquidityLevel] = field(default_factory=list)
    sweep: LiquiditySweepEvent | None = None
    mss_target: MssTarget | None = None
    displacement_event: DisplacementEvent | None = None
    mss_event: StructureBreakEvent | None = None
    displacement_score: float = 0.0
    displacement_time: int = 0
    mss: dict | None = None
    fvg: FvgZone | None = None
    execution_fvg_id: str = ""
    fvg_touch_time: int = 0
    entry_ready_time: int = 0
    entry_event_id: str = ""
    entry_ready_emitted: bool = False
    entry: EntryZone | None = None
    ote_valid: bool = False
    ote_low: float = 0.0
    ote_mid: float = 0.0
    ote_high: float = 0.0
    price_in_ote: bool = False
    poi_overlaps_ote: bool = False
    fvg_overlaps_ote: bool = False
    fvg_overlaps_ob: bool = False
    order_block: OrderBlockZone | None = None
    causality_valid: bool = True
    causality_errors: list[str] = field(default_factory=list)
    state_reason: str = ""
    pdh: float = 0.0
    pdl: float = 0.0
    pdh_pdl_source: str = ""
    equilibrium: float = 0.0
    range_position: str = "NEUTRAL"
    dealing_high: float = 0.0
    dealing_low: float = 0.0
    premium_discount_zone: str = "NEUTRAL"
    htf_bias: str = "NEUTRAL"
    htf_evidence: list[str] = field(default_factory=list)
    session_name: str = ""
    reasons: list[str] = field(default_factory=list)
    invalidations: list[str] = field(default_factory=list)
    timeline: list[dict[str, str]] = field(default_factory=list)
    setup_id: str = ""
    created_time: int = 0
    updated_time: int = 0
    invalidation_price: float = 0.0
    stop_loss: float = 0.0
    tp1_price: float = 0.0


@dataclass
class IctSetupRecord:
    """Persisted ICT setup — keyed by setup_id, survives across analyze calls."""

    setup_id: str
    symbol: str
    timeframe: str
    trade_bias: str
    state: IctSetupState
    sweep_time: int = 0
    sweep_type: str = ""
    sweep_level: float = 0.0
    sweep_price: float = 0.0
    displacement_score: float = 0.0
    mss_direction: str = ""
    fvg_id: str = ""
    fvg_high: float = 0.0
    fvg_low: float = 0.0
    entry_zone_high: float = 0.0
    entry_zone_low: float = 0.0
    stop_loss: float = 0.0
    invalidation_price: float = 0.0
    tp1_price: float = 0.0
    confidence: float = 0.0
    created_time: int = 0
    updated_time: int = 0
    age_candles: int = 0
    last_event: str = ""
