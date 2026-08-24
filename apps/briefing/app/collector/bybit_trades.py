import os
import time

from dotenv import load_dotenv
from pybit.unified_trading import HTTP

SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000
RETRY_TIMES = 3
RETRY_SLEEP_S = 0.5

load_dotenv()


def _session(session=None) -> HTTP:
    if session is not None:
        return session
    
    return HTTP(
        api_key=os.environ["BYBIT_API_KEY"],
        api_secret=os.environ["BYBIT_API_SECRET"],
    )


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


def reject_hedge(positions: list[dict]) -> None:
    for pos in positions:
        idx = pos.get("positionIdx")
        if idx in (None, "", 0, "0"):
            continue
        raise ValueError(f"hedge mode not supported: positionIdx={idx}")


def fetch_positions(session=None) -> list[dict]:
    http = _session(session)

    def call():
        return http.get_positions(category="linear", settleCoin="USDT")

    rows = _rows(_retry(call))
    reject_hedge(rows)
    return rows


def fetch_open_orders(session=None) -> list[dict]:
    http = _session(session)

    def call():
        return http.get_open_orders(category="linear", settleCoin="USDT")

    return _rows(_retry(call))


def fetch_closed_pnl(session=None, symbol: str | None = None) -> list[dict]:
    http = _session(session)
    kwargs = {"category": "linear", "limit": 100}
    if symbol:
        kwargs["symbol"] = symbol

    def call():
        return http.get_closed_pnl(**kwargs)

    return _rows(_retry(call))


def fetch_transaction_log_page(
    session=None, start_ms=None, end_ms=None, cursor=None
) -> tuple[list[dict], str | None]:
    http = _session(session)
    kwargs = {"category": "linear", "currency": "USDT"}
    if start_ms is not None:
        kwargs["startTime"] = start_ms
    if end_ms is not None:
        kwargs["endTime"] = end_ms
    if cursor:
        kwargs["cursor"] = cursor

    def call():
        return http.get_transaction_log(**kwargs)

    resp = _retry(call)
    return _rows(resp), _cursor(resp)


def fetch_transaction_log(session=None, start_ms: int = 0, end_ms: int = 0) -> list[dict]:
    rows = []
    window_start = start_ms
    while window_start <= end_ms:
        window_end = min(window_start + SEVEN_DAYS_MS - 1, end_ms)
        cursor = None
        while True:
            page, cursor = fetch_transaction_log_page(
                session=session,
                start_ms=window_start,
                end_ms=window_end,
                cursor=cursor,
            )
            rows.extend(page)
            if not cursor:
                break
        window_start = window_end + 1
    return rows
