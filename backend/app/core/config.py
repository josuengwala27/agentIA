from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://agent:agent@localhost:5433/agent_formation"
    secret_key: str = "dev-secret-key-change-in-production"
    cors_origins: str = "http://localhost:3000"
    ollama_base_url: str = "http://localhost:11434"
    ollama_llm_model: str = "llama3.2"
    ollama_embed_model: str = "nomic-embed-text"
    embedding_dim: int = 768
    chunk_size: int = 800
    chunk_overlap: int = 120
    upload_dir: str = "uploads"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    algorithm: str = "HS256"
    skip_db_init: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
