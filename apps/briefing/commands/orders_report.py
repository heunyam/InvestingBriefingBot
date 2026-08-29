"""
청산 주문 기반 성과 리포트.

기간 지표를 stdout에 찍고, 기본은 DISCORD_DAILY_WEBHOOK_URL 로 보낸다.

make orders-report
make orders-report ARGS="--period 30d"
make orders-report ARGS="--period all --symbol BTCUSDT"
make orders-report ARGS="--stdout-only"
make orders-report ARGS="--backfill"
"""

import argparse
import sys
import time

from dotenv import load_dotenv

from apps.briefing.app.models.order import all
from apps.briefing.app.outbounds import discord
from apps.briefing.app.services import order_analytics, order_enrich, order_report, order_sync


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="청산 주문 성과를 DAILY webhook(또는 stdout)으로 보낸다."
    )
    parser.add_argument(
        "--period",
        choices=("7d", "30d", "all"),
        default="7d",
        help="집계 구간. filled_at 기준",
    )
    parser.add_argument("--symbol", default=None, help="한 심볼만")
    parser.add_argument(
        "--stdout-only",
        action="store_true",
        help="Discord 호출 없이 본문만 출력",
    )
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="order lookback을 최대 2년으로 늘려 동기화·enrich한 뒤 리포트",
    )
    return parser.parse_args(argv)


def app(argv: list[str] | None = None) -> str:
    args = _parse_args(argv)
    if args.backfill:
        result = order_sync.sync_all(backfill=True)
        print(
            f"backfill fetched={result['fetched']} saved={result['saved']} "
            f"enriched={result['enriched']['updated']}"
        )
    else:
        end_ms = int(time.time() * 1000)
        start_ms = end_ms - order_sync.DEFAULT_LOOKBACK_MS
        enriched = order_enrich.enrich_orders(start_ms=start_ms, end_ms=end_ms)
        print(f"enriched={enriched['updated']}")

    now_ms = int(time.time() * 1000)
    stats = order_analytics.summarize(
        all(),
        period=args.period,
        now_ms=now_ms,
        symbol=args.symbol,
    )
    text = order_report.format_report(stats)
    print(text)
    if args.stdout_only:
        return text
    discord.send_daily(text)
    return text


if __name__ == "__main__":
    load_dotenv()
    app(sys.argv[1:])
