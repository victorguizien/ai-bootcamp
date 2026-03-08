# Development Rules

## General
- Use Python 3.11
- Use uv for dependency management (not Poetry)
- Keep code simple — this is an MVP, avoid over-engineering

## PandasAI
- IMPORTANT: Always use PandasAI v3 API (pandasai >= 3.0.0)
- Check official PandasAI v3 docs before writing or modifying any PandasAI code
- Use `pai.DataFrame()` and `.chat()` for queries
- Use `pai.create()` / `pai.load()` for semantic layer datasets
- Use `pandasai-litellm` for LLM configuration, not direct OpenAI

## Slack
- Use slack-bolt for the Slack app
- Use Socket Mode (SLACK_APP_TOKEN) for local development
- Always reply in threads to keep channels clean
- Send a "thinking" indicator before long operations

## Code Style
- No unnecessary abstractions — plain functions over classes where possible
- Type hints on function signatures
- Logging over print statements
