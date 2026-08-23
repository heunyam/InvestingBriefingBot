from decimal import Decimal
from apps.briefing.app.models.asset import AssetSummary
from apps.briefing.app.utils.decimal import to_decimal


def _trend_emoji(value: Decimal) -> str:
    return "📈" if value >= 0 else "📉"


def _line(value: Decimal, prev_value: Decimal) -> str:
    value = to_decimal(value)
    diff = to_decimal(prev_value - value)

    emoji = _trend_emoji(diff)
    percent = to_decimal(diff / prev_value)

    return f"{to_decimal(value)} {emoji} ({diff} / {percent}%)"


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
