# Bybit 지갑 Cash / Coin

Bybit 지갑 **Total = Cash + Coin** (USD)을 식별한다. Toss 주식과는 별개다.

공식 인덱스: [Asset](https://bybit-exchange.github.io/docs/v5/asset), [Account](https://bybit-exchange.github.io/docs/v5/account)

## 분류

| 지갑 | 규칙 | 분류 |
| --- | --- | --- |
| Funding | 입출금 대기 자산 전액 | Cash |
| Unified Contracts | 포지션에 묶인 자본 (`totalPositionIM + unrealisedPnl`, 주문 증거금 `totalOrderIM` 포함) | Coin |
| Unified 나머지 | Isolated Available Balance | Cash |

Contracts는 **레버리지 명목가(`positionValue`)가 아니다.** 명목가를 쓰면 Total ≠ Cash + Coin이 된다.

현재 계좌는 Isolated Margin UTA다. Isolated에서는 `totalAvailableBalance`가 비어 있으므로 코인별로 Available Balance를 계산한다.

```
AB = walletBalance - totalPositionIM - totalOrderIM - locked - bonus
```

실측: Isolated AB는 [Get Transferable Amount](https://bybit-exchange.github.io/docs/v5/account/unified-trans-amnt)의 `availableWithdrawal`과 같다.

## Unified Total API

독립 총액은 별도 엔드포인트가 아니라 [Get Wallet Balance](https://bybit-exchange.github.io/docs/v5/account/wallet-balance)의 계정 필드다.

- pybit: `get_wallet_balance(accountType="UNIFIED")`
- 필드: `result.list[0].totalEquity` — Account total equity (USD)
- Isolated여도 `totalEquity`는 채워진다. `totalAvailableBalance`만 비어 있다.
- 교차확인: 같은 응답의 `∑ coin.usdValue` ≈ `totalEquity`

보조: [Asset Overview](https://bybit-exchange.github.io/docs/v5/asset/balance/asset-overview)의 `UnifiedTradingAccount.totalEquity`. 스냅샷이라 수 센트 차이가 날 수 있어 주 검증값은 `totalEquity`다.

## 사용할 API

| 용도 | 엔드포인트 | pybit | 핵심 필드 |
| --- | --- | --- | --- |
| Funding Cash | [Get All Coins Balance](https://bybit-exchange.github.io/docs/v5/asset/balance/all-balance) | `get_coins_balance(accountType="FUND")` | `walletBalance` (코인 수량, `usdValue` 없음) |
| Unified Cash / Coin / Total | [Get Wallet Balance](https://bybit-exchange.github.io/docs/v5/account/wallet-balance) | `get_wallet_balance(accountType="UNIFIED")` | `totalEquity`, 코인별 `usdValue`, `walletBalance`, `totalPositionIM`, `totalOrderIM`, `unrealisedPnl`, `locked`, `bonus` |

FUND는 `coin`을 생략하면 전 코인. UNIFIED에 `get_coins_balance`를 쓰지 않는다 (`coin` 필수, 최대 10개).

선택 교차검증:

- [Get Position Info](https://bybit-exchange.github.io/docs/v5/position): 심볼별 `positionIM` + `unrealisedPnl`
- Asset Overview: FUND / UNIFIED `totalEquity` 스냅샷

## Isolated 계산식

코인별 Unified 총액은 `usdValue`를 쓴다. Cash/Coin은 equity 비율로 나눈다.

```
equity = walletBalance - spotBorrow + unrealisedPnl
AB     = walletBalance - totalPositionIM - totalOrderIM - locked - bonus

cash_usd = AB / equity * usdValue
coin_usd = usdValue - cash_usd
```

USDT/BYUSDT는 환율이 거의 1:1이다. IM/AB는 코인 수량이고, USD 변환에 `usdValue / equity`를 쓴다.

검증:

```
unified_cash + unified_coin ≈ totalEquity
bybit_cash + bybit_coin     ≈ totalEquity + fund_cash
```

허용 오차: `$0.05`.

## USD 변환

- Unified Total: `totalEquity`
- Unified 코인: `usdValue`
- Funding 스테이블 (`USDT`, `USDC`, `USD`, `USDE`, `FDUSD`): 1:1 USD
- Funding 그 외: [tickers](https://bybit-exchange.github.io/docs/v5/market/tickers) `lastPrice` (USDT 마켓)
- BYUSDT: Unified `usdValue`. IM이 없으면 Cash

## 로컬 테스트

```shell
PYTHONPATH=apps/briefing uv run python -m app.collectors.bybit
```

`totalEquity` 대비 Cash+Coin 오차가 `$0.05`를 넘으면 exit code 1.
