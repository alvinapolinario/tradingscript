"""Technical helpers / validation for broker-provided indicator payloads."""
from __future__ import annotations

from app.schemas import AnalyzeRequest


def validate_symbol_sanity(req: AnalyzeRequest) -> list[str]:
    warnings: list[str] = []
    s = req.symbol
    if s.point <= 0:
        warnings.append("invalid_point")
    if s.tick_size <= 0:
        warnings.append("invalid_tick_size")
    if s.contract_size <= 0:
        warnings.append("invalid_contract_size")
    if s.volume_min <= 0 or s.volume_step <= 0:
        warnings.append("invalid_volume_constraints")
    if s.digits < 0 or s.digits > 8:
        warnings.append("unusual_digits")
    # Do not assume 2 or 3 digits — both are valid for gold depending on broker
    return warnings


def volume_step_ok(volume: float, step: float, vmin: float, vmax: float, tol: float = 1e-8) -> bool:
    if step <= 0:
        return False
    if volume + tol < vmin or volume - tol > vmax:
        return False
    # volume should be an integer multiple of step
    n = round(volume / step)
    return abs(n * step - volume) <= tol
