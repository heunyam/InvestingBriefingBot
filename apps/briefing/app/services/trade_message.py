from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

KST = timezone(timedelta(hours=9))
ZERO = Decimal("0")
PRICE_Q = Decimal("0.0001")


def _d(v) -> Decimal:
    if v is None or v == "":
        return ZERO
    return Decimal(str(v))


def _fmt_ms(ms: int | None) -> str:
    if not ms:
        return "-"
    dt = datetime.fromtimestamp(ms / 1000, tz=KST)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _fmt_price(value) -> str:
    d = _d(value).quantize(PRICE_Q, rounding=ROUND_HALF_UP)
    sign = "-" if d < ZERO else ""
    d = abs(d)
    text = format(d, "f")
    if "." in text:
        whole, frac = text.split(".", 1)
        frac = frac[:4].rstrip("0")
        whole = f"{int(whole):,}"
        return f"{sign}{whole}.{frac}" if frac else f"{sign}{whole}"
    return f"{sign}{int(text):,}"


def _fmt_qty(value) -> str:
    d = _d(value)
    if d == d.to_integral_value():
        return f"{int(d):,}"
    return _fmt_price(d)


def _fmt_money(value) -> str:
    n = _d(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return f"{int(n):,}"


def _fmt_roe(
    pnl: Decimal, price: Decimal, qty: Decimal, leverage: Decimal
) -> str | None:
    notional = price * qty
    if notional == ZERO or leverage == ZERO:
        return None
    roe = (pnl * leverage / notional) * Decimal("100")
    return f"{roe.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}%"


def _kr_side(side: str | None) -> str:
    if side == "LONG":
        return "롱"
    if side == "SHORT":
        return "숏"
    return side or "-"


def _dot(side: str | None) -> str:
    if side == "LONG":
        return "🟢"
    if side == "SHORT":
        return "🔴"
    return "⚪"


def _leverage(doc: dict) -> Decimal:
    return _d((doc.get("position") or {}).get("leverage"))


def _symbol_line(doc: dict) -> str:
    symbol = doc.get("symbol") or "-"
    side = doc.get("side")
    kr = _kr_side(side)
    lev = _leverage(doc)
    lev_s = (
        f"(x{int(lev)})"
        if lev != ZERO and lev == lev.to_integral_value()
        else (f"(x{lev})" if lev != ZERO else "")
    )
    return f"{_dot(side)} {kr}: {symbol}{lev_s}"


def _last_event(doc: dict) -> dict:
    events = doc.get("events") or []
    return events[-1] if events else {}


def _event_qty(ev: dict) -> Decimal:
    return abs(_d(ev.get("quantity")))


def _event_realized(ev: dict) -> Decimal:
    return _d(ev.get("cash_flow")) + _d(ev.get("realized_pnl"))


def _entry_qty(doc: dict) -> Decimal:
    total = ZERO
    for ev in doc.get("events") or []:
        if ev.get("event_type") in ("OPEN", "ADD"):
            total += _event_qty(ev)
    if total != ZERO:
        return total
    return abs(_d((doc.get("position") or {}).get("size")))


def format_trade_message(doc: dict) -> str:
    last = _last_event(doc)
    last_type = last.get("event_type")
    if doc.get("status") == "CLOSED":
        return _format_flat(doc, last)
    if last_type == "PARTIAL_CLOSE":
        return _format_partial(doc, last)
    return _format_open(doc, last)


def _header_time_price(doc: dict, last: dict) -> tuple[str, str]:
    price = (
        last.get("price")
        or (doc.get("prices") or {}).get("exit")
        or (doc.get("prices") or {}).get("entry")
    )
    ts = (
        last.get("occurred_at_ms") or doc.get("closed_at_ms") or doc.get("opened_at_ms")
    )
    return _fmt_price(price) if price not in (None, "") else "-", _fmt_ms(ts)


def _format_open(doc: dict, last: dict) -> str:
    kr = _kr_side(doc.get("side"))
    market, when = _header_time_price(doc, last)
    size = (doc.get("position") or {}).get("size")
    entry = (doc.get("prices") or {}).get("entry")
    lines = [
        f"{kr} 진입",
        "",
        _symbol_line(doc),
        f"📍 시장가: {market}",
        f"📦 수량: {_fmt_qty(size)}",
        f"💵 평단: {_fmt_price(entry) if entry else '-'}",
        "",
        f"⏰ {when}",
    ]
    return "\n".join(lines)


def _format_partial(doc: dict, last: dict) -> str:
    closed_qty = _event_qty(last)
    remain = abs(_d((doc.get("position") or {}).get("size")))
    before = remain + closed_qty
    realized = _event_realized(last)
    pnl = _d((doc.get("pnl") or {}).get("amount"))
    market, when = _header_time_price(doc, last)
    title = "부분 익절" if realized >= ZERO else "부분 손절"
    lines = [
        title,
        "",
        _symbol_line(doc),
        f"📍 시장가: {market}",
        f"📦 수량: {_fmt_qty(before)} → {_fmt_qty(remain)}",
        f"💰 실현: {_fmt_money(realized)}",
        f"📊 PNL: {_fmt_money(pnl)}",
    ]
    roe = _fmt_roe(realized, _d(last.get("price")), closed_qty, _leverage(doc))
    if roe is not None:
        lines.append(f"📈 ROE: {roe}")
    lines.extend(["", f"⏰ {when}"])
    return "\n".join(lines)


def _format_flat(doc: dict, last: dict) -> str:
    kr = _kr_side(doc.get("side"))
    pnl = _d((doc.get("pnl") or {}).get("amount"))
    title = f"{kr} 익절" if pnl >= ZERO else f"❌ {kr} 손절"
    market, when = _header_time_price(doc, last)
    qty = _entry_qty(doc)
    if qty == ZERO:
        qty = _event_qty(last)
    lines = [
        title,
        "",
        _symbol_line(doc),
        f"📍 시장가: {market}",
        f"💰 실현: {_fmt_money(pnl)}",
    ]
    roe = _fmt_roe(
        pnl,
        _d(last.get("price") or (doc.get("prices") or {}).get("exit")),
        qty,
        _leverage(doc),
    )
    if roe is not None:
        lines.append(f"📈 ROE: {roe}")
    lines.extend(["", f"⏰ {when}"])
    return "\n".join(lines)
