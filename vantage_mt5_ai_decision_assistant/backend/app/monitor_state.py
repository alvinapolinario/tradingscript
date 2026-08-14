"""In-memory monitoring state for the web dashboard."""
from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from threading import Lock
from typing import Any


# Always offered in the monitor pair selector (plus any other live EA symbols).
DEFAULT_MONITOR_PAIRS = ("XAUUSD", "EURUSD", "USDJPY", "BTCUSD")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _norm_symbol(symbol: str | None) -> str:
    s = (symbol or "").strip().upper()
    return s or "UNKNOWN"


def _canonical_monitor_symbol(symbol: str | None) -> str:
    """Map broker symbols (XAUUSD+, GOLD.pro, BTCUSDm) to monitor pair keys."""
    from app.analysis.desk_symbol_validator import is_approved_desk_symbol
    from app.analysis.gold_symbol_validator import is_approved_gold_symbol

    u = _norm_symbol(symbol)
    if u == "UNKNOWN":
        return u

    ok, base = is_approved_gold_symbol(u)
    if ok:
        # UI pair selector uses XAUUSD for all gold aliases.
        return "XAUUSD" if base in ("XAUUSD", "GOLD") else base

    desk_ok, desk_base = is_approved_desk_symbol(u)
    if desk_ok:
        return "XAUUSD" if desk_base in ("XAUUSD", "GOLD") else desk_base

    core = u
    for suffix in ("+", ".", "M", "I"):
        if core.endswith(suffix) and len(core) > len(suffix) + 2:
            core = core[: -len(suffix)]

    if core in DEFAULT_MONITOR_PAIRS:
        return core
    if core.startswith("BTC"):
        return "BTCUSD"
    if core.startswith("XAU"):
        return "XAUUSD"
    return core


@dataclass
class LogEntry:
    ts: str
    level: str
    source: str
    message: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class EaSnapshot:
    connected: bool = False
    last_seen_utc: datetime | None = None
    company: str = ""
    server: str = ""
    account_masked: str = ""
    margin_mode: str = ""
    currency: str = ""
    symbol: str = ""
    broker_symbol: str = ""
    digits: int = 0
    contract_size: float = 0.0
    stops_level: int = 0
    bid: float = 0.0
    ask: float = 0.0
    spread_points: int = 0
    high_spread: bool = False
    action: str = ""
    trend: str = ""
    market_state: str = ""
    bullish_pct: float = 0.0
    bearish_pct: float = 0.0
    neutral_pct: float = 0.0
    bias_lookback: int = 20
    indicator_bullish_pct: float = 0.0
    indicator_bearish_pct: float = 0.0
    candle_status: str = ""
    backend_status: str = ""
    position_count: int = 0
    total_buy_volume: float = 0.0
    total_sell_volume: float = 0.0
    pending_order_count: int = 0
    pending_orders: dict | None = None
    pending_orders_supported: bool = False
    floating_pl: float = 0.0
    equity: float = 0.0
    balance: float = 0.0
    floating_pl_pct_of_equity: float = 0.0
    float_profit_target_pct: float = 10.0
    float_profit_target_hit: bool = False
    nearest_support: str = ""
    nearest_resistance: str = ""
    note: str = ""
    ea_version: str = ""
    terminal_connected: bool = False
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
    risk_warning: str = ""
    recovery_level_1: str = ""
    recovery_level_2: str = ""
    bullish_confirmation: str = ""
    technical_invalidation: str = ""
    immediate_support: str = ""
    level_source: str = ""
    pl_calendar: dict | None = None
    trade_stats: dict | None = None
    server_year: int = 0
    server_month: int = 0
    strategy: dict | None = None
    pullback: dict | None = None
    pullback_supported: bool = False
    pullback_v2: dict | None = None
    pullback_v2_supported: bool = False
    gold_smc: dict | None = None
    gold_smc_supported: bool = False
    liquidity_grab: dict | None = None
    liquidity_grab_supported: bool = False
    breakout_structure: dict | None = None
    breakout_structure_supported: bool = False
    market_state_engine: dict | None = None
    market_state_engine_supported: bool = False
    swing_strategy: dict | None = None
    swing_strategy_supported: bool = False
    amd_ifvg: dict | None = None
    amd_ifvg_supported: bool = False
    box_theory: dict | None = None
    box_theory_supported: bool = False
    box_python_engine: bool = False
    ict: dict | None = None
    ict_supported: bool = False
    ict_python_engine: bool = False
    h4_m15_fvg: dict | None = None
    h4_m15_fvg_supported: bool = False
    max_position_risk_pct: float | None = None


