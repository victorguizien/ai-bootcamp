"""One-time script to create PandasAI datasets for all 4 tables.

Run once:
    uv run python scripts/create_datasets.py

After this, pai.load("public/<table>") works at runtime.
"""

import os
import pandasai as pai
from pandasai_litellm.litellm import LiteLLM
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_NAME = os.getenv("DB_NAME")

CONNECTION = {
    "host": DB_HOST,
    "port": DB_PORT,
    "user": DB_USER,
    "password": DB_PASS,
    "database": DB_NAME,
}

TABLES = [
    {
        "path": "public/users",
        "table": "users",
        "description": "Core user registry — one row per registered user with profile attributes. Central dimension table joined by sessions, subscriptions, and payments.",
        "columns": [
            {"name": "user_id", "type": "integer", "description": "Primary key — unique identifier for each registered user"},
            {"name": "signup_date", "type": "datetime", "description": "When the user created their account, used for cohort analysis"},
            {"name": "country", "type": "string", "description": "Geographic region (US, EU, India, Rest) for regional reporting"},
            {"name": "device_type", "type": "string", "description": "Platform registered from (iOS, Android, Web) — acquisition channel indicator"},
        ],
    },
    {
        "path": "public/subscriptions",
        "table": "subscriptions",
        "description": "Tracks subscription lifecycle per user — plan tier, activation/expiration dates, and status. Users may have multiple records over time.",
        "columns": [
            {"name": "subscription_id", "type": "integer", "description": "Primary key — unique identifier for each subscription"},
            {"name": "user_id", "type": "integer", "description": "Foreign key to users table"},
            {"name": "plan", "type": "string", "description": "Subscription tier (free, monthly, annual) — determines pricing and feature access"},
            {"name": "start_date", "type": "datetime", "description": "When the subscription was activated"},
            {"name": "end_date", "type": "datetime", "description": "When the subscription ended — NULL means still active"},
            {"name": "status", "type": "string", "description": "Current state (active, canceled, expired) — used for churn and retention metrics"},
        ],
    },
    {
        "path": "public/payments",
        "table": "payments",
        "description": "Transactional record of every payment collected. Core table for revenue reporting, ARPU, and payment method analytics.",
        "columns": [
            {"name": "payment_id", "type": "integer", "description": "Primary key — unique identifier for each payment"},
            {"name": "subscription_id", "type": "integer", "description": "Foreign key to subscriptions table"},
            {"name": "payment_date", "type": "datetime", "description": "When the payment was processed — used for MRR trending and LTV analysis"},
            {"name": "amount_usd", "type": "float", "description": "Payment amount in USD — atomic unit for revenue aggregations (MRR, ARR, total revenue)"},
            {"name": "method", "type": "string", "description": "Payment method used (card, paypal, apple_pay, google_pay)"},
        ],
    },
    {
        "path": "public/sessions",
        "table": "sessions",
        "description": "Event-level log of user engagement sessions — when, how long, and what content users interacted with. Source for DAU, WAU, MAU metrics.",
        "columns": [
            {"name": "session_id", "type": "integer", "description": "Primary key — unique identifier for each session"},
            {"name": "user_id", "type": "integer", "description": "Foreign key to users table"},
            {"name": "session_date", "type": "datetime", "description": "Date of the session — used for daily engagement aggregation"},
            {"name": "duration_minutes", "type": "float", "description": "Session length in minutes — measures engagement depth"},
            {"name": "activity_type", "type": "string", "description": "Content category consumed (browse, read, listen)"},
        ],
    },
]


def main():
    pai.config.set({"llm": LiteLLM(model="gpt-4.1-mini")})

    for table in TABLES:
        print(f"Creating dataset: {table['path']}...")
        pai.create(
            path=table["path"],
            description=table["description"],
            source={
                "type": "postgres",
                "connection": CONNECTION,
                "table": table["table"],
                "columns": table["columns"],
            },
        )
        print(f"  Done: {table['path']}")

    print("\nAll datasets created. You can now use pai.load('public/<table>').")


if __name__ == "__main__":
    main()
