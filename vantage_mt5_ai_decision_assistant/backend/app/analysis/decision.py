"""Rule-based decision engine — separates new-entry vs existing-position advice."""
from __future__ import annotations

from datetime import datetime, timezone

from app.config import get_settings
from app.schemas import (
    AdvisoryAction,
    AnalyzeRequest,
    AnalyzeResponse,
    ExistingPositionDecision,
    NewEntryDecision,
    RiskStatus,
)

CRITICAL_WARNING = (
    "Position risk exceeds configured maximum. Do not add exposure or widen the stop."
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def classify_risk_status(
    equity_risk_pct: float | None,
    available: bool,
    *,
    low_max: float | None = None,
    mod_max: float | None = None,
    high_max: float | None = None,
    very_high_max: float | None = None,
) -> RiskStatus:
    s = get_settings()
    if not available or equity_risk_pct is None:
        return RiskStatus.UNAVAILABLE
    pct = float(equity_risk_pct)
    lo = s.risk_low_max_pct if low_max is None else low_max
    mo = s.risk_moderate_max_pct if mod_max is None else mod_max
    hi = s.risk_high_max_pct if high_max is None else high_max
    vh = s.risk_very_high_max_pct if very_high_max is None else very_high_max
    if pct < lo:
        return RiskStatus.LOW
    if pct < mo:
        return RiskStatus.MODERATE
    if pct < hi:
        return RiskStatus.HIGH
    if pct < vh:
        return RiskStatus.VERY_HIGH
    return RiskStatus.CRITICAL


def _fmt_price(v: float) -> str:
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.2f}"


def _level_from(levels: dict, *keys: str, default: float) -> float:
    for k in keys:
        if k in levels and levels[k] is not None:
            try:
                return float(levels[k])
            except (TypeError, ValueError):
                continue
    return default


def _market_state(req: AnalyzeRequest) -> str:
    s = get_settings()
    trend = (req.structure.trend or "NEUTRAL").upper()
    note = (req.structure.note or "").upper()
    rsi = req.indicators.rsi14
    if trend == "BEARISH" and rsi <= s.rsi_exhaust:
        return "BEARISH_EXHAUSTED"
    if "MULTI_LEVEL" in note or "IMPULSE" in note:
        return "BEARISH_IMPULSE"
    if req.structure.retest_pending:
        return "RETEST_PENDING"
    if req.prices.high_spread or (req.environment or "").upper() == "HIGH_SPREAD":
        return "HIGH_SPREAD"
    if (req.environment or "").upper() == "CLOSED_MARKET":
        return "CLOSED_MARKET"
    return trend


