from decimal import Decimal, ROUND_HALF_UP

PERIOD_TITLE = {
    "7d": "최근 7일",
    "30d": "최근 30일",
    "all": "전체",
}
MONEY_Q = Decimal("0.0001")


def _fmt_int(value: int) -> str:
    return f"{value:,}"


def _fmt_money(value: Decimal | None) -> str:
    if value is None:
        return "-"
    d = Decimal(str(value)).quantize(MONEY_Q, rounding=ROUND_HALF_UP)
    sign = "-" if d < 0 else ""
    d = abs(d)
    text = format(d, "f")
    if "." in text:
        whole, frac = text.split(".", 1)
        frac = frac[:4].rstrip("0")
        whole = f"{int(whole):,}"
        body = f"{whole}.{frac}" if frac else whole
    else:
        body = f"{int(text):,}"
    return f"{sign}{body}"


def _fmt_pct(value: Decimal | None) -> str:
    if value is None:
        return "-"
    return f"{(value * 100):.1f}%"


def _fmt_ratio(value: Decimal | None) -> str:
    return _fmt_money(value)


def format_report(stats: dict) -> str:
    period = stats.get("period") or "7d"
    title = PERIOD_TITLE.get(period, period)
    symbol_lines = []
    for row in stats.get("by_symbol") or []:
        symbol_lines.append(
            f"  {row['symbol']}  {_fmt_int(row['n'])}  "
            f"{_fmt_pct(row['win_rate'])}  {_fmt_money(row['net_pnl'])}"
        )
    symbol_block = "\n".join(symbol_lines) if symbol_lines else "  -"
    return "\n".join(
        [
            f"📊 매매 성과 · {title}",
            "",
            f"거래 {_fmt_int(stats['n'])} · 승률 {_fmt_pct(stats['win_rate'])}",
            f"💰 순손익 {_fmt_money(stats['net_pnl'])}",
            (
                f"📐 PF {_fmt_ratio(stats['profit_factor'])} · "
                f"Expectancy {_fmt_ratio(stats['expectancy'])}"
            ),
            (
                f"📈 평균 이익 {_fmt_money(stats['avg_win'])} · "
                f"평균 손실 {_fmt_money(stats['avg_loss'])}"
            ),
            (
                f"🔥 연속 승 {_fmt_int(stats['max_win_streak'])} · "
                f"패 {_fmt_int(stats['max_loss_streak'])}"
            ),
            f"📉 낙폭 {_fmt_money(stats['max_drawdown'])}",
            f"💸 수수료 {_fmt_money(stats['fees'])}",
            "",
            "종목별",
            symbol_block,
        ]
    )
