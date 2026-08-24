import unittest
from unittest.mock import patch

from tinydb import TinyDB
from tinydb.storages import MemoryStorage

from app.models import trade
from app.models import db as db_mod
from app.services import trade_message, trade_sync
from commands import trades as trades_cmd


class FakeHTTP:
    def __init__(self, *, positions=None, orders=None, tx_pages=None):
        self.positions = positions or []
        self.orders = orders or []
        self.tx_pages = list(tx_pages or [])

    def get_positions(self, **kwargs):
        return {"result": {"list": self.positions}}

    def get_open_orders(self, **kwargs):
        return {"result": {"list": self.orders}}

    def get_closed_pnl(self, **kwargs):
        return {"result": {"list": []}}

    def get_transaction_log(self, **kwargs):
        if not self.tx_pages:
            return {"result": {"list": [], "nextPageCursor": ""}}
        return self.tx_pages.pop(0)


def _tx_page(rows):
    return {"result": {"list": rows, "nextPageCursor": ""}}


def _trade_row(id_, symbol, side, qty, price, t, **extra):
    row = {
        "id": id_,
        "type": "TRADE",
        "symbol": symbol,
        "side": side,
        "qty": qty,
        "tradePrice": price,
        "fee": extra.get("fee", "0"),
        "cashFlow": extra.get("cashFlow", "0"),
        "funding": extra.get("funding", "0"),
        "transactionTime": str(t),
    }
    if extra.get("size") is not None:
        row["size"] = str(extra["size"])
    return row


