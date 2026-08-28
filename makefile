UV = ~/.local/bin/uv
export PYTHONPATH := apps/briefing
LAUNCHD = apps/briefing/launchd
AGENTS = $(HOME)/Library/LaunchAgents
DAILY_PLIST = com.gimsejun.investingbriefingbot.daily.plist
WEEKLY_PLIST = com.gimsejun.investingbriefingbot.weekly.plist
TRADES_PLIST = com.gimsejun.investingbriefingbot.trades.plist

# make daily          Toss+Bybit 일일 스냅샷 → TinyDB → DISCORD_DAILY_WEBHOOK_URL
# make weekly         주간 집계 → DAILY webhook
# make trades         Bybit 체결 증분 동기화 + 미복기 매매 본문 → DISCORD_TRADE_WEBHOOK_URL (매일 06:50)
# make trades-review  복기 텍스트를 TinyDB에 저장. 없으면 미복기 목록. TRADE webhook 본문 갱신
# make trades-report  CLOSED 성과 리포트 → DAILY webhook (주간과 같은 채널, 별도 메시지)
# make test           apps/briefing/tests
# make load           launchd plist를 ~/Library/LaunchAgents 에 설치
#
# launchd weekly (월 07:10)는 make weekly 다음 make trades-report 를 이어서 호출한다.
# Discord 매매일지는 webhook만 쓴다 (requests). App/Bot Modal은 나중에.

.PHONY: daily weekly load test trades trades-review trades-report
daily:
	$(UV) run python -m commands.daily

weekly:
	$(UV) run python -m commands.weekly

trades:
	$(UV) run python -m commands.trades $(ARGS)

trades-review:
	$(UV) run python -m commands.trades_review $(ARGS)

trades-report:
	$(UV) run python -m commands.trades_report $(ARGS)

test:
	$(UV) run python -m unittest discover -s apps/briefing/tests -v

load:
	cp $(LAUNCHD)/$(DAILY_PLIST) $(AGENTS)/
	cp $(LAUNCHD)/$(WEEKLY_PLIST) $(AGENTS)/
	cp $(LAUNCHD)/$(TRADES_PLIST) $(AGENTS)/
	-launchctl unload $(AGENTS)/$(DAILY_PLIST)
	launchctl load $(AGENTS)/$(DAILY_PLIST)
	-launchctl unload $(AGENTS)/$(WEEKLY_PLIST)
	launchctl load $(AGENTS)/$(WEEKLY_PLIST)
	-launchctl unload $(AGENTS)/$(TRADES_PLIST)
	launchctl load $(AGENTS)/$(TRADES_PLIST)
