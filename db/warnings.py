"""Guild/user-scoped warnings, ordered by increasing database ID.

All mutations serialize per guild/user using a transaction advisory lock. This
keeps selection and deletion atomic across helper callers, including concurrent
inserts. External SQL writers must follow the same locking protocol to share
that guarantee. Reads return committed snapshots, not locks across Discord I/O.
"""

from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
import hashlib
from typing import AsyncIterator

import asyncpg


@dataclass(frozen=True, slots=True)
class Warning:
    id: int
    guild_id: int
    user_id: int
    moderator_id: int
    reason: str | None
    timestamp: datetime | None


@asynccontextmanager
async def _mutation(pool: asyncpg.Pool, guild_id: int, user_id: int) -> AsyncIterator[asyncpg.Connection]:
    key = f"elinium:warnings:{guild_id}:{user_id}".encode("ascii")
    lock_id = int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "big", signed=True)
    async with pool.acquire() as conn:
        async with conn.transaction(isolation="read_committed"):
            await conn.execute("SELECT pg_advisory_xact_lock($1::bigint)", lock_id)
            yield conn


async def add_warning(
    pool: asyncpg.Pool, guild_id: int, user_id: int, moderator_id: int,
    reason: str | None = "No reason provided.",
) -> Warning:
    """Insert one warning with the database timestamp; return its complete row."""
    async with _mutation(pool, guild_id, user_id) as conn:
        row = await conn.fetchrow(
            """INSERT INTO warnings (guild_id, user_id, moderator_id, reason)
               VALUES ($1, $2, $3, $4) RETURNING *""",
            guild_id, user_id, moderator_id, reason,
        )
    return Warning(**dict(row))


async def get_warnings(pool: asyncpg.Pool, guild_id: int, user_id: int) -> list[Warning]:
    """Return oldest-first rows (ID order); an absent history returns []."""
    rows = await pool.fetch(
        "SELECT * FROM warnings WHERE guild_id = $1 AND user_id = $2 ORDER BY id",
        guild_id, user_id,
    )
    return [Warning(**dict(row)) for row in rows]


async def count_warnings(pool: asyncpg.Pool, guild_id: int, user_id: int) -> int:
    return await pool.fetchval(
        "SELECT COUNT(*) FROM warnings WHERE guild_id = $1 AND user_id = $2", guild_id, user_id,
    )


async def delete_warning(pool: asyncpg.Pool, guild_id: int, user_id: int, warning_id: int) -> Warning | None:
    """Delete by database ID, never by displayed number; None if not in scope."""
    async with _mutation(pool, guild_id, user_id) as conn:
        row = await conn.fetchrow(
            "DELETE FROM warnings WHERE guild_id = $1 AND user_id = $2 AND id = $3 RETURNING *",
            guild_id, user_id, warning_id,
        )
    return Warning(**dict(row)) if row else None


async def clear_warnings(
    pool: asyncpg.Pool, guild_id: int, user_id: int, num_or_index: int | None = None,
) -> list[Warning]:
    """Delete all (None), a 1-based display index (>0), or the latest N (<0).

    Return the removed rows in oldest-first order for accurate logging. Zero is
    invalid; an out-of-range index/count raises IndexError without deleting any
    rows. Clearing all of an empty history returns []. Numbering is evaluated at
    mutation time, so callers needing stable identity should use delete_warning.
    """
    if num_or_index is not None:
        if type(num_or_index) is not int:
            raise TypeError("Warning index/count must be an integer or None.")
        if num_or_index == 0:
            raise ValueError("Warning index/count cannot be zero.")
    async with _mutation(pool, guild_id, user_id) as conn:
        rows = await conn.fetch(
            "SELECT * FROM warnings WHERE guild_id = $1 AND user_id = $2 ORDER BY id FOR UPDATE",
            guild_id, user_id,
        )
        if num_or_index is None:
            selected = rows
        elif abs(num_or_index) > len(rows):
            raise IndexError("Warning index/count exceeds the current history.")
        elif num_or_index > 0:
            selected = [rows[num_or_index - 1]]
        else:
            selected = rows[num_or_index:]
        if selected:
            await conn.execute(
                "DELETE FROM warnings WHERE guild_id = $1 AND user_id = $2 AND id = ANY($3::integer[])",
                guild_id, user_id, [row["id"] for row in selected],
            )
    return [Warning(**dict(row)) for row in selected]
