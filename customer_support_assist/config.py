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
        action.strip() for action in os.getenv("APPROVAL_REQUIRED_ACTIONS", "refund_order,initiate_refund,create_return,initiate_return,cancel_order,cancel_item,update_inventory").split(",") if action.strip()
    )
    log_dir: str = os.getenv("LOG_DIR", "logs")
    langfuse_public_key: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    langfuse_secret_key: str = os.getenv("LANGFUSE_SECRET_KEY", "")
    langfuse_host: str = os.getenv("LANGFUSE_BASE_URL") or os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    app_env: str = os.getenv("APP_ENV", "development")
    app_version: str = os.getenv("APP_VERSION", "0.1.0")
    langgraph_checkpoint_store: str = os.getenv("LANGGRAPH_CHECKPOINT_STORE", "memory")


settings = Settings()
