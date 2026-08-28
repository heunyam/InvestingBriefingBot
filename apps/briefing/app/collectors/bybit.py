import os
from decimal import Decimal
from enum import StrEnum

from pybit.unified_trading import HTTP


class AccountType(StrEnum):
    UNIFIED = "UNIFIED"
    FUND = "FUND"


bybit_session: HTTP | None = None


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

def get_bybit_session(session: HTTP | None = None) -> HTTP:
    if session:
        return session

    global bybit_session
    if bybit_session:
        return bybit_session

    bybit_session = HTTP(api_key=os.environ["BYBIT_API_KEY"], api_secret=os.environ["BYBIT_API_SECRET"])
    return bybit_session


def fetch(session: HTTP | None = None) -> dict:
    session = get_bybit_session(session)
    wallet = _fetch_wallet_balance(session)

    fund = _fetch_coins_balance(session, AccountType.FUND)
    unified = _fetch_coins_balance(session, AccountType.UNIFIED)

    unified_cash = sum([_d(coin["transferBalance"]) for coin in unified])
    fund_cash = sum([_d(coin["transferBalance"]) for coin in fund])

    unified_total = _d(wallet["totalEquity"])

    coin = unified_total - unified_cash
    cash = unified_cash + fund_cash
    return {
        "cash": cash, 
        "coin": coin, 
        "total": unified_total + fund_cash
    }


if __name__ == "__main__":
    s = get_bybit_session()
    unified_data = _fetch_coins_balance(s, AccountType.UNIFIED)
    fund_data = _fetch_coins_balance(s, AccountType.FUND)
    wallet_data = _fetch_wallet_balance(s)

    data = fetch()
    print(data)

    # print(json.dumps(wallet, indent=2))
    # print(json.dumps(unified, indent=2))
    # print(json.dumps(fund, indent=2))