def _apply_heartbeat_fields(ea: EaSnapshot, payload: dict[str, Any]) -> None:
    ea.connected = True
    ea.company = str(payload.get("company", ea.company))
    ea.server = str(payload.get("server", ea.server))
    ea.account_masked = str(payload.get("account_login_masked", ea.account_masked))
    ea.margin_mode = str(payload.get("margin_mode", ea.margin_mode))
    ea.currency = str(payload.get("currency", ea.currency))
    raw = str(payload.get("broker_symbol") or payload.get("symbol", ea.symbol) or ea.symbol)
    ea.broker_symbol = _norm_symbol(raw)
    ea.symbol = str(payload.get("symbol", ea.symbol) or ea.symbol)
    ea.digits = int(payload.get("digits", ea.digits) or 0)
    ea.contract_size = float(payload.get("contract_size", ea.contract_size) or 0)
    ea.stops_level = int(payload.get("stops_level", ea.stops_level) or 0)
    ea.bid = float(payload.get("bid", ea.bid) or 0)
    ea.ask = float(payload.get("ask", ea.ask) or 0)
    ea.spread_points = int(payload.get("spread_points", ea.spread_points) or 0)
    ea.high_spread = bool(payload.get("high_spread", ea.high_spread))
    ea.action = str(payload.get("action", ea.action))
    ea.trend = str(payload.get("trend", ea.trend))
    ea.market_state = str(payload.get("market_state", ea.market_state))
    ea.bullish_pct = float(payload.get("bullish_pct", ea.bullish_pct) or 0)
    ea.bearish_pct = float(payload.get("bearish_pct", ea.bearish_pct) or 0)
    ea.neutral_pct = float(payload.get("neutral_pct", ea.neutral_pct) or 0)
    ea.bias_lookback = int(payload.get("bias_lookback", ea.bias_lookback) or 20)
    ea.indicator_bullish_pct = float(
        payload.get("indicator_bullish_pct", ea.indicator_bullish_pct) or 0
    )
    ea.indicator_bearish_pct = float(
        payload.get("indicator_bearish_pct", ea.indicator_bearish_pct) or 0
    )
    ea.candle_status = str(payload.get("candle_status", ea.candle_status))
    ea.backend_status = str(payload.get("backend_status", "OK"))
    ea.position_count = int(payload.get("position_count", ea.position_count) or 0)
    if payload.get("total_buy_volume") is not None:
        ea.total_buy_volume = float(payload.get("total_buy_volume") or 0)
    if payload.get("total_sell_volume") is not None:
        ea.total_sell_volume = float(payload.get("total_sell_volume") or 0)
    if isinstance(payload.get("pending_orders"), dict):
        po = payload["pending_orders"]
        items = po.get("items") if isinstance(po.get("items"), list) else []
        ea.pending_orders = {
            "count": int(po.get("count") or len(items)),
            "scope": po.get("scope") or "account",
            "items": items,
        }
        ea.pending_order_count = int(ea.pending_orders["count"])
        ea.pending_orders_supported = True
    elif payload.get("pending_order_count") is not None:
        ea.pending_order_count = int(payload.get("pending_order_count") or 0)
        ea.pending_orders_supported = True
    if payload.get("max_position_risk_pct") is not None:
        try:
            ea.max_position_risk_pct = float(payload["max_position_risk_pct"])
        except (TypeError, ValueError):
            pass
    ea.floating_pl = float(payload.get("floating_pl", ea.floating_pl) or 0)
    ea.equity = float(payload.get("equity", ea.equity) or 0)
    ea.balance = float(payload.get("balance", ea.balance) or 0)
    ea.floating_pl_pct_of_equity = float(
        payload.get("floating_pl_pct_of_equity", ea.floating_pl_pct_of_equity) or 0
    )
    ea.float_profit_target_pct = float(
        payload.get("float_profit_target_pct", ea.float_profit_target_pct) or 10.0
    )
    ea.float_profit_target_hit = bool(
        payload.get("float_profit_target_hit", ea.float_profit_target_hit)
    )
    if ea.equity > 0 and "floating_pl_pct_of_equity" not in payload:
        ea.floating_pl_pct_of_equity = (ea.floating_pl / ea.equity) * 100.0
    if ea.equity > 0 and ea.floating_pl_pct_of_equity >= ea.float_profit_target_pct > 0:
        ea.float_profit_target_hit = True
    ea.nearest_support = str(payload.get("nearest_support", ea.nearest_support))
    ea.nearest_resistance = str(payload.get("nearest_resistance", ea.nearest_resistance))
    ea.note = str(payload.get("note", ea.note))
    ea.ea_version = str(payload.get("ea_version", ea.ea_version))
    ea.terminal_connected = bool(payload.get("terminal_connected", True))
    ea.new_entry_decision = str(payload.get("new_entry_decision", ea.new_entry_decision))
    ea.existing_position_decision = str(
        payload.get("existing_position_decision", ea.existing_position_decision)
    )
    ea.risk_status = str(payload.get("risk_status", ea.risk_status))
    ea.equity_risk_pct = float(payload.get("equity_risk_pct", ea.equity_risk_pct) or 0)
    ea.estimated_sl_loss = float(payload.get("estimated_sl_loss", ea.estimated_sl_loss) or 0)
    ea.entry = float(payload.get("entry", ea.entry) or 0)
    ea.sl = float(payload.get("sl", ea.sl) or 0)
    ea.new_position_allowed = bool(payload.get("new_position_allowed", ea.new_position_allowed))
    ea.add_position_allowed = bool(payload.get("add_position_allowed", ea.add_position_allowed))
    ea.exceeds_max_position_risk = bool(
        payload.get("exceeds_max_position_risk", ea.exceeds_max_position_risk)
    )
    ea.risk_warning = str(payload.get("risk_warning", ea.risk_warning))
    ea.recovery_level_1 = str(payload.get("recovery_level_1", ea.recovery_level_1))
    ea.recovery_level_2 = str(payload.get("recovery_level_2", ea.recovery_level_2))
    ea.bullish_confirmation = str(payload.get("bullish_confirmation", ea.bullish_confirmation))
    ea.technical_invalidation = str(
        payload.get("technical_invalidation", ea.technical_invalidation)
    )
    ea.immediate_support = str(payload.get("immediate_support", ea.immediate_support))
    ea.level_source = str(payload.get("level_source", ea.level_source))
    if ea.immediate_support and not ea.nearest_support:
        ea.nearest_support = ea.immediate_support
    if isinstance(payload.get("trade_stats"), dict):
        ea.trade_stats = payload["trade_stats"]
    ea.server_year = int(payload.get("server_year", ea.server_year) or 0)
    ea.server_month = int(payload.get("server_month", ea.server_month) or 0)
    if isinstance(payload.get("strategy"), dict):
        ea.strategy = payload["strategy"]
    elif isinstance(payload.get("m5_desk"), dict):
        ea.strategy = payload["m5_desk"]
    if isinstance(payload.get("pullback"), dict):
        ea.pullback = payload["pullback"]
        ea.pullback_supported = True
    if isinstance(payload.get("pullback_v2"), dict):
        ea.pullback_v2 = payload["pullback_v2"]
        ea.pullback_v2_supported = True
    if isinstance(payload.get("gold_smc"), dict):
        ea.gold_smc = payload["gold_smc"]
        ea.gold_smc_supported = True
    if isinstance(payload.get("liquidity_grab"), dict):
        ea.liquidity_grab = payload["liquidity_grab"]
        ea.liquidity_grab_supported = True
    if isinstance(payload.get("breakout_structure"), dict):
        ea.breakout_structure = payload["breakout_structure"]
        ea.breakout_structure_supported = True
    if isinstance(payload.get("market_state_engine"), dict):
        ea.market_state_engine = payload["market_state_engine"]
        ea.market_state_engine_supported = True
    if isinstance(payload.get("swing_strategy"), dict):
        ea.swing_strategy = payload["swing_strategy"]
        ea.swing_strategy_supported = True
    if isinstance(payload.get("amd_ifvg"), dict):
        ea.amd_ifvg = payload["amd_ifvg"]
        ea.amd_ifvg_supported = True
    if isinstance(payload.get("box_theory"), dict):
        ea.box_theory = payload["box_theory"]
        ea.box_theory_supported = True
    if isinstance(payload.get("ict"), dict):
        ea.ict = payload["ict"]
        ea.ict_supported = True
    if isinstance(payload.get("h4_m15_fvg"), dict):
        ea.h4_m15_fvg = payload["h4_m15_fvg"]
        ea.h4_m15_fvg_supported = True


