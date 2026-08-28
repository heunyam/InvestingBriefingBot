from datetime import timedelta
from decimal import Decimal

from apps.briefing.app.collectors import toss, bybit
from apps.briefing.app.models.asset import AssetSummary
from apps.briefing.app.outbounds import discord
from apps.briefing.app.services.daily_hook import snapshot_weekly
from apps.briefing.app.utils.decimal import to_decimal
from apps.briefing.app.utils.time import kst_now


def collect_daily_data() -> AssetSummary:
    toss_data = toss.fetch()
    bybit_data = bybit.fetch()

    exchange_rate = toss_data["exchange_rate"]

    cash = toss_data["cash"] + bybit_data["cash"]
    stock = toss_data["stock"]
    coin = bybit_data["coin"]
    total = cash + stock + coin

    now = kst_now()
    return AssetSummary(
        date=now.date(),
        total=total,
        cash=cash,
        stock=stock,
        coin=coin,
        exchange_rate=exchange_rate,
        created_at=now,
    )


def format_message(asset: AssetSummary, prev: AssetSummary) -> str:
    def _trend_emoji(value: Decimal) -> str:
        return "📈" if value >= 0 else "📉"

    def _line(value: Decimal, prev_value: Decimal) -> str:
        value = to_decimal(value)
        prev_value = to_decimal(prev_value)
        diff = to_decimal(value - prev_value)

        emoji = _trend_emoji(diff)
        percent = (
            to_decimal(diff / prev_value * 100) if prev_value > 0 else Decimal("0")
        )

        return f"{value} {emoji} ({diff} / {percent}%)"

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


def run_daily():
    summary = collect_daily_data()
    summary.save()

    try:
        summary_yesterday = AssetSummary.load(summary.date - timedelta(days=1))
    except FileNotFoundError:
        summary_yesterday = summary

    message = format_message(summary, summary_yesterday)
    discord.send_daily(message)

    snapshot_weekly(summary)
