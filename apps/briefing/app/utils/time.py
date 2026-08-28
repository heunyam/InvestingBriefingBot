from datetime import datetime, timedelta, timezone, date

DATE_FORMAT = "%Y-%m-%d"


def to_str(dt: datetime, format: str) -> str:
    return dt.strftime(format)


def kst_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=9)))


def to_kst(dt: datetime) -> datetime:
    return dt.astimezone(tz=timezone(timedelta(hours=9)))


def yesterday(dt: datetime) -> datetime:
    return dt - timedelta(days=1)


def get_week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())
