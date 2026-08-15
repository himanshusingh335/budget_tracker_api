from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openrouter_api_key: str
    openrouter_model: str = "deepseek/deepseek-v4-pro"

    database_url: str = "postgresql://postgres:postgres@localhost:5432/agent_service"
    db_pool_min_size: int = 1
    db_pool_max_size: int = 5

    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False

    summarization_keep_messages: int = 20

    log_level: str = "INFO"
    log_dir: str = "logs"
    log_file: str = "app.log"
    log_retention_days: int = 30

    mcp_config_path: str = "mcp_servers.json"


settings = Settings()
