from decimal import Decimal, ROUND_HALF_UP


def fmt_decimal(value) -> str:
    if value is None:
        return "-"
    text = f"{Decimal(str(value)):,.4f}".rstrip("0").rstrip(".")
    return text or "0"


def fmt_money(value) -> str:
    if value is None:
        return "-"
    n = Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return f"{int(n):,}"


def fmt_pct(value) -> str:
    if value is None:
        return "-"
    return f"{float(value) * 100:.1f}%"


def fmt_roe(pnl, price, qty, leverage) -> str | None:
    if not leverage:
        return None
    lev = Decimal(str(leverage))
    notional = Decimal(str(price)) * Decimal(str(qty))
    if notional == 0 or lev == 0:
        return None
    roe = (Decimal(str(pnl)) * lev / notional) * Decimal("100")
    return f"{roe.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}%"
