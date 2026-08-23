# InvestingBriefingBot

개인용 자산 관련 스크립트 저장소

`apps/briefing`
- 자산이 들어있는 Platform 에서 제공하는 API를 통해 금액 정보를 취합하여 Json 데이터로 저장.
- 이후 개인 Discord 채널에 일별로 표시합니다.

```mermaid
graph LR
    A["Investing Platform<br/>(Toss, Bybit)"] -->|"Open API (Fetch)" | B[InvestingBriefingBot]
    B --> |Post Message| C[Discord]
```

