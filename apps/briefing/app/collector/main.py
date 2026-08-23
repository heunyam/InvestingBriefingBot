from app.collector import toss
from app.collector import bybit
from app.utils.time import kst_now

from app.models.asset import AssetSummary


def collect_data() -> AssetSummary:
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
