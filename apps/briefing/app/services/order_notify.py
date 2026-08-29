from apps.briefing.app.models.order import Order, all, save
from apps.briefing.app.outbounds import discord_trade
from apps.briefing.app.services.order_message import format_order_message


def notify_unposted(*, stdout_only: bool = False) -> list[Order]:
    posted: list[Order] = []
    pending = sorted(
        [order for order in all() if not order.discord_message_id],
        key=lambda order: order.filled_at,
    )
    for order in pending:
        content = format_order_message(order)
        if stdout_only:
            print("---")
            print(content)
            posted.append(order)
            continue
        message_id = discord_trade.send_trade(content)
        save(order.model_copy(update={"discord_message_id": message_id}))
        posted.append(order)
    return posted
