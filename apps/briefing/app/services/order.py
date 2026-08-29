from typing import Literal

from apps.briefing.app.models.order import Order
from apps.briefing.app.utils.decimal import d
from apps.briefing.app.utils.time import from_ms, kst_now


def _parse_side(raw: str) -> Literal["BUY", "SELL"]:
    side = (raw or "").strip().upper()
    if side == "BUY":
        return "BUY"
    if side == "SELL":
        return "SELL"
    raise ValueError(f"unsupported side: {raw!r}")


def _parse_fee(row: dict):
    detail = row.get("cumFeeDetail") or {}
    if isinstance(detail, dict):
        usdt = detail.get("USDT")
        if usdt not in (None, ""):
            return d(usdt)
    return d(row.get("cumExecFee"))


def map_order(row: dict, *, synced_at=None) -> Order:
    synced_at = synced_at or kst_now()
    return Order(
        order_id=str(row["orderId"]),
        symbol=str(row["symbol"]),
        side=_parse_side(row.get("side") or ""),
        reduce_only=bool(row.get("reduceOnly")),
        order_type=str(row.get("orderType") or ""),
        quantity=d(row.get("cumExecQty")),
        average_price=d(row.get("avgPrice")),
        fee=_parse_fee(row),
        filled_at=from_ms(row["updatedTime"]),
        created_at=from_ms(row["createdTime"]),
        realized_pnl=None,
        leverage=None,
        synced_at=synced_at,
    )
