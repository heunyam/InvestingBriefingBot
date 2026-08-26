# InvestingBriefingBot

Personal investing monorepo. Two areas live here and stay separate:

| Area | Path | Runtime |
| --- | --- | --- |
| Daily briefing bot | `apps/briefing/` | Python 3.14, local Mac |
| TradingView scripts | `apps/pine/` | Pine Script v6, TradingView cloud |

Do not mix Python bot code with Pine. Do not add TradingView API clients unless asked.

Root stays repo-level only (`makefile`, `pyproject.toml`, `.env*`, docs). Apps live under `apps/`.

## Python bot

Daily job: collect Toss + Bybit snapshots, persist to TinyDB (`apps/briefing/app/data/db.json`), post a Discord summary.

- Entry: `make daily` → `PYTHONPATH=apps/briefing` → `commands/daily.py` (07:00). Weekly: `make weekly` → `commands/weekly.py` (Mondays 07:10 after daily). Trades: `make trades` (daily 06:50) → `commands/trades.py`.
- Trades: `make trades` syncs Bybit fills from **2026-08-25 00:00 KST** onward. TinyDB keeps one event per exec under a `trade_id` round-trip; Discord posts coalesce same Bybit `orderId` ENTRY/EXIT fills into one message on `DISCORD_TRADE_WEBHOOK_URL` (`discord.messages[].event_keys`). Save a review with `make trades-review ARGS="--id <prefix> --entry '...' --exit '...'"` (TinyDB on that `trade_id` + edit latest TRADE webhook message; review text is not yet in the Discord body). `make trades-report` posts 7d CLOSED stats to `DISCORD_DAILY_WEBHOOK_URL` as its own message (same Monday 07:10 `make weekly` job; does not touch per-trade Discord ids). Discord App/Bot is later; webhook only for Discord.
- Import paths stay `app.*` and `commands.*`. Do not rename those packages.
- Secrets stay in `.env` (never commit). Copy from `.env.example`.
- Snapshots are `AssetSummary` documents in TinyDB table `asset_summary` (daily, keyed by `date`) and `weekly` (one row per week, upsert on `week_start`). Use `AssetSummary.save` / `save_week` / `all` / `all_weeks`.
- `apps/briefing/app/data/*.json` and `apps/briefing/launchd/*.log` are gitignored. Do not force-add them.
- After changing the launchd plist, run `make load` so `~/Library/LaunchAgents/` matches.

## What not to do

- Do not commit `.env`, portfolio JSON, or launchd logs.
