"""Settings command flows with mocked Discord I/O and database helpers."""

from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import discord

from cogs.moderation import Moderation
from db.settings import GuildSettings
from utils import send_modlog_embed


def make_cog(pool):
    bot = SimpleNamespace(
        db_pool=pool,
        EMOJIS={key: key for key in ("HEART", "SPARKLE", "RIBBON", "ERROR")},
        user=SimpleNamespace(id=99, name="Elinium", mention="<@99>", avatar=None),
    )
    return Moderation(bot)


def make_channel(channel_id):
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = channel_id
    channel.name = f"channel-{channel_id}"
    channel.mention = f"<#{channel_id}>"
    channel.send = AsyncMock()
    return channel


def make_interaction(guild_id=1, channels=None):
    channels = channels or {}
    return SimpleNamespace(
        guild=SimpleNamespace(id=guild_id, name=f"guild-{guild_id}", get_channel=channels.get),
        user=SimpleNamespace(id=10, name="Member", mention="<@10>", avatar=None),
        response=SimpleNamespace(defer=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
    )


class SettingsFlowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.pool = object()
        self.cog = make_cog(self.pool)

    def test_constructor_has_no_obsolete_settings_state(self):
        self.assertFalse(hasattr(self.cog, "all_modlog_settings"))
        self.assertFalse(hasattr(self.cog, "confession_channels_data"))

    async def test_modlog_command_writes_integer_ids_before_success(self):
        channel = make_channel(100)
        interaction = make_interaction()
        ctx = SimpleNamespace(guild=interaction.guild, author=interaction.user, send=AsyncMock())
        with patch("cogs.moderation.db_settings.set_modlog_channel", new_callable=AsyncMock) as setter:
            await self.cog.set_modlog_channel.callback(self.cog, ctx, channel)
            setter.assert_awaited_once_with(self.pool, 1, 100)
            self.assertIn(channel.mention, ctx.send.call_args.kwargs["embed"].description)
            ctx.send.reset_mock()
            setter.side_effect = ConnectionError("offline")
            with self.assertRaises(ConnectionError):
                await self.cog.set_modlog_channel.callback(self.cog, ctx, channel)
            ctx.send.assert_not_awaited()

    async def test_modlog_uses_current_database_channel(self):
        old, new = make_channel(100), make_channel(200)
        interaction = make_interaction(channels={100: old, 200: new})
        with patch("utils.db_settings.get_settings", new=AsyncMock(side_effect=[GuildSettings(1, 100), GuildSettings(1, 200)])) as getter:
            for _ in range(2):
                await send_modlog_embed(self.cog.bot, interaction.guild, "Warn", interaction.user, self.cog.bot.user, "reason", warning_count=1)
        self.assertEqual(getter.await_count, 2)
        old.send.assert_awaited_once()
        new.send.assert_awaited_once()
        self.assertIn("**Warning Count:** 1", new.send.call_args.kwargs["embed"].description)

    async def test_modlog_missing_or_unavailable_settings_do_not_break_action(self):
        interaction = make_interaction()
        for result in (GuildSettings(1), GuildSettings(1, 999), ConnectionError("offline")):
            with self.subTest(result=type(result).__name__):
                getter = AsyncMock(side_effect=result) if isinstance(result, Exception) else AsyncMock(return_value=result)
                with patch("utils.db_settings.get_settings", new=getter), patch("utils.log.exception") as error_log:
                    await send_modlog_embed(self.cog.bot, interaction.guild, "Warn", interaction.user, self.cog.bot.user, "reason")
                    self.assertEqual(error_log.called, isinstance(result, Exception))

    async def test_confession_setter_defers_then_saves_and_logs(self):
        interaction = make_interaction()
        channel = make_channel(200)
        with patch("cogs.moderation.db_settings.set_confession_channel", new_callable=AsyncMock) as setter, \
                patch("cogs.moderation.send_modlog_embed", new_callable=AsyncMock) as log:
            async def save(*args):
                interaction.response.defer.assert_awaited_once_with(ephemeral=True)
                interaction.followup.send.assert_not_awaited()
            setter.side_effect = save
            await self.cog.set_confession_channel.callback(self.cog, interaction, channel)
        setter.assert_awaited_once_with(self.pool, 1, 200)
        interaction.followup.send.assert_awaited_once()
        log.assert_awaited_once()

    async def test_failed_confession_setting_does_not_report_success_or_log(self):
        interaction = make_interaction()
        with patch("cogs.moderation.db_settings.set_confession_channel", new=AsyncMock(side_effect=ConnectionError("private detail"))), \
                patch("cogs.moderation.send_modlog_embed", new_callable=AsyncMock) as log, \
                patch("cogs.moderation.log.exception"):
            await self.cog.set_confession_channel.callback(self.cog, interaction, make_channel(200))
        log.assert_not_awaited()
        self.assertIn("couldn't save", interaction.followup.send.call_args.args[0])
        self.assertNotIn("private detail", interaction.followup.send.call_args.args[0])
        self.assertTrue(interaction.followup.send.call_args.kwargs["ephemeral"])

    async def test_confess_unconfigured_or_failed_lookup_does_not_send_or_clear(self):
        channel = make_channel(200)
        for result in (GuildSettings(1), ConnectionError("offline")):
            interaction = make_interaction(channels={200: channel})
            getter = AsyncMock(side_effect=result) if isinstance(result, Exception) else AsyncMock(return_value=result)
            with patch("cogs.moderation.db_settings.get_settings", new=getter), \
                    patch("cogs.moderation.db_settings.set_confession_channel", new_callable=AsyncMock) as setter, \
                    patch("cogs.moderation.log.exception"):
                await self.cog.confess.callback(self.cog, interaction, "test")
            setter.assert_not_awaited()
            channel.send.assert_not_awaited()
            self.assertTrue(interaction.followup.send.call_args.kwargs["ephemeral"])

    async def test_invalid_confession_channel_clears_only_confession_setting(self):
        for invalid_channel in (None, SimpleNamespace(id=200)):
            interaction = make_interaction(channels={200: invalid_channel})
            with patch("cogs.moderation.db_settings.get_settings", new=AsyncMock(return_value=GuildSettings(1, 100, 200))), \
                    patch("cogs.moderation.db_settings.set_confession_channel", new_callable=AsyncMock) as setter:
                await self.cog.confess.callback(self.cog, interaction, "test")
            setter.assert_awaited_once_with(self.pool, 1, None)
            self.assertIn("no longer exists", interaction.followup.send.call_args.args[0])

    async def test_failed_invalid_channel_cleanup_reports_database_failure(self):
        interaction = make_interaction()
        with patch("cogs.moderation.db_settings.get_settings", new=AsyncMock(return_value=GuildSettings(1, 100, 200))), \
                patch("cogs.moderation.db_settings.set_confession_channel", new=AsyncMock(side_effect=ConnectionError("offline"))), \
                patch("cogs.moderation.log.exception"):
            await self.cog.confess.callback(self.cog, interaction, "test")
        self.assertIn("couldn't update", interaction.followup.send.call_args.args[0])
        self.assertTrue(interaction.followup.send.call_args.kwargs["ephemeral"])

    async def test_confess_fetches_settings_on_each_request(self):
        first, second = make_channel(200), make_channel(300)
        interaction = make_interaction(channels={200: first, 300: second})
        with patch("cogs.moderation.db_settings.get_settings", new=AsyncMock(side_effect=[GuildSettings(1, None, 200), GuildSettings(1, None, 300)])) as getter, \
                patch("cogs.moderation.send_modlog_embed", new_callable=AsyncMock), patch("builtins.print"):
            for text in ("first", "second"):
                await self.cog.confess.callback(self.cog, interaction, text)
        self.assertEqual(getter.await_count, 2)
        self.assertEqual(first.send.call_args.kwargs["embed"].description, "first")
        self.assertEqual(second.send.call_args.kwargs["embed"].description, "second")
