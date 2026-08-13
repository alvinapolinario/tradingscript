"""H4 → M15 FVG setup engine — types and configuration."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.analysis.ict.types import LiquiditySweepEvent
from app.market_structure.types import FvgZone


class H4M15SetupState(str, Enum):
    WAITING_FOR_HTF_FVG = "WAITING_FOR_HTF_FVG"
    HTF_FVG_FOUND = "HTF_FVG_FOUND"
    WAITING_FOR_HTF_MITIGATION = "WAITING_FOR_HTF_MITIGATION"
    HTF_FVG_TOUCHED = "HTF_FVG_TOUCHED"
    WAITING_FOR_LIQUIDITY_SWEEP = "WAITING_FOR_LIQUIDITY_SWEEP"
    LIQUIDITY_SWEPT = "LIQUIDITY_SWEPT"
    WAITING_FOR_DISPLACEMENT = "WAITING_FOR_DISPLACEMENT"
    DISPLACEMENT_CONFIRMED = "DISPLACEMENT_CONFIRMED"
    WAITING_FOR_MSS = "WAITING_FOR_MSS"
    MSS_CONFIRMED = "MSS_CONFIRMED"
    WAITING_FOR_LTF_FVG = "WAITING_FOR_LTF_FVG"
    LTF_FVG_CREATED = "LTF_FVG_CREATED"
    WAITING_FOR_RETRACE = "WAITING_FOR_RETRACE"
    ENTRY_READY = "ENTRY_READY"
    SETUP_INVALIDATED = "SETUP_INVALIDATED"
    SETUP_EXPIRED = "SETUP_EXPIRED"


class RetraceMode(str, Enum):
    TOUCH = "TOUCH"
    MIDPOINT = "MIDPOINT"
    PCT_25 = "25_PERCENT"
    CUSTOM = "CUSTOM_PERCENT"


@dataclass
class H4M15FvgConfig:
    htf_timeframe: str = "H4"
    execution_timeframe: str = "M15"
    min_h4_fvg_atr: float = 0.10
    min_m15_fvg_atr: float = 0.10
    fvg_min_gap_atr: float = 0.05
    min_body_ratio: float = 0.60
    min_range_atr_ratio: float = 1.20
    displacement_min_score: float = 50.0
    pivot_left: int = 2
    pivot_right: int = 2
    swing_min_atr: float = 0.3
    sweep_min_penetration_atr: float = 0.05
    sweep_max_penetration_atr: float = 0.75
    sweep_require_reentry: bool = True
    sl_buffer_atr: float = 0.15
    max_confirmation_m15_bars: int = 32
    max_retrace_m15_bars: int = 24
    max_h4_age_bars: int = 40
    allow_reentry: bool = False
    retrace_mode: RetraceMode = RetraceMode.TOUCH
    retrace_custom_pct: float = 50.0
    causal_window_m15_bars: int = 1
    invalidate_htf_on_close_break: bool = True
    weight_htf_structure: float = 15.0
    weight_h4_fvg_quality: float = 10.0
    weight_h4_location: float = 10.0
    weight_liquidity_sweep: float = 15.0
    weight_displacement: float = 15.0
    weight_mss: float = 15.0
    weight_entry_fvg: float = 10.0
    weight_retrace: float = 5.0
    weight_session: float = 5.0


DEFAULT_H4_M15_CONFIG = H4M15FvgConfig()


@dataclass
class StateTransitionLog:
    timestamp: int
    setup_id: str
    symbol: str
    old_state: str
    new_state: str
    reason: str
    related_event_id: str = ""


@dataclass
class H4M15Setup:
    setup_id: str
    symbol: str
    direction: str  # BULLISH | BEARISH
    state: H4M15SetupState
    htf_fvg: FvgZone
    htf_first_touch_time: int = 0
    htf_touch_bar_index: int = -1
    pd_location: str = "NEUTRAL"
    pd_position: float = 0.5
    htf_bias: str = "NEUTRAL"
    bias_alignment: bool = False
    sweep: LiquiditySweepEvent | None = None
    displacement_time: int = 0
    displacement_score: float = 0.0
    displacement_event_id: str = ""
    mss_time: int = 0
    mss_price: float = 0.0
    mss_swing_id: str = ""
    entry_fvg: FvgZone | None = None
    entry_ready_time: int = 0
    entry_price: float = 0.0
    structural_stop: float = 0.0
    target_price: float = 0.0
    risk_reward: float = 0.0
    setup_score: float = 0.0
    setup_grade: str = "LOW"
    invalidation_reason: str = ""
    expiration_reason: str = ""
    created_time: int = 0
    updated_time: int = 0
    m15_bars_since_touch: int = 0
    m15_bars_since_mss: int = 0
    m15_bars_since_ltf_fvg: int = 0
    reasons: list[str] = field(default_factory=list)
    rejections: list[str] = field(default_factory=list)
    transition_log: list[StateTransitionLog] = field(default_factory=list)
    entry_ready_emitted: bool = False

    @property
    def trade_bias(self) -> str:
        return self.direction
