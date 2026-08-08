from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"

    database_url: str = "postgresql://postgres:postgres@localhost:5432/agent_service"

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
