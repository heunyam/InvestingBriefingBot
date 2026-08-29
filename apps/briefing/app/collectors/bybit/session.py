import os

from pybit.unified_trading import HTTP

bybit_session: HTTP | None = None


def get_bybit_session(session: HTTP | None = None) -> HTTP:
    if session:
        return session

    global bybit_session
    if bybit_session:
        return bybit_session

    bybit_session = HTTP(
        api_key=os.environ["BYBIT_API_KEY"], api_secret=os.environ["BYBIT_API_SECRET"]
    )
    return bybit_session
