"""
CLOSED 매매 성과 리포트.

기간 지표를 stdout에 찍고, 기본은 DISCORD_DAILY_WEBHOOK_URL 로 보낸다
(주간 브리핑과 같은 채널, 별도 메시지). TRADE webhook·매매 문서 message_id는 건드리지 않는다.

make trades-report
make trades-report ARGS="--period 30d"
make trades-report ARGS="--period all --symbol BTCUSDT"
make trades-report ARGS="--stdout-only"
make trades-report ARGS="--backfill"
launchd `make weekly` (월 07:10)가 주간 메시지 다음에 이 명령을 한 번 더 돌린다.
"""

import argparse
import time

from app.models import trade
from app.outbound import discord
from app.services import trade_analytics, trade_report, trade_sync


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CLOSED 성과를 DAILY webhook(또는 stdout)으로 보낸다. TRADE webhook은 쓰지 않는다."
    )
    parser.add_argument(
        "--period",
        choices=("7d", "30d", "all"),
        default="7d",
        help="집계 구간. closed_at_ms 기준",
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
        help="tx lookback을 최대 2년으로 늘려 동기화한 뒤 리포트",
    )
    return parser.parse_args(argv)


def app(argv: list[str] | None = None) -> str:
    args = _parse_args(argv)
    if args.backfill:
        result = trade_sync.sync_all(backfill=True)
        print(
            f"backfill synced={len(result['synced'])} "
            f"pending_review={len(result['pending_review'])}"
        )
    now_ms = int(time.time() * 1000)
    stats = trade_analytics.summarize(
        trade.all(),
        period=args.period,
        now_ms=now_ms,
        symbol=args.symbol,
    )
    text = trade_report.format_report(stats)
    print(text)
    if args.stdout_only:
        return text
    discord.send_daily(text)
    return text


if __name__ == "__main__":
    import sys

    app(sys.argv[1:])
