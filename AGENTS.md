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

- Entry: `make daily` → `PYTHONPATH=apps/briefing` → `commands/daily.py`
- Import paths stay `app.*` and `commands.*`. Do not rename those packages.
- Secrets stay in `.env` (never commit). Copy from `.env.example`.
- Snapshots are `AssetSummary` documents in TinyDB table `asset_summary`, keyed by `date` (KST, former JSON filename). Use `AssetSummary.save` / `AssetSummary.load`. Do not add a `store/` package.
- `apps/briefing/app/data/*.json` and `apps/briefing/launchd/*.log` are gitignored. Do not force-add them.
- After changing the launchd plist, run `make load` so `~/Library/LaunchAgents/` matches.

## Pine Script (`apps/pine/`)

Write **Pine Script v6 only** (`//@version=6`). There is no local compiler or backtester. The user copies a `.pine` file into TradingView’s Pine Editor, saves it, and clicks **Add to chart**.

### Layout

```
apps/pine/
  lessons/      # numbered tutorials; learn in order
  indicators/   # reusable overlays / panes
  strategies/   # order logic + backtests (later)
```

### How to work on a script

1. Read the matching lesson or existing script before editing.
2. Keep one concern per file. Prefer `indicator()` until the user asks for `strategy()`.
3. After writing, tell the user exactly which file to paste into the Pine Editor and what they should see on the chart.
4. Do not invent undocumented builtins. Prefer the official docs:
   - User Manual: https://www.tradingview.com/pine-script-docs/
   - v6 Reference: https://www.tradingview.com/pine-script-reference/v6/

### Conventions

- Title strings in `indicator()` / `strategy()` are human-readable (Korean OK).
- User inputs use `input.*()` and names end with `Input` (e.g. `fastInput`).
- Use `ta.*` builtins instead of reimplementing SMA/EMA/RSI/MACD.
- Plot with named colors (`color.blue`), not magic RGB, unless the user wants a custom palette.
- `bool` is never `na` in v6. Use short-circuit `and` / `or`.
- Comments explain *why* (signal intent), not *what* the next line does.

### Learning path

Stay on the current lesson until the user wants the next one.

1. `apps/pine/lessons/01-first-indicator.pine` — declaration, series, `plot`
2. Inputs (`input.int`) and `ta.macd`
3. Overlay vs pane, `hline`, colors
4. Conditions, `bgcolor`, `alertcondition`
5. First `strategy()` with `strategy.entry` / `strategy.close`

## What not to do

- Do not “run” Pine from the terminal.
- Do not convert lessons into a Python backtest unless asked.
- Do not publish scripts to TradingView Community from this repo.
- Do not commit `.env`, portfolio JSON, or launchd logs.
