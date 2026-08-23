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

- Entry: `make daily` → `PYTHONPATH=apps/briefing` → `commands/daily.py`. Weekly: `make weekly` → `commands/weekly.py` (Mondays 07:10 after daily).
- Import paths stay `app.*` and `commands.*`. Do not rename those packages.
- Secrets stay in `.env` (never commit). Copy from `.env.example`.
- Snapshots are `AssetSummary` documents in TinyDB table `asset_summary` (daily, keyed by `date`) and `weekly` (one row per week, upsert on `week_start`). Use `AssetSummary.save` / `save_week` / `all` / `all_weeks`.
- `apps/briefing/app/data/*.json` and `apps/briefing/launchd/*.log` are gitignored. Do not force-add them.
- After changing the launchd plist, run `make load` so `~/Library/LaunchAgents/` matches.

## What not to do

- Do not commit `.env`, portfolio JSON, or launchd logs.
