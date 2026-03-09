"""Guardrails — PII detection and safety checks."""

import re

# PII patterns
_EMAIL_RE = re.compile(r"\S+@\S+\.\S+")
_PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CC_RE = re.compile(r"\b(?:\d[ -]*?){13,16}\b")

# SQL injection patterns
_SQL_RE = re.compile(
    r"\b(DROP|DELETE|UPDATE|INSERT|ALTER|TRUNCATE|EXEC)\b",
    re.IGNORECASE,
)


def check_pii(text: str) -> dict:
    """Check if the message contains PII patterns.

    Returns:
        {"safe": bool, "reason": str}
    """
    if _EMAIL_RE.search(text):
        return {"safe": False, "reason": "Your message appears to contain an email address. Please remove it and try again."}
    if _PHONE_RE.search(text):
        return {"safe": False, "reason": "Your message appears to contain a phone number. Please remove it and try again."}
    if _SSN_RE.search(text):
        return {"safe": False, "reason": "Your message appears to contain a Social Security Number. Please remove it and try again."}
    if _CC_RE.search(text):
        return {"safe": False, "reason": "Your message appears to contain a credit card number. Please remove it and try again."}
    return {"safe": True, "reason": ""}


def check_safety(text: str) -> dict:
    """Check for SQL injection or destructive patterns.

    Returns:
        {"safe": bool, "reason": str}
    """
    if _SQL_RE.search(text):
        return {"safe": False, "reason": "Your message contains a potentially unsafe keyword. I can only answer data analysis questions."}
    return {"safe": True, "reason": ""}
