import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import apps.briefing.app.db.tables as db
from apps.briefing.app.models.order import Order
from apps.briefing.app.services.order_analytics import summarize
from apps.briefing.app.services.order import (
    attach_position_context,
    enrich_orders,
    format_order_message,
    map_order,
    notify_orders,
    sync_all,
)

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
    side: str | None = None,
    reduce_only: bool = False,
    realized_pnl: Decimal | None = None,
    leverage: str | None = None,
    quantity: Decimal = Decimal("1"),
    average_price: Decimal = Decimal("100"),
    position_qty_before: Decimal | None = None,
    position_qty_after: Decimal | None = None,
    position_avg_price: Decimal | None = None,
) -> Order:
    if side is None:
        side = "SELL" if reduce_only else "BUY"
    return Order(
        order_id=order_id,
        symbol="QQQUSDT",
        side=side,
        reduce_only=reduce_only,
        order_type="Market",
        quantity=quantity,
        average_price=average_price,
        fee=Decimal("0.1"),
        filled_at=FILLED_AT,
        created_at=FILLED_AT,
        realized_pnl=realized_pnl,
        leverage=leverage,
        position_qty_before=position_qty_before,
        position_qty_after=position_qty_after,
        position_avg_price=position_avg_price,
        synced_at=SYNCED_AT,
    )


class TestOrders(DbTestCase):
    def test_map_order(self):
        order = map_order(ORDER_HISTORY_ROW, synced_at=SYNCED_AT)
        self.assertEqual(order.side, "BUY")
        self.assertEqual(order.fee, Decimal("0.5"))
        self.assertIsNone(order.realized_pnl)

    def test_save_upsert_idempotent(self):
        order = map_order(ORDER_HISTORY_ROW, synced_at=SYNCED_AT)
        Order.save(order)
        Order.save(order.model_copy(update={"quantity": Decimal("12")}))
        self.assertEqual(len(Order.all()), 1)
        self.assertEqual(Order.load(order.order_id).quantity, Decimal("12"))

    @patch("apps.briefing.app.services.order.enrich_orders")
    @patch("apps.briefing.app.services.order.time.time")
    @patch("apps.briefing.app.services.order.bybit.fetch_order_history")
    def test_sync_all_mocked(self, mock_fetch, mock_time, mock_enrich):
        mock_time.return_value = 1_700_000_000
        mock_fetch.return_value = [ORDER_HISTORY_ROW]
        mock_enrich.return_value = {"fetched": 0, "updated": 0}
        result = sync_all()
        self.assertEqual(result["saved"], 1)
        self.assertEqual(len(Order.all()), 1)

    @patch("apps.briefing.app.services.order.enrich_orders")
    @patch("apps.briefing.app.services.order.time.time")
    @patch("apps.briefing.app.services.order.bybit.fetch_order_history")
    def test_sync_all_dry_run_skips_persist(self, mock_fetch, mock_time, mock_enrich):
        mock_time.return_value = 1_700_000_000
        mock_fetch.return_value = [ORDER_HISTORY_ROW]
        result = sync_all(dry_run=True)
        self.assertEqual(result["saved"], 1)
        self.assertEqual(len(result["new_orders"]), 1)
        self.assertEqual(len(Order.all()), 0)
        mock_enrich.assert_not_called()

    @patch("apps.briefing.app.services.order.bybit.fetch_closed_pnl")
    def test_enrich_sets_realized_pnl(self, mock_fetch):
        Order.save(_order(order_id="exit-order-id", reduce_only=True))
        mock_fetch.return_value = [
            {"orderId": "exit-order-id", "closedPnl": "12.5", "leverage": "3"}
        ]
        self.assertEqual(enrich_orders(start_ms=1, end_ms=2)["updated"], 1)
        self.assertEqual(Order.load("exit-order-id").realized_pnl, Decimal("12.5"))

    def test_analytics_summarize(self):
        Order.save(_order(order_id="entry"))
        Order.save(_order(order_id="win", reduce_only=True, realized_pnl=Decimal("10")))
        Order.save(_order(order_id="loss", reduce_only=True, realized_pnl=Decimal("-5")))
        Order.save(_order(order_id="flat", reduce_only=True, realized_pnl=Decimal("0")))
        now_ms = int(FILLED_AT.timestamp() * 1000) + 86_400_000
        stats = summarize(Order.all(), period="7d", now_ms=now_ms)
        self.assertEqual(stats["n"], 2)
        self.assertEqual(stats["net_pnl"], Decimal("5"))

    def test_save_returns_true_only_for_new_order(self):
        order = map_order(ORDER_HISTORY_ROW, synced_at=SYNCED_AT)
        self.assertTrue(Order.save(order))
        self.assertFalse(Order.save(order))

    @patch("apps.briefing.app.services.order.discord.send_trade")
    def test_notify_orders_stdout_only_skips_discord(self, mock_send):
        posted = notify_orders([_order(order_id="new")], stdout_only=True)
        self.assertEqual(posted, 1)
        mock_send.assert_not_called()

    @patch("apps.briefing.app.services.order.discord.send_trade")
    def test_notify_orders_posts_new_only(self, mock_send):
        Order.save(_order(order_id="old"))
        order = _order(order_id="new")
        posted = notify_orders([order])
        self.assertEqual(posted, 1)
        mock_send.assert_called_once()
        self.assertTrue(mock_send.call_args.args[0].startswith("```"))


