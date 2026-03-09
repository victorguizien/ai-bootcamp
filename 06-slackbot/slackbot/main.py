"""Talk-to-Your-Data Slackbot — full pipeline."""

import matplotlib
matplotlib.use("Agg")  # non-interactive backend, must be before any other matplotlib import

import logging
import os
import time
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)
from pathlib import Path

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from slackbot.engine.analyst import (
    init_pandasai,
    preview_dataset,
    query_dataset,
    query_multiple_datasets,
)
from slackbot.engine.memory import get_thread_dataset
from slackbot.engine.resolver import resolve_dataset
from slackbot.intake.guardrails import check_pii, check_safety
from slackbot.intake.router import classify_intent, decompose_message, strip_mention
from slackbot.output.logger import log_feedback, log_query
from slackbot.output.formatter import (
    build_blocks,
    format_chitchat,
    format_help,
    format_response,
    format_table_preview,
)
from slackbot.intake.refiner import refine_query
from slackbot.output.insights import generate_insight
from slackbot.output.suggestions import suggest_rephrasing

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set working directory to project root so PandasAI's relative paths work
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(_PROJECT_ROOT)

# Ensure chart export directory exists
_CHARTS_DIR = _PROJECT_ROOT / "exports" / "charts"
_CHARTS_DIR.mkdir(parents=True, exist_ok=True)

# Initialize PandasAI
init_pandasai()

# Slack app (Socket Mode)
app = App(token=os.environ["SLACK_BOT_TOKEN"])

TABLES = {"users", "subscriptions", "payments", "sessions"}


def _extract_table_name(message: str) -> str | None:
    """Try to extract a table name from a preview request."""
    lower = message.lower()
    for table in TABLES:
        if table in lower:
            return f"public/{table}"
    return None


def _handle_question(question: str, channel: str, thread_ts: str, client, user: str = "unknown"):
    """Full pipeline for a data question."""
    thinking = client.chat_postMessage(
        channel=channel,
        thread_ts=thread_ts,
        text=":hourglass_flowing_sand: Thinking...",
    )

    start = time.time()

    try:
        dataset = resolve_dataset(question)

        # For follow-ups like "break that down by month", the resolver can't
        # figure out the table. Fall back to whatever dataset this thread was
        # already using.
        if dataset is None:
            dataset = get_thread_dataset(thread_ts)

        if dataset is None:
            client.chat_update(
                channel=channel,
                ts=thinking["ts"],
                text="I couldn't determine which data source to use. I can help with: *users*, *subscriptions*, *payments*, and *sessions*.\n\nSay *help* for examples.",
            )
            return

        dataset_label = ", ".join(dataset) if isinstance(dataset, list) else dataset

        # Refine the question for better PandasAI results
        refined = refine_query(question)

        if isinstance(dataset, list):
            result = query_multiple_datasets(dataset, refined, thread_ts=thread_ts)
        else:
            result = query_dataset(dataset, refined, thread_ts=thread_ts)

        duration = time.time() - start

        # Error with suggestions
        if result["type"] == "error":
            error_text = "I had trouble answering that."
            suggestions = suggest_rephrasing(question)
            if suggestions:
                error_text += f"\n\n*Try rephrasing:*\n{suggestions}"
            client.chat_update(channel=channel, ts=thinking["ts"], text=error_text)
            log_query(client, user=user, question=question, dataset=dataset_label, result_type="error", duration=duration)
            return

        formatted = format_response(result)
        logger.info("Result type=%s, file_path=%s, csv_path=%s", result["type"], formatted.get("file_path"), formatted.get("csv_path"))

        # Generate insight + follow-up suggestions
        extras = generate_insight(question, result["type"], result["content"])
        insight = extras.get("insight") if extras else None
        follow_ups = extras.get("follow_ups") if extras else None

        blocks = build_blocks(formatted["text"], insight=insight, follow_ups=follow_ups)

        client.chat_update(
            channel=channel,
            ts=thinking["ts"],
            text=formatted["text"],  # fallback for notifications
            blocks=blocks,
        )

        # Upload chart if present
        if formatted["file_path"]:
            chart_path = Path(formatted["file_path"])
            # Resolve relative paths against project root
            if not chart_path.is_absolute():
                chart_path = _PROJECT_ROOT / chart_path
            if chart_path.exists():
                client.files_upload_v2(
                    channel=channel,
                    thread_ts=thread_ts,
                    file=str(chart_path),
                    title="Chart",
                )
            else:
                logger.error("Chart file not found: %s", chart_path)
                client.chat_postMessage(
                    channel=channel,
                    thread_ts=thread_ts,
                    text=":warning: Chart was generated but the file couldn't be found.",
                )

        # Upload CSV if present (large DataFrames)
        if formatted.get("csv_path"):
            client.files_upload_v2(
                channel=channel,
                thread_ts=thread_ts,
                file=formatted["csv_path"],
                title="Full results",
                filename="query_result.csv",
            )

        log_query(client, user=user, question=question, dataset=dataset_label, result_type=result["type"], duration=duration)

    except Exception as e:
        logger.error("Query handler error: %s", e)
        duration = time.time() - start
        client.chat_update(
            channel=channel,
            ts=thinking["ts"],
            text="Something went wrong. Please try again later.",
        )
        log_query(client, user=user, question=question, dataset="unknown", result_type="error", duration=duration)


