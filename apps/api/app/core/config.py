from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "PALS API"
    database_url: str = "postgresql+asyncpg://pals:pals@localhost:5432/pals"
    database_connect_timeout_seconds: float = Field(default=3.0, gt=0)
    cors_origins: str = "http://localhost:3000"
    ai_provider: str = "openai"
    ai_model: str = "gpt-5-mini"
    ai_api_key: SecretStr | None = None
    ai_timeout_seconds: float = Field(default=20.0, gt=0)
    document_storage_root: Path = Path("./data/documents")
    document_max_size_bytes: int = Field(default=25 * 1024 * 1024, gt=0)
    rag_chunk_target_tokens: int = Field(default=800, gt=0)
    rag_chunk_overlap_tokens: int = Field(default=120, ge=0)
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    embedding_batch_size: int = Field(default=64, gt=0)
    retrieval_top_k: int = Field(default=8, gt=0, le=50)
    retrieval_max_limit: int = Field(default=50, gt=0, le=50)
    retrieval_min_relevance: float = Field(default=0.0, ge=-1.0, le=1.0)

    @model_validator(mode="after")
    def validate_chunk_configuration(self) -> Settings:
        if self.rag_chunk_overlap_tokens >= self.rag_chunk_target_tokens:
            raise ValueError("RAG chunk overlap must be smaller than the target")
        self.embedding_provider = self.embedding_provider.strip().lower()
        if self.embedding_provider not in {"openai", "fake"}:
            raise ValueError("Embedding provider must be 'openai' or 'fake'")
        self.embedding_model = self.embedding_model.strip()
        if not self.embedding_model:
            raise ValueError("Embedding model must not be empty")
        if self.embedding_dimensions != 1536:
            raise ValueError("Embedding dimensions must be 1536 for the current schema")
        if self.retrieval_top_k > self.retrieval_max_limit:
            raise ValueError("Retrieval top-k must not exceed the maximum limit")
        return self

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
