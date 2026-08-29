from decimal import Decimal

from apps.briefing.app.collectors import bybit_orders
from apps.briefing.app.models.order import all, save


def enrich_orders(*, start_ms: int, end_ms: int, session=None) -> dict:
    rows = bybit_orders.fetch_closed_pnl(
        session=session, start_ms=start_ms, end_ms=end_ms
    )
    by_order_id = {str(row["orderId"]): row for row in rows if row.get("orderId")}

    matched = 0
    updated = 0
    for order in all():
        if not order.reduce_only or order.realized_pnl is not None:
            continue
        row = by_order_id.get(order.order_id)
        if row is None:
            continue
        matched += 1
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

    return {"fetched": len(rows), "matched": matched, "updated": updated}