def _process_single(question: str, channel: str, thread_ts: str, client, user: str = "unknown", order: int = 0):
    """Process a single request: guardrails → intent → route.

    Returns (order, None) so compound requests can be sorted.
    """
    start = time.time()

    # Guardrails
    pii = check_pii(question)
    if not pii["safe"]:
        client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=f":warning: {pii['reason']}")
        log_query(client, user=user, question=question, dataset="N/A", result_type="blocked_pii", duration=time.time() - start)
        return order

    safety = check_safety(question)
    if not safety["safe"]:
        client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=f":warning: {safety['reason']}")
        log_query(client, user=user, question=question, dataset="N/A", result_type="blocked_safety", duration=time.time() - start)
        return order

    # Intent classification
    classified = classify_intent(question)
    intent = classified["intent"]

    if intent == "help":
        help_blocks = format_help()
        client.chat_postMessage(channel=channel, thread_ts=thread_ts, text="Here's what I can do:", blocks=help_blocks)
        log_query(client, user=user, question=question, dataset="N/A", result_type="help", duration=time.time() - start)
        return order

    if intent == "chitchat":
        client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=format_chitchat())
        log_query(client, user=user, question=question, dataset="N/A", result_type="chitchat", duration=time.time() - start)
        return order

    if intent == "table_preview":
        table_path = _extract_table_name(question)
        if table_path:
            thinking = client.chat_postMessage(
                channel=channel, thread_ts=thread_ts,
                text=":hourglass_flowing_sand: Loading preview...",
            )
            result = preview_dataset(table_path)
            client.chat_update(
                channel=channel, ts=thinking["ts"],
                text=format_table_preview(result),
            )
            log_query(client, user=user, question=question, dataset=table_path, result_type="preview", duration=time.time() - start)
        else:
            client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text="Which table would you like to see? Available: *users*, *subscriptions*, *payments*, *sessions*.",
            )
        return order

    # Data question
    _handle_question(question, channel, thread_ts, client, user=user)
    return order


def _process_message(question: str, channel: str, thread_ts: str, client, user: str = "unknown"):
    """Decompose compound messages, then process sub-requests in parallel."""
    if not question:
        client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text="I didn't catch a question. Try asking something about your data!",
        )
        return

    parts = decompose_message(question)

    if len(parts) == 1:
        _process_single(parts[0], channel, thread_ts, client, user=user, order=0)
        return

    # Process sequentially to preserve message order in thread
    for i, part in enumerate(parts):
        _process_single(part, channel, thread_ts, client, user=user, order=i)


@app.event("app_mention")
def handle_mention(event, client):
    """Handle @bot mentions in channels."""
    channel = event["channel"]
    thread_ts = event.get("thread_ts", event["ts"])
    question = strip_mention(event.get("text", ""))
    user = event.get("user", "unknown")
    _process_message(question, channel, thread_ts, client, user=user)


@app.event("message")
def handle_message(event, client):
    """Handle DMs."""
    if event.get("bot_id") or event.get("subtype"):
        return
    if event.get("channel_type") != "im":
        return

    channel = event["channel"]
    thread_ts = event.get("thread_ts", event["ts"])
    question = event.get("text", "").strip()
    user = event.get("user", "unknown")
    _process_message(question, channel, thread_ts, client, user=user)


@app.event("reaction_added")
def handle_reaction(event, client):
    """Log thumbs up/down reactions on bot messages only."""
    reaction = event.get("reaction", "")
    if reaction not in ("+1", "-1", "thumbsup", "thumbsdown"):
        return

    item = event.get("item", {})
    channel = item.get("channel", "")
    message_ts = item.get("ts", "")

    # Only log reactions on the bot's own messages
    try:
        result = client.conversations_history(
            channel=channel, latest=message_ts, inclusive=True, limit=1
        )
        msgs = result.get("messages", [])
        if not msgs:
            return
        bot_user_id = client.auth_test()["user_id"]
        if msgs[0].get("user") != bot_user_id:
            return
    except Exception:
        return

    user = event.get("user", "unknown")
    log_feedback(client, user=user, reaction=reaction, channel=channel, message_ts=message_ts)


@app.event("member_joined_channel")
def handle_bot_join(event, client):
    """Post a welcome message when the bot joins a channel."""
    # Only respond when the bot itself joins
    bot_user_id = client.auth_test()["user_id"]
    if event.get("user") != bot_user_id:
        return

    channel = event["channel"]
    client.chat_postMessage(
        channel=channel,
        text=(
            ":wave: Hi! I'm your data analysis bot.\n\n"
            "Ask me questions about your data in plain English — no SQL needed.\n\n"
            "*Available tables:* users, subscriptions, payments, sessions\n\n"
            "*Try:*\n"
            "- _How many users signed up last month?_\n"
            "- _What's the total revenue by payment method?_\n"
            "- _Show me the sessions table_\n"
            "- _Plot revenue over time_\n\n"
            "Say *help* for more examples."
        ),
    )


if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    logger.info("Bot starting...")
    handler.start()
