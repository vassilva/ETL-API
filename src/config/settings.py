"""
Centralized configuration.

This is the only module that reads environment variables (and the local .env
file). Everything else receives configuration through get_settings().

Database settings are validated only when a connection is requested, so
offline tests never need credentials.
"""

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

DEFAULT_API_BASE_URL = "https://dummyjson.com"
DEFAULT_API_TIMEOUT_SECONDS = 30.0
DEFAULT_DB_CONNECT_TIMEOUT_SECONDS = 10

REQUIRED_DB_VARIABLES = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")


class ConfigurationError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class DatabaseSettings:
    # Connection details are excluded from repr so they never reach logs,
    # tracebacks or test reports.
    host: str = field(repr=False)
    port: str = field(repr=False)
    name: str = field(repr=False)
    user: str = field(repr=False)
    password: str = field(repr=False)
    connect_timeout: int = DEFAULT_DB_CONNECT_TIMEOUT_SECONDS


@dataclass(frozen=True)
class Settings:
    api_base_url: str
    api_timeout: float
    db_connect_timeout: int

    def database(self):
        """Return validated database settings (reads credentials lazily)."""
        missing = [
            name for name in REQUIRED_DB_VARIABLES
            if os.environ.get(name) in (None, "")
        ]

        if missing:
            raise ConfigurationError(
                "Missing database configuration: " + ", ".join(missing)
            )

        return DatabaseSettings(
            host=os.environ["DB_HOST"],
            port=os.environ["DB_PORT"],
            name=os.environ["DB_NAME"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            connect_timeout=self.db_connect_timeout
        )


def _number_from_env(name, default, cast):
    value = os.environ.get(name)

    if value in (None, ""):
        return default

    try:
        return cast(value)
    except ValueError:
        raise ConfigurationError(f"{name} must be a number") from None


@lru_cache(maxsize=1)
def get_settings():
    # Existing environment variables (e.g. injected by Jenkins) take
    # precedence over the local .env file.
    load_dotenv(PROJECT_ROOT / ".env", override=False)

    return Settings(
        api_base_url=os.environ.get("API_BASE_URL") or DEFAULT_API_BASE_URL,
        api_timeout=_number_from_env(
            "API_TIMEOUT_SECONDS", DEFAULT_API_TIMEOUT_SECONDS, float
        ),
        db_connect_timeout=_number_from_env(
            "DB_CONNECT_TIMEOUT_SECONDS", DEFAULT_DB_CONNECT_TIMEOUT_SECONDS, int
        )
    )
