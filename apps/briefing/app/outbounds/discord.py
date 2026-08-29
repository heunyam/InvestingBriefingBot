import os

import requests


def _post(url: str, content: str) -> None:
    response = requests.post(url, json={"content": content}, timeout=30)
    response.raise_for_status()


def send_daily(message: str) -> None:
    _post(os.environ["DISCORD_DAILY_WEBHOOK_URL"], message)


def send_trade(content: str) -> None:
    _post(os.environ["DISCORD_TRADE_WEBHOOK_URL"], content)
