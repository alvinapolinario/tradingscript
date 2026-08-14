"""Pydantic schemas for EA ↔ backend contract."""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class AdvisoryAction(str, Enum):
    """Legacy primary action (compat). Prefer new_entry_decision + existing_position_decision."""

    HOLD = "HOLD"
    HOLD_WITH_CAUTION = "HOLD_WITH_CAUTION"
    PROTECT_PROFIT = "PROTECT_PROFIT"
    EXIT_WARNING = "EXIT_WARNING"
    WAIT_FOR_RETEST = "WAIT_FOR_RETEST"
    BUY_WATCH = "BUY_WATCH"
    SELL_WATCH = "SELL_WATCH"
    NO_TRADE = "NO_TRADE"
    HIGH_SPREAD = "HIGH_SPREAD"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
    BACKEND_OFFLINE = "BACKEND_OFFLINE"
    RISK_CALCULATION_UNAVAILABLE = "RISK_CALCULATION_UNAVAILABLE"
    CRITICAL_RISK = "CRITICAL_RISK"
    NO_NEW_TRADE = "NO_NEW_TRADE"


class NewEntryDecision(str, Enum):
    BUY_ALLOWED = "BUY_ALLOWED"
    SELL_ALLOWED = "SELL_ALLOWED"
    WAIT = "WAIT"
    NO_NEW_TRADE = "NO_NEW_TRADE"
    HIGH_SPREAD = "HIGH_SPREAD"
    RISK_BLOCKED = "RISK_BLOCKED"


class ExistingPositionDecision(str, Enum):
    HOLD = "HOLD"
    HOLD_WITH_CAUTION = "HOLD_WITH_CAUTION"
    PROTECT_PROFIT = "PROTECT_PROFIT"
    EXIT_WARNING = "EXIT_WARNING"
    CRITICAL_RISK = "CRITICAL_RISK"
    POSITION_DATA_UNAVAILABLE = "POSITION_DATA_UNAVAILABLE"
    NONE = "NONE"  # flat — no open position


