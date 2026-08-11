"""Strict Gold symbol validation — mirrors MQL5 VantageGoldSMCValidator rules."""
from __future__ import annotations

import re

# Default approved base aliases (uppercase)
DEFAULT_ALIASES = ("XAUUSD", "GOLD")

_HARD_REJECT = {
    "XAGUSD",
    "XAUEUR",
    "XAUGBP",
    "XAUAUD",
    "EURUSD",
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

_BLOCKED_ALIAS = {
    "XAGUSD",
    "XAUEUR",
    "GOLDENCOIN",
    "EURUSD",
    "BTCUSD",
    "US30",
    "OIL",
    "WTI",
    "BRENT",
}


def _norm(symbol: str) -> str:
    return (symbol or "").strip().upper()


def _strip_prefixes(s: str, allow: bool) -> str:
    if not allow:
        return s
    out = s
    for _ in range(3):
        m = re.match(r"^([A-Z0-9]{1,3})[._\-](.+)$", out)
        if not m:
            break
        out = m.group(2)
    return out


def _strip_suffixes(s: str, allow: bool) -> str:
    if not allow:
        return s
    out = s
    # Vantage / raw account symbols: EURUSD+, XAUUSD+, etc.
    while len(out) > 4 and out[-1] in "+#":
        out = out[:-1]
    for _ in range(4):
        m = re.match(r"^(.+)[._\-]([A-Z0-9]{1,6})$", out)
        if not m:
            break
        out = m.group(1)
    return out


def _match_core(core: str, aliases: set[str], allow_suffix: bool) -> str | None:
    if core in aliases:
        return core
    if not allow_suffix:
        return None
    for peel in (1, 2):
        if len(core) <= peel + 3:
            break
        head = core[:-peel]
        if head in aliases and core[-peel:].isalnum():
            return head
    return None


def is_approved_gold_symbol(
    symbol: str,
    aliases_csv: str = "XAUUSD,GOLD",
    *,
    allow_suffix: bool = True,
    allow_prefix: bool = True,
) -> tuple[bool, str]:
    """Return (ok, base_alias). Strict — no loose GOLD/XAU substring."""
    u = _norm(symbol)
    if len(u) < 3:
        return False, ""
    if u in _HARD_REJECT or u.startswith("XAG") or u.startswith("GOLDEN"):
        return False, ""

    aliases: set[str] = set()
    for part in (aliases_csv or "XAUUSD,GOLD").split(","):
        a = part.strip().upper()
        if len(a) < 3 or not a.isalnum() or a in _BLOCKED_ALIAS:
            continue
        aliases.add(a)
    if not aliases:
        aliases = set(DEFAULT_ALIASES)

    core = _strip_suffixes(_strip_prefixes(u, allow_prefix), allow_suffix)
    base = _match_core(core, aliases, allow_suffix)
    if base is None:
        return False, ""
    return True, base
