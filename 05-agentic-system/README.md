# Agentic System — PandasAI Exploration

## Overview

Exploring PandasAI as a natural-language data analysis tool. Connected to a shared PostgreSQL database, experimented with different tables (`users`, `subscriptions`, `payments`, `sessions`), query styles, and the semantic layer.

## Setup

```bash
# Python 3.11 / uv
uv venv --python 3.11 .venv
source .venv/bin/activate
uv pip install pandas numpy sqlalchemy psycopg2-binary pyyaml jupyter ipykernel matplotlib seaborn pandasai pandasai-litellm python-dotenv pandasai-sql
```

Create a `.env` file with your credentials:

```bash
host=your-database-host
port=5432
database=your-database-name
username=your-username
password=your-password
OPENAI_API_KEY=sk-your-key-here
```

Register the Jupyter kernel:

```bash
python -m ipykernel install --user --name 05-agentic-system --display-name "Python 3.11 (05-agentic-system)"
```

## Run

Open `pandasai_quickstart_guide.ipynb` in VSCode and select the **Python 3.11 (05-agentic-system)** kernel.

## What was done

1. **Explored the notebook** — ran through all cells to understand how PandasAI loads data, chats with DataFrames, and creates reusable datasets
2. **Connected to different tables** — queried `users`, `subscriptions`, `payments`, and `sessions` from the shared Postgres DB
3. **Experimented with query styles** — simple aggregations, filtered groupbys, analytical/ratio questions, and comparisons over time
4. **Semantic layer** — created datasets with column descriptions to improve PandasAI's accuracy
5. **Reflections** — notes on how PandasAI could fit into a Slackbot architecture (router, guardrails, formatting)

## Project structure

```
05-agentic-system/
├── pandasai_quickstart_guide.ipynb   # Main notebook with all experiments
├── datasets/                          # Semantic layer configs (auto-generated)
├── pyproject.toml
├── poetry.lock
├── AGENTS.md
└── README.md
```

## Notes

- `pandasai-sql` requires Python 3.11 or below
- The `pai.create()` calls are commented out since datasets only need to be created once. Use `pai.load()` to reload them.
- Simple queries (counts, averages, groupbys) work reliably. More analytical questions are hit or miss depending on phrasing.
