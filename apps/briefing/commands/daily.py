"""
데일리 요약

Toss + Bybit 지갑 스냅샷을 모아 TinyDB에 저장한 뒤, DISCORD_DAILY_WEBHOOK_URL 로 요약을 보낸다.

make daily
"""

from dotenv import load_dotenv

from apps.briefing.app.services.daily import run_daily


def app():
    run_daily()


if __name__ == "__main__":
    load_dotenv()
    app()
