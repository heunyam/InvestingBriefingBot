"""
Bybit 매매일지 동기화.

Transaction Log 증분 + 포지션 TP/SL 스냅샷을 TinyDB `trades`에 upsert한다.
복기 텍스트가 없는 매매는 DISCORD_TRADE_WEBHOOK_URL 로 create/edit한다.
기간 성과 리포트는 `make trades-report` (DAILY webhook). 이 명령은 TRADE webhook만 쓴다.

make trades
make trades ARGS="--stdout-only"
"""

from app.models import trade
from app.outbound import discord_trade
from app.services import trade_message, trade_sync


def notify_pending_reviews(docs: list[dict] | None = None) -> list[dict]:
    """Discord upsert for trades missing Open/Close review text."""
    targets = docs if docs is not None else trade.all()
    posted = []
    for doc in targets:
        if not trade_sync.needs_user_review(doc):
            continue
        content = trade_message.format_trade_message(doc)
        message_id = discord_trade.upsert_trade_message(doc, content)
        doc.setdefault("discord", {})["message_id"] = message_id
        trade.save(doc)
        posted.append(doc)
    return posted


def app(stdout_only: bool = False) -> None:
    result = trade_sync.sync_all()
    pending = result["pending_review"]
    print(f"synced={len(result['synced'])} pending_review={len(pending)}")
    for doc in pending:
        print(
            f"- {doc.get('status')} {doc.get('symbol')} {doc.get('side')} "
            f"{(doc.get('trade_id') or '')[:8]}"
        )
    if stdout_only:
        # Discord 호출 없이 미복기 본문만 확인
        for doc in pending:
            print("---")
            print(trade_message.format_trade_message(doc))
        return
    posted = notify_pending_reviews(pending)
    print(f"discord_upserted={len(posted)}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Bybit 체결 동기화 후 미복기 매매를 TRADE webhook으로 보낸다."
    )
    parser.add_argument(
        "--stdout-only",
        action="store_true",
        help="Discord 호출 없이 미복기 메시지 본문만 출력",
    )
    args = parser.parse_args()
    app(stdout_only=args.stdout_only)
