import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.collector import bybit_trades
from app.models import trade
from app.models.db import Doc, get_db

ZERO = Decimal("0")
META_TABLE = "trade_sync_meta"
META_KEY = "bybit_tx"
DEFAULT_LOOKBACK_MS = 30 * 24 * 60 * 60 * 1000
BACKFILL_LOOKBACK_MS = 2 * 365 * 24 * 60 * 60 * 1000
FUNDING_INTERVAL_MS = 8 * 60 * 60 * 1000
# 이 시각(KST) 이전 체결은 동기화하지 않는다. 예전 lookback이 중첩 포지션을 꼬이게 해서.
SYNC_START_MS = int(
    datetime(2026, 8, 25, 0, 0, 0, tzinfo=timezone(timedelta(hours=9))).timestamp()
    * 1000
)

_TP_ORDER_TYPES = {
    "TakeProfit",
    "TakeProfitMarket",
    "PartialTakeProfit",
}
_SL_ORDER_TYPES = {
    "StopLoss",
    "Stop",
    "StopMarket",
    "PartialStopLoss",
}
_TRAILING_ORDER_TYPES = {
    "TrailingStop",
    "TrailingProfit",
}


def _meta_table():
    return get_db().table(META_TABLE)


def get_last_synced_ms() -> int | None:
    rows = _meta_table().search(Doc.key == META_KEY)
    if not rows:
        return None
    return rows[0].get("last_end_ms")


def set_last_synced_ms(end_ms: int) -> None:
    _meta_table().upsert(
        {"key": META_KEY, "last_end_ms": end_ms},
        Doc.key == META_KEY,
    )


def _d(v) -> Decimal:
    if v is None or v == "":
        return ZERO
    return Decimal(str(v))


def _ms_now() -> int:
    return int(time.time() * 1000)


def _bybit_side_to_delta(side: str, qty: Decimal) -> Decimal:
    if side == "Buy":
        return qty
    if side == "Sell":
        return -qty
    return ZERO


def _position_side(signed: Decimal) -> str | None:
    if signed > ZERO:
        return "LONG"
    if signed < ZERO:
        return "SHORT"
    return None


def _event_type(prev: Decimal, nxt: Decimal) -> str:
    if prev == ZERO and nxt != ZERO:
        return "OPEN"
    if prev != ZERO and nxt == ZERO:
        return "CLOSE"
    if abs(nxt) > abs(prev) and (prev == ZERO or (prev > ZERO) == (nxt > ZERO)):
        return "ADD"
    return "PARTIAL_CLOSE"


def find_open(symbol: str, side: str) -> dict | None:
    for row in trade.all():
        if (
            row.get("symbol") == symbol
            and row.get("side") == side
            and row.get("status") == "OPEN"
        ):
            return row
    return None


def needs_user_review(doc: dict) -> bool:
    review = doc.get("review")
    if not review:
        return True
    return not (review.get("entry_reason") and review.get("exit_reason"))


def _kind_from_stop_order_type(stop_order_type: str) -> str | None:
    t = stop_order_type or ""
    if t in _TRAILING_ORDER_TYPES or "Trailing" in t:
        return "TRAILING_STOP"
    if t in _TP_ORDER_TYPES or "TakeProfit" in t:
        return "TP"
    if t in _SL_ORDER_TYPES or "StopLoss" in t or t in ("Stop", "StopMarket"):
        return "SL"
    return None


def _order_mode(order: dict, kind: str) -> str:
    tpsl = (order.get("tpslMode") or "").lower()
    stop = order.get("stopOrderType") or ""
    if tpsl == "partial" or "Partial" in stop:
        return "PARTIAL"
    if kind == "TRAILING_STOP":
        return "PARTIAL"
    return "FULL"


def _active_order_status(status: str) -> bool:
    s = (status or "").lower()
    return s in ("", "new", "untriggered", "active", "created")


