"""Application settings, loaded from environment variables / .env."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    database_url: str
    groq_api_key: str
    embedding_model_name: str = "all-MiniLM-L6-v2"
    groq_model_name: str = "openai/gpt-oss-120b"
    gemini_api_key: str | None = None
    gemini_model_name: str = "gemini-3.1-flash-lite"
    llm_provider: str = "groq"


@lru_cache
def get_settings() -> Settings:
    return Settings()
