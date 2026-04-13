Mac Cron 세팅
```shell
code ~/Library/LaunchAgents/com.investingbriefingbot.plist
launchctl unload ~/Library/LaunchAgents/com.investingbriefingbot.plist
launchctl load ~/Library/LaunchAgents/com.investingbriefingbot.plist
launchctl list | grep investingbriefingbot
```