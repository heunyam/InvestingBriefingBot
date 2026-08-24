"""매매 복기 저장 (CLI + TRADE webhook).

TinyDB `review`를 채운다. message_id가 있으면 webhook 본문만 갱신한다.

  make trades-review
  make trades-review ARGS="--id <trade_id접두> --entry '돌파' --exit '익절'"
  make trades-review ARGS="--id <접두> --entry '...' --exit '...' --chart ./shot.png"
  make trades-review ARGS="--id <접두> --entry '...' --exit '...' --stdout-only"
"""

import argparse

from app.models import trade
from app.outbound import discord_trade
from app.services import trade_message, trade_review


def _print_pending() -> None:
    pending = trade_review.pending_closed_reviews()
    print(f"pending_review={len(pending)}")
    for doc in pending:
        pnl = (doc.get("pnl") or {}).get("amount")
        print(
            f"- {(doc.get('trade_id') or '')[:8]} {doc.get('symbol')} "
            f"{doc.get('side')} pnl={pnl}"
        )


def app(argv: list[str] | None = None) -> dict | None:
    parser = argparse.ArgumentParser(
        description="CLOSED 매매 복기를 TinyDB에 저장하고 TRADE webhook 본문을 갱신한다."
    )
    parser.add_argument("--id", dest="trade_id", help="trade_id 또는 고유 접두")
    parser.add_argument("--entry", help="진입 근거")
    parser.add_argument("--exit", dest="exit_reason", help="청산 근거")
    parser.add_argument("--chart", help="선택. 로컬 차트 이미지 경로")
    parser.add_argument(
        "--stdout-only",
        action="store_true",
        help="저장만 하고 TRADE webhook은 부르지 않음",
    )
    args = parser.parse_args(argv)
    if not args.trade_id:
        _print_pending()
        return None
    if not args.entry or not args.exit_reason:
        parser.error("--entry 와 --exit 가 필요합니다")
    doc = trade_review.resolve_trade(args.trade_id)
    doc = trade_review.save_cli_review(
        doc,
        entry_reason=args.entry,
        exit_reason=args.exit_reason,
        chart_path=args.chart,
    )
    print(f"reviewed={(doc.get('trade_id') or '')[:8]} {doc.get('symbol')}")
    if args.stdout_only:
        print(trade_message.format_trade_message(doc))
        return doc
    content = trade_message.format_trade_message(doc)
    message_id = discord_trade.upsert_trade_message(doc, content)
    doc.setdefault("discord", {})["message_id"] = message_id
    trade.save(doc)
    print(f"discord_upserted={message_id}")
    return doc


if __name__ == "__main__":
    import sys

    app(sys.argv[1:])
