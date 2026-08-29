import time
from decimal import Decimal

from apps.briefing.app.collectors import bybit_orders
from apps.briefing.app.db.tables import Doc, get_db
from apps.briefing.app.models.order import save
from apps.briefing.app.services.order import map_order
from apps.briefing.app.services.order_enrich import enrich_orders

META_TABLE = "order_sync_meta"
META_KEY = "bybit_order_history"
DEFAULT_LOOKBACK_MS = 30 * 24 * 60 * 60 * 1000
BACKFILL_LOOKBACK_MS = 2 * 365 * 24 * 60 * 60 * 1000
ZERO = Decimal("0")


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


def _ms_now() -> int:
    return int(time.time() * 1000)


def _has_exec_qty(row: dict) -> bool:
    qty = row.get("cumExecQty")
    if qty is None or qty == "":
        return False
    return Decimal(str(qty)) > ZERO


def sync_all(*, backfill: bool = False, session=None) -> dict:
    end_ms = _ms_now()

    if backfill:
        start_ms = end_ms - BACKFILL_LOOKBACK_MS
    else:
        last = get_last_synced_ms()
        if last is None:
            start_ms = end_ms - DEFAULT_LOOKBACK_MS
        else:
            start_ms = last

    if start_ms > end_ms:
        return {
            "fetched": 0,
            "saved": 0,
            "enriched": {"fetched": 0, "matched": 0, "updated": 0},
            "start_ms": start_ms,
            "end_ms": end_ms,
        }

    rows = bybit_orders.fetch_order_history(
        session=session, start_ms=start_ms, end_ms=end_ms
    )

    saved = 0
    for row in rows:
        if not _has_exec_qty(row):
            continue
        save(map_order(row))
        saved += 1

    set_last_synced_ms(end_ms)
    enriched = enrich_orders(start_ms=start_ms, end_ms=end_ms, session=session)
    return {
        "fetched": len(rows),
        "saved": saved,
        "enriched": enriched,
        "start_ms": start_ms,
        "end_ms": end_ms,
    }
