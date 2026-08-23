import os
import requests
from dotenv import load_dotenv

load_dotenv()

RANDOM_WEBHOOK_URL = os.getenv("DISCORD_RANDOM_WEBHOOK_URL")
DAILY_WEBHOOK_URL = os.getenv("DISCORD_DAILY_WEBHOOK_URL")
NEWS_WEBHOOK_URL = os.getenv("DISCORD_NEWS_WEBHOOK_URL")


def send_message(message: str) -> None:
    response = requests.post(RANDOM_WEBHOOK_URL, json={"content": message})
    response.raise_for_status()


def send_daily(message: str) -> None:
    response = requests.post(DAILY_WEBHOOK_URL, json={"content": message})
    response.raise_for_status()


DISCORD_LIMIT = 2000


def send_news(content: str):
    if not content:
        return
    for chunk in _split(content):
        r = requests.post(NEWS_WEBHOOK_URL, json={"content": chunk})
        r.raise_for_status()


def _split(content: str) -> list[str]:
    if len(content) <= DISCORD_LIMIT:
        return [content]

    chunks = []
    lines = content.split("\n")
    current = ""

    for line in lines:
        if len(current) + len(line) + 1 > DISCORD_LIMIT:
            chunks.append(current.strip())
            current = ""
        current += line + "\n"

    if current.strip():
        chunks.append(current.strip())

    return chunks
