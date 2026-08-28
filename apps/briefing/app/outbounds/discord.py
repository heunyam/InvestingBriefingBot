import os
import requests
from dotenv import load_dotenv

load_dotenv()

DAILY_WEBHOOK_URL = os.environ["DISCORD_DAILY_WEBHOOK_URL"]


def send_daily(message: str) -> None:
    response = requests.post(
        DAILY_WEBHOOK_URL, json={"content": message}
    )
    response.raise_for_status()
