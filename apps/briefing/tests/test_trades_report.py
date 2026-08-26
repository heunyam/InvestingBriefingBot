import unittest
from decimal import Decimal
from unittest.mock import patch

from tinydb import TinyDB
from tinydb.storages import MemoryStorage

from app.collector import bybit_trades
from app.models import trade
from app.models import db as db_mod
from app.services import trade_analytics, trade_report, trade_sync
from commands import trades_report


def _closed(
    trade_id,
    symbol,
    *,
    opened,
    closed,
    amount,
    result,
    fee="0",
    funding="0",
    reviewed=False,
    stats_eligible=True,
):
    doc = trade.new_trade(trade_id, symbol, "LONG", opened, closed)
    doc["status"] = "CLOSED"
    doc["closed_at_ms"] = closed
    doc["pnl"] = {
        "amount": None if amount is None else str(amount),
        "result": result,
    }
    doc["stats_eligible"] = stats_eligible
    doc["events"] = [
        {
            "event_key": f"{trade_id}:open",
            "event_type": "OPEN",
            "occurred_at_ms": opened,
            "fee": "0",
            "funding": "0",
        },
        {
            "event_key": f"{trade_id}:close",
            "event_type": "CLOSE",
            "occurred_at_ms": closed,
            "fee": str(fee),
            "funding": str(funding),
        },
    ]
    if reviewed:
        doc["review"] = {
            "entry_reason": "breakout",
            "exit_reason": "target",
        }
    return doc


class TestTradeAnalytics(unittest.TestCase):
    def setUp(self):
        self._db = TinyDB(storage=MemoryStorage)
        self._orig = db_mod._db
        db_mod._db = self._db

    def tearDown(self):
        db_mod._db = self._orig

    def test_mixed_win_loss_and_zero_pnl(self):
        docs = [
            _closed(
                "w1",
                "BTCUSDT",
                opened=1,
                closed=10,
                amount="10",
                result="WIN",
                fee="1",
                reviewed=True,
            ),
            _closed(
                "l1",
                "BTCUSDT",
                opened=2,
                closed=20,
                amount="-5",
                result="LOSS",
                funding="0.5",
            ),
            _closed("z1", "ETHUSDT", opened=3, closed=30, amount="0", result=None),
            _closed("n1", "ETHUSDT", opened=4, closed=40, amount=None, result=None),
            _closed("w2", "ETHUSDT", opened=5, closed=50, amount="5", result="WIN"),
        ]
        stats = trade_analytics.summarize(docs, period="all", now_ms=100)
        self.assertEqual(stats["n"], 3)
        self.assertEqual(stats["wins"], 2)
        self.assertEqual(stats["losses"], 1)
        self.assertEqual(stats["net_pnl"], Decimal("10"))
        self.assertEqual(stats["win_rate"], Decimal("2") / Decimal("3"))
        self.assertEqual(stats["profit_factor"], Decimal("15") / Decimal("5"))
        self.assertEqual(stats["avg_win"], Decimal("7.5"))
        self.assertEqual(stats["avg_loss"], Decimal("-5"))
        self.assertEqual(stats["expectancy"], Decimal("10") / Decimal("3"))
        self.assertEqual(stats["max_win_streak"], 1)
        self.assertEqual(stats["max_loss_streak"], 1)
        self.assertEqual(stats["max_drawdown"], Decimal("-5"))
        self.assertEqual(stats["fees"], Decimal("1"))
        self.assertEqual(stats["funding"], Decimal("0.5"))
        self.assertEqual(stats["review_rate"], Decimal("1") / Decimal("3"))
        by_sym = {row["symbol"]: row for row in stats["by_symbol"]}
        self.assertEqual(by_sym["BTCUSDT"]["n"], 2)
        self.assertEqual(by_sym["ETHUSDT"]["n"], 1)

    def test_first_open_until_flat_excluded(self):
        docs = [
            _closed(
                "old",
                "BTCUSDT",
                opened=10,
                closed=80,
                amount="100",
                result="WIN",
                stats_eligible=False,
            ),
            _closed("new", "BTCUSDT", opened=90, closed=100, amount="2", result="WIN"),
        ]
        stats = trade_analytics.summarize(docs, period="all", now_ms=200)
        self.assertEqual(stats["n"], 1)
        self.assertEqual(stats["net_pnl"], Decimal("2"))

    def test_period_and_symbol_filter(self):
        now = 10 * trade_analytics.DAY_MS
        docs = [
            _closed(
                "a",
                "BTCUSDT",
                opened=1,
                closed=now - 2 * trade_analytics.DAY_MS,
                amount="1",
                result="WIN",
            ),
            _closed(
                "b",
                "ETHUSDT",
                opened=1,
                closed=now - 2 * trade_analytics.DAY_MS,
                amount="2",
                result="WIN",
            ),
            _closed(
                "c",
                "BTCUSDT",
                opened=1,
                closed=now - 20 * trade_analytics.DAY_MS,
                amount="9",
                result="WIN",
            ),
        ]
        week = trade_analytics.summarize(
            docs, period="7d", now_ms=now, symbol="BTCUSDT"
        )
        self.assertEqual(week["n"], 1)
        self.assertEqual(week["net_pnl"], Decimal("1"))