class TestTradeSyncStep2(unittest.TestCase):
    def setUp(self):
        self._db = TinyDB(storage=MemoryStorage)
        self._orig = db_mod._db
        db_mod._db = self._db
        self._epoch = patch.object(trade_sync, "SYNC_START_MS", 0)
        self._epoch.start()

    def tearDown(self):
        self._epoch.stop()
        db_mod._db = self._orig

    def test_split_entry_same_trade_id_then_close(self):
        http = FakeHTTP(
            tx_pages=[
                _tx_page(
                    [
                        _trade_row("1", "ETHUSDT", "Buy", "1", "100", 100),
                        _trade_row("2", "ETHUSDT", "Buy", "1", "110", 200),
                        _trade_row(
                            "3",
                            "ETHUSDT",
                            "Sell",
                            "2",
                            "120",
                            300,
                            cashFlow="30",
                        ),
                    ]
                )
            ]
        )
        trade_sync.sync_transaction_log(session=http, end_ms=400)
        rows = trade.all()
        self.assertEqual(len(rows), 1)
        doc = rows[0]
        self.assertEqual(doc["status"], "CLOSED")
        types = [e["event_type"] for e in doc["events"]]
        self.assertEqual(types, ["OPEN", "ADD", "CLOSE"])
        self.assertEqual(doc["trade_id"], rows[0]["trade_id"])

    def test_partial_close_keeps_trade_id(self):
        http = FakeHTTP(
            tx_pages=[
                _tx_page(
                    [
                        _trade_row("1", "ETHUSDT", "Buy", "2", "100", 100),
                        _trade_row(
                            "2",
                            "ETHUSDT",
                            "Sell",
                            "1",
                            "110",
                            200,
                            cashFlow="10",
                        ),
                    ]
                )
            ]
        )
        trade_sync.sync_transaction_log(session=http, end_ms=300)
        rows = trade.all()
        self.assertEqual(len(rows), 1)
        doc = rows[0]
        self.assertEqual(doc["status"], "OPEN")
        self.assertEqual(doc["position"]["size"], "1")
        types = [e["event_type"] for e in doc["events"]]
        self.assertEqual(types, ["OPEN", "PARTIAL_CLOSE"])
        trade_id = doc["trade_id"]
        http2 = FakeHTTP(
            tx_pages=[
                _tx_page(
                    [
                        _trade_row(
                            "3",
                            "ETHUSDT",
                            "Sell",
                            "1",
                            "120",
                            300,
                            cashFlow="20",
                        )
                    ]
                )
            ]
        )
        trade_sync.sync_transaction_log(session=http2, end_ms=400)
        rows = trade.all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["trade_id"], trade_id)
        self.assertEqual(rows[0]["status"], "CLOSED")
        self.assertEqual(
            [e["event_type"] for e in rows[0]["events"]],
            ["OPEN", "PARTIAL_CLOSE", "CLOSE"],
        )

    def test_reopen_gets_new_trade_id(self):
        page1 = _tx_page(
            [
                _trade_row("1", "ETHUSDT", "Buy", "1", "100", 100),
                _trade_row("2", "ETHUSDT", "Sell", "1", "110", 200, cashFlow="10"),
            ]
        )
        page2 = _tx_page([_trade_row("3", "ETHUSDT", "Buy", "1", "105", 300)])
        trade_sync.sync_transaction_log(session=FakeHTTP(tx_pages=[page1]), end_ms=250)
        first_id = trade.all()[0]["trade_id"]
        trade_sync.sync_transaction_log(session=FakeHTTP(tx_pages=[page2]), end_ms=400)
        ids = {d["trade_id"] for d in trade.all()}
        self.assertEqual(len(ids), 2)
        open_docs = [d for d in trade.all() if d["status"] == "OPEN"]
        self.assertEqual(len(open_docs), 1)
        self.assertNotEqual(open_docs[0]["trade_id"], first_id)

    def test_partial_tpsl_from_open_orders(self):
        http = FakeHTTP(
            positions=[
                {
                    "symbol": "BTCUSDT",
                    "side": "Buy",
                    "size": "0.10",
                    "positionIdx": 0,
                    "avgPrice": "64000",
                    "leverage": "3",
                    "takeProfit": "",
                    "stopLoss": "62000",
                    "updatedTime": "1000",
                }
            ],
            orders=[
                {
                    "symbol": "BTCUSDT",
                    "orderId": "ord-tp-1",
                    "stopOrderType": "PartialTakeProfit",
                    "triggerPrice": "67000",
                    "qty": "0.04",
                    "tpslMode": "Partial",
                    "orderStatus": "Untriggered",
                },
                {
                    "symbol": "BTCUSDT",
                    "orderId": "ord-tp-2",
                    "stopOrderType": "PartialTakeProfit",
                    "triggerPrice": "69000",
                    "qty": "0.06",
                    "tpslMode": "Partial",
                    "orderStatus": "Untriggered",
                },
            ],
        )
        docs = trade_sync.sync_open_positions(session=http)
        self.assertEqual(len(docs), 1)
        kinds = [(p["kind"], p["mode"], p["trigger_price"]) for p in docs[0]["protections"]]
        self.assertIn(("SL", "FULL", "62000"), kinds)
        self.assertIn(("TP", "PARTIAL", "67000"), kinds)
        self.assertIn(("TP", "PARTIAL", "69000"), kinds)
        text = trade_message.format_trade_message(docs[0])
        self.assertIn("BTCUSDT", text)
        self.assertIn("진입", text)

    def test_tpsl_cleared_when_orders_gone(self):
        http1 = FakeHTTP(
            positions=[
                {
                    "symbol": "BTCUSDT",
                    "side": "Buy",
                    "size": "0.1",
                    "positionIdx": 0,
                    "avgPrice": "64000",
                    "takeProfit": "67000",
                    "stopLoss": "62000",
                }
            ]
        )
        trade_sync.sync_open_positions(session=http1)
        self.assertEqual(len(trade.all()[0]["protections"]), 2)
        http2 = FakeHTTP(
            positions=[
                {
                    "symbol": "BTCUSDT",
                    "side": "Buy",
                    "size": "0.1",
                    "positionIdx": 0,
                    "avgPrice": "64000",
                    "takeProfit": "",
                    "stopLoss": "",
                }
            ],
            orders=[],
        )
        trade_sync.sync_open_positions(session=http2)
        self.assertEqual(trade.all()[0]["protections"], [])
        self.assertIn("진입", trade_message.format_trade_message(trade.all()[0]))

    def test_discord_skips_reviewed(self):
        pending = trade.new_trade("pend0001", "BTCUSDT", "LONG", 1, 1)
        pending["prices"]["entry"] = "100"
        pending["position"] = {"size": "1", "leverage": "2"}
        trade.save(pending)
        done = trade.new_trade("done0001", "ETHUSDT", "LONG", 1, 1)
        done["status"] = "CLOSED"
        done["review"] = {
            "entry_reason": "breakout",
            "exit_reason": "target",
        }
        trade.save(done)
        with patch(
            "app.outbound.discord_trade.upsert_trade_message", return_value="mid"
        ) as mock_up:
            posted = trades_cmd.notify_pending_reviews(trade.all())
        self.assertEqual(len(posted), 1)
        self.assertEqual(posted[0]["trade_id"], "pend0001")
        mock_up.assert_called_once()

    def test_tx_idempotent(self):
        page = _tx_page([_trade_row("1", "ETHUSDT", "Buy", "1", "100", 100)])
        trade_sync.sync_transaction_log(
            session=FakeHTTP(tx_pages=[page]), end_ms=300
        )
        n1 = len(trade.all()[0]["events"])
        trade_sync.set_last_synced_ms(0)
        trade_sync.sync_transaction_log(
            session=FakeHTTP(
                tx_pages=[_tx_page([_trade_row("1", "ETHUSDT", "Buy", "1", "100", 100)])]
            ),
            end_ms=300,
        )
        self.assertEqual(len(trade.all()[0]["events"]), n1)

    def test_trailing_stop_from_open_orders(self):
        http = FakeHTTP(
            positions=[
                {
                    "symbol": "BTCUSDT",
                    "side": "Buy",
                    "size": "0.1",
                    "positionIdx": 0,
                    "avgPrice": "64000",
                    "takeProfit": "",
                    "stopLoss": "",
                }
            ],
            orders=[
                {
                    "symbol": "BTCUSDT",
                    "orderId": "trail-1",
                    "stopOrderType": "TrailingStop",
                    "triggerPrice": "63000",
                    "qty": "0.1",
                    "orderStatus": "Untriggered",
                }
            ],
        )
        docs = trade_sync.sync_open_positions(session=http)
        kinds = {p["kind"] for p in docs[0]["protections"]}
        self.assertEqual(kinds, {"TRAILING_STOP"})
        self.assertEqual(docs[0]["protections"][0]["mode"], "PARTIAL")
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
        self.assertEqual(docs[0]["side"], "LONG")
        kinds = {p["kind"] for p in docs[0]["protections"]}
        self.assertEqual(kinds, {"TP", "SL"})

    def test_mid_window_sell_is_long_partial_not_short_open(self):
        http = FakeHTTP(
            tx_pages=[
                _tx_page(
                    [
                        _trade_row(
                            "528118843_BTCUSDT_1_0",
                            "BTCUSDT",
                            "Sell",
                            "0.125",
                            "72100",
                            200,
                            cashFlow="1026",
                            size="0.375",
                        ),
                        _trade_row(
                            "528118843_BTCUSDT_2_0",
                            "BTCUSDT",
                            "Sell",
                            "0.2",
                            "78000",
                            300,
                            cashFlow="2823",
                            size="0.175",
                        ),
                    ]
                )
            ]
        )
        trade_sync.sync_transaction_log(session=http, end_ms=400)
        rows = trade.all()
        self.assertEqual(len(rows), 1)
        doc = rows[0]
        self.assertEqual(doc["side"], "LONG")
        self.assertEqual(doc["status"], "OPEN")
        self.assertEqual(doc["position"]["size"], "0.175")
        self.assertEqual(
            [e["event_type"] for e in doc["events"]],
            ["PARTIAL_CLOSE", "PARTIAL_CLOSE"],
        )
        self.assertFalse(any(d["side"] == "SHORT" for d in rows))

    def test_settlement_rows_are_not_fills(self):
        eight = trade_sync.FUNDING_INTERVAL_MS
        http = FakeHTTP(
            tx_pages=[
                _tx_page(
                    [
                        _trade_row("1", "MUUSDT", "Buy", "5", "954", 100),
                        {
                            "id": "fund1",
                            "type": "SETTLEMENT",
                            "symbol": "MUUSDT",
                            "side": "Buy",
                            "qty": "5",
                            "tradePrice": "960",
                            "fee": "0",
                            "cashFlow": "0",
                            "funding": "0.1",
                            "transactionTime": str(eight),
                        },
                        _trade_row(
                            "2", "MUUSDT", "Sell", "5", "911", eight + 50, cashFlow="-10"
                        ),
                    ]
                )
            ]
        )
        trade_sync.sync_transaction_log(session=http, end_ms=eight + 100)
        docs = trade.all()
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["status"], "CLOSED")
        self.assertEqual([e["event_type"] for e in docs[0]["events"]], ["OPEN", "CLOSE"])

    def test_purge_legacy_funding_adds_closes_trade(self):
        eight = trade_sync.FUNDING_INTERVAL_MS
        doc = trade.new_trade("576c9bxx", "MUUSDT", "LONG", 100, 100)
        trade.upsert_event(
            doc,
            {
                "event_key": "a",
                "event_type": "OPEN",
                "price": "954",
                "quantity": "5",
                "fee": "0",
                "cash_flow": "0",
                "funding": "0",
                "realized_pnl": "0",
                "occurred_at_ms": 100,
                "source_ids": ["open"],
            },
            100,
        )
        trade.upsert_event(
            doc,
            {
                "event_key": "b",
                "event_type": "ADD",
                "price": "960",
                "quantity": "5",
                "fee": "0",
                "cash_flow": "0",
                "funding": "0",
                "realized_pnl": "0",
                "occurred_at_ms": eight,
                "source_ids": ["fund"],
            },
            eight,
        )
        trade.upsert_event(
            doc,
            {
                "event_key": "c",
                "event_type": "PARTIAL_CLOSE",
                "price": "911",
                "quantity": "5",
                "fee": "0",
                "cash_flow": "-10",
                "funding": "0",
                "realized_pnl": "0",
                "occurred_at_ms": eight + 50,
                "source_ids": ["close"],
            },
            eight + 50,
        )
        trade.save(doc)
        self.assertEqual(trade.load("576c9bxx")["status"], "OPEN")
        trade_sync.purge_funding_like_events()
        fixed = trade.load("576c9bxx")
        self.assertEqual(fixed["status"], "CLOSED")
        self.assertEqual(fixed["position"]["size"], "0")

    def test_stamp_leverage_from_closed_pnl(self):
        doc = trade.new_trade("04c76axx", "ETHUSDT", "LONG", 1, 1)
        doc["status"] = "CLOSED"
        doc["position"] = {"size": "0", "leverage": None}
        trade.save(doc)

        class ClosedHTTP:
            def get_positions(self, **kwargs):
                return {"result": {"list": []}}

            def get_closed_pnl(self, **kwargs):
                return {
                    "result": {
                        "list": [{"symbol": "ETHUSDT", "leverage": "5", "closedPnl": "1"}]
                    }
                }

        trade_sync.stamp_leverage(session=ClosedHTTP())
        self.assertEqual(trade.load("04c76axx")["position"]["leverage"], "5")

    def test_stamp_leverage_from_flat_position(self):
        doc = trade.new_trade("04c76axx", "ETHUSDT", "LONG", 1, 1)
        doc["status"] = "CLOSED"
        doc["position"] = {"size": "0", "leverage": None}
        trade.save(doc)
        http = FakeHTTP(
            positions=[
                {
                    "symbol": "ETHUSDT",
                    "side": "Buy",
                    "size": "0",
                    "positionIdx": 0,
                    "leverage": "10",
                }
            ]
        )
        trade_sync.stamp_leverage(session=http)
        self.assertEqual(trade.load("04c76axx")["position"]["leverage"], "10")


