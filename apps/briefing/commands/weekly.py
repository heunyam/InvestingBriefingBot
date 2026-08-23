from datetime import timedelta

from app.outbound import discord
from app.models.asset import AssetSummary
from app.services.formatter import format_weekly_message, to_week_start
from app.utils.time import kst_now


def app():
    daily = AssetSummary.all()
    this_week_start = to_week_start(kst_now().date())
    for i in range(6):
        week_start = this_week_start - timedelta(weeks=i)
        snapshot = AssetSummary.for_week(week_start, daily)
        if snapshot is not None:
            snapshot.save_week(week_start)

    message = format_weekly_message(AssetSummary.all_weeks())
    print(message)
    discord.send_daily(message)


if __name__ == "__main__":
    app()
