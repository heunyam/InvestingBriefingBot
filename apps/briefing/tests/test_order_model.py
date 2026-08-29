import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import apps.briefing.app.db.tables as db
from apps.briefing.app.models.order import Order, all, load, save
from apps.briefing.app.services.order import map_order
from apps.briefing.app.services.order_sync import sync_all

KST = timezone(timedelta(hours=9))
SYNCED_AT = datetime(2026, 8, 29, 10, 0, 0, tzinfo=KST)

ORDER_HISTORY_ROW = {
    "orderId": "84d6f4d9-00a0-48c9-a17c-8e5c1937eaaf",
    "symbol": "QQQUSDT",
    "side": "Buy",
    "reduceOnly": False,
    "orderType": "Market",
    "cumExecQty": "11.42",
    "avgPrice": "720.3",
    "cumFeeDetail": {"USDT": "0.5"},
    "cumExecFee": "0.4",
    "updatedTime": "1787849427669",
    "createdTime": "1787849427600",
}


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


class TestOrderModel(DbTestCase):
    def test_order_field_schema(self):
        schema = Order.model_json_schema()
        props = schema["properties"]
        for name in Order.model_fields:
            with self.subTest(field=name):
                self.assertIn("title", props[name])
                self.assertIn("description", props[name])

    def test_map_order(self):
        order = map_order(ORDER_HISTORY_ROW, synced_at=SYNCED_AT)
        self.assertEqual(order.order_id, "84d6f4d9-00a0-48c9-a17c-8e5c1937eaaf")
        self.assertEqual(order.symbol, "QQQUSDT")
        self.assertEqual(order.side, "BUY")
        self.assertFalse(order.reduce_only)
        self.assertEqual(order.order_type, "Market")
        self.assertEqual(order.quantity, Decimal("11.42"))
        self.assertEqual(order.average_price, Decimal("720.3"))
        self.assertEqual(order.fee, Decimal("0.5"))
        self.assertEqual(
            order.filled_at,
            datetime.fromtimestamp(1787849427669 / 1000, tz=KST),
        )
        self.assertEqual(
            order.created_at,
            datetime.fromtimestamp(1787849427600 / 1000, tz=KST),
        )
        self.assertIsNone(order.realized_pnl)
        self.assertIsNone(order.leverage)
        self.assertEqual(order.synced_at, SYNCED_AT)

    def test_map_order_fee_fallback(self):
        row = {**ORDER_HISTORY_ROW, "cumFeeDetail": {}, "cumExecFee": "0.4"}
        order = map_order(row, synced_at=SYNCED_AT)
        self.assertEqual(order.fee, Decimal("0.4"))

    def test_save_upsert_idempotent(self):
        order = map_order(ORDER_HISTORY_ROW, synced_at=SYNCED_AT)
        save(order)
        updated = order.model_copy(update={"quantity": Decimal("12")})
        save(updated)
        self.assertEqual(len(all()), 1)
        loaded = load(order.order_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.quantity, Decimal("12"))

    @patch("apps.briefing.app.services.order_sync.enrich_orders")
    @patch("apps.briefing.app.services.order_sync._ms_now")
    @patch("apps.briefing.app.services.order_sync.bybit_orders.fetch_order_history")
    def test_sync_all_mocked(self, mock_fetch, mock_now, mock_enrich):
        mock_now.return_value = 1_700_000_000_000
        mock_fetch.return_value = [
            ORDER_HISTORY_ROW,
            {"orderId": "zero-qty", "cumExecQty": "0"},
        ]
        mock_enrich.return_value = {"fetched": 0, "matched": 0, "updated": 0}
        result = sync_all()
        self.assertEqual(result["fetched"], 2)
        self.assertEqual(result["saved"], 1)
        self.assertEqual(len(all()), 1)
        mock_fetch.assert_called_once()
        mock_enrich.assert_called_once()


if __name__ == "__main__":
    unittest.main()
