import os
from pathlib import Path

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DB_URL = os.getenv("POSTGRES_URL")
DB_SCHEMA = os.getenv("DB_SCHEMA", "ecommerce")

if not DB_URL:
    raise ValueError("POSTGRES_URL is not set. Add it to the .env file.")

engine = create_engine(DB_URL, future=True)

SQL_PATH = Path(__file__).resolve().parents[1] / "sql" / "seed_ecommerce_large.sql"


def ensure_schema_and_seed():
    script = SQL_PATH.read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS ecommerce;"))
        conn.execute(text(script))
    print(f"Schema and seed data loaded into PostgreSQL schema '{DB_SCHEMA}' successfully.")


if __name__ == "__main__":
    ensure_schema_and_seed()