class TestTradeReportCli(unittest.TestCase):
    def setUp(self):
        self._db = TinyDB(storage=MemoryStorage)
        self._orig = db_mod._db
        db_mod._db = self._db
        trade.save(
            _closed(
                "w1",
                "BTCUSDT",
                opened=1,
                closed=10,
                amount="4",
                result="WIN",
                reviewed=True,
            )
        )

    def tearDown(self):
        db_mod._db = self._orig

    def test_stdout_only_skips_http(self):
        with patch("app.outbound.discord.send_daily") as send:
            text = trades_report.app(["--period", "all", "--stdout-only"])
        send.assert_not_called()
        self.assertIn("매매 성과 · 전체", text)
        self.assertIn("거래 1", text)

    def test_webhook_uses_daily_url_not_trade(self):
        captured = []

        class FakeResp:
            def raise_for_status(self):
                return None

            def json(self):
                return {"id": "report-id"}

        def fake_post(url, **kwargs):
            captured.append((url, kwargs.get("json") or {}))
            return FakeResp()

        with patch(
            "app.outbound.discord.DAILY_WEBHOOK_URL",
            "https://discord.test/webhooks/daily",
        ):
            with patch("app.outbound.discord.requests.post", side_effect=fake_post):
                with patch("app.outbound.discord_trade.send_trade") as trade_send:
                    trades_report.app(["--period", "all"])
        trade_send.assert_not_called()
        self.assertEqual(len(captured), 1)
        url, body = captured[0]
        self.assertIn("/webhooks/daily", url)
        self.assertNotIn("trade", url)
        content = body["content"]
        self.assertTrue(content.startswith("```\n"))
        self.assertTrue(content.endswith("\n```"))
        saved = trade.load("w1")
        self.assertEqual((saved.get("discord") or {}).get("messages") or [], [])

    def test_format_matches_layout(self):
        stats = trade_analytics.summarize(trade.all(), period="all", now_ms=100)
        text = trade_report.format_report(stats)
        self.assertIn("📊 매매 성과", text)
        self.assertIn("💰 순손익", text)
        self.assertIn("📝 복기", text)
        self.assertIn("종목별", text)
        self.assertIn("BTCUSDT", text)


class TestBackfillLookback(unittest.TestCase):
    def setUp(self):
        self._db = TinyDB(storage=MemoryStorage)
        self._orig = db_mod._db
        db_mod._db = self._db
        self._epoch = patch.object(trade_sync, "SYNC_START_MS", 0)
        self._epoch.start()

    def tearDown(self):
        self._epoch.stop()
        db_mod._db = self._orig

    def test_backfill_uses_two_year_window(self):
        captured = {}

        def fake_fetch(session=None, start_ms=0, end_ms=0):
            captured["start"] = start_ms
            captured["end"] = end_ms
            return []

        trade_sync.set_last_synced_ms(1)
        with patch.object(bybit_trades, "fetch_transaction_log", fake_fetch):
            trade_sync.sync_transaction_log(end_ms=10_000, backfill=True)
        self.assertEqual(captured["end"], 10_000)
        self.assertEqual(
            captured["start"], max(0, 10_000 - trade_sync.BACKFILL_LOOKBACK_MS)
        )

    def test_backfill_flags_open_at_window_start(self):
        end_ms = trade_sync.BACKFILL_LOOKBACK_MS + 50
        preexisting = trade.new_trade("preexist", "BTCUSDT", "LONG", 10, 10)
        trade.upsert_event(
            preexisting,
            {
                "event_key": "pre:open",
                "event_type": "OPEN",
                "occurred_at_ms": 10,
                "price": "100",
                "quantity": "1",
                "fee": "0",
                "realized_pnl": "0",
                "cash_flow": "0",
                "funding": "0",
                "source_ids": ["0"],
            },
            10,
        )
        trade.save(preexisting)
        rows = [
            {
                "id": "2",
                "type": "TRADE",
                "symbol": "BTCUSDT",
                "side": "Sell",
                "qty": "1",
                "tradePrice": "110",
                "fee": "0",
                "cashFlow": "10",
                "funding": "0",
                "transactionTime": "80",
            },
            {
                "id": "3",
                "type": "TRADE",
                "symbol": "BTCUSDT",
                "side": "Buy",
                "qty": "1",
                "tradePrice": "100",
                "fee": "0",
                "cashFlow": "0",
                "funding": "0",
                "transactionTime": "90",
            },
            {
                "id": "4",
                "type": "TRADE",
                "symbol": "BTCUSDT",
                "side": "Sell",
                "qty": "1",
                "tradePrice": "102",
                "fee": "0",
                "cashFlow": "2",
                "funding": "0",
                "transactionTime": "100",
            },
        ]

        def fake_fetch(session=None, start_ms=0, end_ms=0):
            return [r for r in rows if start_ms <= int(r["transactionTime"]) <= end_ms]

        with patch.object(bybit_trades, "fetch_transaction_log", fake_fetch):
            trade_sync.sync_transaction_log(end_ms=end_ms, backfill=True)

        docs = sorted(trade.all(), key=lambda d: d["opened_at_ms"])
        self.assertEqual(len(docs), 2)
        self.assertFalse(docs[0]["stats_eligible"])
        self.assertEqual(docs[0]["trade_id"], "preexist")
        self.assertTrue(docs[1]["stats_eligible"])
        stats = trade_analytics.summarize(docs, period="all", now_ms=end_ms)
        self.assertEqual(stats["n"], 1)
        self.assertEqual(stats["net_pnl"], Decimal("2"))


if __name__ == "__main__":
    unittest.main()
