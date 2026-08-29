import os

import requests


def send_trade(content: str) -> str:
    url = os.environ["DISCORD_TRADE_WEBHOOK_URL"]
    text = (content or "").rstrip()
    if not (text.strip().startswith("```") and text.strip().endswith("```")):
        text = f"```\n{text}\n```"
    response = requests.post(
        url + "?wait=true",
        json={"content": text},
        timeout=30,
    )
    response.raise_for_status()
    return str(response.json()["id"])
