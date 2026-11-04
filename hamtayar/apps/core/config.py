"""Validated application settings; no clients or I/O are created here."""

from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from packages.knowledge.configuration import KnowledgeConfiguration


class Settings(BaseSettings):
    """Read HAMTAYAR_* settings from the environment or a local .env file."""

    model_config = SettingsConfigDict(
        env_prefix="HAMTAYAR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Hamtayar"
    environment: Literal["local", "test", "staging", "production"] = "local"
    debug: bool = False

    # Optional until the corresponding real adapters are registered.
    padin_base_url: AnyHttpUrl | None = None
    qdrant_url: AnyHttpUrl | None = None
    embedding_base_url: AnyHttpUrl | None = None
    reranker_base_url: AnyHttpUrl | None = None
    llm_base_url: AnyHttpUrl | None = None

    llm_model: str | None = None
    embedding_model: str | None = None
    reranker_model: str | None = None
    knowledge_config_path: Path = Path("config/knowledge.toml")

    request_timeout_seconds: float = Field(default=30.0, gt=0, le=600)
    llm_timeout_seconds: float = Field(default=120.0, gt=0, le=600)
    temp_dir: Path = Path(".runtime/tmp")
    max_upload_size_bytes: int = Field(default=20 * 1024 * 1024, gt=0)


def get_settings() -> Settings:
    """Load settings on demand, so tests can replace the environment safely."""
    return Settings()


def load_knowledge_settings(settings: Settings) -> KnowledgeConfiguration:
    """Load Knowledge settings at composition time using existing app overrides."""
    from packages.knowledge.configuration import load_knowledge_configuration

    overrides = None
    if settings.embedding_model is not None:
        overrides = {"embedding": {"model_id": settings.embedding_model}}
    return load_knowledge_configuration(
        settings.knowledge_config_path, overrides=overrides
    )
