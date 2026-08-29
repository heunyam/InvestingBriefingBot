"""
Bybit Filled order-history 증분 동기화 → TinyDB orders → TRADE webhook 매매일지.

make orders
make orders ARGS="--backfill"
make orders ARGS="--stdout-only"
"""

import argparse
import json

from dotenv import load_dotenv

from apps.briefing.app.services.order_notify import notify_unposted
from apps.briefing.app.services.order_sync import sync_all


def app(*, backfill: bool = False, stdout_only: bool = False) -> dict:
    result = sync_all(backfill=backfill)
    if stdout_only:
        print(json.dumps(result, indent=2))
        notify_unposted(stdout_only=True)
        return result

    print(
        f"fetched={result['fetched']} saved={result['saved']} "
        f"enriched={result['enriched']['updated']} "
        f"start_ms={result['start_ms']} end_ms={result['end_ms']}"
    )
    posted = notify_unposted()
    print(f"discord_posted={len(posted)}")
    return result


if __name__ == "__main__":
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Bybit Filled order-history를 TinyDB orders에 동기화하고 TRADE webhook에 게시한다."
    )
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="lookback을 최대 2년으로 늘려 동기화",
    )
    parser.add_argument(
        "--stdout-only",
        action="store_true",
        help="Discord 호출 없이 sync 결과·매매일지 본문만 출력",
    )
    args = parser.parse_args()
    app(backfill=args.backfill, stdout_only=args.stdout_only)
