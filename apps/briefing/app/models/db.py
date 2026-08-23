import os

from tinydb import Query, TinyDB

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DB_PATH = os.path.join(DATA_DIR, "db.json")
TABLE = "asset_summary"
_LEGACY_TABLE = "daily"

Doc = Query()

_db: TinyDB | None = None


def get_db() -> TinyDB:
    global _db
    if _db is None:
        os.makedirs(DATA_DIR, exist_ok=True)
        _db = TinyDB(DB_PATH)
        _migrate_legacy_table(_db)
    return _db


def _migrate_legacy_table(db: TinyDB) -> None:
    if _LEGACY_TABLE not in db.tables():
        return
    old = db.table(_LEGACY_TABLE)
    new = db.table(TABLE)
    if len(old) and not len(new):
        for doc in old:
            new.insert(dict(doc))
    db.drop_table(_LEGACY_TABLE)


def asset_summary_table():
    return get_db().table(TABLE)
