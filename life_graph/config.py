"""Application configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Life Graph application settings.

    All settings can be overridden via environment variables
    prefixed with LIFE_GRAPH_ (e.g., LIFE_GRAPH_DATABASE_URL).
    """

    # Application
    app_name: str = "Life Graph"
    debug: bool = False
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql+asyncpg://life_graph:life_graph@localhost:5432/life_graph"
    database_url_sync: str = "postgresql://life_graph:life_graph@localhost:5432/life_graph"
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Embeddings
    embedding_model: str = "all-mpnet-base-v2"
    embedding_dimension: int = 768

    # LLM (via LiteLLM)
    llm_model_cheap: str = "gemini/gemini-2.0-flash"
    llm_model_expensive: str = "gemini/gemini-2.5-pro"
    llm_daily_budget_usd: float = 1.0

    # Proactive Recall
    recall_max_session_start: int = 5
    recall_max_during_session: int = 2
    recall_cooldown_days: int = 7
    recall_confidence_threshold: float = 0.7

    # Decay
    decay_archive_threshold: float = 0.01
    decay_default_lambda: float = 0.1

    # Cold Start
    cold_start_min_memories: int = 50

    # Multi-Modal (Voice / Whisper)
    whisper_model: str = "small"

    # MinIO / Object Storage
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "life-graph"

    model_config = {"env_prefix": "LIFE_GRAPH_"}


settings = Settings()
