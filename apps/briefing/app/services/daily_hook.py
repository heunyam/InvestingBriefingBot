from apps.briefing.app.models.asset import AssetSummary
from apps.briefing.app.utils.time import get_week_start


def snapshot_weekly(asset_summary: AssetSummary):
    this_week_start = get_week_start(asset_summary.date)
    # Weekly DB 에서 해당 date 로 조회하기
    this_weekly: AssetSummary | None = AssetSummary.load_by_date_in_weekly(date=this_week_start)

    if this_weekly is None:
        asset_summary.save_week(this_week_start)