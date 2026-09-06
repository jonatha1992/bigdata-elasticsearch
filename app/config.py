"""Application settings, loaded from the environment and the local .env file."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Runtime configuration.

    Field names map to upper-case environment variables, so ``elastic_password``
    is read from ``ELASTIC_PASSWORD``. The secret itself is never defaulted to a
    real value: an unset password fails fast at startup instead of silently
    sending anonymous requests.
    """

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    elastic_url: str = "http://127.0.0.1:9200"
    elastic_user: str = "elastic"
    elastic_password: str = ""
    elastic_timeout: float = 10.0

    concept_index: str = "clinical-concepts"

    database_url: str = f"sqlite:///{(PROJECT_ROOT / 'curation.db').as_posix()}"

    @property
    def elastic_auth(self) -> tuple[str, str]:
        return self.elastic_user, self.elastic_password


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance so the .env file is read once."""
    return Settings()
