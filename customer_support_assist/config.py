import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    postgres_url: str = os.getenv("POSTGRES_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/postgres")
    db_schema: str = os.getenv("DB_SCHEMA", "ecommerce")
    model_name: str = os.getenv("MODEL_NAME", "gpt-4o-mini")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    allowed_tables: tuple[str, ...] = tuple(
        table.strip() for table in os.getenv("ALLOWED_TABLES", "customers,orders,order_items,products,returns,refunds,inventory,shipments").split(",") if table.strip()
    )
    approval_required_actions: tuple[str, ...] = tuple(
        action.strip() for action in os.getenv("APPROVAL_REQUIRED_ACTIONS", "refund_order,create_return,cancel_order,update_inventory").split(",") if action.strip()
    )
    log_dir: str = os.getenv("LOG_DIR", "logs")


settings = Settings()
print(f"Loaded settings ****** : {settings}")
