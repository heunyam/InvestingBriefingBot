import unittest
from datetime import datetime

from app.models import trade
from app.services import trade_message


def _ms(stamp: str) -> int:
    dt = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=trade_message.KST)
    return int(dt.timestamp() * 1000)


class TestTradeMessageFormat(unittest.TestCase):
    def test_open_long(self):
        doc = trade.new_trade("t1", "ETHUSDT", "LONG", _ms("2026-06-22 22:34:03"), 1)
        doc["prices"]["entry"] = "1765.420979"
        doc["position"] = {"size": "400", "leverage": "10"}
        doc["events"] = [
            {
                "event_type": "OPEN",
                "price": "1763.082442",
                "quantity": "400",
                "occurred_at_ms": _ms("2026-06-22 22:34:03"),
                "cash_flow": "0",
                "realized_pnl": "0",
            }
        ]
        text = trade_message.format_trade_message(doc)
        self.assertEqual(
            text,
            "\n".join(
                [
                    "롱 진입",
                    "",
                    "🟢 롱: ETHUSDT(x10)",
                    "📍 시장가: 1,763.0824",
                    "📦 수량: 400",
                    "💵 평단: 1,765.421",
                    "",
                    "⏰ 2026-06-22 22:34:03",
                ]
            ),
        )

    def test_stop_loss_long(self):
        doc = trade.new_trade("t2", "ETHUSDT", "LONG", 1, 1)
        doc["status"] = "CLOSED"
        doc["pnl"] = {"amount": "-30703", "result": "LOSS"}
        doc["position"] = {"size": "0", "leverage": "10"}
        doc["events"] = [
            {
                "event_type": "OPEN",
                "price": "1765.420979",
                "quantity": "400",
                "occurred_at_ms": 1,
                "cash_flow": "0",
                "realized_pnl": "0",
            },
            {
                "event_type": "CLOSE",
                "price": "1688.662783",
                "quantity": "400",
                "occurred_at_ms": _ms("2026-06-23 15:35:23"),
                "cash_flow": "-30703",
                "realized_pnl": "0",
            },
        ]
        text = trade_message.format_trade_message(doc)
        self.assertIn("❌ 롱 손절", text)
        self.assertIn("📍 시장가: 1,688.6628", text)
        self.assertIn("💰 실현: -30,703", text)
        self.assertIn("📈 ROE: -45.45%", text)
        self.assertIn("⏰ 2026-06-23 15:35:23", text)

    def test_take_profit_long(self):
        doc = trade.new_trade("t3", "BTCUSDT", "LONG", 1, 1)
        doc["status"] = "CLOSED"
        doc["pnl"] = {"amount": "1011", "result": "WIN"}
        doc["position"] = {"size": "0", "leverage": "10"}
        doc["events"] = [
            {
                "event_type": "OPEN",
                "price": "80000",
                "quantity": "0.1",
                "occurred_at_ms": 1,
                "cash_flow": "0",
                "realized_pnl": "0",
            },
            {
                "event_type": "CLOSE",
                "price": "80166.4",
                "quantity": "0.1",
                "occurred_at_ms": _ms("2026-05-07 23:36:49"),
                "cash_flow": "1011",
                "realized_pnl": "0",
            },
        ]
        text = trade_message.format_trade_message(doc)
        self.assertEqual(
            text.split("\n")[0],
            "롱 익절",
        )
        self.assertIn("🟢 롱: BTCUSDT(x10)", text)
        self.assertIn("📍 시장가: 80,166.4", text)
        self.assertIn("💰 실현: 1,011", text)
        self.assertIn("📈 ROE:", text)
        self.assertIn("⏰ 2026-05-07 23:36:49", text)

    def test_partial_take_profit_short(self):
        doc = trade.new_trade("t4", "ETHUSDT", "SHORT", 1, 1)
        doc["status"] = "OPEN"
        doc["pnl"] = {"amount": "27993", "result": "WIN"}
        doc["position"] = {"size": "280", "leverage": "10"}
        doc["events"] = [
            {
                "event_type": "OPEN",
                "price": "2100",
                "quantity": "600",
                "occurred_at_ms": 1,
                "cash_flow": "0",
                "realized_pnl": "0",
            },
            {
                "event_type": "PARTIAL_CLOSE",
                "price": "2123.76",
                "quantity": "320",
                "occurred_at_ms": _ms("2026-05-19 05:05:23"),
                "cash_flow": "31992",
                "realized_pnl": "0",
            },
        ]
        text = trade_message.format_trade_message(doc)
        self.assertEqual(
            text,
            "\n".join(
                [
                    "부분 익절",
                    "",
                    "🔴 숏: ETHUSDT(x10)",
                    "📍 시장가: 2,123.76",
                    "📦 수량: 600 → 280",
                    "💰 실현: 31,992",
                    "📊 PNL: 27,993",
                    "📈 ROE: 47.07%",
                    "",
                    "⏰ 2026-05-19 05:05:23",
                ]
            ),
        )


if __name__ == "__main__":
    unittest.main()
