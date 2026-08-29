import time
from decimal import Decimal

from apps.briefing.app.collectors import bybit
from apps.briefing.app.db.tables import Doc, get_db
from apps.briefing.app.models.order import Order, all, save
from apps.briefing.app.outbounds import discord
from apps.briefing.app.services.order import map_order
from apps.briefing.app.services.order_message import (
    attach_position_context,
    format_order_message,
)

META_TABLE = "order_sync_meta"
META_KEY = "bybit_order_history"
DEFAULT_LOOKBACK_MS = 30 * 24 * 60 * 60 * 1000
BACKFILL_LOOKBACK_MS = 2 * 365 * 24 * 60 * 60 * 1000
ZERO = Decimal("0")


def _meta_table():
    return get_db().table(META_TABLE)


def get_last_synced_ms() -> int | None:
    rows = _meta_table().search(Doc.key == META_KEY)
    if not rows:
        return None
    return rows[0].get("last_end_ms")


def set_last_synced_ms(end_ms: int) -> None:
    _meta_table().upsert(
        {"key": META_KEY, "last_end_ms": end_ms},
        Doc.key == META_KEY,
    )


def _ms_now() -> int:
    return int(time.time() * 1000)


def _has_exec_qty(row: dict) -> bool:
    qty = row.get("cumExecQty")
    if qty is None or qty == "":
        return False
    return Decimal(str(qty)) > ZERO


def enrich_orders(*, start_ms: int, end_ms: int, session=None) -> dict:
    rows = bybit.fetch_closed_pnl(session=session, start_ms=start_ms, end_ms=end_ms)
    by_order_id = {str(row["orderId"]): row for row in rows if row.get("orderId")}

    updated = 0
    for order in all():
        if not order.reduce_only or order.realized_pnl is not None:
            continue
        row = by_order_id.get(order.order_id)
        if row is None:
            continue
        leverage = row.get("leverage")
        save(
            order.model_copy(
                update={
                    "realized_pnl": Decimal(str(row["closedPnl"])),
                    "leverage": str(leverage) if leverage not in (None, "") else None,
                }
            )
        )
        updated += 1

    return {"fetched": len(rows), "updated": updated}


def notify_orders(orders: list[Order], *, stdout_only: bool = False) -> int:
    posted = 0
    for order in sorted(
        attach_position_context(orders), key=lambda item: item.filled_at
    ):
        content = format_order_message(order)
        if stdout_only:
            print("---")
            print(content)
        else:
            discord.send_trade(f"```\n{content}\n```")
        posted += 1
    return posted


def sync_all(*, backfill: bool = False, session=None) -> dict:
    end_ms = _ms_now()

    if backfill:
        start_ms = end_ms - BACKFILL_LOOKBACK_MS
    else:
        last = get_last_synced_ms()
        if last is None:
            start_ms = end_ms - DEFAULT_LOOKBACK_MS
        else:
            start_ms = last

    if start_ms > end_ms:
        return {
            "fetched": 0,
            "saved": 0,
            "new_orders": [],
            "enriched": {"fetched": 0, "updated": 0},
            "start_ms": start_ms,
            "end_ms": end_ms,
        }

    rows = bybit.fetch_order_history(session=session, start_ms=start_ms, end_ms=end_ms)

    new_orders: list[Order] = []
    saved = 0
    for row in rows:
        if not _has_exec_qty(row):
            continue
        order = map_order(row)
        if save(order):
            new_orders.append(order)
        saved += 1

    set_last_synced_ms(end_ms)
    enriched = enrich_orders(start_ms=start_ms, end_ms=end_ms, session=session)
    return {
        "fetched": len(rows),
        "saved": saved,
        "new_orders": new_orders,
        "enriched": enriched,
        "start_ms": start_ms,
        "end_ms": end_ms,
    }