class TestSyncStartFloor(unittest.TestCase):
    def setUp(self):
        self._db = TinyDB(storage=MemoryStorage)
        self._orig = db_mod._db
        db_mod._db = self._db

    def tearDown(self):
        db_mod._db = self._orig

    def test_ignores_fills_before_sync_start(self):
        epoch = trade_sync.SYNC_START_MS
        http = FakeHTTP(
            tx_pages=[
                _tx_page(
                    [
                        _trade_row(
                            "old", "BTCUSDT", "Buy", "1", "100", epoch - 1000
                        ),
                        _trade_row(
                            "new",
                            "BTCUSDT",
                            "Buy",
                            "1",
                            "100",
                            epoch + 1000,
                            size="1",
                        ),
                        _trade_row(
                            "close",
                            "BTCUSDT",
                            "Sell",
                            "1",
                            "110",
                            epoch + 2000,
                            cashFlow="10",
                            size="0",
                        ),
                    ]
                )
            ]
        )
        trade_sync.sync_transaction_log(session=http, end_ms=epoch + 3000)
        docs = trade.all()
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["status"], "CLOSED")
        source_ids = {
            sid
            for ev in docs[0]["events"]
            for sid in (ev.get("source_ids") or [])
        }
        self.assertNotIn("old", source_ids)
        self.assertIn("new", source_ids)

    def test_sync_all_noop_before_start(self):
        with patch.object(trade_sync, "_ms_now", return_value=trade_sync.SYNC_START_MS - 1):
            result = trade_sync.sync_all(session=FakeHTTP())
        self.assertEqual(result["synced"], [])
        self.assertEqual(trade.all(), [])


if __name__ == "__main__":
    unittest.main()
