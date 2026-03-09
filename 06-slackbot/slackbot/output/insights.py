"""Post-answer insights and follow-up suggestions."""

import json
import logging
import os

import pandas as pd
from openai import OpenAI

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a data analyst assistant. The user asked a question about their data and got a raw answer. Provide two things:

1. **Insight** — a brief, useful interpretation of the result
2. **Follow-up questions** — 2-3 natural next questions the user might want to ask

INSIGHT RULES:
- 1-2 sentences max
- Be specific — reference actual numbers from the answer
- Add context: is this good or bad? Is there a trend? Anything surprising?
- If it's a simple number, put it in perspective
- If it's a table, highlight the key takeaway
- Don't repeat the raw data — the user already sees it
- Be direct, don't hedge

FOLLOW-UP RULES:
- Exactly 3 short follow-up questions
- Max 6-8 words each (e.g. "Breakdown by country?", "Trend over last 6 months?", "Compare to previous month?")
- They should be answerable with the available tables: users, subscriptions, payments, sessions
- Mix angles: drill down, compare, visualize

Return ONLY a JSON object: {"insight": "...", "follow_ups": ["question 1", "question 2", "question 3"]}
If there's nothing insightful, use an empty string for insight. Always include follow-ups."""


def generate_insight(question: str, result_type: str, content) -> dict | None:
    """Generate insight and follow-up suggestions for a query result.

    Returns:
        {"insight": str | None, "follow_ups": list[str]} or None on failure
    """
    if result_type not in ("text", "dataframe", "number"):
        return None

    if isinstance(content, pd.DataFrame):
        if len(content) > 10:
            summary = f"DataFrame with {len(content)} rows. First 5:\n{content.head().to_string()}"
        else:
            summary = content.to_string()
    else:
        summary = str(content)

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"Question: {question}\n\nAnswer:\n{summary}"},
            ],
            temperature=0.3,
        )

        raw = response.choices[0].message.content.strip()
        parsed = json.loads(raw)

        return {
            "insight": parsed.get("insight") or None,
            "follow_ups": parsed.get("follow_ups", []),
        }

    except Exception as e:
        logger.error("Insight generation failed: %s", e)
        return None
