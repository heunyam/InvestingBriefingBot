"""주간 브리핑.

저장된 일일 스냅샷으로 최근 주간 행을 upsert하고,
DISCORD_DAILY_WEBHOOK_URL 로 주간 요약을 보낸다. launchd는 월요일 07:10(daily 다음).
같은 `make weekly`가 이어서 `trades-report`를 같은 webhook에 별도 메시지로 보낸다.

  make weekly
"""

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
