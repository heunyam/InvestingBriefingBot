from datetime import date, timedelta
from decimal import Decimal

from app.models.asset import AssetSummary
from app.utils.decimal import to_decimal
from app.utils.time import kst_now


def _trend_emoji(value: Decimal) -> str:
    return "📈" if value >= 0 else "📉"


def _line(value: Decimal, prev_value: Decimal) -> str:
    value = to_decimal(value)
    prev_value = to_decimal(prev_value)
    diff = to_decimal(value - prev_value)

    emoji = _trend_emoji(diff)
    percent = to_decimal(diff / prev_value * 100) if prev_value > 0 else Decimal("0")

    return f"{value} {emoji} ({diff} / {percent}%)"


def format_message(asset: AssetSummary, prev: AssetSummary | None) -> str:
    total_line = _line(asset.total, prev.total)
    cash_line = _line(asset.cash, prev.cash)
    stock_line = _line(asset.stock, prev.stock)
    coin_line = _line(asset.coin, prev.coin)

    lines = [
        "```",
        f"Total: {total_line}",
        "",
        f"Cash:  {cash_line}",
        f"Stock: {stock_line}",
        f"Coin:  {coin_line}",
        "",
        f"Exchange Rate:  {asset.exchange_rate}",
        "```",
    ]

    return "\n".join(lines)


def to_week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _weekly_line(
    week_start: date,
    current: AssetSummary | None,
    prev: AssetSummary | None,
) -> str:
    if current is None:
        return f"{week_start.isoformat()}: No Data"

    label = current.date.isoformat()
    if prev is None:
        return f"{label}: {to_decimal(current.total)} (- / -)"

    return f"{label}: {_line(current.total, prev.total)}"


def format_weekly_message(rows: list[AssetSummary]) -> str:
    by_week = {to_week_start(row.date): row for row in rows}
    week_start = to_week_start(kst_now().date())
    weeks = [
        (week_start - timedelta(weeks=i), by_week.get(week_start - timedelta(weeks=i)))
        for i in range(5, -1, -1)
    ]

    lines = [
        "```",
        "[Weekly 변동]",
        "",
    ]
    pairs = list(zip(weeks[1:], weeks[:-1]))
    for i, ((week_start, current), (_, prev)) in enumerate(pairs):
        if i == len(pairs) - 1:
            lines.append("")
        lines.append(_weekly_line(week_start, current, prev))
    lines.append("```")
    return "\n".join(lines)
