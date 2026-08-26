import unittest
from unittest.mock import patch

from tinydb import TinyDB
from tinydb.storages import MemoryStorage

from app.models import trade
from app.models import db as db_mod
from app.services import trade_review
from commands import trades_review


class TestTradesReviewCli(unittest.TestCase):
    def setUp(self):
        self._db = TinyDB(storage=MemoryStorage)
        self._orig = db_mod._db
        db_mod._db = self._db
        doc = trade.new_trade("abc12345ffff", "BTCUSDT", "LONG", 1, 1)
        doc["status"] = "CLOSED"
        doc["closed_at_ms"] = 2
        doc["pnl"] = {"amount": "10", "result": "WIN"}
        trade.save(doc)

    def tearDown(self):
        db_mod._db = self._orig

    def test_save_by_prefix_stdout_only(self):
        with patch("app.outbound.discord_trade.send_trade") as send:
            with patch("app.outbound.discord_trade.edit_trade") as edit:
                trades_review.app(
                    [
                        "--id",
                        "abc12345",
                        "--entry",
                        "breakout",
                        "--exit",
                        "target",
                        "--stdout-only",
                    ]
                )
        send.assert_not_called()
        edit.assert_not_called()
        saved = trade.load("abc12345ffff")
        self.assertEqual(saved["review"]["entry_reason"], "breakout")
        self.assertEqual(saved["review"]["exit_reason"], "target")

    def test_list_pending_without_id(self):
        trades_review.app([])
        pending = trade_review.pending_closed_reviews()
        self.assertEqual(len(pending), 1)
