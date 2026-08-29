"""
Bybit Filled order-history 증분 동기화 → TinyDB orders → TRADE webhook 매매일지.

make orders
make orders ARGS="--backfill"
make orders ARGS="--stdout-only"
"""

import argparse
import json

from dotenv import load_dotenv

from apps.briefing.app.services.order import notify_orders, sync_all


def app(*, backfill: bool = False, stdout_only: bool = False) -> dict:
    result = sync_all(backfill=backfill, dry_run=stdout_only)
    if stdout_only:
        print(json.dumps(result, indent=2))
        notify_orders(result["new_orders"], stdout_only=True)
        return result

    print(
        f"fetched={result['fetched']} saved={result['saved']} "
        f"enriched={result['enriched']['updated']} "
        f"start_ms={result['start_ms']} end_ms={result['end_ms']}"
    )
    print(f"discord_posted={notify_orders(result['new_orders'])}")
    return result


if __name__ == "__main__":
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--backfill", action="store_true")
    parser.add_argument("--stdout-only", action="store_true")
    args = parser.parse_args()
    app(backfill=args.backfill, stdout_only=args.stdout_only)
