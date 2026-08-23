import json
import os
from datetime import date as Date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.db import DATA_DIR, Doc, asset_summary_table


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

    @classmethod
    def load(cls, date_: Date) -> "AssetSummary":
        rows = asset_summary_table().search(Doc.date == date_.isoformat())
        if not rows:
            raise FileNotFoundError(f"No data found for {date_}")
        return cls.model_validate(rows[0])

    @classmethod
    def migrate_json_files(cls) -> int:
        if not os.path.isdir(DATA_DIR):
            return 0

        count = 0
        for name in sorted(os.listdir(DATA_DIR)):
            if name == "db.json" or not name.endswith(".json"):
                continue
            path = os.path.join(DATA_DIR, name)
            with open(path) as f:
                data = json.load(f)
            if "date" not in data:
                data["date"] = name.removesuffix(".json")
            cls.model_validate(data).save()
            count += 1
        return count
