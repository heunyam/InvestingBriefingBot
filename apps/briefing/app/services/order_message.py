from decimal import Decimal, ROUND_HALF_UP

from apps.briefing.app.models.order import Order

ZERO = Decimal("0")
MONEY_Q = Decimal("0.0001")


def _fmt_money(value: Decimal | None) -> str:
    if value is None:
        return "-"
    d = Decimal(str(value)).quantize(MONEY_Q, rounding=ROUND_HALF_UP)
    sign = "-" if d < ZERO else ""
    d = abs(d)
    text = format(d, "f")
    if "." in text:
        whole, frac = text.split(".", 1)
        frac = frac[:4].rstrip("0")
        whole = f"{int(whole):,}"
        body = f"{whole}.{frac}" if frac else whole
    else:
        body = f"{int(text):,}"
    return f"{sign}{body}"


def _fmt_qty(value: Decimal) -> str:
    if value == value.to_integral_value():
        return f"{int(value):,}"
    return _fmt_money(value)


def _side_label(order: Order) -> str:
    if order.side == "BUY":
        return "매수"
    return "매도"


def _role_label(order: Order) -> str:
    return "청산" if order.reduce_only else "진입"


def format_order_message(order: Order) -> str:
    lines = [
        f"{_role_label(order)} · {_side_label(order)} {order.symbol}",
    ]
    if order.leverage:
        lines[0] += f" (x{order.leverage})"
    lines.extend(
        [
            f"유형: {order.order_type}",
            f"수량: {_fmt_qty(order.quantity)} · 가격: {_fmt_money(order.average_price)}",
            f"수수료: {_fmt_money(order.fee)}",
        ]
    )
    if order.reduce_only and order.realized_pnl is not None:
        lines.append(f"실현손익: {_fmt_money(order.realized_pnl)}")
    lines.append(f"체결: {order.filled_at.strftime('%Y-%m-%d %H:%M:%S')}")
    return "\n".join(lines)
