UV = ~/.local/bin/uv
export PYTHONPATH := apps/briefing

.PHONY: daily
daily:
	$(UV) run python -m commands.daily

.PHONY: load
load:
	cp apps/briefing/launchd/com.gimsejun.investingbriefingbot.daily.plist ~/Library/LaunchAgents/
	launchctl unload ~/Library/LaunchAgents/com.gimsejun.investingbriefingbot.daily.plist
	launchctl load ~/Library/LaunchAgents/com.gimsejun.investingbriefingbot.daily.plist
