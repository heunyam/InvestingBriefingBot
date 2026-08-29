UV = ~/.local/bin/uv
export PYTHONPATH := .
LAUNCHD = apps/briefing/launchd
AGENTS = $(HOME)/Library/LaunchAgents
DAILY_PLIST = com.gimsejun.investingbriefingbot.daily.plist
WEEKLY_PLIST = com.gimsejun.investingbriefingbot.weekly.plist
ORDERS_PLIST = com.gimsejun.investingbriefingbot.orders.plist

# make daily          Toss+Bybit 일일 스냅샷 → TinyDB → DISCORD_DAILY_WEBHOOK_URL
# make weekly         주간 집계 → DAILY webhook (launchd 월 07:10은 이어서 orders-report)
# make orders         Bybit Filled order-history 증분 동기화 + TRADE webhook 매매일지 (매일 06:50)
# make orders-report  청산 주문 성과 리포트 → DAILY webhook
# make test           apps/briefing/tests
# make load           launchd plist를 ~/Library/LaunchAgents 에 설치

.PHONY: daily weekly load test orders orders-report
daily:
	$(UV) run python -m apps.briefing.commands.daily

weekly:
	$(UV) run python -m apps.briefing.commands.weekly

orders:
	$(UV) run python -m apps.briefing.commands.orders $(ARGS)

orders-report:
	$(UV) run python -m apps.briefing.commands.orders_report $(ARGS)

test:
	$(UV) run python -m unittest discover -s apps/briefing/tests -v

load:
	cp $(LAUNCHD)/$(DAILY_PLIST) $(AGENTS)/
	cp $(LAUNCHD)/$(WEEKLY_PLIST) $(AGENTS)/
	cp $(LAUNCHD)/$(ORDERS_PLIST) $(AGENTS)/
	-launchctl unload $(AGENTS)/$(DAILY_PLIST)
	launchctl load $(AGENTS)/$(DAILY_PLIST)
	-launchctl unload $(AGENTS)/$(WEEKLY_PLIST)
	launchctl load $(AGENTS)/$(WEEKLY_PLIST)
	-launchctl unload $(AGENTS)/$(ORDERS_PLIST)
	launchctl load $(AGENTS)/$(ORDERS_PLIST)
