"""주간 브리핑.

저장된 일일 스냅샷으로 최근 주간 행을 upsert하고,
DISCORD_DAILY_WEBHOOK_URL 로 주간 요약을 보낸다.

  make weekly
"""

from dotenv import load_dotenv

from apps.briefing.app.services.weekly import run_weekly


def app():
    run_weekly()


if __name__ == "__main__":
    load_dotenv()
    app()
