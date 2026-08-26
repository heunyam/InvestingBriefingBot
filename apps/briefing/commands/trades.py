"""
Bybit 매매일지 동기화.

Transaction Log 증분 + 포지션 TP/SL 스냅샷을 TinyDB `trades`에 upsert한다.
복기 텍스트가 없는 매매의 미전송 체결은 DISCORD_TRADE_WEBHOOK_URL 로 보낸다.
같은 Bybit `orderId`의 OPEN/ADD(또는 PARTIAL/CLOSE) 분할체결은 Discord 1통으로 합친다.
TinyDB `events[]`는 exec 단위 그대로 둔다.
기간 성과 리포트는 `make trades-report` (DAILY webhook). 이 명령은 TRADE webhook만 쓴다.

make trades
make trades ARGS="--stdout-only"
"""

from app.models import trade
from app.outbound import discord_trade
from app.services import trade_message, trade_sync


def notify_pending_reviews(docs: list[dict] | None = None) -> list[dict]:
    """Post Discord messages for unposted size events, coalesced by order_id."""
    targets = docs if docs is not None else trade.all()
    posted = []
    for doc in targets:
        if not trade_sync.needs_user_review(doc):
            continue
        already = trade.posted_event_keys(doc)
        sent_any = False
        for burst in trade_message.iter_notify_bursts(doc.get("events") or [], already):
            content = trade_message.format_trade_burst(doc, burst)
            message_id = discord_trade.send_trade(content)
            keys = [str(ev.get("event_key")) for ev in burst if ev.get("event_key")]
            display = trade_message.burst_display_type(burst)
            order_id = next(
                (str(ev.get("order_id")) for ev in burst if ev.get("order_id")),
                None,
            )
            trade.record_discord_message(
                doc,
                event_key=keys[0],
                event_keys=keys,
                message_id=message_id,
                event_type=display,
                order_id=order_id,
            )
            already.update(keys)
            sent_any = True
        if sent_any:
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
        for doc in pending:
            already: set[str] = set()
            for burst in trade_message.iter_notify_bursts(
                doc.get("events") or [], already
            ):
                print("---")
                print(trade_message.format_trade_burst(doc, burst))
                already.update(
                    str(ev.get("event_key")) for ev in burst if ev.get("event_key")
                )
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
