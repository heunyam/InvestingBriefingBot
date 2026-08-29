import os

from tinydb import Query, TinyDB

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db")
DB_PATH = os.path.join(DATA_DIR, "db.json")
ASSET_SUMMARY_TABLE = "asset_summary"
WEEKLY_TABLE = "weekly"
ORDERS_TABLE = "orders"

Doc = Query()

_db: TinyDB | None = None


def get_db() -> TinyDB:
    global _db
    if _db is None:
        os.makedirs(DATA_DIR, exist_ok=True)
        _db = TinyDB(DB_PATH)
    return _db


def asset_summary_table():
    return get_db().table(ASSET_SUMMARY_TABLE)


def weekly_table():
    return get_db().table(WEEKLY_TABLE)


def orders_table():
    return get_db().table(ORDERS_TABLE)
