from decimal import Decimal

from app.models.db import Doc, trades_table

ZERO = Decimal("0")


def event_key(symbol, seq, exec_id=None, order_id=None) -> str:
    extra = exec_id or order_id or ""
    return f"{symbol}:{seq}:{extra}"


def new_trade(
    trade_id: str, symbol: str, side: str, opened_at_ms: int, now_ms: int
) -> dict:
    return {
        "trade_id": trade_id,
        "symbol": symbol,
        "side": side,
        "status": "OPEN",
        "opened_at_ms": opened_at_ms,
        "closed_at_ms": None,
        "prices": {"entry": None, "exit": None},
        "pnl": {"amount": None, "result": None},
        "position": {"size": "0", "leverage": None},
        "discord": {"message_id": None},
        "events": [],
        "protections": [],
        "review": None,
        "stats_eligible": True,
        "created_at_ms": now_ms,
        "updated_at_ms": now_ms,
    }


def _d(v) -> Decimal:
    if v is None or v == "":
        return ZERO
    return Decimal(str(v))


def _s(v) -> str | None:
    if v is None:
        return None
    return str(v)


def weighted_avg(fills: list[tuple[Decimal, Decimal]]) -> Decimal | None:
    qty = sum((q for _, q in fills), ZERO)
    if qty == ZERO:
        return None
    return sum((p * q for p, q in fills), ZERO) / qty


def sign_pnl(amount: Decimal | None) -> str | None:
    if amount is None or amount == ZERO:
        return None
    return "WIN" if amount > ZERO else "LOSS"


def recompute(doc: dict) -> dict:
    entry_fills = []
    exit_fills = []
    cash_flow = ZERO
    funding = ZERO
    fee = ZERO
    size = ZERO

    for ev in doc.get("events") or []:
        price = _d(ev.get("price"))
        qty = _d(ev.get("quantity"))
        fee += _d(ev.get("fee"))
        cash_flow += _d(ev.get("cash_flow"))
        funding += _d(ev.get("funding"))
        cash_flow += _d(ev.get("realized_pnl"))
        kind = ev.get("event_type")
        if kind in ("OPEN", "ADD"):
            entry_fills.append((price, qty))
            size += qty
        elif kind in ("PARTIAL_CLOSE", "CLOSE"):
            exit_fills.append((price, qty))
            size -= qty

    entry = weighted_avg(entry_fills)
    exit_ = weighted_avg(exit_fills)
    amount = None
    if doc.get("events") and (
        cash_flow != ZERO or funding != ZERO or fee != ZERO or exit_fills
    ):
        amount = cash_flow + funding - fee

    closed = size == ZERO and bool(exit_fills)
    doc["prices"] = {"entry": _s(entry), "exit": _s(exit_)}
    doc["pnl"] = {"amount": _s(amount), "result": sign_pnl(amount)}
    pos = doc.get("position") or {}
    pos["size"] = str(size)
    doc["position"] = pos
    doc["status"] = "CLOSED" if closed else "OPEN"
    if closed:
        last = doc["events"][-1]
        doc["closed_at_ms"] = last.get("occurred_at_ms")
    else:
        doc["closed_at_ms"] = None
    return doc


def upsert_event(doc: dict, event: dict, now_ms: int) -> dict:
    events = list(doc.get("events") or [])
    key = event["event_key"]
    replaced = False
    for i, existing in enumerate(events):
        if existing.get("event_key") == key:
            events[i] = event
            replaced = True
            break
    if not replaced:
        events.append(event)
    doc["events"] = events
    doc["updated_at_ms"] = now_ms
    return recompute(doc)


def upsert_protection(doc: dict, protection: dict, now_ms: int) -> dict:
    items = list(doc.get("protections") or [])
    oid = protection["bybit_order_id"]
    replaced = False
    for i, existing in enumerate(items):
        if existing.get("bybit_order_id") == oid:
            items[i] = protection
            replaced = True
            break
    if not replaced:
        items.append(protection)
    doc["protections"] = items
    doc["updated_at_ms"] = now_ms
    return doc


def save(doc: dict) -> None:
    trades_table().upsert(doc, Doc.trade_id == doc["trade_id"])


def load(trade_id: str) -> dict | None:
    rows = trades_table().search(Doc.trade_id == trade_id)
    return dict(rows[0]) if rows else None


def all() -> list[dict]:
    return [dict(row) for row in trades_table().all()]
