UV = ~/.local/bin/uv
export PYTHONPATH := .
REPO_ROOT := $(CURDIR)
LAUNCHD = apps/briefing/launchd
AGENTS = $(HOME)/Library/LaunchAgents
LABEL = com.investingbriefingbot
DAILY_PLIST = $(LABEL).daily.plist
WEEKLY_PLIST = $(LABEL).weekly.plist
ORDERS_PLIST = $(LABEL).orders.plist

# make daily          Toss+Bybit 일일 스냅샷 → TinyDB → DISCORD_DAILY_WEBHOOK_URL
# make weekly         주간 집계 → DAILY webhook (launchd 월 07:10은 이어서 orders-report)
# make orders         Bybit Filled order-history 증분 동기화 + TRADE webhook 매매일지 (매일 06:50)
# make orders-report  청산 주문 성과 리포트 → DAILY webhook
# make test           apps/briefing/tests
# make load           launchd 템플릿(.plist.in)을 로컬 경로로 치환해 LaunchAgents에 설치

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

define install_plist
	sed 's|@@REPO_ROOT@@|$(REPO_ROOT)|g' \
		$(LAUNCHD)/$(1).plist.in > $(AGENTS)/$(1).plist
endef

load:
	$(call install_plist,$(LABEL).daily)
	$(call install_plist,$(LABEL).weekly)
	$(call install_plist,$(LABEL).orders)
	-launchctl unload $(AGENTS)/$(DAILY_PLIST)
	launchctl load $(AGENTS)/$(DAILY_PLIST)
	-launchctl unload $(AGENTS)/$(WEEKLY_PLIST)
	launchctl load $(AGENTS)/$(WEEKLY_PLIST)
	-launchctl unload $(AGENTS)/$(ORDERS_PLIST)
	launchctl load $(AGENTS)/$(ORDERS_PLIST)
