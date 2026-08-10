"""Premium / discount zones relative to a dealing range."""


def premium_discount(dealing_high: float, dealing_low: float, price: float) -> str:
    if dealing_high <= dealing_low:
        return "NEUTRAL"
    eq = (dealing_high + dealing_low) / 2.0
    if price >= eq + (dealing_high - eq) * 0.5:
        return "DEEP_PREMIUM"
    if price >= eq:
        return "PREMIUM"
    if price <= eq - (eq - dealing_low) * 0.5:
        return "DEEP_DISCOUNT"
    if price <= eq:
        return "DISCOUNT"
    return "NEUTRAL"
