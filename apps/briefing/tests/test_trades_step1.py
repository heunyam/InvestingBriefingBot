import unittest

from tinydb import TinyDB
from tinydb.storages import MemoryStorage

from app.collector import bybit_trades
from app.models import trade
from app.models.db import Doc


class FakeHTTP:
    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = []

    def get_positions(self, **kwargs):
        self.calls.append(("positions", kwargs))
        return {"result": {"list": self.pages.pop(0)}}

    def get_open_orders(self, **kwargs):
        self.calls.append(("orders", kwargs))
        return {"result": {"list": self.pages.pop(0)}}

    def get_transaction_log(self, **kwargs):
        self.calls.append(("tx", kwargs))
        return self.pages.pop(0)


class TestBybitTrades(unittest.TestCase):
    def test_reject_hedge(self):
        http = FakeHTTP([[{"symbol": "BTCUSDT", "positionIdx": 1, "size": "1"}]])
        with self.assertRaises(ValueError):
            bybit_trades.fetch_positions(session=http)

    def test_one_way_ok(self):
        http = FakeHTTP([[{"symbol": "BTCUSDT", "positionIdx": 0, "size": "1"}]])
        rows = bybit_trades.fetch_positions(session=http)
        self.assertEqual(len(rows), 1)

    def test_tx_cursor_and_window(self):
        page1 = {
            "result": {
                "list": [{"id": "a"}],
                "nextPageCursor": "c1",
            }
        }
        page2 = {"result": {"list": [{"id": "b"}], "nextPageCursor": ""}}
        http = FakeHTTP([page1, page2])
        rows = bybit_trades.fetch_transaction_log(session=http, start_ms=0, end_ms=1000)
        self.assertEqual([r["id"] for r in rows], ["a", "b"])
        self.assertEqual(http.calls[1][1]["cursor"], "c1")


class TestTradeDoc(unittest.TestCase):
    def test_weighted_avg_and_pnl(self):
        doc = trade.new_trade("t1", "BTCUSDT", "LONG", 1, 1)
        trade.upsert_event(
            doc,
            {
                "event_key": "k1",
                "event_type": "OPEN",
                "price": "100",
                "quantity": "2",
                "fee": "1",
                "cash_flow": "0",
                "funding": "0",
                "realized_pnl": "0",
                "occurred_at_ms": 1,
            },
            1,
        )
        trade.upsert_event(
            doc,
            {
                "event_key": "k2",
                "event_type": "ADD",
                "price": "200",
                "quantity": "2",
                "fee": "1",
                "cash_flow": "0",
                "funding": "0",
                "realized_pnl": "0",
                "occurred_at_ms": 2,
            },
            2,
        )
        self.assertEqual(doc["prices"]["entry"], "150")
        trade.upsert_event(
            doc,
            {
                "event_key": "k3",
                "event_type": "CLOSE",
                "price": "180",
                "quantity": "4",
                "fee": "0",
                "cash_flow": "0",
                "funding": "2",
                "realized_pnl": "120",
                "occurred_at_ms": 3,
            },
            3,
        )
        self.assertEqual(doc["status"], "CLOSED")
        self.assertEqual(doc["prices"]["exit"], "180")
        self.assertEqual(doc["pnl"]["amount"], "120")
        self.assertEqual(doc["pnl"]["result"], "WIN")

    def test_event_idempotent(self):
        doc = trade.new_trade("t1", "BTCUSDT", "LONG", 1, 1)
        ev = {
            "event_key": "k1",
            "event_type": "OPEN",
            "price": "100",
            "quantity": "1",
            "fee": "0",
            "occurred_at_ms": 1,
        }
        trade.upsert_event(doc, ev, 1)
        trade.upsert_event(doc, ev, 2)
        self.assertEqual(len(doc["events"]), 1)

    def test_protection_idempotent_and_save(self):
        db = TinyDB(storage=MemoryStorage)
        table = db.table("trades")
        doc = trade.new_trade("t1", "BTCUSDT", "LONG", 1, 1)
        p = {
            "bybit_order_id": "o1",
            "kind": "TP",
            "trigger_price": "110",
            "quantity": "1",
            "mode": "FULL",
            "status": "ACTIVE",
        }
        trade.upsert_protection(doc, p, 1)
        trade.upsert_protection(doc, {**p, "status": "CANCELLED"}, 2)
        self.assertEqual(len(doc["protections"]), 1)
        self.assertEqual(doc["protections"][0]["status"], "CANCELLED")
        table.upsert(doc, Doc.trade_id == "t1")
        table.upsert(doc, Doc.trade_id == "t1")
        self.assertEqual(len(table), 1)


if __name__ == "__main__":
    unittest.main()
