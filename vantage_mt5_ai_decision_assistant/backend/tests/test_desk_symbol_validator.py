"""Desk symbol validator — gold + major FX pairs."""
from app.analysis.desk_symbol_validator import is_approved_desk_symbol
from app.analysis.gold_symbol_validator import is_approved_gold_symbol


def test_desk_symbol_validator_matrix():
    desk_cases = [
        ("XAUUSD", True, "XAUUSD"),
        ("XAUUSD.a", True, "XAUUSD"),
        ("GOLD", True, "GOLD"),
        ("EURUSD", True, "EURUSD"),
        ("EURUSDm", True, "EURUSD"),
        ("EURUSD+", True, "EURUSD"),
        ("USDJPY", True, "USDJPY"),
        ("USDJPY.pro", True, "USDJPY"),
        ("USDJPY+", True, "USDJPY"),
        ("GBPUSD", False, ""),
        ("BTCUSD", False, ""),
        ("XAGUSD", False, ""),
    ]
    for sym, expect, base in desk_cases:
        ok, got_base = is_approved_desk_symbol(sym)
        assert ok is expect, f"{sym}: expected {expect}, got {ok} base={got_base}"
        if expect:
            assert got_base == base

    # Gold SMC validator stays gold-only
    assert is_approved_gold_symbol("EURUSD")[0] is False
    assert is_approved_gold_symbol("USDJPY")[0] is False
    assert is_approved_gold_symbol("XAUUSD")[0] is True


def test_normalize_strategy_blob_fixes_vantage_plus_suffix():
    from app.analysis.desk_symbol_validator import normalize_strategy_symbol_blob

    raw = {
        "valid": True,
        "gold_symbol_valid": False,
        "symbol": "EURUSD+",
        "disable_reason": "ICT Strategy Engine is disabled. Supported pairs: XAUUSD, EURUSD, USDJPY.",
    }
    fixed = normalize_strategy_symbol_blob(raw, "EURUSD+")
    assert fixed["gold_symbol_valid"] is True
    assert fixed["base_symbol"] == "EURUSD"
    assert fixed["disable_reason"] == ""
