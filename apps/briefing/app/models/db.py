import os

from tinydb import Query, TinyDB

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DB_PATH = os.path.join(DATA_DIR, "db.json")
TABLE = "daily"

Daily = Query()

_db: TinyDB | None = None


def get_db() -> TinyDB:
    global _db
    if _db is None:
        os.makedirs(DATA_DIR, exist_ok=True)
        _db = TinyDB(DB_PATH)
    return _db


def daily_table():
    return get_db().table(TABLE)
