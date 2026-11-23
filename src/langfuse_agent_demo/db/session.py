"""Engine and session factory for the Northwind SQLite database.

The database path comes from the ``NORTHWIND_DB_PATH`` setting (see ``.env.example``).
"""

from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from ..config import get_settings


def get_db_path() -> Path:
    return get_settings().northwind_db_path


@lru_cache
def get_engine() -> Engine:
    # mode=ro: the app never writes, and a missing file fails instead of creating an empty one.
    return create_engine(f"sqlite:///file:{get_db_path()}?mode=ro&uri=true")


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine())
