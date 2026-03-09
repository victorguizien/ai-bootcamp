"""Simple in-memory response cache for identical queries."""

import hashlib
import logging
import time

logger = logging.getLogger(__name__)

CACHE_TTL = 300  # 5 minutes
_cache: dict[str, dict] = {}


def _key(dataset: str, question: str) -> str:
    """Generate a cache key from dataset + question."""
    raw = f"{dataset}|{question.strip().lower()}"
    return hashlib.md5(raw.encode()).hexdigest()


def get(dataset: str, question: str) -> dict | None:
    """Return cached result if it exists and hasn't expired."""
    k = _key(dataset, question)
    entry = _cache.get(k)
    if entry and (time.time() - entry["ts"]) < CACHE_TTL:
        logger.info("Cache hit for: %s", question[:50])
        return entry["result"]
    if entry:
        del _cache[k]
    return None


def put(dataset: str, question: str, result: dict) -> None:
    """Store a result in the cache."""
    # Don't cache errors
    if result.get("type") == "error":
        return
    k = _key(dataset, question)
    _cache[k] = {"result": result, "ts": time.time()}
