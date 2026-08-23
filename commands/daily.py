from app.outbound import discord

from app.collectors import toss, bybit
from app.models.asset import AssetSummary
from app.store import daily
from app.utils.time import kst_now, yesterday
from app.utils.decimal import to_decimal
from app.formatter import format_message


def collect_data() -> AssetSummary:
    toss_data = toss.fetch()
    bybit_data = bybit.fetch()

    exchange_rate = toss_data["exchange_rate"]

    cash = (
        toss_data["cash_usd"]
        + toss_data["cash_krw"] / exchange_rate
        + bybit_data["cash_usd"]
    )
    stock = toss_data["us_stock_usd"] + toss_data["kr_stock"] / exchange_rate
    coin = bybit_data["coin_usd"]
    total = cash + stock + coin

    return AssetSummary(
        total_usd=to_decimal(total),
        cash_usd=to_decimal(cash),
        stock_usd=to_decimal(stock),
        coin_usd=to_decimal(coin),
        exchange_rate=to_decimal(exchange_rate),
        created_at=kst_now(),
    )


def app():
    try:
        summary = collect_data()
        daily.save(summary)
        try:
            summary_yesterday = daily.load(date_=yesterday(summary.created_at).date())
        except FileNotFoundError:
            summary_yesterday = None
        diff = summary.compare(summary_yesterday)
        message = format_message(summary, diff)
        print(message)
        discord.send_daily(message)
    except Exception as e:
        discord.send_daily(f"Error occurred: {e}")


if __name__ == "__main__":
    app()
