"""Application settings, loaded from environment variables and the ``.env`` file.

Copy ``.env.example`` to ``.env`` and adjust the values. Real environment variables take
precedence over ``.env``.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Path to the Northwind SQLite database; relative paths resolve against the working directory.
    northwind_db_path: Path


@lru_cache
def get_settings() -> Settings:
    return Settings()
