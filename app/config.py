"""Central application configuration.

All settings are externally configurable via environment variables (see
.env.example). No secrets or machine-specific paths are hard-coded.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", protected_namespaces=())

    app_env: str = "development"

    # Persistence
    database_url: str = "sqlite:///./data/flashcards.db"

    # Local, OpenAI-compatible inference server (e.g. Ollama, llama.cpp server, LM Studio)
    model_base_url: str = "http://host.docker.internal:11434/v1"
    model_name: str = "gemma3n:e4b"
    model_api_key: str = "not-needed"
    model_timeout_seconds: float = 30.0
    model_max_retries: int = 1

    # Flashcard generation / non-AI logic parameters
    max_cards_per_chunk: int = 3
    chunk_max_chars: int = 1200
    duplicate_similarity_threshold: float = 0.85


@lru_cache
def get_settings() -> Settings:
    return Settings()
