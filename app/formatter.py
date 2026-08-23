from decimal import Decimal
from app.models.asset import AssetDiff, AssetSummary


def get_trend_emoji(value: Decimal) -> str:
    return "📈" if value >= 0 else "📉"


def format_message(summary: AssetSummary, diff: AssetDiff | None) -> str:
    def with_diff(value: Decimal, diff_usd: Decimal, diff_pct: Decimal) -> str:
        sign = "+" if diff_usd >= 0 else ""
        emoji = get_trend_emoji(diff_usd)
        return f"${value} {emoji} ({sign}{diff_usd} / {sign}{diff_pct}%)"

    total_line = (
        with_diff(summary.total_usd, diff.total_usd, diff.total_pct)
        if diff
        else f"${summary.total_usd}"
    )
    cash_line = (
        with_diff(summary.cash_usd, diff.cash_usd, diff.cash_pct)
        if diff
        else f"${summary.cash_usd}"
    )
    stock_line = (
        with_diff(summary.stock_usd, diff.stock_usd, diff.stock_pct)
        if diff
        else f"${summary.stock_usd}"
    )
    coin_line = (
        with_diff(summary.coin_usd, diff.coin_usd, diff.coin_pct)
        if diff
        else f"${summary.coin_usd}"
    )

    lines = [
        "```",
        f"총액: {total_line}",
        "",
        f"Cash:  {cash_line}",
        f"Stock: {stock_line}",
        f"Coin:  {coin_line}",
        "",
        f"환율:  {summary.exchange_rate}",
        "```",
    ]

    return "\n".join(lines)
