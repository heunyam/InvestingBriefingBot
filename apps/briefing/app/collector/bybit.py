import os
from decimal import Decimal
from enum import StrEnum

from dotenv import load_dotenv
from pybit.unified_trading import HTTP

load_dotenv()

API_KEY = os.environ["BYBIT_API_KEY"]
API_SECRET = os.environ["BYBIT_API_SECRET"]


class AccountType(StrEnum):
    UNIFIED = "UNIFIED"
    FUND = "FUND"


def _d(v) -> Decimal:
    return Decimal(str(v or 0))


def _fetch_wallet_balance(session: HTTP) -> dict:
    wallet = session.get_wallet_balance(accountType=AccountType.UNIFIED)["result"][
        "list"
    ][0]

    return wallet


def _fetch_coins_balance(session: HTTP, account_type: AccountType) -> dict:
    fund = session.get_coins_balance(accountType=account_type, coin="USDT,BYUSDT")[
        "result"
    ]["balance"]

    return fund


def fetch() -> dict:
    session = HTTP(api_key=API_KEY, api_secret=API_SECRET)
    wallet = _fetch_wallet_balance(session)

    fund = _fetch_coins_balance(session, AccountType.FUND)
    unified = _fetch_coins_balance(session, AccountType.UNIFIED)

    unified_cash = sum([_d(coin["transferBalance"]) for coin in unified])
    fund_cash = sum([_d(coin["transferBalance"]) for coin in fund])

    unified_total = _d(wallet["totalEquity"])

    coin = unified_total - unified_cash
    cash = unified_cash + fund_cash
    return {"cash": cash, "coin": coin, "total": unified_total + fund_cash}


if __name__ == "__main__":
    session = HTTP(api_key=API_KEY, api_secret=API_SECRET)
    unified = _fetch_coins_balance(session, AccountType.UNIFIED)
    fund = _fetch_coins_balance(session, AccountType.FUND)
    wallet = _fetch_wallet_balance(session)

    data = fetch()
    print(data)

    # print(json.dumps(wallet, indent=2))
    # print(json.dumps(unified, indent=2))
    # print(json.dumps(fund, indent=2))
