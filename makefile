UV = ~/.local/bin/uv

.PHONY: daily
daily:
	$(UV) run python -m commands.daily

.PHONY: load
load:
	cp launchd/com.gimsejun.investingbriefingbot.daily.plist ~/Library/LaunchAgents/
	launchctl unload ~/Library/LaunchAgents/com.gimsejun.investingbriefingbot.daily.plist
	launchctl load ~/Library/LaunchAgents/com.gimsejun.investingbriefingbot.daily.plist
