from decimal import Decimal

from apps.briefing.app.models.order import Order
from apps.briefing.app.utils.format import fmt_decimal, fmt_money, fmt_roe

ZERO = Decimal("0")


def _signed_delta(order: Order) -> Decimal:
    long = (order.side == "BUY") ^ order.reduce_only
    if order.reduce_only:
        return -order.quantity if long else order.quantity
    return order.quantity if long else -order.quantity


def attach_position_context(orders: list[Order]) -> list[Order]:
    by_symbol: dict[str, Decimal] = {}
    avg_by_symbol: dict[str, Decimal] = {}
    context: dict[str, dict] = {}

    for order in sorted(
        orders, key=lambda item: (item.filled_at, item.created_at, item.order_id)
    ):
        pos_before = by_symbol.get(order.symbol, ZERO)
        delta = _signed_delta(order)
        pos_after = pos_before + delta
        before = abs(pos_before)
        after = abs(pos_after)

        if not order.reduce_only and pos_before != ZERO and (pos_before > ZERO) == (delta > ZERO):
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
    long = (order.side == "BUY") ^ order.reduce_only
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
            [title, "", symbol, f"📍 시장가: {price}", qty, f"💵 평단: {avg}", "", f"⏰ {when}"]
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
