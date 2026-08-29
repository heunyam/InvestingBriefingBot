"""
청산 주문 기반 성과 리포트 → DISCORD_DAILY_WEBHOOK_URL

make orders-report
make orders-report ARGS="--period 30d --stdout-only"
make orders-report ARGS="--backfill"
"""

import argparse
import sys
import time

from dotenv import load_dotenv

from apps.briefing.app.models.order import Order
from apps.briefing.app.outbounds import discord
from apps.briefing.app.services import order, order_analytics


def app(argv: list[str] | None = None) -> str:
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", choices=("7d", "30d", "all"), default="7d")
    parser.add_argument("--symbol", default=None)
    parser.add_argument("--stdout-only", action="store_true")
    parser.add_argument("--backfill", action="store_true")
    args = parser.parse_args(argv)

    if args.backfill:
        result = order.sync_all(backfill=True)
        print(
            f"backfill saved={result['saved']} enriched={result['enriched']['updated']}"
        )
    else:
        end_ms = int(time.time() * 1000)
        start_ms = end_ms - order.DEFAULT_LOOKBACK_MS
        print(
            f"enriched={order.enrich_orders(start_ms=start_ms, end_ms=end_ms)['updated']}"
        )

    text = order_analytics.format_report(
        order_analytics.summarize(
            Order.all(),
            period=args.period,
            now_ms=int(time.time() * 1000),
            symbol=args.symbol,
        )
    )
    print(text)
    if not args.stdout_only:
        discord.send_daily(text)
    return text


if __name__ == "__main__":
    load_dotenv()
    app(sys.argv[1:])