class RiskStatus(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"
    CRITICAL = "CRITICAL"
    UNAVAILABLE = "UNAVAILABLE"


class BrokerInfo(BaseModel):
    company: str = ""
    server: str = ""
    currency: str = ""
    margin_mode: str = ""
    account_login_masked: str = ""


class SymbolInfo(BaseModel):
    name: str
    digits: int
    point: float
    tick_size: float
    tick_value: float
    tick_value_profit: float = 0.0
    tick_value_loss: float = 0.0
    contract_size: float
    volume_min: float
    volume_max: float
    volume_step: float
    stops_level: int = 0
    freeze_level: int = 0
    spread_float: bool = True
    trade_mode: int = 0
    trade_execution: int = 0
    filling_mode: int = 0


class PriceInfo(BaseModel):
    bid: float
    ask: float
    last: float = 0.0
    spread_points: int
    high_spread: bool = False
    server_time: str = ""
    local_time: str = ""
    utc_time: str = ""


class CandleInfo(BaseModel):
    timeframe: str = "M30"
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


class IndicatorInfo(BaseModel):
    ema20: float
    ema50: float
    ema200: float
    bb_upper: float
    bb_middle: float
    bb_lower: float
    rsi14: float
    atr14: float
    volume_sma: float = 0.0


class StructureInfo(BaseModel):
    trend: str = "NEUTRAL"
    oversized_candle: bool = False
    support_break: bool = False
    retest_pending: bool = False
    bear_reject: bool = False
    bull_reject: bool = False
    note: str = ""
    nearest_support: str = ""
    nearest_resistance: str = ""
    daily_pivot: float = 0.0
    bullish_pct: float = 0.0
    bearish_pct: float = 0.0
    neutral_pct: float = 0.0
    bias_lookback: int = 20
    indicator_bullish_pct: float = 0.0
    indicator_bearish_pct: float = 0.0


class RiskInfo(BaseModel):
    available: bool = False
    status: str = "RISK_CALCULATION_UNAVAILABLE"
    last_error: int = 0
    stop_distance_price: float = 0.0
    stop_distance_points: float = 0.0
    money_at_risk: float = 0.0
    equity_risk_pct: float = 0.0
    reward_to_target: float = 0.0
    reward_risk_ratio: float = 0.0
    margin_required: float = 0.0
    entry: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    volume: float = 0.0


class PositionItem(BaseModel):
    ticket: int
    type: str
    volume: float
    price_open: float
    price_current: float
    sl: float = 0.0
    tp: float = 0.0
    profit: float = 0.0
    swap: float = 0.0
    time_open: str = ""
    comment: str = ""
    magic: int = 0


class PositionsInfo(BaseModel):
    count: int = 0
    total_buy_volume: float = 0.0
    total_sell_volume: float = 0.0
    weighted_avg_entry: float = 0.0
    total_floating_pl: float = 0.0
    items: list[PositionItem] = Field(default_factory=list)


class PendingOrderItem(BaseModel):
    ticket: int = 0
    symbol: str = ""
    digits: int = 0
    type: str = ""
    volume: float = 0.0
    price_open: float = 0.0
    price_current: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    time_setup: str = ""
    comment: str = ""
    magic: int = 0
    distance_price: float = 0.0
    distance_points: float = 0.0
    risk_available: bool = False
    risk_status: str = "RISK_CALCULATION_UNAVAILABLE"
    money_at_risk: float = 0.0
    equity_risk_pct: float = 0.0
    reward_risk_ratio: float = 0.0
    margin_required: float = 0.0


class PendingOrdersInfo(BaseModel):
    count: int = 0
    items: list[PendingOrderItem] = Field(default_factory=list)


class AnalyzeRequest(BaseModel):
    schema_version: str = "1.0"
    mode: str = "advisory_only"
    broker: BrokerInfo = Field(default_factory=BrokerInfo)
    symbol: SymbolInfo
    prices: PriceInfo
    candle: CandleInfo
    indicators: IndicatorInfo
    structure: StructureInfo = Field(default_factory=StructureInfo)
    levels: dict[str, float] = Field(default_factory=dict)
    positions: PositionsInfo = Field(default_factory=PositionsInfo)
    # Optional — omit when absent so analyze does not wipe a fresher heartbeat book
    pending_orders: Optional[PendingOrdersInfo] = None
    risk: RiskInfo = Field(default_factory=RiskInfo)
    environment: str = "NORMAL"
    extra: Optional[dict[str, Any]] = None


class AnalyzeResponse(BaseModel):
    action: AdvisoryAction
    rationale: str
    trend: str
    environment: str
    market_state: str = "NEUTRAL"
    new_entry_decision: NewEntryDecision = NewEntryDecision.NO_NEW_TRADE
    existing_position_decision: ExistingPositionDecision = ExistingPositionDecision.NONE
    risk_status: RiskStatus = RiskStatus.NONE
    exceeds_max_position_risk: bool = False
    max_position_risk_pct: float = 2.0
    new_position_allowed: bool = False
    add_position_allowed: bool = False
    immediate_support: str = ""
    recovery_level_1: str = ""
    recovery_level_2: str = ""
    bullish_confirmation: str = ""
    technical_invalidation: str = ""
    risk_warning: str = ""
    nearest_support: str
    nearest_resistance: str
    timestamp_utc: str
    generated_at_utc: str
    age_seconds: int = 0
    advisory_only: bool = True
    symbol: str
    digits: int
    contract_size: float
    estimated_money_risk: Optional[float] = None
    equity_risk_pct: Optional[float] = None
    entry: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    bullish_pct: float = 0.0
    bearish_pct: float = 0.0
    neutral_pct: float = 0.0
    bias_lookback: int = 20
    indicator_bullish_pct: float = 0.0
    indicator_bearish_pct: float = 0.0


class HealthResponse(BaseModel):
    status: str
    service: str
    advisory_only: bool = True
    version: str = "1.2.0"
    monitor_url: str = "http://187.77.142.118:8000/monitor"
    telegram: Optional[dict[str, Any]] = None
    discord: Optional[dict[str, Any]] = None


class HeartbeatRequest(BaseModel):
    ea_version: str = "1.0.0"
    company: str = ""
    server: str = ""
    account_login_masked: str = ""
    margin_mode: str = ""
    currency: str = ""
    symbol: str = ""
    digits: int = 0
    contract_size: float = 0.0
    stops_level: int = 0
    bid: float = 0.0
    ask: float = 0.0
    spread_points: int = 0
    high_spread: bool = False
    action: str = ""
    trend: str = ""
    bullish_pct: float = 0.0
    bearish_pct: float = 0.0
    neutral_pct: float = 0.0
    bias_lookback: int = 20
    indicator_bullish_pct: float = 0.0
    indicator_bearish_pct: float = 0.0
    candle_status: str = ""
    backend_status: str = "OK"
    position_count: int = 0
    total_buy_volume: float = 0.0
    total_sell_volume: float = 0.0
    pending_order_count: int = 0
    pending_orders: Optional[dict[str, Any]] = None
    floating_pl: float = 0.0
    equity: float = 0.0
    balance: float = 0.0
    floating_pl_pct_of_equity: float = 0.0
    float_profit_target_pct: float = 10.0
    float_profit_target_hit: bool = False
    nearest_support: str = ""
    nearest_resistance: str = ""
    note: str = ""
    terminal_connected: bool = True
    new_entry_decision: str = ""
    existing_position_decision: str = ""
    risk_status: str = ""
    equity_risk_pct: float = 0.0
    estimated_sl_loss: float = 0.0
    entry: float = 0.0
    sl: float = 0.0
    new_position_allowed: bool = False
    add_position_allowed: bool = False
    exceeds_max_position_risk: bool = False
    market_state: str = ""
    risk_warning: str = ""
    immediate_support: str = ""
    recovery_level_1: str = ""
    recovery_level_2: str = ""
    bullish_confirmation: str = ""
    technical_invalidation: str = ""
    level_source: str = ""
    pl_calendar: Optional[dict[str, Any]] = None
    trade_stats: Optional[dict[str, Any]] = None
    server_year: int = 0
    server_month: int = 0
    # Optional M5 Alignment Desk feed (H1/M15/M5 gates). Ignored by M30 cockpit.
    strategy: Optional[dict[str, Any]] = None
    # Pullback Probability Analyzer blob (advisory; not used by SETUP_OK gates)
    pullback: Optional[dict[str, Any]] = None
    # Pullback Desk V2 experimental blob (advisory; independent scores)
    pullback_v2: Optional[dict[str, Any]] = None
    # Gold SMC Intelligence Engine blob (advisory; Gold-only; Phase 1 scaffold)
    gold_smc: Optional[dict[str, Any]] = None
    # Liquidity Grab Detection blob (advisory; Gold-only)
    liquidity_grab: Optional[dict[str, Any]] = None
    # Breakout Structure Intelligence blob (advisory; Gold-only)
    breakout_structure: Optional[dict[str, Any]] = None
    # Institutional Market State Engine v2 blob (advisory; Gold-only)
    market_state_engine: Optional[dict[str, Any]] = None
    swing_strategy: Optional[dict[str, Any]] = None
    amd_ifvg: Optional[dict[str, Any]] = None
    box_theory: Optional[dict[str, Any]] = None
    ict: Optional[dict[str, Any]] = None
    # Closed multi-TF candles for Python canonical engines (optional)
    ict_candles: Optional[dict[str, Any]] = None
    box_candles: Optional[dict[str, Any]] = None
    # H4→M15 FVG — closed H4/M15 candles for Python engine (optional)
    h4_m15_fvg_candles: Optional[dict[str, Any]] = None
    # Pre-computed H4→M15 blob (optional passthrough)
    h4_m15_fvg: Optional[dict[str, Any]] = None
    # EA risk thresholds (optional; also may arrive via analyze extra)
    max_position_risk_pct: Optional[float] = None


class HeartbeatResponse(BaseModel):
    status: str = "ok"
    received_utc: str
    monitor_url: str = "http://187.77.142.118:8000/monitor"
    calendar_year: int = 0
    calendar_month: int = 0


class CalendarMonthRequest(BaseModel):
    year: int
    month: int


class SelectSymbolRequest(BaseModel):
    symbol: str


class AiAnalyzeRequest(BaseModel):
    symbol: str = ""
    extra_question: str = ""
    bypass_cache: bool = False


# --- Market news / macro intelligence (Step 2+) ---


class MarketNewsEconomicEventIn(BaseModel):
    """Single economic calendar row from MT5 bridge or external provider."""

    event_id: str = ""
    external_event_id: str = ""
    currency: str
    country: str = ""
    event: str
    importance: str = "MEDIUM"
    scheduled_at: str
    previous: float | None = None
    forecast: float | None = None
    actual: float | None = None
    status: str = "SCHEDULED"
    category: str = "OTHER"


class Mt5CalendarIngestRequest(BaseModel):
    """POST /api/v1/market-news/mt5-calendar payload (Step 3)."""

    source: str = "MT5_CALENDAR"
    server_time_utc: str = ""
    terminal: str = ""
    broker: str = ""
    events: list[MarketNewsEconomicEventIn] = Field(default_factory=list)


class NormalizedNewsItemIn(BaseModel):
    """Textual news ingest (manual / RSS / licensed API)."""

    source: str = "NEWS_PROVIDER"
    external_id: str = ""
    headline: str
    summary: str = ""
    body: str = ""
    published_at: str
    currencies: list[str] = Field(default_factory=list)
    symbols: list[str] = Field(default_factory=list)
    category: str = "OTHER"
    importance: str = "MEDIUM"
    raw_url: str = ""


class MarketNewsIngestRequest(BaseModel):
    """Bulk news ingest — Step 5+."""

    items: list[NormalizedNewsItemIn] = Field(default_factory=list)


class MarketNewsCurrencyBiasOut(BaseModel):
    direction: str
    confidence: float
    horizon: str = "INTRADAY"


class MarketNewsAiAnalysisOut(BaseModel):
    """Structured AI interpretation shape (Step 11)."""

    headline: str
    category: str
    time_horizon: str
    currencies: dict[str, MarketNewsCurrencyBiasOut] = Field(default_factory=dict)
    symbols: dict[str, MarketNewsCurrencyBiasOut] = Field(default_factory=dict)
    drivers: list[str] = Field(default_factory=list)
    counter_drivers: list[str] = Field(default_factory=list)


class MarketNewsAnalyzeRequest(BaseModel):
    """POST /api/v1/market-news/analyze — manual re-run (Step 11)."""

    symbol: str = "XAUUSD"
    headline: str | None = None
    force: bool = False
