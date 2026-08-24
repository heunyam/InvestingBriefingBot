import unittest
from unittest.mock import patch

from tinydb import TinyDB
from tinydb.storages import MemoryStorage

from app.collector import bybit_trades
from app.models import trade
from app.models import db as db_mod
from app.services import trade_message, trade_sync


class FakeHTTP:
    def __init__(self, *, positions=None, tx_pages=None):
        self.positions = positions or []
        self.tx_pages = list(tx_pages or [])

    def get_positions(self, **kwargs):
        return {"result": {"list": self.positions}}

    def get_open_orders(self, **kwargs):
        return {"result": {"list": []}}

    def get_closed_pnl(self, **kwargs):
        return {"result": {"list": []}}

    def get_transaction_log(self, **kwargs):
        if not self.tx_pages:
            return {"result": {"list": [], "nextPageCursor": ""}}
        return self.tx_pages.pop(0)


class TestTradeSync(unittest.TestCase):
    def setUp(self):
        self._db = TinyDB(storage=MemoryStorage)
        self._orig = db_mod._db
        db_mod._db = self._db
        self._epoch = patch.object(trade_sync, "SYNC_START_MS", 0)
        self._epoch.start()

    def tearDown(self):
        self._epoch.stop()
        db_mod._db = self._orig

    def test_sync_open_positions_with_tpsl(self):
        http = FakeHTTP(
            positions=[
                {
                    "symbol": "BTCUSDT",
                    "side": "Buy",
                    "size": "0.1",
                    "positionIdx": 0,
                    "avgPrice": "64000",
                    "leverage": "3",
                    "takeProfit": "67000",
                    "stopLoss": "62000",
                    "updatedTime": "1000",
                }
            ]
        )
        docs = trade_sync.sync_open_positions(session=http)
        self.assertEqual(len(docs), 1)
        doc = docs[0]
        self.assertEqual(doc["status"], "OPEN")
        self.assertEqual(doc["side"], "LONG")
        self.assertEqual(doc["prices"]["entry"], "64000")
        kinds = {p["kind"] for p in doc["protections"]}
        self.assertEqual(kinds, {"TP", "SL"})
        self.assertTrue(trade_sync.needs_user_review(doc))

    def test_sync_open_positions_skips_before_sync_start(self):
        self._epoch.stop()
        try:
            with patch.object(trade_sync, "SYNC_START_MS", 1_000_000):
                http = FakeHTTP(
                    positions=[
                        {
                            "symbol": "OLDUSDT",
                            "side": "Buy",
                            "size": "1",
                            "avgPrice": "10",
                            "createdTime": "999999",
                        },
                        {
                            "symbol": "NEWUSDT",
                            "side": "Sell",
                            "size": "2",
                            "avgPrice": "20",
                            "createdTime": "1000000",
                        },
                    ]
                )
                docs = trade_sync.sync_open_positions(session=http)
                self.assertEqual(len(docs), 1)
                self.assertEqual(docs[0]["symbol"], "NEWUSDT")
                self.assertEqual(docs[0]["opened_at_ms"], 1_000_000)
        finally:
            self._epoch = patch.object(trade_sync, "SYNC_START_MS", 0)
            self._epoch.start()

    def test_tx_open_close(self):
        http = FakeHTTP(
            tx_pages=[
                {
                    "result": {
                        "list": [
                            {
                                "id": "1",
                                "type": "TRADE",
                                "symbol": "ETHUSDT",
                                "side": "Buy",
                                "qty": "1",
                                "tradePrice": "100",
                                "fee": "0.1",
                                "cashFlow": "0",
                                "funding": "0",
                                "transactionTime": "100",
                            },
                            {
                                "id": "2",
                                "type": "TRADE",
                                "symbol": "ETHUSDT",
                                "side": "Sell",
                                "qty": "1",
                                "tradePrice": "110",
                                "fee": "0.1",
                                "cashFlow": "10",
                                "funding": "0",
                                "transactionTime": "200",
                            },
                        ],
                        "nextPageCursor": "",
                    }
                }
            ]
        )
        self._db.table(trade_sync.META_TABLE).truncate()
        docs = trade_sync.sync_transaction_log(session=http, end_ms=300)
        closed = [d for d in trade.all() if d["status"] == "CLOSED"]
        self.assertEqual(len(closed), 1)
        self.assertEqual(closed[0]["symbol"], "ETHUSDT")
        self.assertEqual(closed[0]["side"], "LONG")

    def test_tx_idempotent(self):
        page = {
            "result": {
                "list": [
                    {
                        "id": "1",
                        "type": "TRADE",
                        "symbol": "ETHUSDT",
                        "side": "Buy",
                        "qty": "1",
                        "tradePrice": "100",
                        "fee": "0",
                        "cashFlow": "0",
                        "funding": "0",
                        "transactionTime": "100",
                    }
                ],
                "nextPageCursor": "",
            }
        }
        self._db.table(trade_sync.META_TABLE).truncate()
        trade_sync.sync_transaction_log(
            session=FakeHTTP(tx_pages=[page]), end_ms=300
        )
        n1 = len(trade.all()[0]["events"])
        self._db.table(trade_sync.META_TABLE).truncate()
        trade_sync.sync_transaction_log(
            session=FakeHTTP(tx_pages=[dict(page)]), end_ms=300
        )
        self.assertEqual(len(trade.all()[0]["events"]), n1)

    def test_format_and_notify(self):
        doc = trade.new_trade("abcdef12", "BTCUSDT", "LONG", 1, 1)
        doc["prices"]["entry"] = "100"
        doc["position"] = {"size": "1", "leverage": "2"}
        text = trade_message.format_trade_message(doc)
        self.assertIn("진입", text)
        self.assertIn("BTCUSDT", text)
        with patch(
            "app.outbound.discord_trade.upsert_trade_message", return_value="mid"
        ) as mock_up:
            from commands import trades as trades_cmd

            posted = trades_cmd.notify_pending_reviews([doc])
            self.assertEqual(len(posted), 1)
            mock_up.assert_called_once()
            saved = trade.load("abcdef12")
            self.assertEqual(saved["discord"]["message_id"], "mid")


if __name__ == "__main__":
    unittest.main()
