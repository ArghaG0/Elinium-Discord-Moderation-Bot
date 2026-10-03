"""DB contracts, including opt-in PostgreSQL integration tests.

Set TEST_DATABASE_URL explicitly to a disposable test database. This module
never reads .env or DATABASE_URL. Every test owns a unique schema; cleanup drops
only that generated schema. Without TEST_DATABASE_URL, integration tests skip.
"""

import asyncio
from datetime import datetime, timezone
import os
import unittest
from unittest.mock import AsyncMock
import uuid

import asyncpg

from db import blacklists, settings, warnings
from utils import init_db


class InputValidationTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_blacklists_never_touch_storage(self):
        pool = AsyncMock()
        for helper in (blacklists.add_word, blacklists.remove_word, blacklists.add_link, blacklists.remove_link):
            for value in ("", "  ", "x" * 256, "bad\x00entry"):
                with self.subTest(helper=helper.__name__, value_length=len(value)):
                    with self.assertRaises(ValueError):
                        await helper(pool, 1, value)
        pool.fetchval.assert_not_awaited()

    async def test_invalid_warning_selector_never_acquires_connection(self):
        pool = AsyncMock()
        for selector, exception in ((0, ValueError), (False, TypeError), (1.5, TypeError), ("1", TypeError)):
            with self.subTest(selector=selector):
                with self.assertRaises(exception):
                    await warnings.clear_warnings(pool, 1, 2, selector)
        pool.acquire.assert_not_called()

    async def test_database_errors_propagate_instead_of_empty_results(self):
        pool = AsyncMock()
        pool.fetchrow.side_effect = ConnectionError("offline")
        pool.fetch.side_effect = ConnectionError("offline")
        pool.fetchval.side_effect = ConnectionError("offline")
        for call in (
            settings.get_settings(pool, 1), warnings.get_warnings(pool, 1, 2),
            blacklists.get_all_blacklists(pool), blacklists.add_word(pool, 1, "blocked"),
        ):
            with self.assertRaises(ConnectionError):
                await call


