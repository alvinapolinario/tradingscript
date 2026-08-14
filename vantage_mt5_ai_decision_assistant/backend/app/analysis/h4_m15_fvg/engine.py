"""H4 → M15 FVG setup engine — state machine orchestration."""
from __future__ import annotations

import copy

from app.analysis.h4_m15_fvg.types import (
    DEFAULT_H4_M15_CONFIG,
    H4M15FvgConfig,
    H4M15Setup,
    H4M15SetupState,
    RetraceMode,
    StateTransitionLog,
)
from app.analysis.ict.liquidity import build_liquidity_levels
from app.analysis.ict.sweep import detect_liquidity_sweep
from app.analysis.ict.types import IctConfig, LiquiditySweepEvent
from app.market_structure.fvg import apply_candle_mitigation, detect_fvgs, make_fvg_id
from app.market_structure.premium_discount import premium_discount
from app.market_structure.structure import detect_mss
from app.market_structure.swings import find_swings
from app.market_structure.types import Candle, FvgStatus, FvgZone

TERMINAL = {
    H4M15SetupState.SETUP_INVALIDATED,
    H4M15SetupState.SETUP_EXPIRED,
    H4M15SetupState.ENTRY_READY,
}

_EXEC_FVG_DIRECTION_MISMATCH = (
    "Execution FVG direction and structure confirmation do not match active HTF setup."
)


def _clear_stale_exec_fvg_rejection(setup: H4M15Setup) -> None:
    """Remove transient mismatch note once a valid execution FVG is linked."""
    if not setup.rejections:
        return
    setup.rejections = [r for r in setup.rejections if r != _EXEC_FVG_DIRECTION_MISMATCH]


def make_setup_id(symbol: str, htf_fvg: FvgZone) -> str:
    d = "B" if htf_fvg.direction == "BULLISH" else "S"
    return f"H4M15-{symbol.upper()}-{d}-{htf_fvg.created_time}"


def _cfg_as_ict(cfg: H4M15FvgConfig) -> IctConfig:
    return IctConfig(
        fvg_min_gap_atr=cfg.fvg_min_gap_atr,
        sweep_min_penetration_atr=cfg.sweep_min_penetration_atr,
        sweep_max_penetration_atr=cfg.sweep_max_penetration_atr,
        sweep_require_reentry=cfg.sweep_require_reentry,
        pivot_left=cfg.pivot_left,
        pivot_right=cfg.pivot_right,
        swing_min_atr=cfg.swing_min_atr,
        displacement_min_body_atr=cfg.min_body_ratio,
    )


class _GapCfg:
    def __init__(self, min_atr: float):
        self.fvg_min_gap_atr = min_atr
        self.ifvg_min_break_atr = 0.05
        self.ifvg_require_body_close = True


def displacement_metrics(candle: Candle, atr: float) -> tuple[float, float, float]:
    rng = candle.high - candle.low
    eps = 1e-9
    body_ratio = abs(candle.close - candle.open) / max(rng, eps)
    range_atr = rng / atr if atr else 0.0
    score = min(100.0, body_ratio * 50.0 + range_atr * 25.0)
    return body_ratio, range_atr, score


def displacement_ok(candle: Candle, atr: float, cfg: H4M15FvgConfig) -> tuple[bool, float]:
    body_ratio, range_atr, score = displacement_metrics(candle, atr)
    ok = body_ratio >= cfg.min_body_ratio and range_atr >= cfg.min_range_atr_ratio
    return ok, score


def price_in_zone(candle: Candle, zone: FvgZone) -> bool:
    return candle.low <= zone.upper and candle.high >= zone.lower


def htf_touch_detected(setup: H4M15Setup, candle: Candle) -> bool:
    z = setup.htf_fvg
    if setup.direction == "BULLISH":
        return candle.low <= z.upper
    return candle.high >= z.lower