def protections_from_snapshot(position: dict, orders: list[dict] | None = None) -> list[dict]:
    """Replace-style ACTIVE protections from position full TP/SL + open stop orders."""
    now_ms = _ms_now()
    symbol = position.get("symbol") or ""
    qty = str(position.get("size") or "0")
    items = []

    if position.get("takeProfit"):
        items.append(
            {
                "bybit_order_id": f"{symbol}:TP:full",
                "kind": "TP",
                "trigger_price": str(position["takeProfit"]),
                "quantity": qty,
                "mode": "FULL",
                "status": "ACTIVE",
                "updated_at_ms": now_ms,
            }
        )
    if position.get("stopLoss"):
        items.append(
            {
                "bybit_order_id": f"{symbol}:SL:full",
                "kind": "SL",
                "trigger_price": str(position["stopLoss"]),
                "quantity": qty,
                "mode": "FULL",
                "status": "ACTIVE",
                "updated_at_ms": now_ms,
            }
        )

    for order in orders or []:
        if (order.get("symbol") or "") != symbol:
            continue
        if not _active_order_status(order.get("orderStatus") or ""):
            continue
        kind = _kind_from_stop_order_type(order.get("stopOrderType") or "")
        if kind is None:
            continue
        oid = str(order.get("orderId") or "")
        if not oid:
            continue
        trigger = order.get("triggerPrice") or order.get("takeProfit") or order.get("stopLoss")
        if not trigger:
            continue
        items.append(
            {
                "bybit_order_id": oid,
                "kind": kind,
                "trigger_price": str(trigger),
                "quantity": str(order.get("qty") or qty),
                "mode": _order_mode(order, kind),
                "status": "ACTIVE",
                "updated_at_ms": now_ms,
            }
        )
    return items


def _fill_index(row: dict) -> int:
    sid = str(row.get("id") or "")
    if "_" in sid:
        tail = sid.rsplit("_", 1)[-1]
        if tail.isdigit():
            return int(tail)
    return 0


def _after_signed(row: dict) -> Decimal | None:
    raw = row.get("size")
    if raw in (None, ""):
        return None
    return _d(raw)


def _align_book(
    books: dict[str, dict],
    symbol: str,
    implied_prev: Decimal,
    occurred_at_ms: int,
    now_ms: int,
) -> None:
    """Fix book size when lookback starts mid-position (Bybit `size` after fill)."""
    book = books.setdefault(symbol, {"signed": ZERO, "doc": None})
    if book["signed"] == implied_prev:
        return
    side = _position_side(implied_prev)
    doc = book["doc"]
    if side is None:
        book["signed"] = ZERO
        book["doc"] = None
        return
    if doc is None or doc.get("side") != side or doc.get("status") == "CLOSED":
        doc = find_open(symbol, side)
        if doc is None:
            doc = trade.new_trade(
                trade_id=str(uuid.uuid4()),
                symbol=symbol,
                side=side,
                opened_at_ms=occurred_at_ms,
                now_ms=now_ms,
            )
        book["doc"] = doc
    book["signed"] = implied_prev


