from datetime import timedelta

from app.outbound import discord
from app.services.formatter import format_message
from app.collector.main import collect_data
from app.models.asset import AssetSummary


def app():
    # try:
    summary = collect_data()
    summary.save()

    try:
        summary_yesterday = AssetSummary.load(summary.date - timedelta(days=1))
    except FileNotFoundError:
        summary_yesterday = summary

    message = format_message(summary, summary_yesterday)
    discord.send_daily(message)

    # except Exception as e:
    #     discord.send_daily(f"Error occurred: {e}")


if __name__ == "__main__":
    app()
