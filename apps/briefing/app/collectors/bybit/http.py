import time
from collections.abc import Callable

from apps.briefing.app.collectors.bybit.session import get_bybit_session

SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000
RETRY_TIMES = 3
RETRY_SLEEP_S = 0.5


def retry(fn):
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


def rows(resp: dict) -> list[dict]:
    result = (resp or {}).get("result") or {}
    items = result.get("list") or []
    return items if isinstance(items, list) else []


def next_cursor(resp: dict) -> str | None:
    result = (resp or {}).get("result") or {}
    cursor = result.get("nextPageCursor") or None
    return cursor or None


def fetch_windowed(
    session,
    *,
    start_ms: int,
    end_ms: int,
    fetch_page: Callable,
) -> list[dict]:
    items: list[dict] = []
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
            items.extend(page)
            if not cursor:
                break
        window_start = window_end + 1
    return items


def fetch_paginated(
    session,
    *,
    method: str,
    start_ms: int,
    end_ms: int,
    limit: int,
    extra_kwargs: dict | None = None,
) -> list[dict]:
    def fetch_page(session, *, start_ms: int, end_ms: int, cursor: str | None):
        http = get_bybit_session(session)
        kwargs = {
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": limit,
            **(extra_kwargs or {}),
        }
        if cursor:
            kwargs["cursor"] = cursor

        resp = retry(lambda: getattr(http, method)(**kwargs))
        return rows(resp), next_cursor(resp)

    return fetch_windowed(
        session,
        start_ms=start_ms,
        end_ms=end_ms,
        fetch_page=fetch_page,
    )
