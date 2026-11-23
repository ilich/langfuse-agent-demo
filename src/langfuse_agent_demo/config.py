"""Application settings, loaded from environment variables and the ``.env`` file.

Copy ``.env.example`` to ``.env`` and adjust the values. Real environment variables take
precedence over ``.env``.
"""

from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # env_ignore_empty: "GEMINI_API_KEY=" (as shipped in .env.example) means unset, not "".
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", env_ignore_empty=True
    )

    # Path to the Northwind SQLite database; relative paths resolve against the working directory.
    northwind_db_path: Path
    # Refund policy the refund agent reads on every request.
    refund_policy_path: Path = Path("docs/refund-policy.md")
    # The crew's "today"; the real date when unset.
    current_date: date | None = None
    # CrewAI model name for all agents.
    llm_model: str = "gemini/gemini-2.5-flash"
    # Needed only to run the crew, not at startup.
    gemini_api_key: SecretStr | None = None
    # Print each agent step, delegation and tool call to the console while the crew runs.
    crew_verbose: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_today() -> date:
    """The crew's notion of today: the ``CURRENT_DATE`` setting, or the real date."""
    return get_settings().current_date or date.today()
