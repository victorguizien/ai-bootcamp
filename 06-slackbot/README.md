# Talk-to-Your-Data Slackbot

MVP Slackbot for natural-language data analysis over a PostgreSQL database.

## Setup

```bash
uv venv --python 3.11 .venv
source .venv/bin/activate
uv sync
```

Copy `.env.example` to `.env` and fill in your credentials.

## Run

```bash
uv run python -m slackbot.main
```

## Project Structure

```
06-slackbot/
├── slackbot/
│   ├── main.py              # Entry point
│   ├── intake/              # Router + guardrails
│   ├── engine/              # Schema resolver + PandasAI
│   └── output/              # Response formatting
├── tests/
├── AGENTS.md
├── PROJECT_CONTEXT.md
├── pyproject.toml
└── README.md
```