def _apply_fill(
    books: dict[str, dict],
    *,
    symbol: str,
    side: str,
    qty: Decimal,
    price: Decimal,
    fee: Decimal,
    cash_flow: Decimal,
    funding: Decimal,
    occurred_at_ms: int,
    source_id: str,
    now_ms: int,
) -> list[dict]:
    touched = []
    book = books.setdefault(symbol, {"signed": ZERO, "doc": None})
    prev = book["signed"]
    delta = _bybit_side_to_delta(side, qty)
    nxt = prev + delta

    if prev != ZERO and nxt != ZERO and (prev > ZERO) != (nxt > ZERO):
        close_qty = abs(prev)
        close_side = "Sell" if prev > ZERO else "Buy"
        touched.extend(
            _apply_fill(
                books,
                symbol=symbol,
                side=close_side,
                qty=close_qty,
                price=price,
                fee=ZERO,
                cash_flow=cash_flow,
                funding=funding,
                occurred_at_ms=occurred_at_ms,
                source_id=f"{source_id}:close",
                now_ms=now_ms,
            )
        )
        open_qty = abs(nxt)
        open_side = "Buy" if nxt > ZERO else "Sell"
        touched.extend(
            _apply_fill(
                books,
                symbol=symbol,
                side=open_side,
                qty=open_qty,
                price=price,
                fee=fee,
                cash_flow=ZERO,
                funding=ZERO,
                occurred_at_ms=occurred_at_ms,
                source_id=f"{source_id}:open",
                now_ms=now_ms,
            )
        )
        return touched

    etype = _event_type(prev, nxt)
    pos_side = _position_side(nxt if nxt != ZERO else prev)
    if pos_side is None:
        return touched

    doc = book["doc"]
    if etype == "OPEN" or doc is None or doc.get("status") == "CLOSED":
        existing = find_open(symbol, pos_side)
        if existing and etype != "OPEN":
            doc = existing
        elif etype == "OPEN":
            doc = trade.new_trade(
                trade_id=str(uuid.uuid4()),
                symbol=symbol,
                side=pos_side,
                opened_at_ms=occurred_at_ms,
                now_ms=now_ms,
            )
        else:
            doc = existing or trade.new_trade(
                trade_id=str(uuid.uuid4()),
                symbol=symbol,
                side=pos_side,
                opened_at_ms=occurred_at_ms,
                now_ms=now_ms,
            )
        book["doc"] = doc

    fill_qty = abs(delta)
    trade.upsert_event(
        doc,
        {
            "event_key": trade.event_key(symbol, occurred_at_ms, exec_id=source_id),
            "event_type": etype,
            "occurred_at_ms": occurred_at_ms,
            "price": str(price),
            "quantity": str(fill_qty),
            "fee": str(fee),
            "realized_pnl": "0",
            "cash_flow": str(cash_flow),
            "funding": str(funding),
            "source_type": "TRADE",
            "source_ids": [source_id],
        },
        now_ms,
    )
    book["signed"] = nxt
    pos = doc.setdefault("position", {})
    pos["size"] = str(abs(nxt))
    doc["position"] = pos
    if nxt == ZERO:
        book["doc"] = None
    else:
        doc["status"] = "OPEN"
        doc["closed_at_ms"] = None
    trade.save(doc)
    touched.append(doc)
    return touched


def _flag_ineligible_until_first_flat(window_start_ms: int) -> None:
    """Exclude the first in-window round-trip if the symbol was already open."""
    by_symbol: dict[str, list[dict]] = {}
    for doc in trade.all():
        by_symbol.setdefault(doc["symbol"], []).append(doc)
    for docs in by_symbol.values():
        docs.sort(
            key=lambda d: (d.get("opened_at_ms") or 0, d.get("closed_at_ms") or 0)
        )
        first = docs[0]
        events = first.get("events") or []
        first_type = events[0].get("event_type") if events else None
        opened = first.get("opened_at_ms") or 0
        mid_start = opened < window_start_ms or (
            bool(events) and first_type != "OPEN"
        )
        if not mid_start:
            continue
        first["stats_eligible"] = False
        trade.save(first)


def _is_trade_row(row: dict) -> bool:
    return (row.get("type") or "").upper() == "TRADE"


def _is_funding_like_event(ev: dict, size_before: Decimal) -> bool:
    source_type = (ev.get("source_type") or "").upper()
    if source_type and source_type != "TRADE":
        return True
    if source_type == "TRADE":
        return False
    if ev.get("event_type") != "ADD":
        return False
    ts = int(ev.get("occurred_at_ms") or 0)
    if ts <= 0 or ts % FUNDING_INTERVAL_MS != 0:
        return False
    qty = abs(_d(ev.get("quantity")))
    return size_before != ZERO and qty == abs(size_before)


