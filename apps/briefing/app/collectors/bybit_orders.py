import time
from collections.abc import Callable

from apps.briefing.app.collectors.bybit import get_bybit_session

SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000
RETRY_TIMES = 3
RETRY_SLEEP_S = 0.5
PAGE_LIMIT = 50


def _retry(fn):
    last = None
    for attempt in range(RETRY_TIMES):
        try:
            return fn()
        except Exception as exc:
            last = exc
            if attempt == RETRY_TIMES - 1:
                raise
            time.sleep(RETRY_SLEEP_S)
    raise last


def _rows(resp: dict) -> list[dict]:
    result = (resp or {}).get("result") or {}
    rows = result.get("list") or []
    return rows if isinstance(rows, list) else []


def _cursor(resp: dict) -> str | None:
    result = (resp or {}).get("result") or {}
    cursor = result.get("nextPageCursor") or None
    return cursor or None


def _fetch_windowed(
    session,
    *,
    start_ms: int,
    end_ms: int,
    fetch_page: Callable,
) -> list[dict]:
    rows: list[dict] = []
    window_start = start_ms
    while window_start <= end_ms:
        window_end = min(window_start + SEVEN_DAYS_MS - 1, end_ms)
        cursor = None
        while True:
            page, cursor = fetch_page(
                session,
                start_ms=window_start,
                end_ms=window_end,
                cursor=cursor,
            )
            rows.extend(page)
            if not cursor:
                break
        window_start = window_end + 1
    return rows


def _fetch_order_history_page(
    session, *, start_ms: int, end_ms: int, cursor: str | None = None
) -> tuple[list[dict], str | None]:
    http = get_bybit_session(session)
    kwargs = {
        "category": "linear",
        "settleCoin": "USDT",
        "orderStatus": "Filled",
        "startTime": start_ms,
        "endTime": end_ms,
        "limit": PAGE_LIMIT,
    }
    if cursor:
        kwargs["cursor"] = cursor

    def call():
        return http.get_order_history(**kwargs)

    resp = _retry(call)
    return _rows(resp), _cursor(resp)


def _fetch_closed_pnl_page(
    session, *, start_ms: int, end_ms: int, cursor: str | None = None
) -> tuple[list[dict], str | None]:
    http = get_bybit_session(session)
    kwargs = {
        "category": "linear",
        "startTime": start_ms,
        "endTime": end_ms,
        "limit": 100,
    }
    if cursor:
        kwargs["cursor"] = cursor

    def call():
        return http.get_closed_pnl(**kwargs)

    resp = _retry(call)
    return _rows(resp), _cursor(resp)


def fetch_order_history(session=None, *, start_ms: int, end_ms: int) -> list[dict]:
    return _fetch_windowed(
        session,
        start_ms=start_ms,
        end_ms=end_ms,
        fetch_page=_fetch_order_history_page,
    )


def fetch_closed_pnl(session=None, *, start_ms: int, end_ms: int) -> list[dict]:
    return _fetch_windowed(
        session,
        start_ms=start_ms,
        end_ms=end_ms,
        fetch_page=_fetch_closed_pnl_page,
    )
