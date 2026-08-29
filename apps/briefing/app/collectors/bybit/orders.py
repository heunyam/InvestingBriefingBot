from apps.briefing.app.collectors.bybit.http import fetch_paginated

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


def fetch_closed_pnl(session=None, *, start_ms: int, end_ms: int) -> list[dict]:
    return fetch_paginated(
        session,
        method="get_closed_pnl",
        start_ms=start_ms,
        end_ms=end_ms,
        limit=100,
        extra_kwargs={"category": "linear"},
    )
