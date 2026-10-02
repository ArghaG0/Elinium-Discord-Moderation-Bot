"""Normalized blacklist entries and a snapshot for the future AutoMod cache."""

from typing import Literal, TypedDict

import asyncpg


class GuildBlacklist(TypedDict):
    blacklisted_words: list[str]
    blacklisted_links: list[str]


def _normalize(value: str) -> str:
    """Normalize a single entry; command-level splitting stays with the caller."""
    if not isinstance(value, str):
        raise TypeError("Blacklist entries must be strings.")
    value = value.strip().lower()
    if not value or len(value) > 255 or "\x00" in value:
        raise ValueError("Blacklist entries must contain 1-255 characters and no NUL.")
    return value


async def _change(
    pool: asyncpg.Pool, guild_id: int, value: str,
    kind: Literal["word", "link"], *, remove: bool = False,
) -> bool:
    value = _normalize(value)
    # Identifiers are selected internally, never interpolated from user input.
    table, column = {"word": ("blacklisted_words", "word"), "link": ("blacklisted_links", "link")}[kind]
    if remove:
        query = f"DELETE FROM {table} WHERE guild_id = $1 AND {column} = $2 RETURNING id"
    else:
        query = (
            f"INSERT INTO {table} (guild_id, {column}) VALUES ($1, $2) "
            f"ON CONFLICT (guild_id, {column}) DO NOTHING RETURNING id"
        )
    return await pool.fetchval(query, guild_id, value) is not None


async def add_word(pool: asyncpg.Pool, guild_id: int, word: str) -> bool:
    """Return True if inserted; False for an existing normalized word."""
    return await _change(pool, guild_id, word, "word")


async def remove_word(pool: asyncpg.Pool, guild_id: int, word: str) -> bool:
    """Return True if removed; False if absent."""
    return await _change(pool, guild_id, word, "word", remove=True)


async def add_link(pool: asyncpg.Pool, guild_id: int, link: str) -> bool:
    """Return True if inserted; False for an existing normalized link."""
    return await _change(pool, guild_id, link, "link")


async def remove_link(pool: asyncpg.Pool, guild_id: int, link: str) -> bool:
    """Return True if removed; False if absent."""
    return await _change(pool, guild_id, link, "link", remove=True)


async def get_words(pool: asyncpg.Pool, guild_id: int) -> list[str]:
    """Return normalized words in insertion order; [] for an absent list."""
    rows = await pool.fetch("SELECT word FROM blacklisted_words WHERE guild_id = $1 ORDER BY id", guild_id)
    return [row["word"] for row in rows]


async def get_links(pool: asyncpg.Pool, guild_id: int) -> list[str]:
    """Return normalized links in insertion order; [] for an absent list."""
    rows = await pool.fetch("SELECT link FROM blacklisted_links WHERE guild_id = $1 ORDER BY id", guild_id)
    return [row["link"] for row in rows]


async def get_all_blacklists(pool: asyncpg.Pool) -> dict[int, GuildBlacklist]:
    """One committed snapshot, keyed by integer guild ID; empty guilds omitted.

    This is cache-loading data only. This phase does not install a live cache.
    """
    rows = await pool.fetch(
        """SELECT guild_id, 'blacklisted_words' AS kind, word AS value, id FROM blacklisted_words
           UNION ALL
           SELECT guild_id, 'blacklisted_links' AS kind, link AS value, id FROM blacklisted_links
           ORDER BY guild_id, kind, id"""
    )
    result: dict[int, GuildBlacklist] = {}
    for row in rows:
        entries = result.setdefault(row["guild_id"], {"blacklisted_words": [], "blacklisted_links": []})
        entries[row["kind"]].append(row["value"])
    return result
