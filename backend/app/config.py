"""
Centralized application configuration.

Everything an evaluator needs to change (model provider, DB, retrieval knobs)
lives here and is driven entirely by environment variables so the app can be
reconfigured without touching code, per the "flexible LLM configuration"
requirement.
"""
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App ---
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"

    # --- Database ---
    database_url: str = "postgresql+asyncpg://postgres:password123@localhost:5432/lenny_assistant"

    # --- LLM provider toggle ---
    default_llm_provider: Literal["ollama", "anthropic"] = "ollama"

    # --- Ollama ---
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "llama3.2:3b"
    ollama_embed_model: str = "nomic-embed-text"

    # --- Anthropic ---
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-20241022"

    # --- Retrieval ---
    retrieval_top_k: int = 5
    retrieval_similarity_threshold: float = 0.35
    chunk_token_size: int = 650
    chunk_token_overlap: int = 100

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def anthropic_configured(self) -> bool:
        return bool(self.anthropic_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