class TestOrderMessage(unittest.TestCase):
    WHEN = "⏰ 2026-08-28 15:30:00"

    def test_format_long_entry(self):
        text = format_order_message(_order(order_id="long-entry", side="BUY"))
        self.assertEqual(
            text,
            "\n".join(
                [
                    "롱 진입",
                    "",
                    "🟢 롱: QQQUSDT",
                    "📍 시장가: 100",
                    "📦 수량: 1",
                    "💵 평단: 100",
                    "",
                    self.WHEN,
                ]
            ),
        )

    def test_format_short_entry(self):
        text = format_order_message(_order(order_id="short-entry", side="SELL"))
        self.assertEqual(
            text,
            "\n".join(
                [
                    "숏 진입",
                    "",
                    "🔴 숏: QQQUSDT",
                    "📍 시장가: 100",
                    "📦 수량: 1",
                    "💵 평단: 100",
                    "",
                    self.WHEN,
                ]
            ),
        )

    def test_format_take_profit(self):
        text = format_order_message(
            _order(
                order_id="tp",
                side="SELL",
                reduce_only=True,
                realized_pnl=Decimal("12.5"),
                leverage="3",
            )
        )
        self.assertEqual(
            text,
            "\n".join(
                [
                    "롱 익절",
                    "",
                    "🟢 롱: QQQUSDT(x3)",
                    "📍 시장가: 100",
                    "💰 실현: 13",
                    "📈 ROE: 37.50%",
                    "",
                    self.WHEN,
                ]
            ),
        )

    def test_format_stop_loss(self):
        text = format_order_message(
            _order(
                order_id="sl",
                side="SELL",
                reduce_only=True,
                realized_pnl=Decimal("-8.2"),
                leverage="3",
            )
        )
        self.assertEqual(
            text,
            "\n".join(
                [
                    "❌ 롱 손절",
                    "",
                    "🟢 롱: QQQUSDT(x3)",
                    "📍 시장가: 100",
                    "💰 실현: -8",
                    "📈 ROE: -24.60%",
                    "",
                    self.WHEN,
                ]
            ),
        )

    def test_format_partial_take_profit(self):
        text = format_order_message(
            _order(
                order_id="partial-tp",
                side="SELL",
                reduce_only=True,
                quantity=Decimal("5"),
                realized_pnl=Decimal("12.5"),
                leverage="3",
                position_qty_before=Decimal("20"),
                position_qty_after=Decimal("15"),
            )
        )
        self.assertEqual(
            text,
            "\n".join(
                [
                    "롱 분할 익절",
                    "",
                    "🟢 롱: QQQUSDT(x3)",
                    "📍 시장가: 100",
                    "📦 수량: 20 → 15",
                    "💰 실현: 13",
                    "📈 ROE: 7.50%",
                    "",
                    self.WHEN,
                ]
            ),
        )

    def test_format_partial_stop_loss(self):
        text = format_order_message(
            _order(
                order_id="partial-sl",
                side="SELL",
                reduce_only=True,
                quantity=Decimal("5"),
                realized_pnl=Decimal("-8.2"),
                leverage="3",
                position_qty_before=Decimal("20"),
                position_qty_after=Decimal("15"),
            )
        )
        self.assertEqual(
            text,
            "\n".join(
                [
                    "❌ 롱 분할 손절",
                    "",
                    "🟢 롱: QQQUSDT(x3)",
                    "📍 시장가: 100",
                    "📦 수량: 20 → 15",
                    "💰 실현: -8",
                    "📈 ROE: -4.92%",
                    "",
                    self.WHEN,
                ]
            ),
        )

    def test_format_add_entry(self):
        text = format_order_message(
            _order(
                order_id="add",
                side="BUY",
                quantity=Decimal("5"),
                position_qty_before=Decimal("20"),
                position_qty_after=Decimal("25"),
                position_avg_price=Decimal("98"),
            )
        )
        self.assertEqual(
            text,
            "\n".join(
                [
                    "롱 추가 진입",
                    "",
                    "🟢 롱: QQQUSDT",
                    "📍 시장가: 100",
                    "📦 수량: 20 → 25",
                    "💵 평단: 98",
                    "",
                    self.WHEN,
                ]
            ),
        )

    def test_attach_position_context(self):
        t0 = FILLED_AT
        t1 = FILLED_AT + timedelta(minutes=1)
        t2 = FILLED_AT + timedelta(minutes=2)
        t3 = FILLED_AT + timedelta(minutes=3)
        open_order = _order(order_id="open", side="BUY", quantity=Decimal("20"))
        open_order = open_order.model_copy(update={"filled_at": t0, "created_at": t0})
        add_order = _order(
            order_id="add",
            side="BUY",
            quantity=Decimal("5"),
            average_price=Decimal("110"),
        )
        add_order = add_order.model_copy(update={"filled_at": t1, "created_at": t1})
        partial = _order(
            order_id="partial",
            side="SELL",
            reduce_only=True,
            quantity=Decimal("5"),
            realized_pnl=Decimal("10"),
        )
        partial = partial.model_copy(update={"filled_at": t2, "created_at": t2})
        close = _order(
            order_id="close",
            side="SELL",
            reduce_only=True,
            quantity=Decimal("20"),
            realized_pnl=Decimal("20"),
        )
        close = close.model_copy(update={"filled_at": t3, "created_at": t3})
        orders = attach_position_context([partial, close, add_order, open_order])
        by_id = {order.order_id: order for order in orders}
        self.assertEqual(by_id["open"].position_qty_after, Decimal("20"))
        self.assertEqual(by_id["add"].position_qty_before, Decimal("20"))
        self.assertEqual(by_id["add"].position_qty_after, Decimal("25"))
        self.assertEqual(by_id["partial"].position_qty_before, Decimal("25"))
        self.assertEqual(by_id["partial"].position_qty_after, Decimal("20"))
        self.assertEqual(by_id["close"].position_qty_after, Decimal("0"))


if __name__ == "__main__":
    unittest.main()
