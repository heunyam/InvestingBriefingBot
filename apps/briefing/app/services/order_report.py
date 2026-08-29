from apps.briefing.app.utils.format import fmt_decimal, fmt_pct


def format_report(stats: dict) -> str:
    return "\n".join(
        [
            f"📊 매매 성과 · {stats['title']}",
            "",
            f"거래 {stats['n']:,} · 승률 {fmt_pct(stats['win_rate'])}",
            f"💰 순손익 {fmt_decimal(stats['net_pnl'])}",
            f"💸 수수료 {fmt_decimal(stats['fees'])}",
        ]
    )
