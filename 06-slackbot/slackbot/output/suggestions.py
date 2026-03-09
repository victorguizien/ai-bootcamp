"""Error suggestions — use LLM to suggest rephrased questions on failure."""

import logging
import os

from openai import OpenAI

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """The user asked a data analysis question but the system failed to answer it. Suggest a simpler, clearer rephrasing they could try.

Available tables: users (signup_date, country, device_type), subscriptions (plan, status, start_date, end_date), payments (amount_usd, payment_date, method), sessions (session_date, duration_minutes, activity_type).

Rules:
- Suggest 1-2 alternative phrasings
- Keep them short and specific
- Use explicit terms like "sum", "count", "group by", "average"
- Return just the suggestions, one per line, no numbering or bullets"""


def suggest_rephrasing(question: str) -> str | None:
    """Return suggested rephrasings for a failed question."""
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": question},
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error("Suggestion generation failed: %s", e)
        return None
