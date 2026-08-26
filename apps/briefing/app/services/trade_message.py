from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

KST = timezone(timedelta(hours=9))
ZERO = Decimal("0")
PRICE_Q = Decimal("0.0001")
NOTIFY_EVENT_TYPES = frozenset({"OPEN", "ADD", "PARTIAL_CLOSE", "CLOSE"})
ENTRY_EVENT_TYPES = frozenset({"OPEN", "ADD"})
EXIT_EVENT_TYPES = frozenset({"PARTIAL_CLOSE", "CLOSE"})
# order_id 없을 때만: 연속 체결 gap 이내면 같은 Discord 묶음 (분할체결 폴백)
COALESCE_GAP_MS = 120_000


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


def _events_through(doc: dict, event: dict) -> list[dict]:
    events = list(doc.get("events") or [])
    key = event.get("event_key")
    if key:
        out = []
        for ev in events:
            out.append(ev)
            if ev.get("event_key") == key:
                return out
    # Fallback: match by identity / last occurrence of same type+time.
    out = []
    for ev in events:
        out.append(ev)
        if ev is event or (
            ev.get("event_type") == event.get("event_type")
            and ev.get("occurred_at_ms") == event.get("occurred_at_ms")
            and ev.get("quantity") == event.get("quantity")
        ):
            return out
    return events


def _size_after(events: list[dict]) -> Decimal:
    size = ZERO
    for ev in events:
        qty = _event_qty(ev)
        kind = ev.get("event_type")
        if kind in ("OPEN", "ADD"):
            size += qty
        elif kind in ("PARTIAL_CLOSE", "CLOSE"):
            size -= qty
    return size


def _entry_qty_through(events: list[dict]) -> Decimal:
    total = ZERO
    for ev in events:
        if ev.get("event_type") in ("OPEN", "ADD"):
            total += _event_qty(ev)
    return total


def _entry_qty(doc: dict) -> Decimal:
    total = _entry_qty_through(doc.get("events") or [])
    if total != ZERO:
        return total
    return abs(_d((doc.get("position") or {}).get("size")))


def _pnl_through(events: list[dict]) -> Decimal | None:
    cash_flow = ZERO
    funding = ZERO
    fee = ZERO
    exit_fills = False
    for ev in events:
        fee += _d(ev.get("fee"))
        cash_flow += _d(ev.get("cash_flow"))
        funding += _d(ev.get("funding"))
        cash_flow += _d(ev.get("realized_pnl"))
        if ev.get("event_type") in ("PARTIAL_CLOSE", "CLOSE"):
            exit_fills = True
    if not events or not (
        cash_flow != ZERO or funding != ZERO or fee != ZERO or exit_fills
    ):
        return None
    return cash_flow + funding - fee


def format_trade_message(doc: dict, event: dict | None = None) -> str:
    """Format one Discord body. If event is set, use that fill (not only the last)."""
    last = event or _last_event(doc)
    last_type = last.get("event_type")
    if last_type == "CLOSE":
        return _format_flat(doc, last)
    if last_type == "PARTIAL_CLOSE":
        return _format_partial(doc, last)
    if last_type == "ADD":
        return _format_add(doc, last)
    return _format_open(doc, last)


def _notify_family(event_type: str | None) -> str | None:
    if event_type in ENTRY_EVENT_TYPES:
        return "ENTRY"
    if event_type in EXIT_EVENT_TYPES:
        return "EXIT"
    return None


def _same_notify_burst(prev: dict, nxt: dict) -> bool:
    """Same ENTRY/EXIT family + (same order_id, or both missing order_id within gap)."""
    if _notify_family(prev.get("event_type")) != _notify_family(nxt.get("event_type")):
        return False
    oid_a = str(prev.get("order_id") or "").strip()
    oid_b = str(nxt.get("order_id") or "").strip()
    if oid_a and oid_b:
        return oid_a == oid_b
    if oid_a or oid_b:
        return False
    ta = int(prev.get("occurred_at_ms") or 0)
    tb = int(nxt.get("occurred_at_ms") or 0)
    if tb < ta:
        return False
    return (tb - ta) <= COALESCE_GAP_MS


def iter_notify_bursts(events: list[dict], already: set[str]) -> list[list[dict]]:
    """Group unposted notify events into Discord bursts."""
    pending = []
    for ev in events:
        etype = ev.get("event_type")
        if etype not in NOTIFY_EVENT_TYPES:
            continue
        key = ev.get("event_key")
        if not key or key in already:
            continue
        pending.append(ev)

    bursts: list[list[dict]] = []
    current: list[dict] = []
    for ev in pending:
        if current and _same_notify_burst(current[-1], ev):
            current.append(ev)
            continue
        if current:
            bursts.append(current)
        current = [ev]
    if current:
        bursts.append(current)
    return bursts


def iter_all_notify_bursts(events: list[dict]) -> list[list[dict]]:
    """Like iter_notify_bursts but includes already-posted events (for repair)."""
    return iter_notify_bursts(events, already=set())


def message_event_keys(message: dict) -> list[str]:
    keys = []
    for k in message.get("event_keys") or []:
        if k:
            keys.append(str(k))
    if message.get("event_key") and str(message["event_key"]) not in keys:
        keys.insert(0, str(message["event_key"]))
    return keys


def _burst_vwap(events: list[dict]) -> Decimal | None:
    fills = []
    for ev in events:
        price = _d(ev.get("price"))
        qty = _event_qty(ev)
        if qty == ZERO:
            continue
        fills.append((price, qty))
    if not fills:
        return None
    qty = sum((q for _, q in fills), ZERO)
    if qty == ZERO:
        return None
    return sum((p * q for p, q in fills), ZERO) / qty


