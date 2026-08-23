UV = ~/.local/bin/uv
export PYTHONPATH := apps/briefing
LAUNCHD = apps/briefing/launchd
AGENTS = $(HOME)/Library/LaunchAgents
DAILY_PLIST = com.gimsejun.investingbriefingbot.daily.plist
WEEKLY_PLIST = com.gimsejun.investingbriefingbot.weekly.plist

.PHONY: daily weekly load
daily:
	$(UV) run python -m commands.daily

weekly:
	$(UV) run python -m commands.weekly

load:
	cp $(LAUNCHD)/$(DAILY_PLIST) $(AGENTS)/
	cp $(LAUNCHD)/$(WEEKLY_PLIST) $(AGENTS)/
	-launchctl unload $(AGENTS)/$(DAILY_PLIST)
	launchctl load $(AGENTS)/$(DAILY_PLIST)
	-launchctl unload $(AGENTS)/$(WEEKLY_PLIST)
	launchctl load $(AGENTS)/$(WEEKLY_PLIST)
