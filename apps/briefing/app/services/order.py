import time
from decimal import Decimal

from apps.briefing.app.collectors import bybit
from apps.briefing.app.db.tables import Doc, get_db
from apps.briefing.app.models.order import Order
from apps.briefing.app.outbounds import discord
from apps.briefing.app.utils.decimal import d
from apps.briefing.app.utils.format import fmt_decimal, fmt_money, fmt_roe
from apps.briefing.app.utils.time import from_ms, kst_now

ZERO = Decimal(0)

META_TABLE = "order_sync_meta"
META_KEY = "bybit_order_history"
DEFAULT_LOOKBACK_MS = 30 * 24 * 60 * 60 * 1000
BACKFILL_LOOKBACK_MS = 2 * 365 * 24 * 60 * 60 * 1000


def map_order(row: dict, *, synced_at=None) -> Order:
    synced_at = synced_at or kst_now()
    side = (row.get("side") or "").strip().upper()
    if side not in ("BUY", "SELL"):
        raise ValueError(f"unsupported side: {row.get('side')!r}")

    detail = row.get("cumFeeDetail") or {}
    if isinstance(detail, dict) and detail.get("USDT") not in (None, ""):
        fee = d(detail["USDT"])
    else:
        fee = d(row.get("cumExecFee"))

    return Order(
        order_id=str(row["orderId"]),
        symbol=str(row["symbol"]),
        side=side,
        reduce_only=bool(row.get("reduceOnly")),
        order_type=str(row.get("orderType") or ""),
        quantity=d(row.get("cumExecQty")),
        average_price=d(row.get("avgPrice")),
        fee=fee,
        filled_at=from_ms(row["updatedTime"]),
        created_at=from_ms(row["createdTime"]),
        realized_pnl=None,
        leverage=None,
        synced_at=synced_at,
    )


def attach_position_context(orders: list[Order]) -> list[Order]:
    by_symbol: dict[str, Decimal] = {}
    avg_by_symbol: dict[str, Decimal] = {}
    context: dict[str, dict] = {}

    for order in sorted(
        orders, key=lambda item: (item.filled_at, item.created_at, item.order_id)
    ):
        long = order.side == "SELL" if order.reduce_only else order.side == "BUY"
        if order.reduce_only:
            delta = -order.quantity if long else order.quantity
        else:
            delta = order.quantity if long else -order.quantity

        pos_before = by_symbol.get(order.symbol, ZERO)
        pos_after = pos_before + delta
        before = abs(pos_before)
        after = abs(pos_after)

        if (
            not order.reduce_only
            and pos_before != ZERO
            and (pos_before > ZERO) == (delta > ZERO)
        ):
            avg = avg_by_symbol[order.symbol]
            added = abs(delta)
            avg = (before * avg + added * order.average_price) / (before + added)
        elif not order.reduce_only and pos_before == ZERO:
            avg = order.average_price
        else:
            avg = avg_by_symbol.get(order.symbol, order.average_price)

        context[order.order_id] = {
            "position_qty_before": before,
            "position_qty_after": after,
            "position_avg_price": avg,
        }
        by_symbol[order.symbol] = pos_after
        if pos_after != ZERO:
            avg_by_symbol[order.symbol] = avg

    return [
        order.model_copy(update=context.get(order.order_id, {})) for order in orders
    ]


def format_order_message(order: Order) -> str:
    long = order.side == "SELL" if order.reduce_only else order.side == "BUY"
    kr = "롱" if long else "숏"
    dot = "🟢" if long else "🔴"
    lev = f"(x{order.leverage})" if order.leverage else ""
    price = fmt_decimal(order.average_price)
    avg = fmt_decimal(order.position_avg_price or order.average_price)
    when = order.filled_at.strftime("%Y-%m-%d %H:%M:%S")
    symbol = f"{dot} {kr}: {order.symbol}{lev}"
    before = order.position_qty_before
    after = order.position_qty_after

    if not order.reduce_only:
        is_add = before is not None and before > ZERO
        title = f"{kr} 추가 진입" if is_add else f"{kr} 진입"
        qty = (
            f"📦 수량: {fmt_decimal(before)} → {fmt_decimal(after)}"
            if is_add and after is not None
            else f"📦 수량: {fmt_decimal(order.quantity)}"
        )
        return "\n".join(
            [
                title,
                "",
                symbol,
                f"📍 시장가: {price}",
                qty,
                f"💵 평단: {avg}",
                "",
                f"⏰ {when}",
            ]
        )

    pnl = order.realized_pnl or ZERO
    partial = after is not None and after > ZERO
    if partial:
        title = f"{kr} 분할 익절" if pnl >= ZERO else f"❌ {kr} 분할 손절"
    else:
        title = f"{kr} 익절" if pnl >= ZERO else f"❌ {kr} 손절"

    lines = [title, "", symbol, f"📍 시장가: {price}"]
    if partial and before is not None:
        lines.append(f"📦 수량: {fmt_decimal(before)} → {fmt_decimal(after)}")
    lines.append(f"💰 실현: {fmt_money(pnl)}")
    if roe := fmt_roe(pnl, order.average_price, order.quantity, order.leverage):
        lines.append(f"📈 ROE: {roe}")
    lines.extend(["", f"⏰ {when}"])
    return "\n".join(lines)


def enrich_orders(*, start_ms: int, end_ms: int, session=None) -> dict:
    rows = bybit.fetch_closed_pnl(session=session, start_ms=start_ms, end_ms=end_ms)
    by_order_id = {str(row["orderId"]): row for row in rows if row.get("orderId")}

    updated = 0
    for order in Order.all():
        if not order.reduce_only or order.realized_pnl is not None:
            continue
        row = by_order_id.get(order.order_id)
        if row is None:
            continue
        leverage = row.get("leverage")
        Order.save(
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


def sync_all(*, backfill: bool = False, session=None, dry_run: bool = False) -> dict:
    end_ms = int(time.time() * 1000)

    if backfill:
        start_ms = end_ms - BACKFILL_LOOKBACK_MS
    else:
        rows = get_db().table(META_TABLE).search(Doc.key == META_KEY)
        last = rows[0].get("last_end_ms") if rows else None
        start_ms = end_ms - DEFAULT_LOOKBACK_MS if last is None else last

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
        qty = row.get("cumExecQty")
        if qty in (None, "") or d(qty) <= ZERO:
            continue
        order = map_order(row)
        if dry_run:
            if Order.load(order.order_id) is None:
                new_orders.append(order)
            saved += 1
            continue
        if Order.save(order):
            new_orders.append(order)
        saved += 1

    if dry_run:
        return {
            "fetched": len(rows),
            "saved": saved,
            "new_orders": new_orders,
            "enriched": {"fetched": 0, "updated": 0},
            "start_ms": start_ms,
            "end_ms": end_ms,
        }

    get_db().table(META_TABLE).upsert(
        {"key": META_KEY, "last_end_ms": end_ms},
        Doc.key == META_KEY,
    )
    enriched = enrich_orders(start_ms=start_ms, end_ms=end_ms, session=session)
    return {
        "fetched": len(rows),
        "saved": saved,
        "new_orders": new_orders,
        "enriched": enriched,
        "start_ms": start_ms,
        "end_ms": end_ms,
    }
