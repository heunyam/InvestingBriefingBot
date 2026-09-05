import os
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import apps.briefing.app.db.tables as db
from apps.briefing.app.models.asset import AssetSummary
from apps.briefing.app.services.daily_hook import snapshot_weekly


KST = timezone(timedelta(hours=9))


def _summary(*, day: date, total: str = "100") -> AssetSummary:
    return AssetSummary(
        date=day,
        total=Decimal(total),
        cash=Decimal("10"),
        stock_cash=Decimal("5"),
        coin_cash=Decimal("5"),
        stock=Decimal("20"),
        coin=Decimal("70"),
        exchange_rate=Decimal("1300.00"),
        created_at=datetime(day.year, day.month, day.day, 8, 0, tzinfo=KST),
    )


class DbTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        self.tmp.close()
        self._orig_path = db.DB_PATH
        db._db = None
        db.DB_PATH = self.tmp.name

    def tearDown(self):
        if db._db is not None:
            db._db.close()
        db._db = None
        db.DB_PATH = self._orig_path
        os.unlink(self.tmp.name)


class TestWeeklyHook(DbTestCase):
    def test_load_by_date_in_weekly_returns_none_when_missing(self):
        """없는 week를 model_validate(None)으로 터뜨리지 않는다."""
        self.assertIsNone(AssetSummary.load_by_date_in_weekly(date(2026, 8, 31)))

    def test_snapshot_weekly_saves_first_day_of_week(self):
        monday = date(2026, 8, 31)
        summary = _summary(day=monday, total="20190.72")
        snapshot_weekly(summary)
        saved = AssetSummary.load_by_date_in_weekly(monday)
        self.assertIsNotNone(saved)
        self.assertEqual(saved.total, Decimal("20190.72"))

    def test_snapshot_weekly_does_not_overwrite_existing_week(self):
        monday = date(2026, 8, 31)
        snapshot_weekly(_summary(day=monday, total="20190.72"))
        snapshot_weekly(_summary(day=date(2026, 9, 1), total="19637.42"))
        saved = AssetSummary.load_by_date_in_weekly(monday)
        self.assertEqual(saved.total, Decimal("20190.72"))


if __name__ == "__main__":
    unittest.main()
