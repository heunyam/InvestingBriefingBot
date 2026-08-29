from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from apps.briefing.app.db.tables import Doc, orders_table


class Order(BaseModel):
    order_id: str = Field(..., title="주문 ID", description="고유 식별자.")
    symbol: str = Field(..., title="심볼", description="거래 종목.")
    side: Literal["BUY", "SELL"] = Field(
        ..., title="방향", description="매수(BUY) 또는 매도(SELL)."
    )
    reduce_only: bool = Field(
        ...,
        title="청산 전용",
        description="true면 포지션 축소·청산 주문.",
    )
    order_type: str = Field(
        ..., title="주문 유형", description="시장가, 지정가 등 주문 방식."
    )
    quantity: Decimal = Field(
        ...,
        max_digits=50,
        decimal_places=35,
        title="체결 수량",
        description="실제 체결된 수량.",
    )
    average_price: Decimal = Field(
        ...,
        max_digits=50,
        decimal_places=35,
        title="평균 체결가",
        description="체결 수량 가중 평균 가격.",
    )
    fee: Decimal = Field(
        ...,
        max_digits=50,
        decimal_places=35,
        title="수수료",
        description="USDT 기준 거래 수수료.",
    )
    filled_at: datetime = Field(
        ..., title="체결 시각", description="마지막 체결 완료 시각 (KST)."
    )
    created_at: datetime = Field(
        ..., title="주문 생성 시각", description="주문 접수 시각 (KST)."
    )
    realized_pnl: Decimal | None = Field(
        default=None,
        max_digits=50,
        decimal_places=35,
        title="실현 손익",
        description="청산 주문의 확정 손익. 진입 주문은 None.",
    )
    leverage: str | None = Field(
        default=None,
        title="레버리지",
        description="주문 당시 레버리지 배수. 미조회 시 None.",
    )
    synced_at: datetime = Field(
        ..., title="동기화 시각", description="로컬 DB에 반영된 시각 (KST)."
    )
    discord_message_id: str | None = Field(
        default=None,
        title="Discord 메시지 ID",
        description="TRADE webhook에 게시한 메시지. 미전송이면 None.",
    )


def save(order: Order) -> None:
    existing = load(order.order_id)
    if (
        existing
        and existing.discord_message_id
        and not order.discord_message_id
    ):
        order = order.model_copy(
            update={"discord_message_id": existing.discord_message_id}
        )
    doc = order.model_dump(mode="json")
    orders_table().upsert(doc, Doc.order_id == doc["order_id"])


def load(order_id: str) -> Order | None:
    rows = orders_table().search(Doc.order_id == order_id)
    if not rows:
        return None
    return Order.model_validate(rows[0])


def all() -> list[Order]:
    return [Order.model_validate(row) for row in orders_table().all()]
