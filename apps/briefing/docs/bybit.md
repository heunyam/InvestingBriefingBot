# Bybit 지갑 Cash / Coin

Bybit 지갑 **Total = Cash + Coin** (USD)을 식별한다.

Bybit API Docs: [Asset](https://bybit-exchange.github.io/docs/v5/asset), [Account](https://bybit-exchange.github.io/docs/v5/account)

## 분류

| 지갑 | 규칙 | 분류 |
| --- | --- | --- |
| Funding | 입출금 대기 자산 전액 | Cash |
| Unified Contracts | 포지션에 묶인 자본 (`totalPositionIM + unrealisedPnl`, 주문 증거금 `totalOrderIM` 포함) | Coin |
| Unified 나머지 | Isolated Available Balance | Cash |

```
AB = walletBalance - totalPositionIM - totalOrderIM - locked - bonus
```

## Unified Total API

독립 총액은 별도 엔드포인트가 아니라 [Get Wallet Balance](https://bybit-exchange.github.io/docs/v5/account/wallet-balance)의 계정 필드다.

## 사용할 API

| 용도 | 엔드포인트 | pybit | 핵심 필드 |
| --- | --- | --- | --- |
| Funding Cash | [Get All Coins Balance](https://bybit-exchange.github.io/docs/v5/asset/balance/all-balance) | `get_coins_balance(accountType="FUND")` | `walletBalance` (코인 수량, `usdValue` 없음) |
| Unified Cash / Coin / Total | [Get Wallet Balance](https://bybit-exchange.github.io/docs/v5/account/wallet-balance) | `get_wallet_balance(accountType="UNIFIED")` | `totalEquity`, 코인별 `usdValue`, `walletBalance`, `totalPositionIM`, `totalOrderIM`, `unrealisedPnl`, `locked`, `bonus` |


## Isolated 계산식

코인별 Unified 총액은 `usdValue`를 쓴다. Cash/Coin은 equity 비율로 나눈다.

```
equity = walletBalance - spotBorrow + unrealisedPnl
AB     = walletBalance - totalPositionIM - totalOrderIM - locked - bonus

cash_usd = AB / equity * usdValue
coin_usd = usdValue - cash_usd
```

검증:

```
unified_cash + unified_coin ≈ totalEquity
bybit_cash + bybit_coin     ≈ totalEquity + fund_cash
```

## 로컬 테스트

```shell
uv run python -m apps.briefing.app.collectors.bybit
```