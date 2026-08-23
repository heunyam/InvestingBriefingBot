from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.utils.decimal import to_decimal


class AssetSummary(BaseModel):
    total_usd: Decimal = Field(
        max_digits=12, decimal_places=2, description="총  총 금액(USD)"
    )
    cash_usd: Decimal = Field(
        max_digits=12, decimal_places=2, description="현금  총 금액 (USD)"
    )
    stock_usd: Decimal = Field(
        max_digits=12, decimal_places=2, description="주식 총 금액 USD)"
    )
    coin_usd: Decimal = Field(
        max_digits=12, decimal_places=2, description="암호화폐  총 금액 (USD)"
    )
    exchange_rate: Decimal = Field(max_digits=12, decimal_places=2, description="환율")
    created_at: datetime = Field(..., description="생성 시간")

    def _pct(self, today: Decimal, prev: Decimal) -> Decimal:
        if prev == 0:
            return Decimal(0)
        return to_decimal((today - prev) / prev * 100)

    def compare(self, other: "AssetSummary" | None) -> "AssetDiff":
        if other is None:
            return AssetDiff(
                total_usd=Decimal(0),
                total_pct=Decimal(0),
                cash_usd=Decimal(0),
                cash_pct=Decimal(0),
                stock_usd=Decimal(0),
                stock_pct=Decimal(0),
                coin_usd=Decimal(0),
                coin_pct=Decimal(0),
            )

        total_usd_diff = to_decimal(self.total_usd - other.total_usd)
        cash_usd_diff = to_decimal(self.cash_usd - other.cash_usd)
        stick_usd_diff = to_decimal(self.stock_usd - other.stock_usd)
        coin_usd_diff = to_decimal(self.coin_usd - other.coin_usd)

        return AssetDiff(
            total_usd=total_usd_diff,
            total_pct=self._pct(self.total_usd, other.total_usd),
            cash_usd=cash_usd_diff,
            cash_pct=self._pct(self.cash_usd, other.cash_usd),
            stock_usd=stick_usd_diff,
            stock_pct=self._pct(self.stock_usd, other.stock_usd),
            coin_usd=coin_usd_diff,
            coin_pct=self._pct(self.coin_usd, other.coin_usd),
        )


class AssetDiff(BaseModel):
    total_usd: Decimal = Field(
        max_digits=12, decimal_places=2, description="총 금액의 차이 (USD)"
    )
    cash_usd: Decimal = Field(
        max_digits=12, decimal_places=2, description="현금 금액의 차이 (USD)"
    )
    stock_usd: Decimal = Field(
        max_digits=12, decimal_places=2, description="주식 금액의 차이 (USD)"
    )
    coin_usd: Decimal = Field(
        max_digits=12, decimal_places=2, description="암호화폐 금액의 차이 (USD)"
    )
    total_pct: Decimal = Field(
        max_digits=12, decimal_places=2, description="총 금액의 차이 비율 (%)"
    )
    cash_pct: Decimal = Field(
        max_digits=12, decimal_places=2, description="현금 금액의 차이 비율 (%)"
    )
    stock_pct: Decimal = Field(
        max_digits=12, decimal_places=2, description="주식 금액의 차이 비율 (%)"
    )
    coin_pct: Decimal = Field(
        max_digits=12, decimal_places=2, description="암호화폐 금액의 차이 비율 (%)"
    )