def purge_funding_like_events() -> list[dict]:
    """Drop SETTLEMENT/funding rows that were stored as ADD fills."""
    touched = []
    for doc in trade.all():
        events = list(doc.get("events") or [])
        kept = []
        size = ZERO
        for ev in events:
            if _is_funding_like_event(ev, size):
                continue
            kind = ev.get("event_type")
            qty = abs(_d(ev.get("quantity")))
            if kind in ("OPEN", "ADD"):
                size += qty
            elif kind in ("PARTIAL_CLOSE", "CLOSE"):
                size -= qty
            kept.append(ev)
        if len(kept) == len(events):
            continue
        doc["events"] = kept
        trade.recompute(doc)
        trade.save(doc)
        touched.append(doc)
    return touched


def stamp_leverage(session=None) -> list[dict]:
    """Copy leverage from open/flat positions, then closed PnL for the rest."""
    touched = []
    by_symbol = {}
    for pos in bybit_trades.fetch_positions(session=session):
        symbol = pos.get("symbol") or ""
        lev = pos.get("leverage")
        if symbol and lev not in (None, ""):
            by_symbol[symbol] = str(lev)
    missing = [
        doc
        for doc in trade.all()
        if not (doc.get("position") or {}).get("leverage")
        and (doc.get("symbol") or "") not in by_symbol
    ]
    if missing:
        for row in bybit_trades.fetch_closed_pnl(session=session):
            symbol = row.get("symbol") or ""
            lev = row.get("leverage")
            if symbol and lev not in (None, "") and symbol not in by_symbol:
                by_symbol[symbol] = str(lev)
    for doc in trade.all():
        lev = by_symbol.get(doc.get("symbol") or "")
        if not lev:
            continue
        posn = doc.setdefault("position", {})
        if posn.get("leverage") == lev:
            continue
        posn["leverage"] = lev
        doc["position"] = posn
        trade.save(doc)
        touched.append(doc)
    return touched


def sync_transaction_log(
    session=None,
    end_ms: int | None = None,
    *,
    lookback_ms: int | None = None,
    backfill: bool = False,
) -> list[dict]:
    purged = purge_funding_like_events()
    end_ms = end_ms or _ms_now()
    last = get_last_synced_ms()
    span = lookback_ms or (
        BACKFILL_LOOKBACK_MS if backfill else DEFAULT_LOOKBACK_MS
    )
    if last is None or backfill:
        start_ms = max(0, end_ms - span)
    else:
        start_ms = max(0, last - 60_000)
    start_ms = max(start_ms, SYNC_START_MS)
    if start_ms > end_ms:
        set_last_synced_ms(end_ms)
        return purged

    rows = bybit_trades.fetch_transaction_log(
        session=session, start_ms=start_ms, end_ms=end_ms
    )
    trade_rows = [
        r
        for r in rows
        if _is_trade_row(r)
        and int(r.get("transactionTime") or 0) >= SYNC_START_MS
    ]
    trade_rows.sort(
        key=lambda r: (int(r.get("transactionTime") or 0), _fill_index(r))
    )

    known = set()
    for doc in trade.all():
        for ev in doc.get("events") or []:
            for sid in ev.get("source_ids") or []:
                known.add(str(sid))

    books: dict[str, dict] = {}
    for doc in trade.all():
        if doc.get("status") != "OPEN":
            continue
        symbol = doc["symbol"]
        signed = _d(doc.get("position", {}).get("size"))
        if doc.get("side") == "SHORT":
            signed = -signed
        books[symbol] = {"signed": signed, "doc": doc}

    touched_ids = set()
    touched = []
    now_ms = _ms_now()
    for row in trade_rows:
        symbol = row.get("symbol") or ""
        if not symbol:
            continue
        source_id = str(row.get("id") or row.get("tradeId") or row.get("orderId") or "")
        if not source_id or source_id in known:
            continue
        known.add(source_id)
        qty = _d(row.get("qty"))
        side = row.get("side") or ""
        delta = _bybit_side_to_delta(side, qty)
        after = _after_signed(row)
        if after is not None:
            _align_book(
                books,
                symbol,
                after - delta,
                int(row.get("transactionTime") or now_ms),
                now_ms,
            )
        for doc in _apply_fill(
            books,
            symbol=symbol,
            side=side,
            qty=qty,
            price=_d(row.get("tradePrice")),
            fee=_d(row.get("fee")),
            cash_flow=_d(row.get("cashFlow")),
            funding=_d(row.get("funding")),
            occurred_at_ms=int(row.get("transactionTime") or now_ms),
            source_id=source_id,
            now_ms=now_ms,
        ):
            if doc["trade_id"] not in touched_ids:
                touched_ids.add(doc["trade_id"])
                touched.append(doc)

    if last is None or backfill:
        _flag_ineligible_until_first_flat(start_ms)
    set_last_synced_ms(end_ms)
    for doc in purged:
        if doc["trade_id"] not in touched_ids:
            touched_ids.add(doc["trade_id"])
            touched.append(doc)
    return touched


