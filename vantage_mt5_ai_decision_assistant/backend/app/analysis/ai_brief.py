"""Build a ChatGPT-ready markdown snapshot from monitor status."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


DEFAULT_ASK = """Using ONLY the snapshot above:
1) Summarize the situation in 5 bullets.
2) Rank risks (capital, structure, timing).
3) Give 3 manual next actions (no auto-trade language).
4) What would invalidate the current bias?
5) What data is missing for a better call?"""


def _f(v: Any, digits: int = 2) -> str:
    try:
        return f"{float(v):.{digits}f}"
    except (TypeError, ValueError):
        return "—"


def _bar(pct: float, width: int = 10) -> str:
    try:
        p = max(0.0, min(100.0, float(pct)))
    except (TypeError, ValueError):
        p = 0.0
    filled = int(round((p / 100.0) * width))
    return "█" * filled + "░" * (width - filled)


def _yn(ok: bool) -> str:
    return "YES" if ok else "NO"


def build_ai_brief_markdown(status: dict[str, Any], *, extra_question: str | None = None) -> str:
    """Compose paste/analyze markdown for the selected pair snapshot."""
    ea = status.get("vantage_ea") or {}
    brief = status.get("decision_brief") or {}
    stats = status.get("stats") or {}
    now = (status.get("backend") or {}).get("now_utc") or datetime.now(timezone.utc).isoformat()
    symbol = status.get("selected_symbol") or ea.get("symbol") or "—"

    lines: list[str] = [
        "# Vantage MT5 Advisory Snapshot",
        f"Generated (UTC): {now}",
        (
            f"Pair: {symbol} | Account: {ea.get('account_masked') or '—'} | "
            f"Server: {ea.get('server') or '—'}"
        ),
        "Mode: ADVISORY ONLY — do not treat as an order to trade",
        "",
        "## 1. Executive headline",
        str(brief.get("headline") or "No headline yet."),
        "",
        "## 2. Decision matrix",
        "| Field | Value |",
        "|------|--------|",
        f"| Trend | {ea.get('trend') or '—'} |",
        f"| Market state | {ea.get('market_state') or '—'} |",
        f"| New entry | {ea.get('new_entry_decision') or '—'} |",
        f"| Existing position | {ea.get('existing_position_decision') or '—'} |",
        f"| Risk status | {ea.get('risk_status') or '—'} |",
        f"| New position allowed | {_yn(bool(ea.get('new_position_allowed')))} |",
        f"| Add position allowed | {_yn(bool(ea.get('add_position_allowed')))} |",
        f"| Primary action | {ea.get('action') or stats.get('last_action') or '—'} |",
        "",
        "## 3. Market snapshot",
        (
            f"- Bid / Ask: {_f(ea.get('bid'), max(0, int(ea.get('digits') or 2)))} / "
            f"{_f(ea.get('ask'), max(0, int(ea.get('digits') or 2)))} | "
            f"Spread: {ea.get('spread_points')} pts"
            + (" · HIGH" if ea.get("high_spread") else "")
        ),
        f"- Digits / Contract: {ea.get('digits') or '—'} / {ea.get('contract_size') or '—'}",
    ]

    lookback = ea.get("bias_lookback") or 20
    lines.append(
        f"- Chart bias (last {lookback}): Bullish {_f(ea.get('bullish_pct'), 1)}% · "
        f"Bearish {_f(ea.get('bearish_pct'), 1)}% · Neutral {_f(ea.get('neutral_pct'), 1)}%"
    )
    lines.append(
        f"- Indicator bias: Bullish {_f(ea.get('indicator_bullish_pct'), 1)}% · "
        f"Bearish {_f(ea.get('indicator_bearish_pct'), 1)}%"
    )
    lines.append(
        f"- Nearest S / R: {ea.get('nearest_support') or '—'} / {ea.get('nearest_resistance') or '—'}"
    )
    levels = brief.get("levels") or {}
    lines.append(
        f"- Levels: Imm support {levels.get('support') or ea.get('immediate_support') or '—'} · "
        f"Recovery {levels.get('recovery_1') or '—'} / {levels.get('recovery_2') or '—'} · "
        f"Bullish conf {levels.get('bullish_confirmation') or '—'}"
    )
    inv = levels.get("invalidation") or ea.get("technical_invalidation") or "—"
    lines.append(f"- Invalidation: {inv}")
    lines.append("")

    lines.extend(
        [
            "## 4. Position & risk",
            (
                f"- Positions: {ea.get('position_count') or 0} | "
                f"Entry {ea.get('entry') or '—'} | SL {ea.get('sl') or '—'}"
            ),
            (
                f"- Equity: {_f(ea.get('equity'))} | Floating P/L: {_f(ea.get('floating_pl'))} "
                f"({_f(ea.get('floating_pl_pct_of_equity'), 2)}% equity)"
            ),
            (
                f"- Est. loss at SL: {_f(ea.get('estimated_sl_loss'))} "
                f"({_f(ea.get('equity_risk_pct'), 2)}% equity)"
            ),
            (
                f"- Float profit target: {_f(ea.get('float_profit_target_pct'), 0)}% equity — "
                f"HIT? {_yn(bool(ea.get('float_profit_target_hit')))}"
            ),
            "",
            "## 5. Charts (ASCII)",
            "### Bias pie (chart candles)",
            f"Bullish {_bar(float(ea.get('bullish_pct') or 0))} {_f(ea.get('bullish_pct'), 1)}%",
            f"Bearish {_bar(float(ea.get('bearish_pct') or 0))} {_f(ea.get('bearish_pct'), 1)}%",
            f"Neutral {_bar(float(ea.get('neutral_pct') or 0))} {_f(ea.get('neutral_pct'), 1)}%",
            "",
            "### Floating P/L vs equity",
        ]
    )
    fpct = float(ea.get("floating_pl_pct_of_equity") or 0)
    lines.append(f"Float P/L {_bar(abs(fpct))} {_f(fpct, 1)}% of equity")
    lines.append(f"Remainder {_bar(max(0.0, 100.0 - abs(fpct)))} {_f(max(0.0, 100.0 - abs(fpct)), 1)}%")
    lines.append("")

    st = ea.get("trade_stats") or {}
    if st.get("ok"):
        wins = int(st.get("wins") or 0)
        losses = int(st.get("losses") or 0)
        total = max(1, wins + losses)
        win_pct = float(st.get("win_rate_pct") or (100.0 * wins / total))
        loss_pct = 100.0 - win_pct if wins + losses else 0.0
        lines.extend(
            [
                "### Win/loss (account stats)",
                f"Wins {_bar(win_pct)} {_f(win_pct, 1)}% ({wins})",
                f"Losses {_bar(loss_pct)} {_f(loss_pct, 1)}% ({losses})",
                (
                    f"PF {_f(st.get('profit_factor'))} | Max DD {_f(st.get('max_drawdown_pct'), 1)}% | "
                    f"Net {_f(st.get('net_profit'))}"
                ),
                "",
            ]
        )

    cal = ea.get("pl_calendar") or {}
    if cal:
        lines.append("### Calendar month (selected)")
        lines.append(
            f"{cal.get('year')}-{int(cal.get('month') or 0):02d} · "
            f"Month P/L {_f(cal.get('month_pl'))} ({_f(cal.get('month_pct'), 2)}%) · "
            f"{cal.get('month_deals') or 0} deals"
        )
        days = cal.get("days") or []
        if days:
            day_bits = []
            for d in days[:31]:
                day_bits.append(f"{int(d.get('d') or 0):02d}:{_f(d.get('pct'), 1)}")
            lines.append("Day map (pct of equity): " + " ".join(day_bits))
        lines.append("")

    lines.append("## 6. Recommendations (priority-ordered)")
    recs = brief.get("recommendations") or []
    if not recs:
        lines.append("1. [LOW] No recommendations yet — wait for EA heartbeat.")
    else:
        for i, r in enumerate(recs, 1):
            lines.append(
                f"{i}. [{(r.get('priority') or 'medium').upper()}] {r.get('title') or '—'} — "
                f"{r.get('detail') or ''}"
            )
    lines.append("")

    lines.append("## 7. Checklist")
    for c in brief.get("checklist") or []:
        mark = "x" if c.get("ok") else " "
        lines.append(f"- [{mark}] {c.get('label') or '—'}")
    lines.append("")

    sit = brief.get("situation") or []
    if sit:
        lines.append("## Situation bullets")
        for s in sit:
            lines.append(f"- {s}")
        lines.append("")

    lines.append("## 8. Ask ChatGPT")
    ask = (extra_question or "").strip() or DEFAULT_ASK
    lines.append(ask)
    lines.append("")
    lines.append("---")
    lines.append("Reminder: advisory decision-support only. Not financial advice. No automatic orders.")
    return "\n".join(lines)


SYSTEM_PROMPT = (
    "You are a cautious trading desk analyst assisting a retail trader. "
    "You receive a Vantage MT5 advisory snapshot (not live orders). "
    "Rules: (1) Use ONLY the snapshot facts — do not invent prices or fills. "
    "(2) Stay advisory/educational — never instruct an auto-trader or claim the EA will execute. "
    "(3) If risk is CRITICAL or add/new is blocked, emphasize capital protection and no averaging down. "
    "(4) Prefer clear bullets and numbered actions. "
    "(5) Call out missing data explicitly. "
    "(6) End with: Advisory only — not an order to trade."
)
