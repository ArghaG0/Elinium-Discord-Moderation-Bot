"""Guild channel settings. A missing row reads as both channels unset."""

from dataclasses import dataclass

import asyncpg


@dataclass(frozen=True, slots=True)
class GuildSettings:
    guild_id: int
    modlog_channel_id: int | None = None
    confession_channel_id: int | None = None


async def get_settings(pool: asyncpg.Pool, guild_id: int) -> GuildSettings:
    row = await pool.fetchrow(
        "SELECT guild_id, modlog_channel_id, confession_channel_id FROM guild_settings WHERE guild_id = $1",
        guild_id,
    )
    return GuildSettings(**dict(row)) if row else GuildSettings(guild_id)


async def set_modlog_channel(pool: asyncpg.Pool, guild_id: int, channel_id: int | None) -> GuildSettings:
    """Set or clear (None) the modlog channel, preserving the confession channel."""
    row = await pool.fetchrow(
        """INSERT INTO guild_settings (guild_id, modlog_channel_id) VALUES ($1, $2)
           ON CONFLICT (guild_id) DO UPDATE SET modlog_channel_id = EXCLUDED.modlog_channel_id
           RETURNING guild_id, modlog_channel_id, confession_channel_id""",
        guild_id, channel_id,
    )
    return GuildSettings(**dict(row))


async def set_confession_channel(pool: asyncpg.Pool, guild_id: int, channel_id: int | None) -> GuildSettings:
    """Set or clear (None) the confession channel, preserving the modlog channel."""
    row = await pool.fetchrow(
        """INSERT INTO guild_settings (guild_id, confession_channel_id) VALUES ($1, $2)
           ON CONFLICT (guild_id) DO UPDATE SET confession_channel_id = EXCLUDED.confession_channel_id
           RETURNING guild_id, modlog_channel_id, confession_channel_id""",
        guild_id, channel_id,
    )
    return GuildSettings(**dict(row))