def select_execution_fvg(
    fvgs: list[FvgZone],
    setup: H4M15Setup,
    cfg: H4M15FvgConfig,
) -> FvgZone | None:
    if not setup.htf_first_touch_time:
        return None
    t_sweep = setup.sweep.sweep_time if setup.sweep else 0
    t_disp = setup.displacement_time
    t_mss = setup.mss_time
    window = cfg.causal_window_m15_bars * 900
    min_time = setup.htf_first_touch_time
    if t_sweep:
        min_time = max(min_time, t_sweep)
    if t_disp:
        min_time = max(min_time, t_disp)
    mss_floor = max(0, t_mss - window) if t_mss else min_time

    candidates: list[FvgZone] = []
    for f in fvgs:
        if f.direction != setup.direction:
            continue
        if f.created_time < setup.htf_first_touch_time:
            continue
        if t_sweep and f.created_time < t_sweep:
            continue
        if t_disp and f.created_time < t_disp:
            continue
        if t_mss and f.created_time < mss_floor:
            continue
        candidates.append(f)
    return candidates[-1] if candidates else None


def grade_score(score: float) -> str:
    if score >= 85:
        return "A_PLUS"
    if score >= 75:
        return "HIGH"
    if score >= 65:
        return "GOOD"
    if score >= 50:
        return "MODERATE"
    return "LOW"


def _session_score_from_time(broker_time_unix: int) -> float:
    from app.analysis.ict.session import get_session_context

    sess = get_session_context(broker_time_unix, [], IctConfig())
    return 70.0 if sess["session"] in ("LONDON", "NEW_YORK") else 40.0


def score_setup(
    setup: H4M15Setup,
    cfg: H4M15FvgConfig,
    *,
    broker_time_unix: int | None = None,
) -> tuple[float, str]:
    s = 0.0
    if setup.bias_alignment:
        s += cfg.weight_htf_structure
    elif setup.htf_bias != "NEUTRAL":
        s += cfg.weight_htf_structure * 0.25
    gap_q = min(1.0, setup.htf_fvg.gap_atr / 0.5)
    s += cfg.weight_h4_fvg_quality * gap_q
    if setup.direction == "BULLISH" and "DISCOUNT" in setup.pd_location:
        s += cfg.weight_h4_location
    elif setup.direction == "BEARISH" and "PREMIUM" in setup.pd_location:
        s += cfg.weight_h4_location
    else:
        s += cfg.weight_h4_location * 0.3
    if setup.sweep and setup.sweep.detected:
        s += cfg.weight_liquidity_sweep * min(1.0, setup.sweep.quality_score / 100.0)
    if setup.displacement_score >= cfg.displacement_min_score:
        s += cfg.weight_displacement * min(1.0, setup.displacement_score / 100.0)
    if setup.mss_time:
        s += cfg.weight_mss
    if setup.entry_fvg:
        s += cfg.weight_entry_fvg * min(1.0, setup.entry_fvg.gap_atr / 0.3)
    if setup.state == H4M15SetupState.ENTRY_READY:
        s += cfg.weight_retrace
    ts = broker_time_unix or setup.entry_ready_time
    if ts and ts > 0:
        session_score = _session_score_from_time(ts)
        s += min(cfg.weight_session, cfg.weight_session * (session_score / 100.0))
    total = round(min(100.0, s), 1)
    return total, grade_score(total)


