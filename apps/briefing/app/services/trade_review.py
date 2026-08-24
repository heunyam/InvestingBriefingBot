import os
import time

from app.models import db, trade
from app.services import trade_sync

CHART_DIR = os.path.join(db.DATA_DIR, "charts")
ALLOWED_CHART_EXTS = {"png", "jpg", "jpeg", "webp", "gif"}


def is_closed_pending_review(doc: dict) -> bool:
    return doc.get("status") == "CLOSED" and trade_sync.needs_user_review(doc)


def pending_closed_reviews() -> list[dict]:
    return [doc for doc in trade.all() if is_closed_pending_review(doc)]


def _chart_ext(filename: str) -> str:
    ext = os.path.splitext(filename or "")[1].lstrip(".").lower()
    if ext == "jpeg":
        ext = "jpg"
    if ext not in ALLOWED_CHART_EXTS:
        raise ValueError("chart must be an image (png, jpg, webp, gif)")
    return ext


def save_chart_bytes(trade_id: str, data: bytes, filename: str) -> str:
    if not data:
        raise ValueError("chart image is required")
    ext = _chart_ext(filename)
    os.makedirs(CHART_DIR, exist_ok=True)
    path = os.path.join(CHART_DIR, f"{trade_id}.{ext}")
    with open(path, "wb") as fh:
        fh.write(data)
    return os.path.join("charts", f"{trade_id}.{ext}")


def resolve_trade(query: str) -> dict:
    q = (query or "").strip()
    if not q:
        raise ValueError("trade id is required")
    exact = trade.load(q)
    if exact is not None:
        return exact
    matches = [d for d in trade.all() if (d.get("trade_id") or "").startswith(q)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise KeyError(f"trade not found: {query}")
    raise ValueError(f"ambiguous trade id prefix: {query}")


def save_cli_review(
    doc: dict,
    *,
    entry_reason: str,
    exit_reason: str,
    chart_path: str | None = None,
    now_ms: int | None = None,
) -> dict:
    entry = (entry_reason or "").strip()
    exit_ = (exit_reason or "").strip()
    if not entry or not exit_:
        raise ValueError("entry_reason and exit_reason are required")
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    existing = doc.get("review") or {}
    chart = existing.get("chart")
    if chart_path:
        with open(chart_path, "rb") as fh:
            data = fh.read()
        storage_key = save_chart_bytes(
            doc["trade_id"], data, os.path.basename(chart_path)
        )
        chart = {"storage_key": storage_key}
    doc["review"] = {
        "entry_reason": entry,
        "exit_reason": exit_,
        "chart": chart,
        "created_at_ms": existing.get("created_at_ms") or now_ms,
        "updated_at_ms": now_ms,
    }
    doc["updated_at_ms"] = now_ms
    trade.save(doc)
    return doc
