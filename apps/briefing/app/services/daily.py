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

    stock_cash = toss_data["cash"]
    coin_cash = bybit_data["cash"]
    cash = stock_cash + coin_cash
    stock = toss_data["stock"]
    coin = bybit_data["coin"]

    now = kst_now()
    return AssetSummary(
        date=now.date(),
        total=cash + stock + coin,
        cash=cash,
        stock_cash=stock_cash,
        coin_cash=coin_cash,
        stock=stock,
        coin=coin,
        exchange_rate=toss_data["exchange_rate"],
        created_at=now,
    )


def format_message(asset: AssetSummary, prev: AssetSummary) -> str:
    def _trend_emoji(value: Decimal) -> str:
        return "📈" if value >= 0 else "📉"

    def _line(value: Decimal, prev_value: Decimal) -> str:
        value = to_decimal(value)
        prev_value = to_decimal(prev_value)
        diff = to_decimal(value - prev_value)
        percent = (
            to_decimal(diff / prev_value * 100) if prev_value > 0 else Decimal("0")
        )
        return f"{value} {_trend_emoji(diff)} ({diff} / {percent}%)"

    return "\n".join(
        [
            "```",
            f"Total: {_line(asset.total, prev.total)}",
            "",
            f"Cash:  {_line(asset.cash, prev.cash)}",
            f"Stock: {_line(asset.stock, prev.stock)}",
            f"Coin:  {_line(asset.coin, prev.coin)}",
            "",
            f"Exchange Rate:  {asset.exchange_rate}",
            "```",
        ]
    )


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