def burst_display_type(events: list[dict]) -> str:
    types = [e.get("event_type") for e in events]
    if "CLOSE" in types:
        return "CLOSE"
    if "PARTIAL_CLOSE" in types:
        return "PARTIAL_CLOSE"
    if "OPEN" in types:
        return "OPEN"
    if "ADD" in types:
        return "ADD"
    return types[-1] or "OPEN"


def format_trade_burst(doc: dict, events: list[dict]) -> str:
    """Format one Discord body for a notify burst (possibly many fills, one order)."""
    if not events:
        return format_trade_message(doc)
    if len(events) == 1:
        return format_trade_message(doc, event=events[0])

    first, last = events[0], events[-1]
    display = burst_display_type(events)
    vwap = _burst_vwap(events)
    burst_qty = sum((_event_qty(e) for e in events), ZERO)
    realized = sum((_event_realized(e) for e in events), ZERO)
    through_first = _events_through(doc, first)
    # Size before first fill in burst = after prior events only.
    before = _size_after(through_first[:-1] if through_first else [])
    through_last = _events_through(doc, last)
    after = _size_after(through_last)
    market = _fmt_price(vwap) if vwap is not None else "-"
    when = _fmt_ms(last.get("occurred_at_ms"))
    entry = (doc.get("prices") or {}).get("entry")
    kr = _kr_side(doc.get("side"))

    if display == "OPEN":
        size = after if after != ZERO else burst_qty
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

    if display == "ADD":
        lines = [
            f"{kr} 추가 진입",
            "",
            _symbol_line(doc),
            f"📍 시장가: {market}",
            f"📦 수량: {_fmt_qty(before)} → {_fmt_qty(after)}",
            f"💵 평단: {_fmt_price(entry) if entry else '-'}",
            "",
            f"⏰ {when}",
        ]
        return "\n".join(lines)

    if display == "PARTIAL_CLOSE":
        pnl = _pnl_for_event(doc, last, through_last)
        title = "부분 익절" if realized >= ZERO else "부분 손절"
        lines = [
            title,
            "",
            _symbol_line(doc),
            f"📍 시장가: {market}",
            f"📦 수량: {_fmt_qty(before)} → {_fmt_qty(after)}",
            f"💰 실현: {_fmt_money(realized)}",
            f"📊 PNL: {_fmt_money(pnl)}",
        ]
        roe = _fmt_roe(realized, vwap or ZERO, burst_qty, _leverage(doc))
        if roe is not None:
            lines.append(f"📈 ROE: {roe}")
        lines.extend(["", f"⏰ {when}"])
        return "\n".join(lines)

    # CLOSE burst (rare multi-fill flat)
    pnl = _pnl_for_event(doc, last, through_last)
    title = f"{kr} 익절" if pnl >= ZERO else f"❌ {kr} 손절"
    qty = _entry_qty_through(through_last) or burst_qty
    lines = [
        title,
        "",
        _symbol_line(doc),
        f"📍 시장가: {market}",
        f"💰 실현: {_fmt_money(pnl)}",
    ]
    roe = _fmt_roe(
        pnl,
        vwap or _d(last.get("price") or (doc.get("prices") or {}).get("exit")),
        qty,
        _leverage(doc),
    )
    if roe is not None:
        lines.append(f"📈 ROE: {roe}")
    lines.extend(["", f"⏰ {when}"])
    return "\n".join(lines)


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
    through = _events_through(doc, last)
    size = _size_after(through)
    if size == ZERO:
        size = abs(_d((doc.get("position") or {}).get("size")))
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


def _format_add(doc: dict, last: dict) -> str:
    kr = _kr_side(doc.get("side"))
    market, when = _header_time_price(doc, last)
    through = _events_through(doc, last)
    after = _size_after(through)
    added = _event_qty(last)
    before = after - added
    entry = (doc.get("prices") or {}).get("entry")
    lines = [
        f"{kr} 추가 진입",
        "",
        _symbol_line(doc),
        f"📍 시장가: {market}",
        f"📦 수량: {_fmt_qty(before)} → {_fmt_qty(after)}",
        f"💵 평단: {_fmt_price(entry) if entry else '-'}",
        "",
        f"⏰ {when}",
    ]
    return "\n".join(lines)


def _pnl_for_event(doc: dict, event: dict, through: list[dict]) -> Decimal:
    events = doc.get("events") or []
    is_latest = bool(events) and (
        event is events[-1]
        or (
            event.get("event_key")
            and events[-1].get("event_key") == event.get("event_key")
        )
    )
    if is_latest:
        raw = (doc.get("pnl") or {}).get("amount")
        if raw not in (None, ""):
            return _d(raw)
    through_pnl = _pnl_through(through)
    if through_pnl is not None:
        return through_pnl
    return _d((doc.get("pnl") or {}).get("amount"))


def _format_partial(doc: dict, last: dict) -> str:
    closed_qty = _event_qty(last)
    through = _events_through(doc, last)
    remain = _size_after(through)
    before = remain + closed_qty
    realized = _event_realized(last)
    pnl = _pnl_for_event(doc, last, through)
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
    through = _events_through(doc, last)
    pnl = _pnl_for_event(doc, last, through)
    title = f"{kr} 익절" if pnl >= ZERO else f"❌ {kr} 손절"
    market, when = _header_time_price(doc, last)
    qty = _entry_qty_through(through)
    if qty == ZERO:
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
