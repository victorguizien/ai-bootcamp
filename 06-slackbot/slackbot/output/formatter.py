"""Response formatter — format results for Slack."""

import os
import tempfile

import pandas as pd

from slackbot.engine.resolver import AVAILABLE_DATASETS


def format_response(result: dict) -> dict:
    """Convert an engine result to a Slack-ready response.

    Returns:
        {"text": str, "file_path": str | None, "csv_path": str | None}
    """
    rtype = result["type"]
    content = result["content"]

    if rtype == "error":
        return {
            "text": "I had trouble answering that. Could you try rephrasing your question?",
            "file_path": None,
            "csv_path": None,
        }

    if rtype == "chart":
        return {
            "text": "Here's your chart:",
            "file_path": content,
            "csv_path": None,
        }

    if rtype == "dataframe":
        return _format_dataframe(content)

    # text — also catch DataFrames that weren't tagged as "dataframe" type
    if isinstance(content, pd.DataFrame):
        return _format_dataframe(content)

    return {"text": str(content), "file_path": None, "csv_path": None}


def _format_dataframe(content) -> dict:
    """Format a DataFrame result with optional CSV export."""
    csv_path = None

    if isinstance(content, pd.DataFrame):
        if len(content) > 15:
            text = f"```\n{content.head(10).to_string()}\n```\n... and {len(content) - 10} more rows (full data attached as CSV)"
            csv_path = _export_csv(content)
        else:
            text = f"```\n{content.to_string()}\n```"
    else:
        text = str(content)

    return {"text": text, "file_path": None, "csv_path": csv_path}


def build_blocks(answer_text: str, insight: str | None = None, follow_ups: list[str] | None = None) -> list[dict]:
    """Build Slack blocks for a rich response."""
    blocks = []

    # Answer
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": answer_text},
    })

    # Insight
    if insight:
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f":bulb: {insight}"}],
        })

    # Follow-up suggestions — one per line in context block
    if follow_ups:
        follow_up_text = "*Suggested follow-ups:*\n" + "\n".join(f"• _{q}_" for q in follow_ups)
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": follow_up_text}],
        })

    # Feedback prompt — always last
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": "React with :thumbsup: or :thumbsdown: to rate this answer"}],
    })

    return blocks


def _export_csv(df: pd.DataFrame) -> str:
    """Save a DataFrame to a temp CSV file and return the path."""
    fd, path = tempfile.mkstemp(suffix=".csv", prefix="query_result_")
    os.close(fd)
    df.to_csv(path, index=False)
    return path


def format_table_preview(result: dict) -> str:
    """Format a dataset preview for Slack."""
    if result["type"] == "error":
        return f"Couldn't load that table: {result['content']}"

    info = result["content"]
    name = info["name"]
    head = info["head"]
    columns = info["columns"]

    col_lines = "\n".join(
        f"  - `{c['name']}` ({c['dtype']})" for c in columns
    )

    return (
        f"*{name}*\n\n"
        f"*Columns:*\n{col_lines}\n\n"
        f"*Sample data (first 5 rows):*\n"
        f"```\n{head.to_string()}\n```"
    )


def format_help() -> list[dict]:
    """Return help message as Slack blocks."""
    blocks = []

    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": "*I can help you analyze data from these tables:*"},
    })

    for ds in AVAILABLE_DATASETS:
        questions = "\n".join(f"• _{q}_" for q in ds["example_questions"])
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{ds['table']}* — {ds['description']}\n{questions}"},
        })

    blocks.append({"type": "divider"})
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": (
            "*Tips:*\n"
            "• Say _show me the payments table_ to preview data\n"
            "• I can handle multi-table questions\n"
            "• Ask follow-ups in the same thread\n"
            "• Try _plot revenue over time_ for charts"
        )}],
    })

    return blocks


def format_chitchat() -> str:
    """Return a friendly redirect for non-data messages."""
    return "Hey! I'm a data analysis bot. Ask me a question about your data, or say *help* to see what I can do."
