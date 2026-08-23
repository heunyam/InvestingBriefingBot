import json
import os
from decimal import Decimal

import requests
from dotenv import load_dotenv

load_dotenv()

TOSS_DOMAIN = "https://openapi.tossinvest.com"
ACCOUNT_SEQ = "1"

# API Docs: "https://developers.tossinvest.com/docs/"

def auth() -> str:
    res = requests.post(
        url=f"{TOSS_DOMAIN}/oauth2/token",
        data={
            "client_id": os.environ["TOSS_API_KEY"],
            "client_secret": os.environ["TOSS_SECRET_KEY"],
            "grant_type": "client_credentials",
        },
    )
    res.raise_for_status()
    return res.json()["access_token"]


def fetch_account(token: str) -> dict:
    res = requests.get(
        url=f"{TOSS_DOMAIN}/api/v1/accounts",
        headers={"Authorization": f"Bearer {token}"},
    )
    res.raise_for_status()
    return res.json()


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


def fetch() -> dict:
    token = auth()
    cash_krw = fetch_buying_power(token, "KRW")["result"]["cashBuyingPower"]
    cash_usd = fetch_buying_power(token, "USD")["result"]["cashBuyingPower"]
    holdings = fetch_asset(token)["result"]
    market = holdings["marketValue"]["amount"]
    kr_stock = market["krw"]
    us_stock_usd = market.get("usd") or "0"
    exchange_rate = fetch_exchange_rate(token)["result"]["rate"]

    return {
        "cash_krw": Decimal(str(cash_krw)),
        "cash_usd": Decimal(str(cash_usd)),
        "kr_stock": Decimal(str(kr_stock)),
        "us_stock_usd": Decimal(str(us_stock_usd)),
        "exchange_rate": Decimal(str(exchange_rate)),
    }


if __name__ == "__main__":
    print(json.dumps(fetch(), indent=2))
