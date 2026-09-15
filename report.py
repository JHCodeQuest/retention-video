"""Builds the client retention PDF by reusing slack-file-bot's analysis and
PDF renderer, so this project narrates exactly the report the bot posts.

Only fictional client data is ever used: slack-file-bot's MOCK_CLIENTS, or a
JSON file passed explicitly. clients_data.get_clients() (the live
outreach-tracker feed) is deliberately never called.
"""
import json
import os
import sys
from pathlib import Path

DEFAULT_BOT_PATH = Path(__file__).resolve().parent.parent / "slack-file-bot"


def _import_bot():
    bot_path = Path(os.environ.get("SLACK_FILE_BOT_PATH") or DEFAULT_BOT_PATH).resolve()
    if not (bot_path / "retention_analysis.py").exists():
        raise SystemExit(
            f"slack-file-bot not found at {bot_path} - set SLACK_FILE_BOT_PATH "
            "to your clone of https://github.com/JHCodeQuest/slack-file-bot"
        )
    if str(bot_path) not in sys.path:
        sys.path.insert(0, str(bot_path))

    import clients_data
    import pdf_report
    import retention_analysis
    import rules_engine
    import stats_pipeline

    return clients_data, pdf_report, retention_analysis, rules_engine, stats_pipeline


def load_clients(clients_json: Path | None) -> list[dict]:
    if clients_json is None:
        clients_data, *_ = _import_bot()
        return clients_data.MOCK_CLIENTS
    return json.loads(Path(clients_json).read_text(encoding="utf-8"))


def build_report(clients: list[dict], dest: Path):
    """Returns (results, pdf_path, overall_tier)."""
    _, pdf_report, retention_analysis, rules_engine, _ = _import_bot()
    results = retention_analysis.analyze(clients)
    pdf_report.build_pdf(results, dest)
    overall = rules_engine.evaluate(retention_analysis.total_profit_gbp(results))
    return results, dest, overall.urgency_tier


def format_gbp(pounds: int) -> str:
    *_, stats_pipeline = _import_bot()
    return stats_pipeline.format_hero(pounds)


def client_color(profit_gbp: int) -> str:
    *_, rules_engine, _ = _import_bot()
    return rules_engine.client_color(profit_gbp)
