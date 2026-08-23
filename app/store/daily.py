import json
import os
from datetime import date, timezone

from app.models.asset import AssetSummary
from app.utils.time import DATE_FORMAT, to_kst, to_str

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def save(summary: AssetSummary):
    today = to_str(to_kst(dt=summary.created_at), format=DATE_FORMAT)
    os.makedirs(DATA_DIR, exist_ok=True)
    file_path = os.path.join(DATA_DIR, f"{today}.json")

    with open(file_path, "w") as f:
        f.write(summary.model_dump_json(indent=2))


def load(date_: date) -> AssetSummary:
    file_path = os.path.join(DATA_DIR, f"{to_str(date_, format=DATE_FORMAT)}.json")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"No data found for {date_}")

    with open(file_path, "r") as f:
        data = json.load(f)

    return AssetSummary.model_validate(data)

