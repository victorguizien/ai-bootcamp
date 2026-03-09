# Talk-to-Your-Data Slackbot

Slack bot that lets you ask questions about your data in plain English. It figures out which table(s) to query, runs the analysis through PandasAI, and replies in the thread. No SQL needed.

## Architecture

![System Design](assets/images/img1.png)

Three subsystems:

- **Intake** — intent classification, compound message decomposer, query refiner, guardrails (PII + SQL injection)
- **Engine** — schema resolver picks the right table(s), PandasAI generates and runs the SQL, Agent handles conversation memory, response cache for repeated queries
- **Output** — formats results for Slack (rich blocks with insights + follow-ups, CSV exports, chart uploads), error suggestions, reaction feedback, query logging

## What was implemented

1. **Intent router** — LLM classifies messages into 4 categories so the bot knows what to do
2. **Compound message decomposer** — LLM splits multi-part requests (e.g. "show me the payments table and get me the amount per month") into separate tasks
3. **Query refiner** — rewrites user questions into PandasAI-friendly prompts before execution. Picks the right chart type, adds explicit aggregations, handles date formatting, and avoids common PandasAI pitfalls
4. **Guardrails** — regex checks for emails, phone numbers, SSNs, credit cards, and SQL injection keywords. Blocks before anything hits the LLM
5. **Schema resolver** — LLM picks which table(s) a question needs. Supports multi-table queries (e.g. "revenue by country" → `payments` + `users`)
6. **PandasAI integration** — translates natural language to SQL, executes against Postgres, returns text/dataframe/chart
7. **Conversation memory** — PandasAI's built-in Agent with `.chat()` / `.follow_up()`. One Agent per thread, so follow-ups like "break that down by month" just work. If you switch topics mid-thread (e.g. payments → users), the Agent detects the dataset change and resets automatically
8. **Table preview** — "show me the payments table" returns first 5 rows + column types
9. **Typing indicator** — posts "Thinking..." that gets replaced with the answer
10. **Chart generation** — detects "plot", "chart", "graph" keywords. The refiner picks the right chart type (line for trends, bar for comparisons) and uses clean matplotlib styling
11. **CSV export** — queries returning >15 rows get a `.csv` file uploaded alongside the truncated preview
12. **Error suggestions** — on failure, an LLM suggests rephrased versions of the question
13. **Response cache** — identical question + dataset pairs cached for 5 minutes
14. **Reaction feedback** — answers prompt for thumbs up/down. Reactions on bot messages get logged to `#bot-logs` with the original answer text
15. **Query logging** — every intent logged to `#bot-logs` — data questions, previews, help, chitchat, guardrail blocks, feedback. Shows who asked, dataset, result type, duration
16. **Welcome message** — bot posts an intro with example questions when it joins a channel
17. **Help command** — lists tables, column descriptions, and suggested questions
18. **Semantic layer** — PandasAI datasets with column descriptions from `01-semantic-layer/sources.yml`
19. **Post-answer insights** — after each answer, an LLM generates a brief interpretation (e.g. "that's a 15% increase from last month") so you get context, not just raw numbers
20. **Follow-up suggestions** — each answer includes 3 short suggested follow-up questions so you always know what to ask next
21. **Rich Slack formatting** — responses use Slack's blocks API: answer in a section block, insight in a context block, follow-ups as bullet points, and a feedback prompt at the bottom

## Setup

```bash
uv venv --python 3.11 .venv
source .venv/bin/activate
uv sync
```

Create a `.env` file:

```bash
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
SLACK_SIGNING_SECRET=your-signing-secret
SLACK_LOG_CHANNEL=C0XXXXXXX  # channel ID for query logs
OPENAI_API_KEY=sk-your-key
DB_HOST=your-db-host
DB_PORT=5432
DB_NAME=your-db-name
DB_USER=your-user
DB_PASS=your-password
```

Create PandasAI datasets (one-time):

```bash
uv run python scripts/create_datasets.py
```

## Run

```bash
uv run python -m slackbot.main
```

## How to test

Once the bot is running, invite it to a channel and try these in order:

**1. Basic data question**
> @bot How many users signed up last month?

Should return a number or short text answer in the thread.

**2. Table preview**
> @bot show me the payments table

Should return first 5 rows with column names and types.

**3. Follow-up in the same thread**
> @bot What's the total revenue by payment method?

