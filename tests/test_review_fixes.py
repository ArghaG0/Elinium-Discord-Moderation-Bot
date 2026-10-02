"""Offline regression checks; no Discord login, .env reads, or JSON writes.

Run with: python -B -m unittest discover -s tests -v
"""

import ast
import copy
import datetime
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord.ext import commands
from discord.ext.commands.view import StringView

from cogs.general import General
from cogs.moderation import Moderation
from db.settings import GuildSettings


def configured_emojis():
    # Evaluate only emoji assignments; importing main would start the bot.
    path = Path(__file__).resolve().parents[1] / "main.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    assignments = [
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            (isinstance(target, ast.Name) and target.id.startswith("EMOJI_"))
            or (isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "bot" and target.attr == "EMOJIS")
            for target in node.targets
        )
    ]
    namespace = {"bot": SimpleNamespace()}
    exec(compile(ast.Module(body=assignments, type_ignores=[]), str(path), "exec"), namespace)
    return namespace["bot"].EMOJIS


class ReviewFixTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = commands.Bot(command_prefix="eli ", intents=discord.Intents.none())
        self.bot.EMOJIS = configured_emojis()
        self.bot.db_pool = AsyncMock()
        with patch.multiple(
            "cogs.moderation",
            load_warnings=lambda: {}, load_blacklists=lambda: {},
        ):
            self.cog = Moderation(self.bot)
        await self.bot.add_cog(self.cog)

    async def asyncTearDown(self):
        await self.bot.close()

    def context(self, subcommand="", *, manage_guild=False, guild=True):
        message = SimpleNamespace(
            _state=self.bot._connection,
            author=SimpleNamespace(id=10), channel=SimpleNamespace(),
            guild=SimpleNamespace(id=20) if guild else None,
            attachments=[], edited_at=None,
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )
        ctx = commands.Context(
            message=message, bot=self.bot, view=StringView(subcommand),
            prefix="eli ", invoked_with="blacklist",
        )
        ctx.permissions = discord.Permissions(manage_guild=manage_guild)
        ctx.send = AsyncMock()
        return ctx

    async def test_blacklist_subcommands_and_aliases_enforce_parent_checks(self):
        group = self.bot.get_command("blacklist")
        for name, child in group.all_commands.items():
            for allowed, guild, expected_error in (
                (False, True, commands.MissingPermissions),
                (True, False, commands.NoPrivateMessage),
                (True, True, None),
            ):
                with self.subTest(command=name, allowed=allowed, guild=guild):
                    ctx = self.context(name, manage_guild=allowed, guild=guild)
                    with patch.object(child, "invoke", new_callable=AsyncMock) as invoke:
                        if expected_error:
                            with self.assertRaises(expected_error):
                                await group.invoke(ctx)
                            invoke.assert_not_awaited()
                        else:
                            await group.invoke(ctx)
                            invoke.assert_awaited_once_with(ctx)
                            ctx.send.assert_not_awaited()

    async def test_blacklist_without_subcommand_still_shows_help(self):
        ctx = self.context(manage_guild=True)
        await self.bot.get_command("bl").invoke(ctx)
        self.assertIn("Please specify a subcommand", ctx.send.call_args.args[0])

    async def test_clearwarnings_zero_does_not_read_write_or_log(self):
        ctx = self.context()
        with (
            patch.object(self.cog, "_check_hierarchy", new=AsyncMock(return_value=True)),
            patch("cogs.moderation.load_warnings") as load,
            patch("cogs.moderation.save_warnings") as save,
            patch("cogs.moderation.send_modlog_embed", new_callable=AsyncMock) as log,
        ):
            await self.cog.clearwarnings.callback(self.cog, ctx, SimpleNamespace(id=30), 0)
            load.assert_not_called()
            save.assert_not_called()
            log.assert_not_awaited()
            self.assertIn("cannot be 0", ctx.send.call_args.args[0])

    async def test_clearwarnings_existing_deletion_modes(self):
        records = [
            {"reason": reason, "moderator_id": 10, "timestamp": "2026-10-02T00:00:00+00:00"}
            for reason in ("first", "second", "third")
        ]
        for argument, remaining in ((None, []), (2, ["first", "third"]), (-2, ["first"])):
            with self.subTest(argument=argument):
                data = {"20": {"30": copy.deepcopy(records)}}
                ctx = self.context()
                with (
                    patch.object(self.cog, "_check_hierarchy", new=AsyncMock(return_value=True)),
                    patch("cogs.moderation.load_warnings", return_value=data),
                    patch("cogs.moderation.save_warnings") as save,
                    patch("cogs.moderation.send_modlog_embed", new_callable=AsyncMock),
                ):
                    member = SimpleNamespace(id=30, display_name="Member")
                    await self.cog.clearwarnings.callback(self.cog, ctx, member, argument)
                    saved = save.call_args.args[0].get("20", {}).get("30", [])
                    self.assertEqual([warning["reason"] for warning in saved], remaining)

    async def test_say_timeout_sends_feedback(self):
        ctx = self.context()
        ctx.message.delete = AsyncMock()
        with patch.object(self.bot, "wait_for", new=AsyncMock(side_effect=TimeoutError)):
            cog = General(self.bot)
            await cog.say_message.callback(cog, ctx)
        self.assertEqual(ctx.send.await_count, 2)
        self.assertIn("You didn't say anything in time", ctx.send.call_args.args[0])
        ctx.message.delete.assert_not_awaited()

    async def test_confession_error_paths_use_configured_error_emoji(self):
        self.assertTrue(self.bot.EMOJIS["ERROR"])
        response = SimpleNamespace(status=403, reason="Forbidden")
        for error in (discord.Forbidden(response, "Denied"), RuntimeError("Send failed")):
            with self.subTest(error=type(error).__name__):
                channel = MagicMock(spec=discord.TextChannel)
                channel.mention = "#confessions"
                channel.send = AsyncMock(side_effect=error)
                interaction = SimpleNamespace(
                    guild=SimpleNamespace(id=20, get_channel=lambda _: channel),
                    response=SimpleNamespace(defer=AsyncMock()),
                    followup=SimpleNamespace(send=AsyncMock()),
                )
                with patch("cogs.moderation.db_settings.get_settings", new=AsyncMock(return_value=GuildSettings(20, None, 40))):
                    await self.cog.confess.callback(self.cog, interaction, "Test message")
                interaction.followup.send.assert_awaited_once()
                self.assertIn(self.bot.EMOJIS["ERROR"], interaction.followup.send.call_args.args[0])
                self.assertTrue(interaction.followup.send.call_args.kwargs["ephemeral"])


if __name__ == "__main__":
    unittest.main()
