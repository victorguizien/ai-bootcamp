# Project Context

## Goal
Build an MVP Slackbot that lets non-technical team members ask natural-language questions about internal data and get instant answers — no SQL or dashboards needed.

## Target Users
Analysts, product managers, marketers — people who want quick data answers without writing queries.

## Data Sources
PostgreSQL database with 4 tables:
- `users` — user profiles (country, device type, signup date, age)
- `subscriptions` — subscription plans and statuses
- `payments` — payment transactions
- `sessions` — user session activity

## Architecture (from system design)

```
Slack → Intake (Router + Guardrails) → Engine (Schema Resolver + PandasAI) → Output (Formatter) → Slack
                                                    ↕
                                            PostgreSQL + Semantic Layer
```

### Subsystems
1. **Intake** (`slackbot/intake/`) — intent classification, PII/guardrail checks
2. **Engine** (`slackbot/engine/`) — schema resolution, PandasAI query execution
3. **Output** (`slackbot/output/`) — format results for Slack (tables, charts, text)

## Scope (MVP)
- Receive messages in Slack via Socket Mode
- Classify intent (data question vs other)
- Route data questions to PandasAI
- Return formatted answers in Slack threads
- Handle errors gracefully

## Out of Scope (for now)
- Conversation memory / follow-up questions
- Scheduled reports
- Multi-table joins
- Caching
