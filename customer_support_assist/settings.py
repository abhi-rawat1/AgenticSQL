import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    def __init__(self, env_name: str | None = None):
        current_env = env_name or os.getenv("APP_ENV", "dev")
        env_file = BASE_DIR / f".{current_env}.env"
        if env_file.exists():
            load_dotenv(env_file, override=True)

        self.app_env = current_env
        self.postgres_url = os.getenv("POSTGRES_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/postgres")
        self.db_schema = os.getenv("DB_SCHEMA", "ecommerce")
        self.model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.allowed_tables = tuple(
            table.strip()
            for table in os.getenv(
                "ALLOWED_TABLES",
                "customers,orders,order_items,products,returns,refunds,inventory,shipments",
            ).split(",")
            if table.strip()
        )
        self.approval_required_actions = tuple(
            action.strip()
            for action in os.getenv(
                "APPROVAL_REQUIRED_ACTIONS",
                "refund_order,create_return,cancel_order,update_inventory",
            ).split(",")
            if action.strip()
        )
        self.log_dir = os.getenv("LOG_DIR", "logs")
        self.api_host = os.getenv("API_HOST", "0.0.0.0")
        self.api_port = int(os.getenv("API_PORT", "8000"))
        self.streamlit_port = int(os.getenv("STREAMLIT_PORT", "8501"))


settings = Settings()
