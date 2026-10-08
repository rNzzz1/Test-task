from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = False

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/docsearch"
    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_index: str = "posts"

    auto_seed_on_startup: bool = True
    csv_data_path: str = "posts.csv"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
