import os
import requests
from dotenv import load_dotenv

load_dotenv()

DAILY_WEBHOOK_URL = os.environ["DISCORD_DAILY_WEBHOOK_URL"]


def _as_code_block(content: str) -> str:
    text = (content or "").rstrip()
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        return stripped
    return f"```\n{text}\n```"


def send_daily(message: str) -> None:
    response = requests.post(
        DAILY_WEBHOOK_URL, json={"content": _as_code_block(message)}
    )
    response.raise_for_status()