class H4M15Engine:
    def __init__(self, cfg: H4M15FvgConfig | None = None):
        self.cfg = cfg or DEFAULT_H4_M15_CONFIG
        self.setups: dict[str, H4M15Setup] = {}
        self.known_htf_ids: set[str] = set()

    def _transition(
        self,
        setup: H4M15Setup,
        new_state: H4M15SetupState,
        reason: str,
        *,
        event_id: str = "",
        candle_time: int = 0,
    ) -> None:
        if setup.state == new_state:
            return
        old = setup.state
        setup.state = new_state
        setup.updated_time = candle_time or setup.updated_time
        setup.transition_log.append(
            StateTransitionLog(
                timestamp=candle_time or setup.updated_time,
                setup_id=setup.setup_id,
                symbol=setup.symbol,
                old_state=old.value,
                new_state=new_state.value,
                reason=reason,
                related_event_id=event_id,
            )
        )
        setup.reasons.append(reason)

    def bootstrap_h4(self, symbol: str, h4_candles: list[Candle], atr_h4: float) -> None:
        if len(h4_candles) < 3:
            return
        cfg = self.cfg
        gap_cfg = _GapCfg(cfg.min_h4_fvg_atr)
        fvgs = detect_fvgs(
            h4_candles,
            timeframe=cfg.htf_timeframe,
            atr=atr_h4,
            cfg=gap_cfg,
            symbol=symbol,
        )
        for f in fvgs:
            if f.gap_atr < cfg.min_h4_fvg_atr:
                continue
            if f.fvg_id in self.known_htf_ids:
                continue
            self.known_htf_ids.add(f.fvg_id)
            sid = make_setup_id(symbol, f)
            if sid in self.setups:
                continue
            setup = H4M15Setup(
                setup_id=sid,
                symbol=symbol.upper(),
                direction=f.direction,
                state=H4M15SetupState.WAITING_FOR_HTF_MITIGATION,
                htf_fvg=copy.deepcopy(f),
                created_time=f.created_time,
                updated_time=f.created_time,
            )
            self.setups[sid] = setup
            self._transition(
                setup,
                H4M15SetupState.HTF_FVG_FOUND,
                f"H4 {f.direction} FVG detected {f.lower:.5f}–{f.upper:.5f} ({f.gap_atr:.2f} ATR).",
                event_id=f.fvg_id,
                candle_time=f.created_time,
            )
            self._transition(
                setup,
                H4M15SetupState.WAITING_FOR_HTF_MITIGATION,
                "Waiting for price to mitigate H4 FVG.",
                event_id=f.fvg_id,
                candle_time=f.created_time,
            )

    def process_m15_bar(
        self,
        candle: Candle,
        m15_history: list[Candle],
        atr_m15: float,
        *,
        htf_bias: str = "NEUTRAL",
        dealing_high: float = 0.0,
        dealing_low: float = 0.0,
    ) -> None:
        idx = len(m15_history) - 1
        ict_cfg = _cfg_as_ict(self.cfg)
        gap_cfg_m15 = _GapCfg(self.cfg.min_m15_fvg_atr)

        for setup in list(self.setups.values()):
            if setup.state in TERMINAL:
                continue

            setup.updated_time = candle.time
            z = setup.htf_fvg
            apply_candle_mitigation(
                z,
                candle,
                invalidate_on_close_break=self.cfg.invalidate_htf_on_close_break,
            )

            if z.status == FvgStatus.INVALIDATED and setup.state not in TERMINAL:
                setup.invalidation_reason = "H4 FVG invalidated by close beyond zone."
                self._transition(
                    setup,
                    H4M15SetupState.SETUP_INVALIDATED,
                    setup.invalidation_reason,
                    candle_time=candle.time,
                )
                continue

            if setup.state in (
                H4M15SetupState.WAITING_FOR_HTF_MITIGATION,
                H4M15SetupState.HTF_FVG_FOUND,
            ):
                if htf_touch_detected(setup, candle):
                    setup.htf_first_touch_time = candle.time
                    setup.htf_touch_bar_index = idx
                    setup.m15_bars_since_touch = 0
                    if dealing_high > dealing_low:
                        setup.pd_location = premium_discount(dealing_high, dealing_low, candle.close)
                        setup.pd_position = (candle.close - dealing_low) / (dealing_high - dealing_low)
                    setup.htf_bias = htf_bias
                    setup.bias_alignment = htf_bias in ("NEUTRAL", setup.direction)
                    self._transition(
                        setup,
                        H4M15SetupState.HTF_FVG_TOUCHED,
                        f"Price entered H4 FVG at {candle.close:.5f}. Mitigation {z.mitigation_pct:.0f}%.",
                        event_id=z.fvg_id,
                        candle_time=candle.time,
                    )
                    self._transition(
                        setup,
                        H4M15SetupState.WAITING_FOR_LIQUIDITY_SWEEP,
                        "Monitoring M15 for liquidity sweep after H4 touch.",
                        candle_time=candle.time,
                    )

            if setup.state in TERMINAL or not setup.htf_first_touch_time:
                continue

            if candle.time < setup.htf_first_touch_time:
                continue

            setup.m15_bars_since_touch += 1

            if setup.state in (
                H4M15SetupState.WAITING_FOR_LIQUIDITY_SWEEP,
                H4M15SetupState.HTF_FVG_TOUCHED,
            ):
                bsl, ssl, _pd = build_liquidity_levels(m15_history, atr_m15, ict_cfg)
                sweep = detect_liquidity_sweep(
                    m15_history,
                    bsl_levels=bsl,
                    ssl_levels=ssl,
                    atr_val=atr_m15,
                    cfg=ict_cfg,
                    after_time=setup.htf_first_touch_time,
                )
                want = "BULLISH" if setup.direction == "BULLISH" else "BEARISH"
                if sweep and sweep.detected and sweep.trade_bias == want and sweep.sweep_time >= setup.htf_first_touch_time:
                    setup.sweep = sweep
                    self._transition(
                        setup,
                        H4M15SetupState.LIQUIDITY_SWEPT,
                        f"{sweep.sweep_type} liquidity swept at {sweep.sweep_price:.5f}.",
                        event_id=f"SWEEP-{sweep.sweep_time}",
                        candle_time=sweep.sweep_time,
                    )
                    self._transition(
                        setup,
                        H4M15SetupState.WAITING_FOR_DISPLACEMENT,
                        "Waiting for directional displacement.",
                        candle_time=candle.time,
                    )

            if setup.state == H4M15SetupState.WAITING_FOR_DISPLACEMENT and setup.sweep:
                post = [c for c in m15_history if c.time >= setup.sweep.sweep_time]
                for c in post:
                    if c.time > candle.time:
                        break
                    ok, score = displacement_ok(c, atr_m15, self.cfg)
                    if ok and (
                        (setup.direction == "BULLISH" and c.close > c.open)
                        or (setup.direction == "BEARISH" and c.close < c.open)
                    ):
                        setup.displacement_time = c.time
                        setup.displacement_score = score
                        setup.displacement_event_id = f"DISP-{c.time}"
                        self._transition(
                            setup,
                            H4M15SetupState.DISPLACEMENT_CONFIRMED,
                            f"Displacement confirmed (score {score:.0f}).",
                            event_id=setup.displacement_event_id,
                            candle_time=c.time,
                        )
                        self._transition(
                            setup,
                            H4M15SetupState.WAITING_FOR_MSS,
                            "Waiting for M15 MSS/BOS.",
                            candle_time=c.time,
                        )
                        break

            if setup.state in (H4M15SetupState.WAITING_FOR_MSS, H4M15SetupState.DISPLACEMENT_CONFIRMED):
                swings = find_swings(
                    m15_history,
                    self.cfg.pivot_left,
                    self.cfg.pivot_right,
                    atr_m15,
                    self.cfg.swing_min_atr,
                )
                mss = detect_mss(m15_history, swings, setup.direction, atr_m15, ict_cfg)
                if mss and mss.get("shift_detected") and candle.time >= setup.htf_first_touch_time:
                    if setup.displacement_time and candle.time >= setup.displacement_time:
                        setup.mss_time = candle.time
                        setup.mss_price = float(mss.get("broken_level") or candle.close)
                        setup.mss_swing_id = f"MSS-{candle.time}"
                        setup.m15_bars_since_mss = 0
                        self._transition(
                            setup,
                            H4M15SetupState.MSS_CONFIRMED,
                            f"M15 {setup.direction} MSS confirmed above/below {setup.mss_price:.5f}.",
                            event_id=setup.mss_swing_id,
                            candle_time=candle.time,
                        )
                        self._transition(
                            setup,
                            H4M15SetupState.WAITING_FOR_LTF_FVG,
                            "Searching for new directional M15 execution FVG.",
                            candle_time=candle.time,
                        )

            if setup.state in (
                H4M15SetupState.WAITING_FOR_LTF_FVG,
                H4M15SetupState.MSS_CONFIRMED,
            ) and setup.mss_time:
                fvgs = detect_fvgs(
                    m15_history,
                    timeframe=self.cfg.execution_timeframe,
                    atr=atr_m15,
                    cfg=gap_cfg_m15,
                    symbol=setup.symbol,
                )
                entry = select_execution_fvg(fvgs, setup, self.cfg)
                if entry:
                    entry = copy.deepcopy(entry)
                    entry.parent_fvg_id = setup.htf_fvg.fvg_id
                    setup.entry_fvg = entry
                    _clear_stale_exec_fvg_rejection(setup)
                    setup.m15_bars_since_ltf_fvg = 0
                    self._transition(
                        setup,
                        H4M15SetupState.LTF_FVG_CREATED,
                        f"M15 execution FVG {entry.lower:.5f}–{entry.upper:.5f} linked to setup.",
                        event_id=entry.fvg_id,
                        candle_time=entry.created_time,
                    )
                    self._transition(
                        setup,
                        H4M15SetupState.WAITING_FOR_RETRACE,
                        "Waiting for retrace into M15 execution FVG.",
                        candle_time=candle.time,
                    )
                elif setup.state == H4M15SetupState.WAITING_FOR_LTF_FVG:
                    wrong = [f for f in fvgs if f.created_time >= setup.htf_first_touch_time and f.direction != setup.direction]
                    if wrong and _EXEC_FVG_DIRECTION_MISMATCH not in setup.rejections:
                        setup.rejections.append(_EXEC_FVG_DIRECTION_MISMATCH)

            if setup.state == H4M15SetupState.WAITING_FOR_RETRACE and setup.entry_fvg:
                setup.m15_bars_since_ltf_fvg += 1
                ef = setup.entry_fvg
                in_zone = price_in_zone(candle, ef)
                retrace_ok = False
                if self.cfg.retrace_mode == RetraceMode.TOUCH:
                    retrace_ok = in_zone
                elif self.cfg.retrace_mode == RetraceMode.MIDPOINT:
                    retrace_ok = (
                        ef.lower <= candle.close <= ef.upper
                        and (
                            (setup.direction == "BULLISH" and candle.close <= ef.midpoint)
                            or (setup.direction == "BEARISH" and candle.close >= ef.midpoint)
                        )
                    )
                if retrace_ok and not setup.entry_ready_emitted:
                    setup.entry_price = candle.close
                    setup.entry_ready_time = candle.time
                    if setup.sweep:
                        if setup.direction == "BULLISH":
                            setup.structural_stop = setup.sweep.sweep_price - self.cfg.sl_buffer_atr * atr_m15
                        else:
                            setup.structural_stop = setup.sweep.sweep_price + self.cfg.sl_buffer_atr * atr_m15
                    setup.setup_score, setup.setup_grade = score_setup(
                        setup, self.cfg, broker_time_unix=candle.time
                    )
                    setup.entry_ready_emitted = True
                    self._transition(
                        setup,
                        H4M15SetupState.ENTRY_READY,
                        f"Retrace into M15 FVG — ENTRY_READY (score {setup.setup_score:.0f}).",
                        event_id=ef.fvg_id,
                        candle_time=candle.time,
                    )

            self._check_invalidation(setup, candle, atr_m15)
            self._check_expiration(setup, candle)

    def _check_invalidation(self, setup: H4M15Setup, candle: Candle, atr_m15: float) -> None:
        if setup.state in TERMINAL or not setup.sweep:
            return
        buf = self.cfg.sl_buffer_atr * atr_m15
        if setup.direction == "BULLISH" and candle.close < setup.sweep.sweep_price - buf:
            setup.invalidation_reason = f"Close below liquidity sweep low ({setup.sweep.sweep_price:.5f})."
            self._transition(
                setup,
                H4M15SetupState.SETUP_INVALIDATED,
                setup.invalidation_reason,
                candle_time=candle.time,
            )
        elif setup.direction == "BEARISH" and candle.close > setup.sweep.sweep_price + buf:
            setup.invalidation_reason = f"Close above liquidity sweep high ({setup.sweep.sweep_price:.5f})."
            self._transition(
                setup,
                H4M15SetupState.SETUP_INVALIDATED,
                setup.invalidation_reason,
                candle_time=candle.time,
            )

    def _check_expiration(self, setup: H4M15Setup, candle: Candle) -> None:
        if setup.state in TERMINAL:
            return
        if setup.htf_first_touch_time and setup.m15_bars_since_touch > self.cfg.max_confirmation_m15_bars:
            setup.expiration_reason = f"Exceeded {self.cfg.max_confirmation_m15_bars} M15 bars since H4 touch."
            self._transition(
                setup,
                H4M15SetupState.SETUP_EXPIRED,
                setup.expiration_reason,
                candle_time=candle.time,
            )
        elif setup.entry_fvg and setup.m15_bars_since_ltf_fvg > self.cfg.max_retrace_m15_bars:
            setup.expiration_reason = f"Exceeded {self.cfg.max_retrace_m15_bars} M15 bars waiting for retrace."
            self._transition(
                setup,
                H4M15SetupState.SETUP_EXPIRED,
                setup.expiration_reason,
                candle_time=candle.time,
            )

    def active_setups(self) -> list[H4M15Setup]:
        return [s for s in self.setups.values() if s.state not in TERMINAL]

    def all_setups(self) -> list[H4M15Setup]:
        return list(self.setups.values())
