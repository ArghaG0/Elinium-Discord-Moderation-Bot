"""Warning command regression checks; no live Discord or legacy JSON access."""

from contextlib import ExitStack
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import discord

from db.warnings import Warning
from test_settings_flows import make_cog, make_interaction


def warning_context(guild_id=1, user_id=20):
    interaction = make_interaction(guild_id)
    ctx = SimpleNamespace(guild=interaction.guild, author=interaction.user, send=AsyncMock())
    member = SimpleNamespace(id=user_id, name="Target", display_name="Target", mention=f"<@{user_id}>", avatar=None, send=AsyncMock())
    return ctx, member


def warning_cog(pool):
    cog = make_cog(pool)
    cog.bot.EMOJIS.update({key: key for key in ("STAR", "FLOWER", "CROWN")})
    cog.bot.get_user = lambda _: None
    cog._check_hierarchy = AsyncMock(return_value=True)
    return cog


class WarningFlowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for name in ("load_warnings", "save_warnings"):
            self.stack.enter_context(patch(f"utils.{name}", side_effect=AssertionError("Legacy warnings I/O")))
        self.stack.enter_context(patch("cogs.moderation.log.exception"))
        self.modlog = self.stack.enter_context(patch("cogs.moderation.send_modlog_embed", new_callable=AsyncMock))
        self.pool = object()
        self.cog = warning_cog(self.pool)
        self.ctx, self.member = warning_context()

    def test_no_warning_state_in_constructor(self):
        self.assertFalse(hasattr(self.cog, "all_warnings_data"))

    async def test_warn_persists_before_dm_feedback_and_modlog(self):
        async def insert(*args):
            self.member.send.assert_not_awaited()
            self.ctx.send.assert_not_awaited()
            self.modlog.assert_not_awaited()
        with patch("cogs.moderation.db_warnings.add_warning", new=AsyncMock(side_effect=insert)) as add, \
                patch("cogs.moderation.db_warnings.count_warnings", new=AsyncMock(return_value=3)) as count:
            await self.cog.warn_user.callback(self.cog, self.ctx, self.member, reason="reason")
        add.assert_awaited_once_with(self.pool, 1, 20, 10, "reason")
        count.assert_awaited_once_with(self.pool, 1, 20)
        self.member.send.assert_awaited_once()
        self.assertIn("Total Warnings: 3", self.ctx.send.call_args.args[0])
        self.assertEqual(self.modlog.call_args.kwargs["warning_count"], 3)

    async def test_failed_insert_does_not_notify_target_or_claim_success(self):
        with patch("cogs.moderation.db_warnings.add_warning", new=AsyncMock(side_effect=ConnectionError("private"))), \
                patch("cogs.moderation.db_warnings.count_warnings", new_callable=AsyncMock) as count:
            await self.cog.warn_user.callback(self.cog, self.ctx, self.member)
        count.assert_not_awaited()
        self.member.send.assert_not_awaited()
        self.modlog.assert_not_awaited()
        self.assertIn("couldn't save", self.ctx.send.call_args.args[0])

    async def test_failed_count_does_not_report_committed_warning_as_failed(self):
        with patch("cogs.moderation.db_warnings.add_warning", new_callable=AsyncMock) as add, \
                patch("cogs.moderation.db_warnings.count_warnings", new=AsyncMock(side_effect=ConnectionError("offline"))):
            await self.cog.warn_user.callback(self.cog, self.ctx, self.member)
        add.assert_awaited_once()
        self.assertIn("has been warned", self.ctx.send.call_args.args[0])
        self.assertIn("unavailable", self.ctx.send.call_args.args[0])
        self.modlog.assert_awaited_once()

    async def test_closed_dms_do_not_prevent_confirmation(self):
        self.member.send.side_effect = discord.Forbidden(SimpleNamespace(status=403, reason="Forbidden"), "closed DMs")
        with patch("cogs.moderation.db_warnings.add_warning", new_callable=AsyncMock), \
                patch("cogs.moderation.db_warnings.count_warnings", new=AsyncMock(return_value=1)):
            await self.cog.warn_user.callback(self.cog, self.ctx, self.member)
        self.assertIn("has been warned", self.ctx.send.call_args.args[0])
        self.modlog.assert_awaited_once()

    async def test_hierarchy_denial_prevents_mutations(self):
        self.cog._check_hierarchy.return_value = False
        with patch("cogs.moderation.db_warnings.add_warning", new_callable=AsyncMock) as add, \
                patch("cogs.moderation.db_warnings.clear_warnings", new_callable=AsyncMock) as clear:
            await self.cog.warn_user.callback(self.cog, self.ctx, self.member)
            await self.cog.clearwarnings.callback(self.cog, self.ctx, self.member)
        add.assert_not_awaited()
        clear.assert_not_awaited()

    async def test_listing_uses_display_positions_utc_and_nullable_fields(self):
        records = [
            Warning(71, 1, 20, 10, "first", datetime(2026, 10, 2, 12, tzinfo=timezone(timedelta(hours=2)))),
            Warning(93, 1, 20, 11, None, None),
        ]
        with patch("cogs.moderation.db_warnings.get_warnings", new=AsyncMock(return_value=records)) as get:
            await self.cog.show_warnings.callback(self.cog, self.ctx, self.member)
        get.assert_awaited_once_with(self.pool, 1, 20)
        fields = self.ctx.send.call_args.kwargs["embed"].fields
        self.assertEqual([field.name for field in fields], ["Warning #1", "Warning #2"])
        self.assertIn("2026-10-02 10:00:00 UTC", fields[0].value)
        self.assertIn("<@10>", fields[0].value)
        self.assertIn("No reason provided.", fields[1].value)
        self.assertIn("Unknown", fields[1].value)

    async def test_empty_history_and_failed_read_are_distinct(self):
        for result, expected in (([], "has no warnings"), (ConnectionError("offline"), "couldn't load")):
            getter = AsyncMock(side_effect=result) if isinstance(result, Exception) else AsyncMock(return_value=result)
            with patch("cogs.moderation.db_warnings.get_warnings", new=getter):
                await self.cog.show_warnings.callback(self.cog, self.ctx, self.member)
            self.assertIn(expected, self.ctx.send.call_args.args[0])

    async def test_empty_invalid_and_failed_deletions_do_not_emit_modlogs(self):
        for result, selector, expected in (([], None, "no warnings"), (IndexError(), 4, "exceeds"), (IndexError(), -4, "exceeds"), (ConnectionError(), None, "couldn't clear")):
            clear = AsyncMock(side_effect=result) if isinstance(result, Exception) else AsyncMock(return_value=result)
            with patch("cogs.moderation.db_warnings.clear_warnings", new=clear):
                await self.cog.clearwarnings.callback(self.cog, self.ctx, self.member, selector)
            self.assertIn(expected, self.ctx.send.call_args.args[0])
            self.modlog.assert_not_awaited()