class MonitorStore:
    def __init__(self, max_logs: int = 300, connected_within_sec: int = 45) -> None:
        self._lock = Lock()
        self._logs: deque[LogEntry] = deque(maxlen=max_logs)
        self._eas: dict[str, EaSnapshot] = {}
        self._selected_symbol: str = DEFAULT_MONITOR_PAIRS[0]
        self._started_utc = _utc_now()
        self._analyze_count = 0
        self._heartbeat_count = 0
        self._last_analyze_utc: datetime | None = None
        self._last_action: str = ""
        self._last_analyze_summary: dict[str, Any] = {}
        self._connected_within_sec = connected_within_sec
        self._cal_req_year: int = 0
        self._cal_req_month: int = 0
        # Analyzer STANDARD | SCALPING — used when persisting accepted signals
        self._analyzer_mode: str = "STANDARD"
        # Strategy Lab session overrides (affect gate evaluation on this host)
        self._lab_overrides: dict[str, Any] = {}
        # symbol -> "YYYY-MM" -> calendar payload
        self._calendar_cache: dict[str, dict[str, dict[str, Any]]] = {}
        for sym in DEFAULT_MONITOR_PAIRS:
            self._eas[sym] = EaSnapshot(symbol=sym)
        self.add_log("INFO", "backend", "Monitor store initialized")

    def set_analyzer_mode(self, mode: str) -> str:
        m = "SCALPING" if str(mode).upper() == "SCALPING" else "STANDARD"
        with self._lock:
            self._analyzer_mode = m
            out = self._analyzer_mode
        return out

    def analyzer_mode(self) -> str:
        with self._lock:
            return self._analyzer_mode

    def lab_overrides(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._lab_overrides)

    def set_lab_overrides(self, overrides: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._lab_overrides = dict(overrides or {})
            out = dict(self._lab_overrides)
        return out

    def clear_lab_overrides(self) -> None:
        with self._lock:
            self._lab_overrides = {}

    def pair_statuses(self) -> list[dict[str, Any]]:
        """Lightweight per-symbol status blobs for Strategy Scanner."""
        now = _utc_now()
        with self._lock:
            out: list[dict[str, Any]] = []
            for name in list(DEFAULT_MONITOR_PAIRS) + [
                k for k in sorted(self._eas.keys()) if k not in DEFAULT_MONITOR_PAIRS and k != "UNKNOWN"
            ]:
                ea = self._eas.get(name) or EaSnapshot(symbol=name)
                connected, age = self._ea_connected(ea, now)
                empty_cal_req = {"year": 0, "month": 0, "cached_months": [], "pending": False}
                payload = self._serialize_ea(
                    ea, now, display_cal=None, calendar_request=empty_cal_req
                )
                out.append(
                    {
                        "selected_symbol": name,
                        "symbol": name,
                        "available_symbols": [name],
                        "vantage_ea": payload,
                        "link_health": {
                            "api_online": True,
                            "ea_online": connected,
                            "any_ea_online": connected,
                            "overall": "CONNECTED" if connected else "WAITING_FOR_EA",
                            "seconds_since_heartbeat": age,
                        },
                    }
                )
            return out

    def _get_or_create(self, symbol: str) -> EaSnapshot:
        key = _canonical_monitor_symbol(symbol)
        if key not in self._eas:
            self._eas[key] = EaSnapshot(symbol=key)
        return self._eas[key]

    def _selected_ea(self) -> EaSnapshot:
        return self._get_or_create(self._selected_symbol)

    def add_log(self, level: str, source: str, message: str, **data: Any) -> None:
        entry = LogEntry(
            ts=_utc_now().isoformat(),
            level=level.upper(),
            source=source,
            message=message,
            data=data or {},
        )
        with self._lock:
            self._logs.appendleft(entry)

    def select_symbol(self, symbol: str) -> dict[str, Any]:
        key = _canonical_monitor_symbol(symbol)
        with self._lock:
            self._get_or_create(key)
            self._selected_symbol = key
            selected = self._selected_symbol
        return {"selected_symbol": selected, "ok": True}

    def record_heartbeat(self, payload: dict[str, Any]) -> None:
        now = _utc_now()
        raw_sym = _norm_symbol(str(payload.get("symbol", "")))
        sym = _canonical_monitor_symbol(raw_sym)
        hp = {**payload, "symbol": sym, "broker_symbol": raw_sym}
        box_err: str | None = None
        box_blob: dict[str, Any] | None = None
        h4_err: str | None = None
        ict_err: str | None = None
        h4_blob: dict[str, Any] | None = None
        ict_blob: dict[str, Any] | None = None

        # Run Python engines outside the store lock — analyze may call monitor_store.add_log.
        if isinstance(payload.get("h4_m15_fvg_candles"), dict):
            try:
                from app.analysis.h4_m15_fvg.heartbeat import process_h4_m15_fvg_heartbeat

                result = process_h4_m15_fvg_heartbeat(hp)
                if isinstance(result, dict):
                    h4_blob = result
            except Exception as exc:
                h4_err = str(exc)

        if isinstance(payload.get("ict_candles"), dict):
            try:
                from app.analysis.ict.heartbeat import process_ict_heartbeat

                result = process_ict_heartbeat(hp)
                if isinstance(result, dict):
                    ict_blob = result
            except Exception as exc:
                ict_err = str(exc)

        if isinstance(payload.get("box_candles"), dict):
            try:
                from app.analysis.box_theory.heartbeat import process_box_heartbeat

                result = process_box_heartbeat(hp)
                if isinstance(result, dict):
                    box_blob = result
            except Exception as exc:
                box_err = str(exc)

        with self._lock:
            self._heartbeat_count += 1
            ea = self._get_or_create(sym)
            ea.last_seen_utc = now
            ea.symbol = sym
            _apply_heartbeat_fields(ea, hp)

            if h4_blob is not None:
                ea.h4_m15_fvg = h4_blob
                ea.h4_m15_fvg_supported = True
            if ict_blob is not None:
                ea.ict = ict_blob
                ea.ict_supported = True
                ea.ict_python_engine = True
            if box_blob is not None:
                ea.box_theory = box_blob
                ea.box_theory_supported = True
                ea.box_python_engine = True

            if isinstance(payload.get("pl_calendar"), dict):
                cal = payload["pl_calendar"]
                ea.pl_calendar = cal
                try:
                    key = f"{int(cal.get('year'))}-{int(cal.get('month')):02d}"
                    self._calendar_cache.setdefault(sym, {})[key] = cal
                except (TypeError, ValueError):
                    pass
                if self._cal_req_year <= 0 and cal.get("year") and cal.get("month"):
                    self._cal_req_year = int(cal["year"])
                    self._cal_req_month = int(cal["month"])

            # Auto-follow first live pair if current selection has never been seen
            sel = self._selected_ea()
            if sel.last_seen_utc is None and sym in DEFAULT_MONITOR_PAIRS:
                self._selected_symbol = sym
            elif sel.last_seen_utc is None and self._selected_symbol == DEFAULT_MONITOR_PAIRS[0]:
                # Keep XAUUSD as default until user picks; still store BTC/etc.
                pass

        if h4_err:
            self.add_log("WARN", "h4_m15_fvg", f"Heartbeat analyze failed: {h4_err}", symbol=sym)
        if ict_err:
            self.add_log("WARN", "ict", f"Heartbeat analyze failed: {ict_err}", symbol=sym)
        if box_err:
            self.add_log("WARN", "box_theory", f"Heartbeat analyze failed: {box_err}", symbol=sym)

        self.add_log(
            "WARN"
            if payload.get("exceeds_max_position_risk") or payload.get("risk_status") == "CRITICAL"
            else "INFO",
            "ea",
            f"Heartbeat {sym} new={payload.get('new_entry_decision', '?')} "
            f"pos={payload.get('existing_position_decision', '?')} risk={payload.get('risk_status', '?')}"
            f" pending={payload.get('pending_order_count', (payload.get('pending_orders') or {}).get('count', '?'))}",
            spread=payload.get("spread_points"),
            positions=payload.get("position_count"),
            equity_risk_pct=payload.get("equity_risk_pct"),
        )

    def update_pending_orders(self, symbol: str, pending_orders: dict[str, Any], **extra: Any) -> None:
        """Merge pending-order blob from analyze/heartbeat without a full heartbeat log."""
        sym = _canonical_monitor_symbol(symbol)
        with self._lock:
            ea = self._get_or_create(sym)
            items = pending_orders.get("items") if isinstance(pending_orders.get("items"), list) else []
            ea.pending_orders = {
                "count": int(pending_orders.get("count") or len(items)),
                "scope": pending_orders.get("scope") or "account",
                "items": items,
            }
            ea.pending_order_count = int(ea.pending_orders["count"])
            ea.pending_orders_supported = True
            if extra.get("total_buy_volume") is not None:
                ea.total_buy_volume = float(extra.get("total_buy_volume") or 0)
            if extra.get("total_sell_volume") is not None:
                ea.total_sell_volume = float(extra.get("total_sell_volume") or 0)
            if extra.get("max_position_risk_pct") is not None:
                try:
                    ea.max_position_risk_pct = float(extra["max_position_risk_pct"])
                except (TypeError, ValueError):
                    pass
            if extra.get("bid") is not None:
                ea.bid = float(extra.get("bid") or 0)
            if extra.get("ask") is not None:
                ea.ask = float(extra.get("ask") or 0)
            if extra.get("trend"):
                ea.trend = str(extra["trend"])
            if extra.get("position_count") is not None:
                ea.position_count = int(extra.get("position_count") or 0)

    def record_analyze(self, req_summary: dict[str, Any], action: str) -> None:
        now = _utc_now()
        sym = _canonical_monitor_symbol(str(req_summary.get("symbol", "")))
        with self._lock:
            self._analyze_count += 1
            self._last_analyze_utc = now
            self._last_action = action
            self._last_analyze_summary = req_summary
            ea = self._get_or_create(sym)
            if ea.last_seen_utc is None or ea.last_seen_utc < now:
                ea.last_seen_utc = now
                ea.connected = True
            ea.action = action
            ea.symbol = sym
            if req_summary.get("trend"):
                ea.trend = str(req_summary["trend"])
            if req_summary.get("new_entry_decision"):
                ea.new_entry_decision = str(req_summary["new_entry_decision"])
            if req_summary.get("existing_position_decision"):
                ea.existing_position_decision = str(req_summary["existing_position_decision"])
            if req_summary.get("risk_status"):
                ea.risk_status = str(req_summary["risk_status"])
            if req_summary.get("market_state"):
                ea.market_state = str(req_summary["market_state"])
        self.add_log("INFO", "analyze", f"Analyze → {action}", **req_summary)

    def _ea_connected(self, ea: EaSnapshot, now: datetime) -> tuple[bool, int | None]:
        age = None
        connected = False
        if ea.last_seen_utc is not None:
            age = int((now - ea.last_seen_utc).total_seconds())
            connected = age <= self._connected_within_sec
        return connected, age

    def _symbol_list(self, now: datetime) -> list[dict[str, Any]]:
        names = list(DEFAULT_MONITOR_PAIRS)
        for key in sorted(self._eas.keys()):
            if key not in names and key != "UNKNOWN":
                names.append(key)
        out: list[dict[str, Any]] = []
        for name in names:
            ea = self._eas.get(name) or EaSnapshot(symbol=name)
            connected, age = self._ea_connected(ea, now)
            out.append(
                {
                    "symbol": name,
                    "connected": connected,
                    "seconds_since_seen": age,
                    "last_seen_utc": _iso(ea.last_seen_utc),
                    "bid": ea.bid,
                    "action": ea.action,
                    "risk_status": ea.risk_status,
                }
            )
        return out

    def _serialize_ea(
        self,
        ea: EaSnapshot,
        now: datetime,
        *,
        display_cal: dict | None,
        calendar_request: dict[str, Any],
    ) -> dict[str, Any]:
        connected, age = self._ea_connected(ea, now)
        return {
            "connected": connected,
            "last_seen_utc": _iso(ea.last_seen_utc),
            "seconds_since_seen": age,
            "company": ea.company,
            "server": ea.server,
            "account_masked": ea.account_masked,
            "margin_mode": ea.margin_mode,
            "currency": ea.currency,
            "symbol": ea.symbol or self._selected_symbol,
            "broker_symbol": ea.broker_symbol or ea.symbol,
            "digits": ea.digits,
            "contract_size": ea.contract_size,
            "stops_level": ea.stops_level,
            "bid": ea.bid,
            "ask": ea.ask,
            "spread_points": ea.spread_points,
            "high_spread": ea.high_spread,
            "action": ea.action,
            "trend": ea.trend,
            "market_state": ea.market_state,
            "bullish_pct": ea.bullish_pct,
            "bearish_pct": ea.bearish_pct,
            "neutral_pct": ea.neutral_pct,
            "bias_lookback": ea.bias_lookback,
            "indicator_bullish_pct": ea.indicator_bullish_pct,
            "indicator_bearish_pct": ea.indicator_bearish_pct,
            "candle_status": ea.candle_status,
            "backend_status_reported": ea.backend_status,
            "position_count": ea.position_count,
            "total_buy_volume": ea.total_buy_volume,
            "total_sell_volume": ea.total_sell_volume,
            "pending_order_count": ea.pending_order_count,
            "pending_orders": ea.pending_orders
            or {"count": 0, "scope": "account", "items": []},
            "pending_orders_supported": ea.pending_orders_supported,
            "max_position_risk_pct": ea.max_position_risk_pct,
            "floating_pl": ea.floating_pl,
            "equity": ea.equity,
            "balance": ea.balance,
            "floating_pl_pct_of_equity": ea.floating_pl_pct_of_equity,
            "float_profit_target_pct": ea.float_profit_target_pct,
            "float_profit_target_hit": ea.float_profit_target_hit,
            "nearest_support": ea.nearest_support,
            "nearest_resistance": ea.nearest_resistance,
            "note": ea.note,
            "ea_version": ea.ea_version,
            "terminal_connected": ea.terminal_connected,
            "new_entry_decision": ea.new_entry_decision,
            "existing_position_decision": ea.existing_position_decision,
            "risk_status": ea.risk_status,
            "equity_risk_pct": ea.equity_risk_pct,
            "estimated_sl_loss": ea.estimated_sl_loss,
            "entry": ea.entry,
            "sl": ea.sl,
            "new_position_allowed": ea.new_position_allowed,
            "add_position_allowed": ea.add_position_allowed,
            "exceeds_max_position_risk": ea.exceeds_max_position_risk,
            "risk_warning": ea.risk_warning,
            "recovery_level_1": ea.recovery_level_1,
            "recovery_level_2": ea.recovery_level_2,
            "bullish_confirmation": ea.bullish_confirmation,
            "technical_invalidation": ea.technical_invalidation,
            "immediate_support": ea.immediate_support or ea.nearest_support,
            "level_source": ea.level_source,
            "pl_calendar": display_cal,
            "trade_stats": ea.trade_stats,
            "strategy": ea.strategy,
            "pullback": ea.pullback,
            "pullback_supported": ea.pullback_supported,
            "pullback_v2": ea.pullback_v2,
            "pullback_v2_supported": ea.pullback_v2_supported,
            "gold_smc": ea.gold_smc,
            "gold_smc_supported": ea.gold_smc_supported,
            "liquidity_grab": ea.liquidity_grab,
            "liquidity_grab_supported": ea.liquidity_grab_supported,
            "breakout_structure": ea.breakout_structure,
            "breakout_structure_supported": ea.breakout_structure_supported,
            "market_state_engine": ea.market_state_engine,
            "market_state_engine_supported": ea.market_state_engine_supported,
            "swing_strategy": ea.swing_strategy,
            "swing_strategy_supported": ea.swing_strategy_supported,
            "amd_ifvg": ea.amd_ifvg,
            "amd_ifvg_supported": ea.amd_ifvg_supported,
            "box_theory": ea.box_theory,
            "box_theory_supported": ea.box_theory_supported,
            "box_python_engine": ea.box_python_engine,
            "ict": ea.ict,
            "ict_supported": ea.ict_supported,
            "ict_python_engine": ea.ict_python_engine,
            "h4_m15_fvg": ea.h4_m15_fvg,
            "h4_m15_fvg_supported": ea.h4_m15_fvg_supported,
            "server_year": ea.server_year,
            "server_month": ea.server_month,
            "calendar_request": calendar_request,
        }

    def status(self) -> dict[str, Any]:
        now = _utc_now()
        with self._lock:
            ea = self._selected_ea()
            connected, age = self._ea_connected(ea, now)
            analyze_age = None
            if self._last_analyze_utc is not None:
                analyze_age = int((now - self._last_analyze_utc).total_seconds())

            sym = self._selected_symbol
            display_cal = ea.pl_calendar
            sym_cache = self._calendar_cache.get(sym, {})
            if self._cal_req_year > 0 and self._cal_req_month > 0:
                key = f"{self._cal_req_year}-{self._cal_req_month:02d}"
                if key in sym_cache:
                    display_cal = sym_cache[key]

            calendar_request = {
                "year": self._cal_req_year,
                "month": self._cal_req_month,
                "cached_months": sorted(sym_cache.keys()),
                "pending": (
                    self._cal_req_year > 0
                    and f"{self._cal_req_year}-{self._cal_req_month:02d}" not in sym_cache
                ),
            }

            any_online = any(self._ea_connected(e, now)[0] for e in self._eas.values())
            symbols = self._symbol_list(now)
            selected = self._selected_symbol

            result = {
                "backend": {
                    "status": "online",
                    "service": "Vantage MT5 AI Decision Assistant Backend",
                    "advisory_only": True,
                    "started_utc": _iso(self._started_utc),
                    "uptime_seconds": int((now - self._started_utc).total_seconds()),
                    "now_utc": _iso(now),
                },
                "selected_symbol": selected,
                "analyzer_mode": self._analyzer_mode,
                "lab_overrides": dict(self._lab_overrides),
                "available_symbols": [x["symbol"] for x in symbols],
                "symbols": symbols,
                "vantage_ea": self._serialize_ea(
                    ea, now, display_cal=display_cal, calendar_request=calendar_request
                ),
                "stats": {
                    "heartbeat_count": self._heartbeat_count,
                    "analyze_count": self._analyze_count,
                    "last_action": self._last_action,
                    "last_analyze_utc": _iso(self._last_analyze_utc),
                    "seconds_since_analyze": analyze_age,
                    "last_analyze_summary": deepcopy(self._last_analyze_summary),
                },
                "link_health": {
                    "api_online": True,
                    "ea_online": connected,
                    "any_ea_online": any_online,
                    "overall": "CONNECTED" if connected else "WAITING_FOR_EA",
                },
            }
        from app.analysis.briefing import build_decision_brief

        result["decision_brief"] = build_decision_brief(result["vantage_ea"], result["stats"])
        try:
            from app.analysis.openai_client import llm_status
            from app.config import get_settings

            st = llm_status(get_settings())
            result["llm"] = {
                "enabled": st.enabled,
                "configured": st.configured,
                "ready": st.ready,
                "model": st.model,
                "detail": st.detail,
            }
        except Exception:
            result["llm"] = {
                "enabled": False,
                "configured": False,
                "ready": False,
                "model": "",
                "detail": "LLM status unavailable",
            }
        try:
            from app.discord_notify import discord_status
            from app.telegram_notify import telegram_status

            result["telegram"] = telegram_status()
            result["discord"] = discord_status()
        except Exception:
            result["telegram"] = {
                "enabled": False,
                "configured": False,
                "cooldown_sec": 300,
                "chat_id_set": False,
            }
            result["discord"] = {
                "enabled": False,
                "configured": False,
                "cooldown_sec": 300,
                "webhook_set": False,
            }
        return result

    def set_calendar_month(self, year: int, month: int) -> dict[str, Any]:
        if year < 2000 or month < 1 or month > 12:
            raise ValueError("Invalid year/month")
        with self._lock:
            self._cal_req_year = year
            self._cal_req_month = month
            sym = self._selected_symbol
            key = f"{year}-{month:02d}"
            cached = self._calendar_cache.get(sym, {}).get(key)
            if cached is not None:
                self._selected_ea().pl_calendar = cached
            pending = cached is None
        return {
            "year": year,
            "month": month,
            "symbol": sym,
            "cached": cached is not None,
            "pending": pending,
            "calendar": cached,
        }

    def calendar_request(self) -> tuple[int, int]:
        with self._lock:
            return self._cal_req_year, self._cal_req_month

    def logs(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._logs)[: max(1, min(limit, 300))]
        return [asdict(x) for x in items]


monitor_store = MonitorStore()
