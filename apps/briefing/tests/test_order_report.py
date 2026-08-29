import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import apps.briefing.app.db.tables as db
from apps.briefing.app.models.order import Order, all, load, save
from apps.briefing.app.services.order import map_order
from apps.briefing.app.services.order_analytics import is_stats_order, summarize
from apps.briefing.app.services.order_enrich import enrich_orders
from apps.briefing.app.services.order_message import format_order_message
from apps.briefing.app.services.order_notify import notify_unposted

KST = timezone(timedelta(hours=9))
SYNCED_AT = datetime(2026, 8, 29, 10, 0, 0, tzinfo=KST)
FILLED_AT = datetime(2026, 8, 28, 15, 30, 0, tzinfo=KST)

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

EXIT_HISTORY_ROW = {
    **ORDER_HISTORY_ROW,
    "orderId": "exit-order-id",
    "side": "Sell",
    "reduceOnly": True,
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


def _order(
    *,
    order_id: str,
    reduce_only: bool = False,
    realized_pnl: Decimal | None = None,
    discord_message_id: str | None = None,
    filled_at: datetime = FILLED_AT,
) -> Order:
    return Order(
        order_id=order_id,
        symbol="QQQUSDT",
        side="SELL" if reduce_only else "BUY",
        reduce_only=reduce_only,
        order_type="Market",
        quantity=Decimal("1"),
        average_price=Decimal("100"),
        fee=Decimal("0.1"),
        filled_at=filled_at,
        created_at=filled_at,
        realized_pnl=realized_pnl,
        leverage="3" if reduce_only else None,
        synced_at=SYNCED_AT,
        discord_message_id=discord_message_id,
    )


class TestOrderEnrich(DbTestCase):
    @patch("apps.briefing.app.services.order_enrich.bybit_orders.fetch_closed_pnl")
    def test_enrich_sets_realized_pnl(self, mock_fetch):
        save(_order(order_id="exit-order-id", reduce_only=True))
        mock_fetch.return_value = [
            {
                "orderId": "exit-order-id",
                "closedPnl": "12.5",
                "leverage": "3",
            }
        ]
        result = enrich_orders(start_ms=1, end_ms=2)
        self.assertEqual(result["updated"], 1)
        loaded = load("exit-order-id")
        self.assertEqual(loaded.realized_pnl, Decimal("12.5"))
        self.assertEqual(loaded.leverage, "3")


class TestOrderAnalytics(DbTestCase):
    def test_analytics_selects_exit_orders(self):
        save(_order(order_id="entry", reduce_only=False))
        save(
            _order(
                order_id="win",
                reduce_only=True,
                realized_pnl=Decimal("10"),
            )
        )
        save(
            _order(
                order_id="loss",
                reduce_only=True,
                realized_pnl=Decimal("-5"),
            )
        )
        save(
            _order(
                order_id="flat",
                reduce_only=True,
                realized_pnl=Decimal("0"),
            )
        )
        now_ms = int(FILLED_AT.timestamp() * 1000) + 86_400_000
        stats = summarize(all(), period="7d", now_ms=now_ms)
        self.assertEqual(stats["n"], 2)
        self.assertEqual(stats["wins"], 1)
        self.assertEqual(stats["losses"], 1)
        self.assertFalse(is_stats_order(_order(order_id="entry")))


class TestOrderMessage(unittest.TestCase):
    def test_format_order_message_entry(self):
        text = format_order_message(_order(order_id="entry"))
        self.assertIn("진입", text)
        self.assertIn("매수", text)
        self.assertNotIn("실현손익", text)

    def test_format_order_message_exit(self):
        text = format_order_message(
            _order(
                order_id="exit",
                reduce_only=True,
                realized_pnl=Decimal("12.5"),
            )
        )
        self.assertIn("청산", text)
        self.assertIn("실현손익", text)


class TestOrderNotify(DbTestCase):
    @patch("apps.briefing.app.services.order_notify.discord_trade.send_trade")
    def test_notify_skips_posted(self, mock_send):
        save(_order(order_id="posted", discord_message_id="msg-1"))
        save(_order(order_id="pending"))
        mock_send.return_value = "msg-2"
        posted = notify_unposted()
        self.assertEqual(len(posted), 1)
        self.assertEqual(load("pending").discord_message_id, "msg-2")
        mock_send.assert_called_once()


class TestOrderPersistence(DbTestCase):
    def test_discord_message_id_preserved_on_resync(self):
        order = map_order(ORDER_HISTORY_ROW, synced_at=SYNCED_AT)
        save(order.model_copy(update={"discord_message_id": "msg-keep"}))
        save(map_order(ORDER_HISTORY_ROW, synced_at=SYNCED_AT))
        loaded = load(order.order_id)
        self.assertEqual(loaded.discord_message_id, "msg-keep")


if __name__ == "__main__":
    unittest.main()
