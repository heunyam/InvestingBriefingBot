from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal

from apps.briefing.app.models.order import Order
from apps.briefing.app.utils.time import kst_now

ZERO = Decimal("0")


def _d(value) -> Decimal:
    if value is None or value == "":
        return ZERO
    return Decimal(str(value))


def _ms_to_datetime(ms: int | str) -> datetime:
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone(timedelta(hours=9)))


def _parse_side(raw: str) -> Literal["BUY", "SELL"]:
    side = (raw or "").strip().upper()
    if side == "BUY":
        return "BUY"
    if side == "SELL":
        return "SELL"
    raise ValueError(f"unsupported side: {raw!r}")


def _parse_fee(row: dict) -> Decimal:
    detail = row.get("cumFeeDetail") or {}
    if isinstance(detail, dict):
        usdt = detail.get("USDT")
        if usdt not in (None, ""):
            return _d(usdt)
    return _d(row.get("cumExecFee"))


def map_order(row: dict, *, synced_at: datetime | None = None) -> Order:
    synced_at = synced_at or kst_now()
    return Order(
        order_id=str(row["orderId"]),
        symbol=str(row["symbol"]),
        side=_parse_side(row.get("side") or ""),
        reduce_only=bool(row.get("reduceOnly")),
        order_type=str(row.get("orderType") or ""),
        quantity=_d(row.get("cumExecQty")),
        average_price=_d(row.get("avgPrice")),
        fee=_parse_fee(row),
        filled_at=_ms_to_datetime(row["updatedTime"]),
        created_at=_ms_to_datetime(row["createdTime"]),
        realized_pnl=None,
        leverage=None,
        synced_at=synced_at,
    )
