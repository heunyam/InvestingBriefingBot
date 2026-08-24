# Bybit 매매일지

TinyDB `trades` 테이블에 심볼·방향별 라운드트립 한 건을 중첩 문서로 저장한다. 실시간 소켓은 쓰지 않는다.

Discord는 **webhook만** 쓴다 (`requests` + `DISCORD_*_WEBHOOK_URL`). Discord App/Bot은 아직 쓰지 않는다.

## 명령

| 명령 | 역할 |
| --- | --- |
| `make daily` | Toss+Bybit 일일 스냅샷 → DAILY webhook |
| `make weekly` | 주간 집계 → DAILY webhook, 이어서 매매 성과 리포트(별도 메시지). launchd 월 07:10 |
| `make trades` | Transaction Log 증분 동기화 + TP/SL 스냅샷 + 미복기 TRADE webhook. launchd 매일 06:50 |
| `make trades-review` | 복기 텍스트를 TinyDB에 저장. webhook 본문 갱신 |
| `make trades-report` | CLOSED 성과 리포트. 기본 최근 7일 → DAILY webhook |

리포트를 `make trades`에 붙이지 않는다. 동기화와 기간 집계를 섞으면 개별 매매 메시지 `discord.message_id`를 덮어쓸 위험이 있다.

```text
make trades
make trades ARGS="--stdout-only"
make trades-review
make trades-review ARGS="--id <접두> --entry '돌파' --exit '익절'"
make trades-report
make trades-report ARGS="--period 30d"
make trades-report ARGS="--period all --symbol BTCUSDT"
make trades-report ARGS="--stdout-only"
make trades-report ARGS="--backfill"
```

`--backfill`은 tx lookback을 최대 2년으로 늘린다. 페이지는 기존처럼 7일 window다. 이후 `trades-report`의 `--period`로 집계한다.

## 환경 변수

`.env` (커밋하지 않음). 예시는 `.env.example`.

| 변수 | 용도 |
| --- | --- |
| `BYBIT_API_KEY` / `BYBIT_API_SECRET` | REST 동기화 |
| `DISCORD_TRADE_WEBHOOK_URL` | 미복기 매매 메시지 (복기 후 edit) |
| `DISCORD_DAILY_WEBHOOK_URL` | 일일·주간 브리핑 + 기간 리포트 (리포트는 주간과 별도 메시지) |

## 동기화 (`make trades`)

1. Transaction Log를 마지막 커서부터 가져온다. 커서가 없으면 기본 30일.
2. **하한:** `2026-08-25 00:00` KST (`SYNC_START_MS`) 이전 체결은 가져오지 않는다. 그 시각 이전이면 `sync_all`은 no-op.
3. TRADE 체결만 OPEN / ADD / PARTIAL_CLOSE / CLOSE로 넣는다. flat 전까지 같은 `trade_id`.
4. 다시 진입하면 새 `trade_id`.
5. 열린 포지션과 미체결 스탑으로 TP/SL(`FULL` / `PARTIAL` / trailing)을 덮어쓴다.
6. `review.entry_reason`과 `review.exit_reason`이 없으면 TRADE webhook create/edit. 있으면 스킵.
7. hedge (`positionIdx != 0`)는 에러.

메타 커서: TinyDB `trade_sync_meta` / `bybit_tx`.

## 복기 (지금은 CLI)

`make trades`는 이유가 비어 있는 매매를 TRADE webhook으로만 올린다. 저장은 CLI다.

```text
make trades-review
make trades-review ARGS="--id a1b2c3d4 --entry '돌파' --exit '익절'"
make trades-review ARGS="--id a1b2c3d4 --entry '돌파' --exit '익절' --chart ./shot.png"
```

`--id`는 전체 `trade_id` 또는 고유한 접두. `--chart`는 선택. 저장 후 `message_id`가 있으면 같은 TRADE webhook 본문을 갱신한다. **본문에는 아직 entry/exit 문구를 넣지 않는다** (Discord Bot interaction 때 넣을 예정). 통계는 복기 여부와 무관하게 CLOSED를 쓴다.

## 리포트 (`make trades-report`)

- 대상: `status=CLOSED`, `closed_at_ms`가 `--period` 안.
- `pnl.amount`가 `0`이거나 없으면 거래 수·승률 분모에서 제외.
- `stats_eligible=false`인 건 제외. backfill(또는 첫 전체 lookback)에서 구간 시작 전에 이미 열려 있던 심볼은 첫 flat까지 이 플래그가 붙는다.
- 승/패는 `pnl.result` (`WIN` / `LOSS`). Closed PnL API 행 단위 승률은 쓰지 않는다.
- Discord는 `discord.send_daily`만 호출한다. TRADE webhook·매매 문서 `message_id`는 쓰지 않는다. 차트 attachment는 넣지 않는다.
- 스케줄: `make weekly`(월 07:10)가 주간 본문 다음에 기본 `--period 7d`로 한 번 더 보낸다. 수동 `make trades-report`도 같은 DAILY webhook이다.

### 지표

| 지표 | 계산 |
| --- | --- |
| 거래 수 `n` | 위 필터를 통과한 CLOSED |
| 승률 | wins / (wins + losses) |
| 순손익 | Σ `pnl.amount` |
| Profit Factor | Σ이익 / \|Σ손실\| (손실 합 0이면 `-`) |
| 평균 이익 | Σ이익 / wins |
| 평균 손실 | Σ손실 / losses (음수) |
| Expectancy | 순손익 / n |
| 최대 연속 승·패 | `closed_at_ms` 시간순 |
| 실현손익 낙폭 | 누적 손익 equity 최고점 대비 최대 하락 |
| 수수료 / 펀딩 | `events[]`의 `fee` / `funding` 합 |
| 복기 완료율 | `entry_reason`과 `exit_reason`이 있는 비율. 분모는 통계 `n` |
| 종목별 | 같은 필터로 n / 승률 / 손익 |

## 장애 복구

- **동기화 누락:** `make trades`를 다시 실행한다. `source_ids`로 체결은 멱등. 커서가 너무 앞이면 `--backfill`로 2년을 다시 훑는다.
- **잘못된 첫 구간 통계:** backfill 뒤 `stats_eligible=false`인 첫 매매는 리포트에서 빠진다. 플래그를 수동으로 `true`로 바꾸면 다시 들어간다.
- **미복기 메시지 중복:** 문서의 `discord.message_id`가 있으면 같은 webhook으로 edit.
- **리포트가 매매 채널로 감:** `DISCORD_TRADE_WEBHOOK_URL`이 아니라 `DISCORD_DAILY_WEBHOOK_URL`인지 확인.
- **TinyDB 손상:** `apps/briefing/app/data/*.json`은 gitignore. 로컬 백업을 복구한다.

## 데이터가 아닌 것

socket watcher, Closed PnL API 승률, 웹 대시보드, Cloud DB, Discord App/Bot Modal(복기 문구를 채널에 보이게 하는 것 포함)은 범위 밖이다.
