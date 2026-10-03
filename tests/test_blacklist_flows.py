"""Blacklist command/cache checks without live Discord access."""
import asyncio
from contextlib import ExitStack
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import discord
from discord.ext import commands
from cogs.moderation import Moderation
from test_settings_flows import make_cog, make_interaction


def blacklist_cog(pool):
    cog = make_cog(pool)
    cog.bot.command_prefix = "eli "
    cog.bot.EMOJIS["BUTTERFLY"] = "BUTTERFLY"
    return cog


def blacklist_context(guild_id=1):
    interaction = make_interaction(guild_id)
    return SimpleNamespace(guild=interaction.guild, author=interaction.user, send=AsyncMock())


def message(content, guild_id=1, *, bot=False):
    return SimpleNamespace(content=content, guild=SimpleNamespace(id=guild_id) if guild_id else None,
        author=SimpleNamespace(bot=bot, name="Member", mention="<@1>"), delete=AsyncMock(),
        channel=SimpleNamespace(name="channel", send=AsyncMock()))


class BlacklistFlowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch("cogs.moderation.log.exception"))
        self.modlog = self.stack.enter_context(patch("cogs.moderation.send_modlog_embed", new_callable=AsyncMock))
        self.pool = object()
        self.cog = blacklist_cog(self.pool)
        self.ctx = blacklist_context()

    async def test_load_precedes_registration_and_failure_prevents_registration(self):
        bot = commands.Bot(command_prefix="eli ", intents=discord.Intents.none())
        bot.db_pool = self.pool
        self.addAsyncCleanup(bot.close)
        cog = Moderation(bot)
        async def load(_):
            self.assertIsNone(bot.get_command("blacklist"))
            self.assertNotIn(cog.on_message, bot.extra_events.get("on_message", []))
            return {1: {"blacklisted_words": ["blocked"], "blacklisted_links": []}}
        with patch("cogs.moderation.db_blacklists.get_all_blacklists", new=AsyncMock(side_effect=load)):
            await bot.add_cog(cog)
        self.assertEqual(cog._get_guild_blacklists(1)["blacklisted_words"], ["blocked"])
        await bot.remove_cog("Moderation")
        with patch("cogs.moderation.db_blacklists.get_all_blacklists", new=AsyncMock(side_effect=ConnectionError())):
            with self.assertRaises(ConnectionError):
                await bot.add_cog(Moderation(bot))
        self.assertIsNone(bot.get_command("blacklist"))
        self.assertIsNone(bot.get_cog("Moderation"))

    async def test_normalization_duplicates_and_cache_changes_for_both_types(self):
        for kind in ("word", "link"):
            key = f"blacklisted_{kind}s"
            async def add(pool, guild, entry):
                self.assertEqual((pool, guild), (self.pool, 1))
                return entry not in self.cog._get_guild_blacklists(1)[key]
            with patch(f"cogs.moderation.db_blacklists.add_{kind}", new=AsyncMock(side_effect=add)) as setter:
                await getattr(self.cog, f"blacklist_add{kind}").callback(self.cog, self.ctx, " A,b ", "A")
            self.assertEqual([call.args[2] for call in setter.await_args_list], ["a", "b", "a"])
            self.assertEqual(self.cog._get_guild_blacklists(1)[key], ["a", "b"])
            self.assertEqual(self.cog._get_guild_blacklists(2)[key], [])
            with patch(f"cogs.moderation.db_blacklists.remove_{kind}", new=AsyncMock(return_value=True)):
                await getattr(self.cog, f"blacklist_remove{kind}").callback(self.cog, self.ctx, " A ")
            self.assertEqual(self.cog._get_guild_blacklists(1)[key], ["b"])

    async def test_failed_writes_never_change_cache(self):
        self.cog.all_blacklists_data[1] = {"blacklisted_words": ["kept"], "blacklisted_links": ["kept"]}
        for kind in ("word", "link"):
            for operation, entry in (("add", "new"), ("remove", "kept")):
                with patch(f"cogs.moderation.db_blacklists.{operation}_{kind}", new=AsyncMock(side_effect=ConnectionError())):
                    await getattr(self.cog, f"blacklist_{operation}{kind}").callback(self.cog, self.ctx, entry)
                self.assertEqual(self.cog._get_guild_blacklists(1)[f"blacklisted_{kind}s"], ["kept"])
                self.assertIn("update failed", self.ctx.send.call_args.args[0])
                self.modlog.assert_not_awaited()

    async def test_partial_batch_reports_only_confirmed_changes(self):
        with patch("cogs.moderation.db_blacklists.add_word", new=AsyncMock(side_effect=[True, ConnectionError()])) as add:
            await self.cog.blacklist_addword.callback(self.cog, self.ctx, "first,second,third")
        self.assertEqual(add.await_count, 2)
        self.assertEqual(self.cog._get_guild_blacklists(1)["blacklisted_words"], ["first"])
        self.assertIn("Added 1", self.ctx.send.call_args.args[0])
        self.assertIn("stopped", self.ctx.send.call_args.args[0])
        self.assertNotIn("second", self.modlog.call_args.args[5])

    async def test_invalid_input_prevents_all_writes(self):
        with patch("cogs.moderation.db_blacklists.add_word", new_callable=AsyncMock) as add:
            for args in ((), (", ,",), ("valid", "x" * 256), ("valid", "bad\x00entry")):
                await self.cog.blacklist_addword.callback(self.cog, self.ctx, *args)
            add.assert_not_awaited()
        self.assertEqual(self.cog.all_blacklists_data, {})

    async def test_list_refresh_and_read_failure(self):
        self.cog.all_blacklists_data[1] = {"blacklisted_words": ["old"], "blacklisted_links": ["oldlink"]}
        for plural in ("words", "links"):
            command = getattr(self.cog, "blacklist_list" + plural)
            with patch(f"cogs.moderation.db_blacklists.get_{plural}", new=AsyncMock(return_value=["fresh"])) as get:
                await command.callback(self.cog, self.ctx)
            get.assert_awaited_once_with(self.pool, 1)
            with patch(f"cogs.moderation.db_blacklists.get_{plural}", new=AsyncMock(side_effect=ConnectionError())):
                await command.callback(self.cog, self.ctx)
            self.assertEqual(self.cog._get_guild_blacklists(1)["blacklisted_" + plural], ["fresh"])
        with patch("cogs.moderation.db_blacklists.get_words", new=AsyncMock(return_value=[])):
            await self.cog.blacklist_listwords.callback(self.cog, self.ctx)
        self.assertEqual(self.cog._get_guild_blacklists(1), {"blacklisted_words": [], "blacklisted_links": ["fresh"]})

    async def test_concurrent_refresh_cannot_overwrite_newer_mutation(self):
        started, release = asyncio.Event(), asyncio.Event()
        async def read(*_):
            started.set()
            await release.wait()
            return []
        with patch("cogs.moderation.db_blacklists.get_words", new=AsyncMock(side_effect=read)), \
                patch("cogs.moderation.db_blacklists.add_word", new=AsyncMock(return_value=True)) as add:
            listing = asyncio.create_task(self.cog.blacklist_listwords.callback(self.cog, self.ctx))
            await asyncio.wait_for(started.wait(), 2)
            editing = asyncio.create_task(self.cog.blacklist_addword.callback(self.cog, self.ctx, "new"))
            await asyncio.sleep(0)
            add.assert_not_awaited()
            release.set()
            await asyncio.wait_for(asyncio.gather(listing, editing), 2)
        self.assertEqual(self.cog._get_guild_blacklists(1)["blacklisted_words"], ["new"])

    async def test_automod_memory_only_guild_isolation_and_ignores(self):
        self.cog.all_blacklists_data = {1: {"blacklisted_words": ["blocked"], "blacklisted_links": ["bad.invalid"]}}
        with patch("cogs.moderation.db_blacklists.get_all_blacklists", side_effect=AssertionError("DB hot path")), \
                patch("cogs.moderation.db_blacklists.get_words", side_effect=AssertionError("DB hot path")), \
                patch("cogs.moderation.db_blacklists.get_links", side_effect=AssertionError("DB hot path")):
            for text, guild, author_bot, deleted in (
                ("BLOCKED", 1, False, True), ("https://bad.invalid", 1, False, True),
                ("blocked", 2, False, False), ("ordinary text", 1, False, False),
                ("blocked", None, False, False), ("blocked", 1, True, False),
                ("eli blacklist addword blocked", 1, False, False),
            ):
                msg = message(text, guild, bot=author_bot)
                await self.cog.on_message(msg)
                self.assertEqual(msg.delete.await_count, int(deleted))
        self.assertNotIn(2, self.cog.all_blacklists_data)
