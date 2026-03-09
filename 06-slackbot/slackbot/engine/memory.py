"""Thread-based agent memory using PandasAI's built-in Agent conversation memory."""

import logging

import pandasai as pai
from pandasai import Agent

logger = logging.getLogger(__name__)

# Map thread_ts -> (Agent, dataset_name)
_agents: dict[str, tuple[Agent, str]] = {}


def get_or_create_agent(thread_ts: str, dataset_name: str) -> tuple[Agent, bool]:
    """Get an existing Agent for a thread, or create a new one.

    If the dataset changed (user switched topics), creates a fresh Agent.

    Returns:
        (agent, is_new): the Agent and whether it was just created
    """
    if thread_ts in _agents:
        existing_agent, existing_dataset = _agents[thread_ts]
        if existing_dataset == dataset_name:
            return existing_agent, False
        # Dataset changed — user switched topics, create new Agent
        logger.info("Thread %s switched from %s to %s, creating new Agent", thread_ts, existing_dataset, dataset_name)

    dataset = pai.load(dataset_name)
    agent = Agent([dataset], memory_size=10)
    _agents[thread_ts] = (agent, dataset_name)
    return agent, True


def get_thread_dataset(thread_ts: str) -> str | None:
    """Return the dataset name for an existing thread, or None."""
    if thread_ts in _agents:
        return _agents[thread_ts][1]
    return None


def clear_thread(thread_ts: str) -> None:
    """Remove an agent for a thread (e.g. on timeout)."""
    _agents.pop(thread_ts, None)
