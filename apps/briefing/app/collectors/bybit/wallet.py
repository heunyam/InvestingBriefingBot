from decimal import Decimal
from enum import StrEnum

from pybit.unified_trading import HTTP

from apps.briefing.app.collectors.bybit.session import get_bybit_session
from apps.briefing.app.utils.decimal import d


class AccountType(StrEnum):
    UNIFIED = "UNIFIED"
    FUND = "FUND"


def _fetch_wallet_balance(session: HTTP) -> dict:
    return session.get_wallet_balance(accountType=AccountType.UNIFIED)["result"]["list"][0]


def _fetch_coins_balance(session: HTTP, account_type: AccountType) -> dict:
    return session.get_coins_balance(
        accountType=account_type, coin="USDT,BYUSDT"
    )["result"]["balance"]


def fetch(session: HTTP | None = None) -> dict:
    session = get_bybit_session(session)
    wallet = _fetch_wallet_balance(session)
    fund = _fetch_coins_balance(session, AccountType.FUND)
    unified = _fetch_coins_balance(session, AccountType.UNIFIED)

    unified_cash = sum(d(coin["transferBalance"]) for coin in unified)
    fund_cash = sum(d(coin["transferBalance"]) for coin in fund)
    unified_total = d(wallet["totalEquity"])

    return {
        "cash": unified_cash + fund_cash,
        "coin": unified_total - unified_cash,
        "total": unified_total + fund_cash,
    }
