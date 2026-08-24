from decimal import Decimal

from app.models import trade

ZERO = Decimal("0")
DAY_MS = 24 * 60 * 60 * 1000
PERIOD_MS = {
    "7d": 7 * DAY_MS,
    "30d": 30 * DAY_MS,
    "all": None,
}


def _d(v) -> Decimal | None:
    if v is None or v == "":
        return None
    return Decimal(str(v))


def period_bounds(period: str, now_ms: int) -> tuple[int | None, int]:
    if period not in PERIOD_MS:
        raise ValueError(f"unknown period: {period}")
    span = PERIOD_MS[period]
    start_ms = None if span is None else max(0, now_ms - span)
    return start_ms, now_ms


def _event_sum(doc: dict, field: str) -> Decimal:
    total = ZERO
    for ev in doc.get("events") or []:
        total += _d(ev.get(field)) or ZERO
    return total


def is_reviewed(doc: dict) -> bool:
    review = doc.get("review") or {}
    return bool(review.get("entry_reason") and review.get("exit_reason"))


def pnl_amount(doc: dict) -> Decimal | None:
    return _d((doc.get("pnl") or {}).get("amount"))


def is_stats_trade(doc: dict) -> bool:
    if doc.get("status") != "CLOSED":
        return False
    if doc.get("stats_eligible") is False:
        return False
    amount = pnl_amount(doc)
    if amount is None or amount == ZERO:
        return False
    return True


def select_closed(
    docs: list[dict],
    *,
    start_ms: int | None,
    end_ms: int,
    symbol: str | None = None,
) -> list[dict]:
    selected = []
    for doc in docs:
        if not is_stats_trade(doc):
            continue
        closed_at = doc.get("closed_at_ms")
        if closed_at is None:
            continue
        closed_at = int(closed_at)
        if start_ms is not None and closed_at < start_ms:
            continue
        if closed_at > end_ms:
            continue
        if symbol and doc.get("symbol") != symbol:
            continue
        selected.append(doc)
    selected.sort(key=lambda d: int(d.get("closed_at_ms") or 0))
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


def _symbol_stats(docs: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for doc in docs:
        groups.setdefault(doc["symbol"], []).append(doc)
    rows = []
    for symbol in sorted(groups):
        items = groups[symbol]
        wins = sum(1 for d in items if (d.get("pnl") or {}).get("result") == "WIN")
        losses = sum(1 for d in items if (d.get("pnl") or {}).get("result") == "LOSS")
        net = sum((pnl_amount(d) or ZERO) for d in items)
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
    docs: list[dict] | None = None,
    *,
    period: str = "7d",
    now_ms: int,
    symbol: str | None = None,
) -> dict:
    start_ms, end_ms = period_bounds(period, now_ms)
    selected = select_closed(
        docs if docs is not None else trade.all(),
        start_ms=start_ms,
        end_ms=end_ms,
        symbol=symbol,
    )
    n = len(selected)
    pnls = [pnl_amount(d) or ZERO for d in selected]
    results = [(d.get("pnl") or {}).get("result") for d in selected]
    wins = sum(1 for r in results if r == "WIN")
    losses = sum(1 for r in results if r == "LOSS")
    gross_profit = sum((p for p in pnls if p > ZERO), ZERO)
    gross_loss = sum((p for p in pnls if p < ZERO), ZERO)
    net = sum(pnls, ZERO)
    win_streak, loss_streak = _streaks([r for r in results if r in ("WIN", "LOSS")])
    reviewed = sum(1 for d in selected if is_reviewed(d))
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
        "fees": sum((_event_sum(d, "fee") for d in selected), ZERO),
        "funding": sum((_event_sum(d, "funding") for d in selected), ZERO),
        "review_rate": None if n == 0 else Decimal(reviewed) / Decimal(n),
        "by_symbol": _symbol_stats(selected),
    }
