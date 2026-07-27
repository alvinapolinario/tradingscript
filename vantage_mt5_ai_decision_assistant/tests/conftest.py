"""Shared fixtures / sample Vantage-like payloads."""
from __future__ import annotations

from copy import deepcopy

from app.schemas import AnalyzeRequest


def base_payload(**overrides) -> dict:
    data = {
        "schema_version": "1.0",
        "mode": "advisory_only",
        "broker": {
            "company": "Vantage International Group Limited",
            "server": "VantageInternational-Demo",
            "currency": "USD",
            "margin_mode": "Hedging",
            "account_login_masked": "******7890",
        },
        "symbol": {
            "name": "XAUUSD+",
            "digits": 3,
            "point": 0.001,
            "tick_size": 0.001,
            "tick_value": 0.01,
            "tick_value_profit": 0.01,
            "tick_value_loss": 0.01,
            "contract_size": 100.0,
            "volume_min": 0.01,
            "volume_max": 100.0,
            "volume_step": 0.01,
            "stops_level": 0,
            "freeze_level": 0,
            "spread_float": True,
            "trade_mode": 4,
            "trade_execution": 2,
            "filling_mode": 1,
        },
        "prices": {
            "bid": 4090.5,
            "ask": 4090.8,
            "last": 4090.6,
            "spread_points": 300,
            "high_spread": False,
            "server_time": "2026.07.23 10:00:00",
            "local_time": "2026.07.23 18:00:00",
            "utc_time": "2026.07.23 10:00:00",
        },
        "candle": {
            "timeframe": "M30",
            "time": "2026.07.23 09:30:00",
            "open": 4106.0,
            "high": 4107.0,
            "low": 4088.0,
            "close": 4092.0,
            "volume": 5000,
        },
        "indicators": {
            "ema20": 4100.0,
            "ema50": 4110.0,
            "ema200": 4120.0,
            "bb_upper": 4125.0,
            "bb_middle": 4105.0,
            "bb_lower": 4085.0,
            "rsi14": 38.0,
            "atr14": 4.5,
            "volume_sma": 4000.0,
        },
        "structure": {
            "trend": "BEARISH",
            "oversized_candle": True,
            "support_break": True,
            "retest_pending": True,
            "bear_reject": False,
            "bull_reject": False,
            "note": "MULTI_LEVEL_BEARISH_IMPULSE",
            "nearest_support": "4085",
            "nearest_resistance": "4095",
            "daily_pivot": 4124.29,
        },
        "levels": {
            "4143": 4143.0,
            "4133": 4133.0,
            "4124_29": 4124.29,
            "4112": 4112.0,
            "4105": 4105.0,
            "4103": 4103.0,
            "4100": 4100.0,
            "4095": 4095.0,
            "4085": 4085.0,
        },
        "positions": {
            "count": 0,
            "total_buy_volume": 0.0,
            "total_sell_volume": 0.0,
            "weighted_avg_entry": 0.0,
            "total_floating_pl": 0.0,
            "items": [],
        },
        "risk": {
            "available": True,
            "status": "OK",
            "last_error": 0,
            "money_at_risk": 0.0,
            "equity_risk_pct": 0.0,
        },
        "environment": "NORMAL",
    }
    for k, v in overrides.items():
        if isinstance(v, dict) and isinstance(data.get(k), dict):
            data[k] = {**data[k], **v}
        else:
            data[k] = v
    return data


def as_request(**overrides) -> AnalyzeRequest:
    return AnalyzeRequest.model_validate(base_payload(**overrides))
