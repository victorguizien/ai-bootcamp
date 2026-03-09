"""Schema resolver — maps a user question to the correct dataset(s)."""

import json
import logging
import os

from openai import OpenAI

logger = logging.getLogger(__name__)

AVAILABLE_DATASETS = [
    {
        "path": "public/users",
        "table": "users",
        "description": "Core user registry — signup date, country, device type",
        "example_questions": [
            "How many users signed up last month?",
            "What's the most popular device type per country?",
            "Show me the signup trend over time",
        ],
    },
    {
        "path": "public/subscriptions",
        "table": "subscriptions",
        "description": "Subscription lifecycle — plan tier, start/end dates, status (active/canceled/expired)",
        "example_questions": [
            "How many active subscriptions are there?",
            "What's the distribution of plans?",
            "What's the churn rate by plan type?",
        ],
    },
    {
        "path": "public/payments",
        "table": "payments",
        "description": "Payment transactions — amount in USD, payment date, payment method",
        "example_questions": [
            "What's the total revenue this month?",
            "What's the average payment amount by method?",
            "Show me revenue over time",
        ],
    },
    {
        "path": "public/sessions",
        "table": "sessions",
        "description": "User engagement sessions — date, duration in minutes, activity type (browse/read/listen)",
        "example_questions": [
            "What's the average session duration?",
            "How many sessions per day?",
            "What's the most popular activity type?",
        ],
    },
]

_SYSTEM_PROMPT = """You are a schema resolver. Given a user question about data, determine which database table(s) are needed to answer it.

Available tables:
{tables}

Rules:
- If the question can be answered with ONE table, return just that table path
- If the question requires data from MULTIPLE tables (e.g. "revenue by country" needs payments + users), return all needed paths
- If the question cannot be answered with any available table, return "none"

Return ONLY a JSON array of table paths, e.g. ["public/users"] or ["public/users", "public/payments"] or ["none"].
No explanation, just the JSON array."""


def _build_table_list() -> str:
    lines = []
    for ds in AVAILABLE_DATASETS:
        lines.append(f"- {ds['path']}: {ds['description']}")
    return "\n".join(lines)


def resolve_dataset(question: str) -> str | list[str] | None:
    """Map a question to the relevant dataset path(s).

    Returns:
        str: single dataset path (e.g. "public/users")
        list[str]: multiple dataset paths for multi-table queries
        None: if no table matches
    """
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": _SYSTEM_PROMPT.format(tables=_build_table_list()),
                },
                {"role": "user", "content": question},
            ],
            temperature=0,
        )

        raw = response.choices[0].message.content.strip()
        paths = json.loads(raw)

        if not paths or paths == ["none"]:
            return None

        # Validate paths
        valid_paths = {ds["path"] for ds in AVAILABLE_DATASETS}
        paths = [p for p in paths if p in valid_paths]

        if not paths:
            return None
        if len(paths) == 1:
            return paths[0]
        return paths

    except Exception as e:
        logger.error("Schema resolution failed: %s", e)
        return None
