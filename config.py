"""Load and validate startup configuration without reading secrets on import."""

from collections.abc import Mapping
from dataclasses import dataclass, field
import logging
import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv


class ConfigError(ValueError):
    """A missing or invalid startup setting (messages never include its value)."""


@dataclass(frozen=True, slots=True)
class Config:
    discord_token: str = field(repr=False)
    database_url: str = field(repr=False)
    bot_owner_id: int | None = None
    log_level: int = logging.INFO


def load_config(environ: Mapping[str, str] | None = None) -> Config:
    """Read the root .env only at startup; existing environment values win.

    An explicit mapping bypasses dotenv and process environment access for tests.
    """
    if environ is None:
        load_dotenv(Path(__file__).resolve().parent / ".env", override=False)
        environ = os.environ

    token = environ.get("DISCORD_TOKEN", "").strip()
    database_url = environ.get("DATABASE_URL", "").strip()
    if not token:
        raise ConfigError("DISCORD_TOKEN is required.")
    if not database_url:
        raise ConfigError("DATABASE_URL is required.")
    # Preserve support for connection strings supplied with surrounding quotes.
    if database_url[:1] in ("'", '"') and database_url[-1:] == database_url[:1]:
        database_url = database_url[1:-1]
    try:
        parsed = urlsplit(database_url)
        valid_url = (
            parsed.scheme in ("postgres", "postgresql")
            and parsed.hostname and parsed.path.strip("/")
            and not parsed.fragment
        )
        parsed.port  # Validate the port without ever reporting the URL itself.
    except ValueError:
        valid_url = False
    if not valid_url:
        raise ConfigError("DATABASE_URL must be a PostgreSQL URL with a host and database name.")

    owner_text = environ.get("BOT_OWNER_ID", "").strip()
    owner_id = None
    if owner_text:
        try:
            owner_id = int(owner_text)
        except ValueError:
            raise ConfigError("BOT_OWNER_ID must be a positive integer, or omitted.") from None
        if not 0 < owner_id < 2**63:
            raise ConfigError("BOT_OWNER_ID must be a positive BIGINT, or omitted.")

    level_name = environ.get("LOG_LEVEL", "INFO").strip().upper()
    levels = {name: getattr(logging, name) for name in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")}
    if level_name not in levels:
        raise ConfigError("LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL.")
    return Config(token, database_url, owner_id, levels[level_name])
