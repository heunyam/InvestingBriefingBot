from apps.briefing.app.collectors.bybit.http import fetch_paginated, rows, retry
from apps.briefing.app.collectors.bybit.session import get_bybit_session

PAGE_LIMIT = 50


def fetch_order_history(session=None, *, start_ms: int, end_ms: int) -> list[dict]:
    return fetch_paginated(
        session,
        method="get_order_history",
        start_ms=start_ms,
        end_ms=end_ms,
        limit=PAGE_LIMIT,
        extra_kwargs={
            "category": "linear",
            "settleCoin": "USDT",
            "orderStatus": "Filled",
        },
    )


def fetch_order_by_id(session=None, *, order_id: str) -> dict | None:
    http = get_bybit_session(session)
    resp = retry(lambda: http.get_order_history(category="linear", orderId=order_id))
    items = rows(resp)
    return items[0] if items else None


def fetch_closed_pnl(session=None, *, start_ms: int, end_ms: int) -> list[dict]:
    return fetch_paginated(
        session,
        method="get_closed_pnl",
        start_ms=start_ms,
        end_ms=end_ms,
        limit=100,
        extra_kwargs={"category": "linear"},
    )
