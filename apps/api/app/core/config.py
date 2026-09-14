from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
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

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
