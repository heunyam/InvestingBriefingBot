from datetime import date, timedelta
from decimal import Decimal

from apps.briefing.app.models.asset import AssetSummary
from apps.briefing.app.outbounds import discord
from apps.briefing.app.utils.decimal import to_decimal
from apps.briefing.app.utils.time import kst_now, get_week_start


def _weekly_line(
    week_start: date,
    current: AssetSummary | None,
    prev: AssetSummary | None,
) -> str:
    def _trend_emoji(value: Decimal) -> str:
        return "📈" if value >= 0 else "📉"

    label = week_start.isoformat()
    line = f"[{label}] "

    if current is None:
        return line + "No Data"

    if prev is None:
        return line + f"${to_decimal(current.total)} (- / -)"

    curr_value = to_decimal(current.total)
    prev_value = to_decimal(prev.total)
    diff = to_decimal(curr_value - prev_value)

    emoji = _trend_emoji(diff)
    percent = to_decimal(diff / prev_value * 100) if prev_value > 0 else Decimal("0")

    return line + f"${curr_value} {emoji} (${diff} / {percent}%)"


def format_weekly_message(rows: list[AssetSummary]) -> str:
    by_week = {get_week_start(row.date): row for row in rows}
    week_start = get_week_start(kst_now().date())
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


def run_weekly():
    message = format_weekly_message(AssetSummary.all_weeks())
    discord.send_daily(message)
