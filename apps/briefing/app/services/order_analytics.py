from decimal import Decimal

from apps.briefing.app.models.order import Order, all

ZERO = Decimal("0")
DAY_MS = 24 * 60 * 60 * 1000
PERIOD_MS = {"7d": 7 * DAY_MS, "30d": 30 * DAY_MS, "all": None}
PERIOD_TITLE = {"7d": "최근 7일", "30d": "최근 30일", "all": "전체"}


def _filled_at_ms(order: Order) -> int:
    return int(order.filled_at.timestamp() * 1000)


def _in_period(order: Order, start_ms: int | None, end_ms: int) -> bool:
    filled_ms = _filled_at_ms(order)
    if start_ms is not None and filled_ms < start_ms:
        return False
    return filled_ms <= end_ms


def summarize(
    orders: list[Order] | None = None,
    *,
    period: str = "7d",
    now_ms: int,
    symbol: str | None = None,
) -> dict:
    if period not in PERIOD_MS:
        raise ValueError(f"unknown period: {period}")
    span = PERIOD_MS[period]
    start_ms = None if span is None else max(0, now_ms - span)

    n = wins = losses = 0
    net_pnl = fees = ZERO
    for order in orders if orders is not None else all():
        if not _in_period(order, start_ms, now_ms):
            continue
        if symbol and order.symbol != symbol:
            continue
        fees += order.fee
        if (
            not order.reduce_only
            or order.realized_pnl is None
            or order.realized_pnl == ZERO
        ):
            continue
        n += 1
        net_pnl += order.realized_pnl
        if order.realized_pnl > ZERO:
            wins += 1
        else:
            losses += 1

    denom = wins + losses
    win_rate = None if denom == 0 else Decimal(wins) / Decimal(denom)
    return {
        "period": period,
        "title": PERIOD_TITLE.get(period, period),
        "n": n,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "net_pnl": net_pnl,
        "fees": fees,
    }
