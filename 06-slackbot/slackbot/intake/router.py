"""Intent router — classifies incoming messages."""

import json
import logging
import os
import re

from openai import OpenAI

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Classify the user's message into exactly one category:
- "data_question": asking about data, metrics, numbers, analysis, trends, comparisons
- "table_preview": asking to see/show a specific table, its columns, or what data is available in it (e.g. "show me the payments table", "what's in users")
- "help": asking what the bot can do, how to use it, asking for examples
- "chitchat": greetings, thanks, jokes, off-topic conversation

Return ONLY the category name, nothing else."""

_DECOMPOSE_PROMPT = """The user sent a message that may contain multiple separate requests. Split it into individual, self-contained requests.

Rules:
- If the message is a single request, return a JSON array with just that one message
- If it contains multiple distinct requests (e.g. "show me the users table and get me revenue by month"), split them
- Each sub-request should be self-contained and make sense on its own
- Keep the original wording as much as possible
- Do NOT split a single complex question into parts (e.g. "revenue by month and method" is ONE request)

Return ONLY a JSON array of strings, e.g. ["request 1", "request 2"]. No explanation."""


def strip_mention(text: str) -> str:
    """Remove <@U12345> mention tags from message text."""
    return re.sub(r"<@\w+>\s*", "", text).strip()


def classify_intent(message: str) -> dict:
    """Classify a message into an intent.

    Returns:
        {"intent": "data_question" | "table_preview" | "help" | "chitchat",
         "message": cleaned message text}
    """
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
            temperature=0,
        )

        intent = response.choices[0].message.content.strip().lower()

        valid_intents = {"data_question", "table_preview", "help", "chitchat"}
        if intent not in valid_intents:
            intent = "data_question"  # default to data question

        return {"intent": intent, "message": message}

    except Exception as e:
        logger.error("Intent classification failed: %s", e)
        return {"intent": "data_question", "message": message}


def decompose_message(message: str) -> list[str]:
    """Split a compound message into individual requests.

    Returns a list of 1+ self-contained request strings.
    """
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": _DECOMPOSE_PROMPT},
                {"role": "user", "content": message},
            ],
            temperature=0,
        )

        raw = response.choices[0].message.content.strip()
        parts = json.loads(raw)

        if isinstance(parts, list) and all(isinstance(p, str) for p in parts):
            return parts

        return [message]

    except Exception as e:
        logger.error("Message decomposition failed: %s", e)
        return [message]
