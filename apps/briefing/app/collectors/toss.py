import json
import os
from decimal import Decimal

import requests
from dotenv import load_dotenv

load_dotenv()

TOSS_DOMAIN = "https://openapi.tossinvest.com"
ACCOUNT_SEQ = "1"
API_KEY = os.environ["TOSS_API_KEY"]
SECRET_KEY = os.environ["TOSS_SECRET_KEY"]

# API Docs: "https://developers.tossinvest.com/docs/"


def auth() -> str:
    res = requests.post(
        url=f"{TOSS_DOMAIN}/oauth2/token",
        data={
            "client_id": API_KEY,
            "client_secret": SECRET_KEY,
            "grant_type": "client_credentials",
        },
    )
    res.raise_for_status()
    return res.json()["access_token"]


# https://developers.tossinvest.com/docs/account#tag/account/getaccounts
def fetch_account(token: str) -> dict:
    res = requests.get(
        url=f"{TOSS_DOMAIN}/api/v1/accounts",
        headers={"Authorization": f"Bearer {token}"},
    )
    res.raise_for_status()
    return res.json()


# https://developers.tossinvest.com/docs/asset#tag/asset/getholdings
def fetch_asset(token: str) -> dict:
    res = requests.get(
        url=f"{TOSS_DOMAIN}/api/v1/holdings",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Tossinvest-Account": ACCOUNT_SEQ,
        },
    )
    res.raise_for_status()
    return res.json()


# https://developers.tossinvest.com/docs/order-info#tag/order-info/getbuyingpower
def fetch_buying_power(token: str, currency: str) -> dict:
    res = requests.get(
        url=f"{TOSS_DOMAIN}/api/v1/buying-power",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Tossinvest-Account": ACCOUNT_SEQ,
        },
        params={"currency": currency},
    )
    res.raise_for_status()
    return res.json()


# https://developers.tossinvest.com/docs/market-info#tag/market-info/getexchangerate
def fetch_exchange_rate(token: str) -> dict:
    res = requests.get(
        url=f"{TOSS_DOMAIN}/api/v1/exchange-rate",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "baseCurrency": "USD",
            "quoteCurrency": "KRW",
        },
    )
    res.raise_for_status()
    return res.json()


def _d(v) -> Decimal:
    return Decimal(str(v or 0))


def fetch() -> dict:
    token = auth()

    exchange_rate = _d(fetch_exchange_rate(token)["result"]["rate"])

    cash_krw = _d(fetch_buying_power(token, "KRW")["result"]["cashBuyingPower"])
    cash_usd = _d(fetch_buying_power(token, "USD")["result"]["cashBuyingPower"])
    cash = cash_usd + (cash_krw / exchange_rate)

    asset = fetch_asset(token)["result"]["marketValue"]["amount"]
    stock_krw = _d(asset["krw"])
    stock_usd = _d(asset.get("usd"))
    stock = stock_usd + (stock_krw / exchange_rate)

    return {
        "cash": _d(cash),
        "stock": _d(stock),
        "exchange_rate": _d(exchange_rate),
    }


if __name__ == "__main__":
    print(json.dumps(fetch(), indent=2))
