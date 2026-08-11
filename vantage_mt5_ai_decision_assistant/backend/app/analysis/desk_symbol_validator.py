"""Desk symbol validation for strategy modules (gold + major FX)."""
from __future__ import annotations

from app.analysis.gold_symbol_validator import (
    _match_core,
    _norm,
    _strip_prefixes,
    _strip_suffixes,
)

DEFAULT_DESK_ALIASES = ("XAUUSD", "GOLD", "EURUSD", "USDJPY")
DESK_SUPPORTED_PAIRS = "XAUUSD, EURUSD, USDJPY"
DESK_STRATEGY_CAPTION = (
    "Advisory only — never places, modifies, or cancels MT5 orders. "
    f"Supported pairs: {DESK_SUPPORTED_PAIRS}."
)
DESK_UNSUPPORTED_FALLBACK = f"Supported pairs: {DESK_SUPPORTED_PAIRS}."

_DESK_HARD_REJECT = {
    "XAGUSD",
    "XAUEUR",
    "XAUGBP",
    "XAUAUD",
    "GBPUSD",
    "BTCUSD",
    "ETHUSD",
    "US30",
    "NAS100",
    "OIL",
    "USOIL",
    "UKOIL",
    "GOLDENCOIN",
    "SILVER",
}

# Aliases that must never be accepted even if listed in config.
_DESK_BLOCKED_ALIAS = {
    "XAGUSD",
    "XAUEUR",
    "GOLDENCOIN",
    "BTCUSD",
    "US30",
    "OIL",
    "WTI",
    "BRENT",
}


def is_approved_desk_symbol(
    symbol: str,
    aliases_csv: str = "XAUUSD,GOLD,EURUSD,USDJPY",
    *,
    allow_suffix: bool = True,
    allow_prefix: bool = True,
) -> tuple[bool, str]:
    """Return (ok, base_alias) for approved desk pairs."""
    u = _norm(symbol)
    if len(u) < 3:
        return False, ""
    if u in _DESK_HARD_REJECT or u.startswith("XAG") or u.startswith("GOLDEN"):
        return False, ""

    aliases: set[str] = set()
    for part in (aliases_csv or ",".join(DEFAULT_DESK_ALIASES)).split(","):
        a = part.strip().upper()
        if len(a) < 3 or not a.isalnum() or a in _DESK_BLOCKED_ALIAS:
            continue
        aliases.add(a)
    if not aliases:
        aliases = set(DEFAULT_DESK_ALIASES)

    core = _strip_suffixes(_strip_prefixes(u, allow_prefix), allow_suffix)
    base = _match_core(core, aliases, allow_suffix)
    if base is None:
        return False, ""
    return True, base


def desk_disable_message(module: str) -> str:
    return f"{module} is disabled. Supported pairs: {DESK_SUPPORTED_PAIRS}."


def normalize_strategy_symbol_blob(blob: dict | None, symbol: str | None) -> dict | None:
    """Correct stale EA gold_symbol_valid flags when broker symbol uses Vantage suffixes."""
    if not isinstance(blob, dict):
        return blob
    sym = (symbol or blob.get("symbol") or blob.get("base_symbol") or "").strip().upper()
    if not sym:
        return blob
    ok, base = is_approved_desk_symbol(sym)
    if not ok or blob.get("gold_symbol_valid") is not False:
        return blob
    fixed = dict(blob)
    fixed["gold_symbol_valid"] = True
    fixed["base_symbol"] = base or sym
    if fixed.get("disable_reason"):
        fixed["disable_reason"] = ""
    return fixed
