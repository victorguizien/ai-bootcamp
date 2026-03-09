"""PandasAI wrapper — query datasets and return structured results."""

import logging
import re
import uuid
from pathlib import Path

import pandas as pd
import pandasai as pai
from pandasai import Agent
from pandasai_litellm.litellm import LiteLLM

from slackbot.engine import cache

_CHARTS_DIR = Path(__file__).resolve().parent.parent.parent / "exports" / "charts"

logger = logging.getLogger(__name__)

_CHART_PATTERN = re.compile(
    r"\b(plot|chart|graph|visuali[sz]e|draw|histogram|bar chart|line chart|pie chart|scatter)\b",
    re.IGNORECASE,
)


def _resolve_chart_path(path_str: str) -> str:
    """Resolve a chart file path, checking multiple locations."""
    p = Path(path_str)
    if p.exists():
        return str(p.resolve())
    # Try relative to project root
    project_root = Path(__file__).resolve().parent.parent.parent
    resolved = project_root / p
    if resolved.exists():
        return str(resolved)
    # Return as-is, let the caller handle missing file
    logger.warning("Chart file not found at %s or %s", p, resolved)
    return str(resolved)


def _classify_response(response) -> dict:
    """Normalize a PandasAI response into {type, content}."""
    logger.info("_classify_response: type=%s, repr=%s", type(response).__name__, repr(response)[:300])

    # PandasAI v3 returns {"type": "dataframe", "value": df} dicts
    if isinstance(response, dict) and "type" in response:
        value = response.get("value", response.get("content", response))
        rtype = response["type"]
        if rtype == "dataframe" and isinstance(value, pd.DataFrame):
            return {"type": "dataframe", "content": value}
        if rtype in ("plot", "chart"):
            return {"type": "chart", "content": _resolve_chart_path(str(value))}
        if rtype in ("string", "number"):
            return {"type": "text", "content": str(value)}
        if isinstance(value, pd.DataFrame):
            return {"type": "dataframe", "content": value}
        return {"type": "text", "content": str(value)}

    # Object with .type and .value attributes (e.g. ChartResponse, DataFrameResponse)
    if hasattr(response, "type") and hasattr(response, "value"):
        rtype = getattr(response, "type", "")
        value = getattr(response, "value", response)
        if rtype == "dataframe" and isinstance(value, pd.DataFrame):
            return {"type": "dataframe", "content": value}
        if rtype in ("plot", "chart"):
            return {"type": "chart", "content": _resolve_chart_path(str(value))}
        if isinstance(value, pd.DataFrame):
            return {"type": "dataframe", "content": value}
        return {"type": "text", "content": str(value)}

    if hasattr(response, "path"):
        return {"type": "chart", "content": _resolve_chart_path(str(response.path))}
    if isinstance(response, pd.DataFrame):
        return {"type": "dataframe", "content": response}
    return {"type": "text", "content": str(response)}


def _maybe_add_chart_hint(question: str) -> str:
    """If the user asks for a chart/plot, add an explicit hint for PandasAI."""
    if _CHART_PATTERN.search(question):
        chart_path = _CHARTS_DIR / f"chart_{uuid.uuid4().hex[:8]}.png"
        return f"{question} Save to '{chart_path}'."
    return question


def init_pandasai() -> None:
    """Configure PandasAI with the LLM. Call once at startup."""
    llm = LiteLLM(model="gpt-4.1-mini")
    pai.config.set({"llm": llm})
    logger.info("PandasAI initialized with gpt-4.1-mini")


def query_dataset(dataset_name: str, question: str, thread_ts: str | None = None) -> dict:
    """Query a single dataset using PandasAI Agent with built-in memory."""
    from slackbot.engine.memory import get_or_create_agent

    # Check cache first (only for non-follow-up questions)
    cached = cache.get(dataset_name, question)
    if cached:
        return cached

    try:
        enhanced_q = _maybe_add_chart_hint(question)

        if thread_ts:
            agent, is_new = get_or_create_agent(thread_ts, dataset_name)
            response = agent.chat(enhanced_q) if is_new else agent.follow_up(enhanced_q)
        else:
            dataset = pai.load(dataset_name)
            response = dataset.chat(enhanced_q)

        result = _classify_response(response)
        cache.put(dataset_name, question, result)
        return result

    except Exception as e:
        logger.error("PandasAI query failed: %s", e)
        return {"type": "error", "content": str(e)}


def query_multiple_datasets(dataset_names: list[str], question: str, thread_ts: str | None = None) -> dict:
    """Query across multiple datasets using PandasAI Agent with all tables loaded.

    Loads ALL available tables so PandasAI can use any intermediate join tables
    (e.g. subscriptions to connect payments to users).
    """
    dataset_key = "+".join(sorted(dataset_names))
    cached = cache.get(dataset_key, question)
    if cached:
        return cached

    try:
        from slackbot.engine.resolver import AVAILABLE_DATASETS
        all_paths = [ds["path"] for ds in AVAILABLE_DATASETS]
        datasets = [pai.load(name) for name in all_paths]
        agent = Agent(datasets, memory_size=10)
        enhanced_q = _maybe_add_chart_hint(question)
        response = agent.chat(enhanced_q)
        result = _classify_response(response)
        cache.put(dataset_key, question, result)
        return result

    except Exception as e:
        logger.error("Multi-table query failed: %s", e)
        return {"type": "error", "content": str(e)}


def preview_dataset(dataset_name: str) -> dict:
    """Return first 5 rows and column info for a dataset."""
    try:
        dataset = pai.load(dataset_name)
        df = dataset.head()
        columns = [
            {"name": col, "dtype": str(df[col].dtype)}
            for col in df.columns
        ]
        return {
            "type": "preview",
            "content": {"head": df, "columns": columns, "name": dataset_name},
        }
    except Exception as e:
        logger.error("Preview failed: %s", e)
        return {"type": "error", "content": str(e)}
