import os

import requests
from dotenv import load_dotenv

load_dotenv()


def _as_code_block(content: str) -> str:
    text = (content or "").rstrip()
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        return stripped
    return f"```\n{text}\n```"


def _trade_webhook_url() -> str:
    url = os.environ.get("DISCORD_TRADE_WEBHOOK_URL") or ""
    if not url:
        raise KeyError("DISCORD_TRADE_WEBHOOK_URL is not set")
    return url


def send_trade(content: str) -> str:
    """Post a trade message. Returns Discord message id."""
    response = requests.post(
        _trade_webhook_url() + "?wait=true",
        json={"content": _as_code_block(content)},
        timeout=30,
    )
    response.raise_for_status()
    return str(response.json()["id"])


def edit_trade(message_id: str, content: str) -> str:
    url = _trade_webhook_url()
    response = requests.patch(
        f"{url}/messages/{message_id}?wait=true",
        json={"content": _as_code_block(content)},
        timeout=30,
    )
    response.raise_for_status()
    return str(response.json().get("id") or message_id)


def delete_trade(message_id: str) -> None:
    """Delete a webhook-owned trade message. 404 is ignored."""
    url = _trade_webhook_url()
    response = requests.delete(f"{url}/messages/{message_id}", timeout=30)
    if response.status_code in (200, 204, 404):
        return
    response.raise_for_status()