@unittest.skipUnless(os.environ.get("TEST_DATABASE_URL"), "Set TEST_DATABASE_URL for isolated PostgreSQL checks")
class DatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Identifiers are generated locally from a fixed prefix and UUID hex.
        self.schema = "elinium_test_" + uuid.uuid4().hex
        self.admin = await asyncpg.connect(os.environ["TEST_DATABASE_URL"], timeout=15)
        self.addAsyncCleanup(self.admin.close)
        await self.admin.execute(f'CREATE SCHEMA "{self.schema}"')
        self.addAsyncCleanup(self.admin.execute, f'DROP SCHEMA "{self.schema}" CASCADE')
        self.pool = await asyncpg.create_pool(
            os.environ["TEST_DATABASE_URL"], min_size=1, max_size=5,
            command_timeout=15, timeout=15,
            server_settings={"search_path": self.schema},
        )
        self.addAsyncCleanup(self.pool.close)
        await init_db(self.pool)

    async def test_startup_loads_cogs_and_persistent_cache(self):
        import sys
        import textwrap

        await blacklists.add_word(self.pool, 1, "blocked")
        # Extension loading/unloading replaces sys.modules entries. Use a fresh
        # interpreter so existing test fixtures retain their original modules.
        script = textwrap.dedent("""
            import asyncio
            import os
            import sys
            from unittest.mock import patch
            import asyncpg
            import main
            from config import load_config

            async def check():
                bot = main.bot
                bot.config = load_config({
                    "DISCORD_TOKEN": "test-token",
                    "DATABASE_URL": os.environ["TEST_DATABASE_URL"],
                })
                create_pool = asyncpg.create_pool
                def isolated_pool(*args, **kwargs):
                    return create_pool(*args, **kwargs, server_settings={"search_path": sys.argv[1]})
                with patch("main.asyncpg.create_pool", new=isolated_pool):
                    await main.setup_hook()
                try:
                    await main.load_extensions()
                    assert set(bot.cogs) == {"General", "Moderation"}
                    for name in ("setmodlogchannel", "warn", "warnings", "clearwarnings",
                                 "blacklist addword", "blacklist removeword", "blacklist listwords",
                                 "blacklist addlink", "blacklist removelink", "blacklist listlinks"):
                        assert bot.get_command(name) is not None, name
                    for name in ("setconfessionchannel", "confess"):
                        assert bot.tree.get_command(name) is not None, name
                    assert bot.get_cog("Moderation")._get_guild_blacklists(1)["blacklisted_words"] == ["blocked"]
                    assert await bot.db_pool.fetchval("SELECT 1") == 1
                finally:
                    await bot.close()
                    await bot.db_pool.close()
            asyncio.run(check())
        """)
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-B", "-c", script, self.schema,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        )
        try:
            output, _ = await asyncio.wait_for(process.communicate(), timeout=90)
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
        self.assertEqual(process.returncode, 0, output.decode(errors="replace"))

    async def test_settings_upserts_preserve_other_channel_and_guild(self):
        self.assertEqual(await settings.get_settings(self.pool, 1), settings.GuildSettings(1))
        await asyncio.gather(
            settings.set_modlog_channel(self.pool, 1, 100),
            settings.set_confession_channel(self.pool, 1, 200),
        )
        self.assertEqual(await settings.get_settings(self.pool, 1), settings.GuildSettings(1, 100, 200))
        await settings.set_modlog_channel(self.pool, 2, 300)
        await settings.set_modlog_channel(self.pool, 1, None)
        self.assertEqual(await settings.get_settings(self.pool, 1), settings.GuildSettings(1, None, 200))
        await settings.set_confession_channel(self.pool, 1, None)
        self.assertEqual(await settings.get_settings(self.pool, 1), settings.GuildSettings(1))
        self.assertEqual((await settings.get_settings(self.pool, 2)).modlog_channel_id, 300)

    async def test_settings_command_flows_persist_across_cog_and_pool_recreation(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from test_settings_flows import make_cog, make_channel, make_interaction
        from utils import send_modlog_embed

        modlog, confession = make_channel(100), make_channel(200)
        interaction = make_interaction(channels={100: modlog, 200: confession})
        ctx = SimpleNamespace(guild=interaction.guild, author=interaction.user, send=AsyncMock())
        cog = make_cog(self.pool)
        with patch("builtins.print"):
            await cog.set_modlog_channel.callback(cog, ctx, modlog)
            await cog.set_confession_channel.callback(cog, interaction, confession)
            self.assertEqual(await settings.get_settings(self.pool, 1), settings.GuildSettings(1, 100, 200))
            self.assertEqual(await settings.get_settings(self.pool, 2), settings.GuildSettings(2))
            modlog.send.assert_awaited_once()  # Actual modlog helper logged channel setup.

            async with asyncpg.create_pool(
                os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2,
                server_settings={"search_path": self.schema},
            ) as restarted_pool:
                restarted = make_cog(restarted_pool)
                with patch("builtins.print"):
                    await restarted.confess.callback(restarted, interaction, "persistent confession")
                confession.send.assert_awaited_once()
                self.assertEqual(confession.send.call_args.kwargs["embed"].description, "persistent confession")
                self.assertEqual(modlog.send.await_count, 2)

                other = make_interaction(2, {100: modlog, 200: confession})
                await restarted.confess.callback(restarted, other, "not configured")
                self.assertIn("not been set up", other.followup.send.call_args.args[0])
                confession.send.assert_awaited_once()
                await send_modlog_embed(restarted.bot, other.guild, "Warn", other.user, restarted.bot.user, "reason")
                self.assertEqual(modlog.send.await_count, 2)

                # Simulate the configured confession channel being deleted.
                missing = make_interaction(channels={100: modlog})
                await restarted.confess.callback(restarted, missing, "missing channel")
                self.assertEqual(await settings.get_settings(restarted_pool, 1), settings.GuildSettings(1, 100, None))
                await send_modlog_embed(restarted.bot, interaction.guild, "Warn", interaction.user, restarted.bot.user, "reason")
                self.assertEqual(modlog.send.await_count, 3)

    async def test_warning_order_timestamp_and_scoped_id_delete(self):
        first = await warnings.add_warning(self.pool, 1, 10, 99, "Reason '); DROP TABLE warnings; --")
        second = await warnings.add_warning(self.pool, 1, 10, 99, None)
        other = await warnings.add_warning(self.pool, 2, 10, 99, "other guild")
        self.assertIsInstance(first.timestamp, datetime)
        self.assertIsNotNone(first.timestamp.tzinfo)
        self.assertEqual(await warnings.get_warnings(self.pool, 1, 10), [first, second])
        self.assertEqual(await warnings.count_warnings(self.pool, 1, 10), 2)
        self.assertIsNone(await warnings.delete_warning(self.pool, 1, 10, other.id))
        self.assertIsNone(await warnings.delete_warning(self.pool, 1, 11, first.id))
        self.assertEqual(await warnings.delete_warning(self.pool, 1, 10, first.id), first)
        self.assertEqual(await warnings.get_warnings(self.pool, 2, 10), [other])
        self.assertEqual(await warnings.get_warnings(self.pool, 1, 11), [])

    async def test_warning_commands_persist_and_preserve_all_deletion_modes(self):
        from unittest.mock import patch
        from test_warning_flows import warning_cog, warning_context

        cog = warning_cog(self.pool)
        ctx, member = warning_context()
        with patch("cogs.moderation.send_modlog_embed", new_callable=AsyncMock) as modlog, \
                patch("builtins.print"):
            for reason in ("first", "second", "third", "fourth"):
                await cog.warn_user.callback(cog, ctx, member, reason=reason)
            self.assertEqual(await warnings.count_warnings(self.pool, 1, 20), 4)
            other_guild = await warnings.add_warning(self.pool, 2, 20, 10, "other guild")
            other_user = await warnings.add_warning(self.pool, 1, 21, 10, "other user")
            async with asyncpg.create_pool(
                os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2,
                server_settings={"search_path": self.schema},
            ) as restarted_pool:
                restarted = warning_cog(restarted_pool)
                await restarted.show_warnings.callback(restarted, ctx, member)
                self.assertEqual([f.name for f in ctx.send.call_args.kwargs["embed"].fields],
                                 ["Warning #1", "Warning #2", "Warning #3", "Warning #4"])
                for invalid in (0, 5, -5):
                    await restarted.clearwarnings.callback(restarted, ctx, member, invalid)
                    self.assertEqual(await warnings.count_warnings(restarted_pool, 1, 20), 4)
                await restarted.clearwarnings.callback(restarted, ctx, member, 2)
                self.assertIn("second", modlog.call_args.args[5])
                await restarted.show_warnings.callback(restarted, ctx, member)
                fields = ctx.send.call_args.kwargs["embed"].fields
                self.assertEqual(fields[1].name, "Warning #2")
                self.assertIn("third", fields[1].value)
                await restarted.clearwarnings.callback(restarted, ctx, member, -2)
                self.assertEqual([r.reason for r in await warnings.get_warnings(restarted_pool, 1, 20)], ["first"])
                await restarted.clearwarnings.callback(restarted, ctx, member)
                self.assertEqual(await warnings.get_warnings(restarted_pool, 1, 20), [])
                await restarted.show_warnings.callback(restarted, ctx, member)
                self.assertIn("no warnings", ctx.send.call_args.args[0])
                self.assertEqual(await warnings.get_warnings(restarted_pool, 2, 20), [other_guild])
                self.assertEqual(await warnings.get_warnings(restarted_pool, 1, 21), [other_user])

    async def test_warning_clear_modes_and_invalid_ranges(self):
        rows = [await warnings.add_warning(self.pool, 1, 10, 99, str(i)) for i in range(5)]
        unaffected = await warnings.add_warning(self.pool, 1, 11, 99, "other user")
        for selector, error in ((0, ValueError), (6, IndexError), (-6, IndexError)):
            with self.assertRaises(error):
                await warnings.clear_warnings(self.pool, 1, 10, selector)
            self.assertEqual(await warnings.get_warnings(self.pool, 1, 10), rows)
        self.assertEqual(await warnings.clear_warnings(self.pool, 1, 10, 2), [rows[1]])
        # Display #2 now identifies the third original record, not database ID 2.
        self.assertEqual(await warnings.clear_warnings(self.pool, 1, 10, 2), [rows[2]])
        self.assertEqual(await warnings.clear_warnings(self.pool, 1, 10, -2), rows[3:])
        self.assertEqual(await warnings.clear_warnings(self.pool, 1, 10), [rows[0]])
        self.assertEqual(await warnings.clear_warnings(self.pool, 1, 10), [])
        with self.assertRaises(IndexError):
            await warnings.clear_warnings(self.pool, 1, 10, -1)
        self.assertEqual(await warnings.get_warnings(self.pool, 1, 11), [unaffected])

    async def test_warning_order_does_not_depend_on_timestamp(self):
        first = await warnings.add_warning(self.pool, 1, 10, 99)
        second = await warnings.add_warning(self.pool, 1, 10, 99)
        await self.pool.execute("UPDATE warnings SET timestamp = $1", datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.assertEqual([row.id for row in await warnings.get_warnings(self.pool, 1, 10)], [first.id, second.id])

    async def test_concurrent_warning_deletions_do_not_remove_the_same_record(self):
        rows = [await warnings.add_warning(self.pool, 1, 10, 99) for _ in range(3)]
        removed = await asyncio.gather(
            warnings.clear_warnings(self.pool, 1, 10, -1),
            warnings.clear_warnings(self.pool, 1, 10, -1),
        )
        self.assertEqual({row.id for result in removed for row in result}, {rows[1].id, rows[2].id})
        self.assertEqual(await warnings.get_warnings(self.pool, 1, 10), rows[:1])

    async def test_failed_warning_insert_releases_lock_and_rolls_back(self):
        with self.assertRaises(asyncpg.NotNullViolationError):
            await warnings.add_warning(self.pool, 1, 10, None)
        self.assertEqual(await warnings.count_warnings(self.pool, 1, 10), 0)
        await asyncio.wait_for(warnings.add_warning(self.pool, 1, 10, 99), timeout=5)
        self.assertEqual(await warnings.count_warnings(self.pool, 1, 10), 1)

    async def test_blacklist_normalization_duplicates_limits_and_cache_snapshot(self):
        for add, get, remove, key in (
            (blacklists.add_word, blacklists.get_words, blacklists.remove_word, "blacklisted_words"),
            (blacklists.add_link, blacklists.get_links, blacklists.remove_link, "blacklisted_links"),
        ):
            self.assertEqual(await get(self.pool, 1), [])
            outcomes = await asyncio.gather(add(self.pool, 1, " BLOCKED "), add(self.pool, 1, "blocked"))
            self.assertEqual(sorted(outcomes), [False, True])
            self.assertTrue(await add(self.pool, 2, "blocked"))
            self.assertTrue(await add(self.pool, 1, "x" * 255))
            self.assertTrue(await add(self.pool, 1, "'); DROP TABLE warnings; --"))
            self.assertEqual((await blacklists.get_all_blacklists(self.pool))[1][key], await get(self.pool, 1))
            self.assertTrue(await remove(self.pool, 1, " BLOCKED "))
            self.assertFalse(await remove(self.pool, 1, "blocked"))
            self.assertEqual(await get(self.pool, 2), ["blocked"])
        self.assertEqual(await warnings.count_warnings(self.pool, 1, 10), 0)
        self.assertEqual((await blacklists.get_all_blacklists(self.pool))[2], {
            "blacklisted_words": ["blocked"], "blacklisted_links": ["blocked"],
        })

    async def test_blacklist_commands_cache_reload_and_automod(self):
        from unittest.mock import patch
        from test_blacklist_flows import blacklist_cog, blacklist_context, message

        cog = blacklist_cog(self.pool)
        ctx = blacklist_context()
        with patch("cogs.moderation.send_modlog_embed", new_callable=AsyncMock), patch("builtins.print"):
            await cog.cog_load()
            self.assertEqual(cog.all_blacklists_data, {})
            await cog.blacklist_addword.callback(cog, ctx, " BLOCKED,second", "blocked")
            await cog.blacklist_addlink.callback(cog, ctx, " BAD.INVALID ")
            self.assertEqual(cog._get_guild_blacklists(1)["blacklisted_words"], ["blocked", "second"])
            self.assertEqual(cog.all_blacklists_data, await blacklists.get_all_blacklists(self.pool))
            for command in (cog.blacklist_listwords, cog.blacklist_listlinks):
                await command.callback(cog, ctx)
            async with asyncpg.create_pool(
                os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2,
                server_settings={"search_path": self.schema},
            ) as restarted_pool:
                restarted = blacklist_cog(restarted_pool)
                await restarted.cog_load()
                self.assertEqual(restarted.all_blacklists_data, cog.all_blacklists_data)
                for text in ("BLOCKED", "bad.invalid"):
                    bad = message(text)
                    other = message(text, 2)
                    await restarted.on_message(bad)
                    await restarted.on_message(other)
                    bad.delete.assert_awaited_once()
                    other.delete.assert_not_awaited()
                await restarted.blacklist_removeword.callback(restarted, ctx, "blocked,second")
                await restarted.blacklist_removelink.callback(restarted, ctx, "bad.invalid")
                self.assertEqual(await blacklists.get_words(restarted_pool, 1), [])
                self.assertEqual(await blacklists.get_links(restarted_pool, 1), [])
                allowed = message("blocked bad.invalid")
                await restarted.on_message(allowed)
                allowed.delete.assert_not_awaited()

    async def test_real_write_failure_keeps_last_committed_cache(self):
        from unittest.mock import patch
        from test_blacklist_flows import blacklist_cog, blacklist_context
        cog = blacklist_cog(self.pool)
        ctx = blacklist_context()
        await blacklists.add_word(self.pool, 1, "kept")
        await cog.cog_load()
        # Force a server-side statement failure without changing public helpers.
        await self.pool.execute("ALTER TABLE blacklisted_words ADD CONSTRAINT reject_new CHECK (word <> 'reject')")
        with patch("cogs.moderation.log.exception"), \
                patch("cogs.moderation.send_modlog_embed", new_callable=AsyncMock):
            await cog.blacklist_addword.callback(cog, ctx, "saved,reject,unprocessed")
        self.assertEqual(await blacklists.get_words(self.pool, 1), ["kept", "saved"])
        self.assertEqual(cog._get_guild_blacklists(1)["blacklisted_words"], ["kept", "saved"])
        self.assertIn("update failed", ctx.send.call_args.args[0])
