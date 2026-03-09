"""Query logger — posts query summaries to a Slack log channel."""

import logging
import os

logger = logging.getLogger(__name__)

LOG_CHANNEL = os.getenv("SLACK_LOG_CHANNEL")


def log_query(client, *, user: str, question: str, dataset: str, result_type: str, duration: float) -> None:
    """Post a query summary to the log channel. Fire-and-forget."""
    if not LOG_CHANNEL:
        return

    try:
        status = ":white_check_mark:" if result_type not in ("error", "blocked_pii", "blocked_safety") else ":x:"
        client.chat_postMessage(
            channel=LOG_CHANNEL,
            text=(
                f"{status} *Query Log*\n"
                f"*User:* <@{user}>\n"
                f"*Question:* {question}\n"
                f"*Dataset:* {dataset}\n"
                f"*Result:* {result_type}\n"
                f"*Duration:* {duration:.1f}s"
            ),
        )
    except Exception as e:
        logger.error("Failed to log query: %s", e)


def log_feedback(client, *, user: str, reaction: str, channel: str, message_ts: str) -> None:
    """Log a thumbs up/down reaction with the original message content."""
    if not LOG_CHANNEL:
        return

    try:
        # Fetch the message that was reacted to
        message_text = "(couldn't fetch message)"
        result = client.conversations_history(
            channel=channel, latest=message_ts, inclusive=True, limit=1
        )
        msgs = result.get("messages", [])
        if msgs:
            message_text = msgs[0].get("text", "(empty)")
            # Truncate long messages
            if len(message_text) > 300:
                message_text = message_text[:300] + "..."

        emoji = ":thumbsup:" if reaction in ("+1", "thumbsup") else ":thumbsdown:"
        client.chat_postMessage(
            channel=LOG_CHANNEL,
            text=(
                f"{emoji} *Feedback* from <@{user}>\n"
                f"*Channel:* <#{channel}>\n"
                f"*Bot answer:*\n> {message_text}"
            ),
        )
    except Exception as e:
        logger.error("Failed to log feedback: %s", e)
