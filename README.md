# InvestingBriefingBot

개인 투자 도구 모노레포.

- **Daily briefing**: Toss + Bybit 잔고를 모아 Discord로 보낸다.
- **Pine Script**: TradingView 지표/전략은 `pine/`에 둔다.

## Setup

```shell
uv sync
cp .env.example .env
```

`.env`에 Toss / Bybit / Discord 값을 채운다. 이 파일은 git에 올리지 않는다.

일일 브리핑:

```shell
make daily
```

macOS launchd (매일 07:00):

```shell
make load
launchctl list | grep investingbriefingbot
```

`launchd/*.plist` 안의 경로를 이 머신 경로로 맞춰야 한다.

## Pine Script

`pine/lessons/`부터 순서대로 보고, 내용을 TradingView **Pine Editor**에 붙여 넣은 뒤 Add to chart 한다. 로컬에서 실행되지 않는다.

## Layout

```
app/          briefing bot
commands/     `python -m commands.daily`
launchd/      macOS scheduler
pine/         Pine Script v6
docs/         collector notes
```