def decide(req: AnalyzeRequest) -> AnalyzeResponse:
    now = _utc_now()
    settings = get_settings()
    env = (req.environment or "NORMAL").upper()
    trend = (req.structure.trend or "NEUTRAL").upper()
    note = (req.structure.note or "").upper()
    pos = req.positions
    risk = req.risk
    market_state = _market_state(req)
    extra = req.extra or {}

    # Editable thresholds: EA extra overrides backend .env defaults
    low_max = float(extra.get("risk_low_max_pct", settings.risk_low_max_pct))
    mod_max = float(extra.get("risk_moderate_max_pct", settings.risk_moderate_max_pct))
    high_max = float(extra.get("risk_high_max_pct", settings.risk_high_max_pct))
    vh_max = float(extra.get("risk_very_high_max_pct", settings.risk_very_high_max_pct))
    max_pos_risk = float(extra.get("max_position_risk_pct", settings.max_position_risk_pct))

    levels = req.levels or {}
    imm_lo = _level_from(levels, "imm_support_lo", "4088", default=4088.0)
    imm_hi = _level_from(levels, "imm_support_hi", "4090", default=4090.0)
    recovery_1 = _level_from(levels, "recovery_1", "4100", default=4100.0)
    recovery_2 = _level_from(levels, "recovery_2", "4105", default=4105.0)
    bullish_conf = _level_from(levels, "bullish_confirmation", "4112", default=4112.0)

    immediate_support = f"{_fmt_price(imm_lo)}\u2013{_fmt_price(imm_hi)}"
    recovery_1_s = _fmt_price(recovery_1)
    recovery_2_s = _fmt_price(recovery_2)
    bullish_conf_s = _fmt_price(bullish_conf)

    risk_available = bool(risk.available and risk.status == "OK")
    equity_pct = float(risk.equity_risk_pct) if risk_available else None
    risk_status = classify_risk_status(
        equity_pct,
        risk_available and pos.count > 0,
        low_max=low_max,
        mod_max=mod_max,
        high_max=high_max,
        very_high_max=vh_max,
    )
    if pos.count == 0:
        risk_status = RiskStatus.NONE

    exceeds_max = bool(
        pos.count > 0
        and risk_available
        and equity_pct is not None
        and equity_pct >= max_pos_risk
    )
    risk_warning = CRITICAL_WARNING if (exceeds_max or risk_status == RiskStatus.CRITICAL) else ""

    # --- Existing position decision ---
    existing = ExistingPositionDecision.NONE
    if pos.count > 0:
        if not risk_available and risk.status == "RISK_CALCULATION_UNAVAILABLE":
            existing = ExistingPositionDecision.POSITION_DATA_UNAVAILABLE
        elif risk_status == RiskStatus.CRITICAL or exceeds_max:
            # Never plain HOLD under critical risk
            if pos.total_floating_pl < 0:
                existing = ExistingPositionDecision.CRITICAL_RISK
            else:
                existing = ExistingPositionDecision.HOLD_WITH_CAUTION
        elif pos.total_floating_pl > 0 and req.structure.bear_reject and trend == "BEARISH":
            existing = ExistingPositionDecision.PROTECT_PROFIT
        elif pos.total_floating_pl < 0 and (req.structure.oversized_candle or trend == "BEARISH"):
            existing = ExistingPositionDecision.EXIT_WARNING
        elif risk_status in (RiskStatus.HIGH, RiskStatus.VERY_HIGH):
            existing = ExistingPositionDecision.HOLD_WITH_CAUTION
        else:
            existing = ExistingPositionDecision.HOLD

    # --- New entry decision (always evaluated; blocked when position risk critical) ---
    new_entry = NewEntryDecision.NO_NEW_TRADE
    if env == "CLOSED_MARKET":
        new_entry = NewEntryDecision.NO_NEW_TRADE
    elif env == "HIGH_SPREAD" or req.prices.high_spread:
        new_entry = NewEntryDecision.HIGH_SPREAD
    elif exceeds_max or risk_status == RiskStatus.CRITICAL:
        new_entry = NewEntryDecision.RISK_BLOCKED
    elif pos.count > 0:
        # Open exposure — suppress averaging / new entries
        new_entry = NewEntryDecision.NO_NEW_TRADE
    elif "MULTI_LEVEL" in note or "IMPULSE" in note or req.structure.retest_pending:
        new_entry = NewEntryDecision.WAIT
    elif market_state == "BEARISH_EXHAUSTED":
        new_entry = NewEntryDecision.NO_NEW_TRADE
    elif trend == "BULLISH" and req.structure.bull_reject and req.indicators.rsi14 < 60:
        new_entry = NewEntryDecision.BUY_ALLOWED
    elif trend == "BEARISH" and req.structure.bear_reject and req.indicators.rsi14 > settings.rsi_exhaust:
        new_entry = NewEntryDecision.SELL_ALLOWED
    elif req.structure.support_break:
        new_entry = NewEntryDecision.WAIT
    else:
        new_entry = NewEntryDecision.NO_NEW_TRADE

    add_allowed = False
    new_allowed = new_entry in (NewEntryDecision.BUY_ALLOWED, NewEntryDecision.SELL_ALLOWED)
    if exceeds_max or risk_status == RiskStatus.CRITICAL or pos.count > 0:
        add_allowed = False
        new_allowed = False

    # Technical invalidation for open BUY: below SL; for open SELL: above SL
    technical_invalidation = ""
    if pos.count > 0 and risk.sl and risk.sl > 0:
        if pos.total_buy_volume >= pos.total_sell_volume:
            technical_invalidation = f"Close below SL {risk.sl:.2f}"
        else:
            technical_invalidation = f"Close above SL {risk.sl:.2f}"
    elif trend == "BEARISH":
        technical_invalidation = f"Break and hold above {bullish_conf_s}"

    # Legacy primary action for EA/monitor badges
    if existing == ExistingPositionDecision.CRITICAL_RISK:
        action = AdvisoryAction.CRITICAL_RISK
        rationale = risk_warning or "Critical open-position risk — advisory warning only."
    elif existing == ExistingPositionDecision.HOLD_WITH_CAUTION:
        action = AdvisoryAction.HOLD_WITH_CAUTION
        rationale = risk_warning or "Hold open position with caution; do not add exposure."
    elif existing == ExistingPositionDecision.PROTECT_PROFIT:
        action = AdvisoryAction.PROTECT_PROFIT
        rationale = "Open profit with adverse rejection — consider protecting gains manually."
    elif existing == ExistingPositionDecision.EXIT_WARNING:
        action = AdvisoryAction.EXIT_WARNING
        rationale = "Open loss with adverse structure — exit warning only (manual)."
    elif existing == ExistingPositionDecision.POSITION_DATA_UNAVAILABLE:
        action = AdvisoryAction.RISK_CALCULATION_UNAVAILABLE
        rationale = "Broker risk calculation unavailable for open position."
    elif existing == ExistingPositionDecision.HOLD:
        action = AdvisoryAction.HOLD
        rationale = "Open position present — hold; no automatic management."
    elif new_entry == NewEntryDecision.HIGH_SPREAD:
        action = AdvisoryAction.HIGH_SPREAD
        rationale = "High spread — fresh entries suppressed."
    elif new_entry == NewEntryDecision.WAIT:
        action = AdvisoryAction.WAIT_FOR_RETEST
        rationale = "Wait for retest / pullback — do not chase."
    elif new_entry == NewEntryDecision.BUY_ALLOWED:
        action = AdvisoryAction.BUY_WATCH
        rationale = "Buy watch only (advisory)."
    elif new_entry == NewEntryDecision.SELL_ALLOWED:
        action = AdvisoryAction.SELL_WATCH
        rationale = "Sell watch only (advisory)."
    elif new_entry == NewEntryDecision.RISK_BLOCKED:
        action = AdvisoryAction.NO_NEW_TRADE
        rationale = risk_warning or "New entries blocked by position risk limits."
    else:
        action = AdvisoryAction.NO_NEW_TRADE
        rationale = "No new trade — flat or conditions not met."

    if pos.count > 0 and action == AdvisoryAction.HOLD and (
        risk_status == RiskStatus.CRITICAL or exceeds_max
    ):
        action = AdvisoryAction.HOLD_WITH_CAUTION
        existing = ExistingPositionDecision.HOLD_WITH_CAUTION
        rationale = CRITICAL_WARNING

    return AnalyzeResponse(
        action=action,
        rationale=rationale,
        trend=trend,
        environment=env,
        market_state=market_state,
        new_entry_decision=new_entry,
        existing_position_decision=existing,
        risk_status=risk_status,
        exceeds_max_position_risk=exceeds_max,
        max_position_risk_pct=max_pos_risk,
        new_position_allowed=new_allowed,
        add_position_allowed=add_allowed,
        immediate_support=immediate_support,
        recovery_level_1=recovery_1_s,
        recovery_level_2=recovery_2_s,
        bullish_confirmation=bullish_conf_s,
        technical_invalidation=technical_invalidation,
        risk_warning=risk_warning,
        nearest_support=req.structure.nearest_support or immediate_support,
        nearest_resistance=req.structure.nearest_resistance or recovery_1_s,
        timestamp_utc=now.isoformat(),
        generated_at_utc=now.isoformat(),
        age_seconds=0,
        advisory_only=True,
        symbol=req.symbol.name,
        digits=req.symbol.digits,
        contract_size=req.symbol.contract_size,
        estimated_money_risk=risk.money_at_risk if risk_available else None,
        equity_risk_pct=equity_pct,
        entry=risk.entry or (pos.weighted_avg_entry if pos.count else None) or None,
        sl=risk.sl or None,
        tp=risk.tp or None,
        bullish_pct=float(req.structure.bullish_pct or 0),
        bearish_pct=float(req.structure.bearish_pct or 0),
        neutral_pct=float(req.structure.neutral_pct or 0),
        bias_lookback=int(req.structure.bias_lookback or 20),
        indicator_bullish_pct=float(req.structure.indicator_bullish_pct or 0),
        indicator_bearish_pct=float(req.structure.indicator_bearish_pct or 0),
    )