def sync_open_positions(session=None) -> list[dict]:
    positions = bybit_trades.fetch_positions(session=session)
    orders = bybit_trades.fetch_open_orders(session=session)
    orders_by_symbol: dict[str, list[dict]] = {}
    for order in orders:
        sym = order.get("symbol") or ""
        if sym:
            orders_by_symbol.setdefault(sym, []).append(order)

    now_ms = _ms_now()
    touched = []

    for pos in positions:
        size = _d(pos.get("size"))
        if size == ZERO:
            continue
        symbol = pos.get("symbol") or ""
        raw_side = (pos.get("side") or "").capitalize()
        side = "LONG" if raw_side == "Buy" else "SHORT" if raw_side == "Sell" else None
        if not symbol or side is None:
            continue
        doc = find_open(symbol, side)
        if doc is None:
            opened = int(pos.get("createdTime") or pos.get("updatedTime") or now_ms)
            if opened < SYNC_START_MS:
                continue
            doc = trade.new_trade(
                trade_id=str(uuid.uuid4()),
                symbol=symbol,
                side=side,
                opened_at_ms=opened,
                now_ms=now_ms,
            )
        elif int(doc.get("opened_at_ms") or 0) < SYNC_START_MS:
            continue
        doc["position"] = {
            "size": str(size),
            "leverage": str(pos.get("leverage") or "") or None,
        }
        avg = pos.get("avgPrice") or pos.get("entryPrice")
        if avg:
            doc.setdefault("prices", {})
            doc["prices"]["entry"] = str(avg)
        doc["status"] = "OPEN"
        doc["closed_at_ms"] = None
        doc["protections"] = protections_from_snapshot(
            pos, orders_by_symbol.get(symbol, [])
        )
        doc["updated_at_ms"] = now_ms
        trade.save(doc)
        touched.append(doc)

    return touched


def sync_all(
    session=None, *, lookback_ms: int | None = None, backfill: bool = False
) -> dict:
    if _ms_now() < SYNC_START_MS:
        return {"synced": [], "pending_review": []}
    tx_touched = sync_transaction_log(
        session=session, lookback_ms=lookback_ms, backfill=backfill
    )
    open_touched = sync_open_positions(session=session)
    lev_touched = stamp_leverage(session=session)
    by_id = {d["trade_id"]: d for d in tx_touched}
    for d in open_touched:
        by_id[d["trade_id"]] = d
    for d in lev_touched:
        by_id[d["trade_id"]] = d
    return {
        "synced": list(by_id.values()),
        "pending_review": [d for d in trade.all() if needs_user_review(d)],
    }