Then reply in the same thread:
> break that down by month

Bot should understand the context from the previous question.

**4. Compound message**
> @bot show me the users table and get me the count of users per country

Should handle both — a table preview and a data question — as separate replies in the thread.

**5. Topic switch in same thread**
> @bot What's the total revenue this month?

Then in the same thread:
> How many users signed up per country?

Bot should detect the dataset change (payments → users) and answer correctly instead of getting confused.

**6. Multi-table query**
> @bot Which countries have the highest average payment amount?

Should pull from both `payments` and `users` automatically.

**7. Chart generation**
> @bot plot total revenue per month by payment method

Should upload a line chart image in the thread.

**8. Help**
> @bot help

Lists all tables, columns, and example questions.

**9. Chitchat**
> @bot hey what's up

Friendly redirect pointing to help.

**10. Guardrail — PII**
> @bot how many users have the email test@example.com

Blocks the message and explains why.

**11. Guardrail — SQL injection**
> @bot DROP TABLE users

Blocks the message.

**12. CSV export**
> @bot get me all payments grouped by date and method

If >15 rows, a `.csv` file gets attached alongside the truncated preview.

**13. Reaction feedback**

React with :thumbsup: or :thumbsdown: on any bot answer. Check `#bot-logs` — feedback shows up with the original answer text.

**14. Query logging**

Check `#bot-logs` after any of the above. Every query has a log entry with user, question, dataset, result type, and duration.

**15. Cache**

Ask the exact same question twice within 5 minutes. Second response should be noticeably faster.

## Results

### Data question
![Data question](assets/images/example1.png)

### Follow-up with memory
![Follow-up](assets/images/example2.png)

### Table preview
![Table preview](assets/images/example3.png)

### Help
![Help](assets/images/example4.png)

### Guardrails
![Guardrails](assets/images/example5.png)

### Compound message (multiple requests in one)
![Compound](assets/images/example6.png)

### Chart generation
![Chart](assets/images/example7.png)

### Query logging
![Query log](assets/images/example8.png)

## Project structure

```
06-slackbot/
├── slackbot/
│   ├── main.py              # Entry point, Slack event handlers, full pipeline
│   ├── intake/
│   │   ├── router.py        # Intent classification + message decomposer (OpenAI)
│   │   ├── refiner.py       # Query refiner — rewrites questions for better PandasAI results
│   │   └── guardrails.py    # PII + safety regex checks
│   ├── engine/
│   │   ├── analyst.py       # PandasAI wrapper (query + preview + chart detection)
│   │   ├── resolver.py      # Question → table(s) mapping (OpenAI)
│   │   ├── memory.py        # Thread-based Agent store for conversation memory
│   │   └── cache.py         # In-memory response cache (5 min TTL)
│   └── output/
│       ├── formatter.py     # Slack response formatting (blocks API) + CSV export
│       ├── insights.py      # Post-answer insights + follow-up suggestions (OpenAI)
│       ├── suggestions.py   # LLM-powered error rephrasing suggestions
│       └── logger.py        # Query + feedback logging to Slack channel
├── scripts/
│   └── create_datasets.py   # One-time dataset creation with semantic layer
├── datasets/                 # Auto-generated PandasAI schema configs
├── exports/charts/           # Generated chart images
├── AGENTS.md
├── PROJECT_CONTEXT.md
├── pyproject.toml
└── README.md
```

## Notes

- PandasAI requires Python 3.11 (`pandasai-sql` doesn't support 3.12+)
- `pai.create()` in `create_datasets.py` only needs to run once. After that `pai.load()` picks up saved schemas
- PandasAI v3's `VirtualDataFrame.head()` takes no arguments — don't pass a number
- PandasAI returns `{"type": "dataframe", "value": df}` dicts, not raw DataFrames — `_classify_response()` normalizes this. Chart responses come back as `ChartResponse` objects with `.type = "chart"` (not `"plot"`)
- The query refiner avoids `TO_CHAR` for date grouping (causes parsing issues) and uses `DATE_TRUNC` instead
- Simple queries work reliably. For better results, be explicit about aggregations ("sum", "group by", "count")
- Memory and cache are in-process only (dicts), reset on restart. Fine for MVP
- Bot handles both @mentions in channels and DMs
- For reaction feedback, add `reaction_added` to your Slack app's event subscriptions
