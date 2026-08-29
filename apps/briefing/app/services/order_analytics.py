from datetime import datetime, timedelta, timezone
from decimal import Decimal

from apps.briefing.app.models.order import Order, all

ZERO = Decimal("0")
DAY_MS = 24 * 60 * 60 * 1000
KST = timezone(timedelta(hours=9))
PERIOD_MS = {
    "7d": 7 * DAY_MS,
    "30d": 30 * DAY_MS,
    "all": None,
}


def period_bounds(period: str, now_ms: int) -> tuple[int | None, int]:
    if period not in PERIOD_MS:
        raise ValueError(f"unknown period: {period}")
    span = PERIOD_MS[period]
    start_ms = None if span is None else max(0, now_ms - span)
    return start_ms, now_ms


def _filled_at_ms(order: Order) -> int:
    return int(order.filled_at.timestamp() * 1000)


def is_stats_order(order: Order) -> bool:
    if not order.reduce_only:
        return False
    if order.realized_pnl is None or order.realized_pnl == ZERO:
        return False
    return True


def _result(order: Order) -> str | None:
    if order.realized_pnl is None or order.realized_pnl == ZERO:
        return None
    return "WIN" if order.realized_pnl > ZERO else "LOSS"


def select_stats_orders(
    orders: list[Order],
    *,
    start_ms: int | None,
    end_ms: int,
    symbol: str | None = None,
) -> list[Order]:
    selected = []
    for order in orders:
        if not is_stats_order(order):
            continue
        filled_ms = _filled_at_ms(order)
        if start_ms is not None and filled_ms < start_ms:
            continue
        if filled_ms > end_ms:
            continue
        if symbol and order.symbol != symbol:
            continue
        selected.append(order)
    selected.sort(key=_filled_at_ms)
    return selected


def select_fee_orders(
    orders: list[Order],
    *,
    start_ms: int | None,
    end_ms: int,
) -> list[Order]:
    selected = []
    for order in orders:
        filled_ms = _filled_at_ms(order)
        if start_ms is not None and filled_ms < start_ms:
            continue
        if filled_ms > end_ms:
            continue
        selected.append(order)
    return selected


def _win_rate(wins: int, losses: int) -> Decimal | None:
    denom = wins + losses
    if denom == 0:
        return None
    return Decimal(wins) / Decimal(denom)


def _streaks(results: list[str]) -> tuple[int, int]:
    max_win = 0
    max_loss = 0
    cur_win = 0
    cur_loss = 0
    for result in results:
        if result == "WIN":
            cur_win += 1
            cur_loss = 0
        elif result == "LOSS":
            cur_loss += 1
            cur_win = 0
        else:
            cur_win = 0
            cur_loss = 0
        max_win = max(max_win, cur_win)
        max_loss = max(max_loss, cur_loss)
    return max_win, max_loss


def _max_drawdown(pnls: list[Decimal]) -> Decimal:
    peak = ZERO
    equity = ZERO
    max_dd = ZERO
    for amount in pnls:
        equity += amount
        if equity > peak:
            peak = equity
        dd = equity - peak
        if dd < max_dd:
            max_dd = dd
    return max_dd


def _symbol_stats(orders: list[Order]) -> list[dict]:
    groups: dict[str, list[Order]] = {}
    for order in orders:
        groups.setdefault(order.symbol, []).append(order)
    rows = []
    for symbol in sorted(groups):
        items = groups[symbol]
        wins = sum(1 for order in items if _result(order) == "WIN")
        losses = sum(1 for order in items if _result(order) == "LOSS")
        net = sum((order.realized_pnl or ZERO) for order in items)
        rows.append(
            {
                "symbol": symbol,
                "n": len(items),
                "win_rate": _win_rate(wins, losses),
                "net_pnl": net,
            }
        )
    return rows


def summarize(
    orders: list[Order] | None = None,
    *,
    period: str = "7d",
    now_ms: int,
    symbol: str | None = None,
) -> dict:
    start_ms, end_ms = period_bounds(period, now_ms)
    source = orders if orders is not None else all()
    selected = select_stats_orders(
        source, start_ms=start_ms, end_ms=end_ms, symbol=symbol
    )
    fee_orders = select_fee_orders(source, start_ms=start_ms, end_ms=end_ms)
    n = len(selected)
    pnls = [order.realized_pnl or ZERO for order in selected]
    results = [_result(order) for order in selected]
    wins = sum(1 for result in results if result == "WIN")
    losses = sum(1 for result in results if result == "LOSS")
    gross_profit = sum((p for p in pnls if p > ZERO), ZERO)
    gross_loss = sum((p for p in pnls if p < ZERO), ZERO)
    net = sum(pnls, ZERO)
    win_streak, loss_streak = _streaks([r for r in results if r in ("WIN", "LOSS")])
    return {
        "period": period,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "n": n,
        "wins": wins,
        "losses": losses,
        "win_rate": _win_rate(wins, losses),
        "net_pnl": net,
        "profit_factor": (
            None if gross_loss == ZERO else gross_profit / abs(gross_loss)
        ),
        "avg_win": None if wins == 0 else gross_profit / wins,
        "avg_loss": None if losses == 0 else gross_loss / losses,
        "expectancy": None if n == 0 else net / n,
        "max_win_streak": win_streak,
        "max_loss_streak": loss_streak,
        "max_drawdown": _max_drawdown(pnls),
        "fees": sum((order.fee for order in fee_orders), ZERO),
        "by_symbol": _symbol_stats(selected),
    }
