from datetime import date as Date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, ValidationError

from apps.briefing.app.db.tables import asset_summary_table, Doc, weekly_table


class AssetSummary(BaseModel):
    date: Date = Field(..., description="영업일 (KST, 예전 파일명)")
    total: Decimal = Field(
        max_digits=50, decimal_places=35, description="총  총 금액(USD)"
    )
    cash: Decimal = Field(
        max_digits=50, decimal_places=35, description="현금 총 금액 (USD)"
    )
    stock: Decimal = Field(
        max_digits=50, decimal_places=35, description="주식 총 금액 (USD)"
    )
    coin: Decimal = Field(
        max_digits=50, decimal_places=35, description="암호화폐 총 금액 (USD)"
    )
    exchange_rate: Decimal = Field(max_digits=12, decimal_places=2, description="환율")
    created_at: datetime = Field(..., description="생성 시간")

    def save(self) -> None:
        doc = self.model_dump(mode="json")
        asset_summary_table().upsert(doc, Doc.date == doc["date"])

    def save_week(self, week_start: Date) -> None:
        doc = self.model_dump(mode="json")
        doc["week_start"] = week_start.isoformat()
        weekly_table().upsert(doc, Doc.week_start == doc["week_start"])

    @classmethod
    def load(cls, date_: Date) -> "AssetSummary":
        rows = asset_summary_table().search(Doc.date == date_.isoformat())
        if not rows:
            raise FileNotFoundError(f"No data found for {date_}")
        return cls.model_validate(rows[0])

    @classmethod
    def all(cls) -> list["AssetSummary"]:
        return [cls.model_validate(row) for row in asset_summary_table().all()]

    @classmethod
    def all_weeks(cls) -> list["AssetSummary"]:
        return [cls.model_validate(row) for row in weekly_table().all()]

    @classmethod
    def load_by_date_in_weekly(cls, date: Date) -> "AssetSummary" | None:
        row = weekly_table().get(Doc.date == date.isoformat())
        try:
            return cls.model_validate(row)
        except ValidationError:
            return None
