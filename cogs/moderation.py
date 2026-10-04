

import discord
from discord.ext import commands
import asyncio
from datetime import datetime, timezone # Import datetime and timezone specifically for utc
from typing import Optional
from discord import app_commands
import logging
from db import settings as db_settings
from db import warnings as db_warnings
from db import blacklists as db_blacklists

# Import your helper functions from utils/utils.py
from utils.utils import (
    send_modlog_embed, parse_duration,
)

log = logging.getLogger(__name__)

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # You can keep track of muted users if needed, though Discord's timeout handles most of it
        self.muted_users = {}

        # cog_load fills this before discord.py registers commands/listeners.
        self.all_blacklists_data: dict[int, db_blacklists.GuildBlacklist] = {}
        self._blacklist_locks: dict[int, asyncio.Lock] = {}

    async def cog_load(self):
        """Load once per cog instance; failure prevents registration of this cog."""
        self.all_blacklists_data = await db_blacklists.get_all_blacklists(self.bot.db_pool)

    def _blacklist_lock(self, guild_id: int) -> asyncio.Lock:
        return self._blacklist_locks.setdefault(guild_id, asyncio.Lock())

    # --- Helper Method: Hierarchy Check ---
    async def _check_hierarchy(self, ctx, member, action_name):
        """Checks if the bot or author can perform an action on a member based on role hierarchy."""
        if member == self.bot.user:
            await ctx.send(f"{self.bot.EMOJIS['SPARKLE']} I cannot {action_name} myself! {self.bot.EMOJIS['SPARKLE']}")
            return False
        if member == ctx.author:
            await ctx.send(f"{self.bot.EMOJIS['SPARKLE']} You cannot {action_name} yourself! {self.bot.EMOJIS['SPARKLE']}")
            return False
        if member == ctx.guild.owner:
            await ctx.send(f"{self.bot.EMOJIS['CROWN']} I cannot {action_name} the server owner. {self.bot.EMOJIS['CROWN']}")
            return False
        # Check if author's role is lower or equal to target's role
        if ctx.author.top_role <= member.top_role and ctx.author != ctx.guild.owner:
            await ctx.send(f"{self.bot.EMOJIS['CROWN']} You cannot {action_name} someone with an equal or higher role than you. {self.bot.EMOJIS['CROWN']}")
            return False
        # Check if bot's role is lower or equal to target's role
        if ctx.guild.me.top_role <= member.top_role:
            await ctx.send(f"{self.bot.EMOJIS['CROWN']} I cannot {action_name} that member because their highest role is equal to or higher than my highest role. Please move my role higher. {self.bot.EMOJIS['CROWN']}")
            return False
        return True

    # --- Helper Method: Get Guild Blacklists ---
    def _get_guild_blacklists(self, guild_id: int):
        return self.all_blacklists_data.get(guild_id, {"blacklisted_words": [], "blacklisted_links": []})

    # --- Automod on_message event listener ---
    @commands.Cog.listener()
    async def on_message(self, message):
        """Automod logic to delete blacklisted words and links, and handle interactive responses."""

        # 1. Ignore messages from bots themselves
        if message.author.bot:
            return

        # 2. Ignore DMs
        if message.guild is None:
            return

        # 3. IMPORTANT: Ignore messages that are commands.
        # This prevents the automod from triggering on command invocations themselves.
        # The bot's built-in command handler will process these.
        if message.content.lower().startswith(self.bot.command_prefix.lower()):
            return # If it's a command, just exit this listener early.

        # --- Automod logic (now runs AFTER the command check) ---
        guild_id = message.guild.id
        guild_blacklists = self._get_guild_blacklists(guild_id)
        blacklisted_words_for_guild = guild_blacklists.get("blacklisted_words", [])
        blacklisted_links_for_guild = guild_blacklists.get("blacklisted_links", [])

        # Check for blacklisted words
        for word in blacklisted_words_for_guild:
            if word.lower() in message.content.lower():
                try:
                    await message.delete()
                    await message.channel.send(f"{self.bot.EMOJIS['SPARKLE']} {message.author.mention}, that word is not allowed! {self.bot.EMOJIS['SPARKLE']}", delete_after=5)
                    print(f"Deleted message from {message.author.name} for blacklisted word in {message.channel.name}.")
                    await send_modlog_embed(
                        self.bot,
                        message.guild,
                        "Automod: Blacklisted Word",
                        message.author,
                        self.bot.user,
                        f"Used blacklisted word: '{word}'"
                    )
                    return # Stop processing after finding one blacklisted word and deleting
                except discord.Forbidden:
                    print(f"Bot lacks permissions to delete messages in {message.channel.name}.")
                    return
                except Exception as e:
                    print(f"Error deleting message for blacklisted word: {e}")
                    return

        # Check for blacklisted links
        for link in blacklisted_links_for_guild:
            if link.lower() in message.content.lower():
                try:
                    await message.delete()
                    await message.channel.send(f"{self.bot.EMOJIS['SPARKLE']} {message.author.mention}, that link is not allowed! {self.bot.EMOJIS['SPARKLE']}", delete_after=5)
                    print(f"Deleted message from {message.author.name} for blacklisted link in {message.channel.name}.")
                    await send_modlog_embed(
                        self.bot,
                        message.guild,
                        "Automod: Blacklisted Link",
                        message.author,
                        self.bot.user,
                        f"Posted blacklisted link: '{link}'"
                    )
                    return # Stop processing after finding one blacklisted link and deleting
                except discord.Forbidden:
                    print(f"Bot lacks permissions to delete messages for links in {message.channel.name}.")
                    return
                except Exception as e:
                    print(f"Error deleting message for blacklisted link: {e}")
                    return

        # --- Interactive Responses (These now run AFTER automod and command checks) ---
        msg_content = message.content.lower()

        if "thank you eli" in msg_content or "thanks eli" in msg_content or "ty eli" in msg_content:
            await message.channel.send(f"You're very welcome, {message.author.mention}! Glad I could help. {self.bot.EMOJIS['HEART']}")
            return

        if "love you eli" in msg_content or "ily eli" in msg_content :
            await message.channel.send(f"Aww, I love you too, {message.author.mention}! {self.bot.EMOJIS['MANYBUTTERFLIES']}")
            return

        if "hello" in msg_content:
            words = msg_content.split()
            if "hello" in words or any(word.startswith("hello") for word in words) or any(word.endswith("hello") for word in words):
                await message.channel.send(f"Hello, {message.author.mention}! {self.bot.EMOJIS['SPARKLE']}")
                return

        if "good morning" in msg_content:
            await message.channel.send(f"Good morning, {message.author.mention}! Hope you have a wonderful day. {self.bot.EMOJIS['STAR']}")
            return

        if "what can you do" in msg_content or "what are your commands" in msg_content:
            await message.channel.send(f"I can do quite a lot! Type `{self.bot.command_prefix}cmds` to see all my commands. {self.bot.EMOJIS['RIBBON']}")
            return

        if "bye" in msg_content or "goodbye" in msg_content:
            await message.channel.send(f"See you later, {message.author.mention}! {self.bot.EMOJIS['BUTTERFLY']}")
            return

        if "eli" in msg_content:
            words = msg_content.split()
            if "eli" in words or any(word.startswith("eli") for word in words) or any(word.endswith("eli") for word in words):
                await message.channel.send(f"Hello {message.author.mention}, how may I help you? {self.bot.EMOJIS['HEART']}")
                return

    # --- Warn Command ---
    @commands.command(name='warn')
    @commands.has_permissions(moderate_members=True)
    async def warn_user(self, ctx, member: discord.Member, *, reason: str = "No reason provided."):
        """Warns a member. Usage: eli warn <@user> [reason]
        Requires 'Moderate Members' permission."""

        if not await self._check_hierarchy(ctx, member, "warn"):
            return

        try:
            await db_warnings.add_warning(self.bot.db_pool, ctx.guild.id, member.id, ctx.author.id, reason)
        except Exception:
            log.exception("Failed to save warning for guild %s user %s", ctx.guild.id, member.id)
            await ctx.send("I couldn't save the warning. Please try again later.")
            return
        try:
            warning_count = await db_warnings.count_warnings(self.bot.db_pool, ctx.guild.id, member.id)
        except Exception:
            # The insert has committed: do not suggest retrying the warning.
            log.exception("Warning saved, but count lookup failed for guild %s user %s", ctx.guild.id, member.id)
            warning_count = "unavailable"

        # Try to DM the user
        try:
            dm_embed = discord.Embed(
                title=f"{self.bot.EMOJIS['HEART']} You have been Warned! {self.bot.EMOJIS['HEART']}",
                description=(
                    f"In **{ctx.guild.name}**:\n"
                    f"{self.bot.EMOJIS['SPARKLE']} **Reason:** {reason}\n"
                    f"{self.bot.EMOJIS['RIBBON']} **Moderator:** {ctx.author.mention}\n"
                    f"{self.bot.EMOJIS['STAR']} **Total Warnings:** {warning_count}"
                ),
                color=0xFFB6C1
            )
            dm_embed.set_footer(text=f"Server: {ctx.guild.name} | Bot: {self.bot.user.name}")
            await member.send(embed=dm_embed)
            print(f"DM sent to {member.name} after warn.")
        except discord.Forbidden:
            print(f"Could not DM {member.name} after warn (DMs forbidden or no mutual guilds).")
        except Exception as dm_e:
            print(f"An unexpected error occurred while DMing {member.name} after warn: {dm_e}")

        await ctx.send(f'{member.mention} has been warned. Reason: {reason} (Total Warnings: {warning_count})')
        print(f"Warned {member.name} in {ctx.guild.name}. Reason: {reason}. Total Warnings: {warning_count}")

        await send_modlog_embed(
            self.bot, # Pass the bot instance to the helper function
            ctx.guild,
            "Warn",
            member,
            ctx.author,
            reason,
            warning_count=warning_count
        )

    @warn_user.error
    async def warn_user_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(f"{self.bot.EMOJIS['CROWN']} You don't have permission to warn members. You need the 'Moderate Members' permission. {self.bot.EMOJIS['CROWN']}")
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send(f"{self.bot.EMOJIS['SPARKLE']} Could not find that member. Please make sure you spelled the name correctly or provided a valid ID/mention. {self.bot.EMOJIS['SPARKLE']}")
        else:
            await ctx.send(f"{self.bot.EMOJIS['HEART']} An error occurred: {error} {self.bot.EMOJIS['HEART']}")
            print(f"Error in warn_user: {error}")

    # --- Warnings Command ---
    @commands.command(name='warnings')
    @commands.has_permissions(moderate_members=True)
    async def show_warnings(self, ctx, member: discord.Member):
        """Displays a member's warnings. Usage: eli warnings <@user>
        Requires 'Moderate Members' permission."""
        try:
            user_warnings = await db_warnings.get_warnings(self.bot.db_pool, ctx.guild.id, member.id)
        except Exception:
            log.exception("Failed to read warnings for guild %s user %s", ctx.guild.id, member.id)
            await ctx.send("I couldn't load the warnings. Please try again later.")
            return

        if not user_warnings:
            await ctx.send(f"{member.mention} has no warnings in this server.")
            return

        embed = discord.Embed(
            title=f"{self.bot.EMOJIS['STAR']} Warnings for {member.display_name} {self.bot.EMOJIS['STAR']}",
            color=0xFFB6C1,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
        embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)

        for i, warning in enumerate(user_warnings):
            moderator = self.bot.get_user(warning.moderator_id)
            mod_name = moderator.mention if moderator else f"<@{warning.moderator_id}>"
            timestamp = warning.timestamp.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC') if warning.timestamp else "Unknown"
            embed.add_field(
                name=f"Warning #{i+1}",
                value=(
                    f"{self.bot.EMOJIS['SPARKLE']} **Reason:** {warning.reason or 'No reason provided.'}\n"
                    f"{self.bot.EMOJIS['RIBBON']} **Moderator:** {mod_name}\n"
                    f"{self.bot.EMOJIS['FLOWER']} **Date:** {timestamp}"
                ),
                inline=False
            )
        await ctx.send(embed=embed)

    @show_warnings.error
    async def show_warnings_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(f"{self.bot.EMOJIS['CROWN']} You don't have permission to view warnings. You need the 'Moderate Members' permission. {self.bot.EMOJIS['CROWN']}")
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send(f"{self.bot.EMOJIS['SPARKLE']} Could not find that member. Please make sure you spelled the name correctly or provided a valid ID/mention. {self.bot.EMOJIS['SPARKLE']}")
        else:
            await ctx.send(f"{self.bot.EMOJIS['HEART']} An error occurred: {error} {self.bot.EMOJIS['HEART']}")
            print(f"Error in show_warnings: {error}")

    # --- Clear Warnings Command ---
    @commands.command(name='clearwarnings', aliases=['delwarns', 'removewarns'])
    @commands.guild_only()
    @commands.has_permissions(kick_members=True) # Require kick_members permission to clear warnings
    async def clearwarnings(self, ctx, member: discord.Member, num_or_index: Optional[int] = None):
        """Clears all warnings, a specific warning, or a number of recent warnings for a member.
        Usage:
        - eli clearwarnings <@user/ID> -> Clears ALL warnings for the user.
        - eli clearwarnings <@user/ID> <index> -> Removes a specific warning by its number (e.g., '1' for the first warning).
        - eli clearwarnings <@user/ID> -<count> -> Removes the last <count> warnings (e.g., '-1' for the latest, '-2' for the two latest).
        """

        if not await self._check_hierarchy(ctx, member, "clear warnings for"):
            return

        if num_or_index == 0:
            await ctx.send("Warning number/count cannot be 0. Use a positive warning number, a negative count for recent warnings, or omit it to clear all warnings.")
            return

        try:
            removed_warnings = await db_warnings.clear_warnings(
                self.bot.db_pool, ctx.guild.id, member.id, num_or_index,
            )
        except IndexError:
            await ctx.send("That warning number or count exceeds the current history. Use `eli warnings` to check the member's current warnings.")
            return
        except Exception:
            log.exception("Failed to clear warnings for guild %s user %s", ctx.guild.id, member.id)
            await ctx.send("I couldn't clear the warnings. Please try again later.")
            return

        if not removed_warnings:
            await ctx.send(f"{self.bot.EMOJIS['SPARKLE']} {member.display_name} has no warnings to clear in this server. {self.bot.EMOJIS['SPARKLE']}")
            return

        removed_count = len(removed_warnings)
        if num_or_index is None:
            action_feedback_msg = f"{self.bot.EMOJIS['HEART']} Successfully cleared all {removed_count} warnings for **{member.display_name}**. {self.bot.EMOJIS['HEART']}"
        elif num_or_index > 0:
            action_feedback_msg = f"{self.bot.EMOJIS['HEART']} Successfully removed warning #{num_or_index} for **{member.display_name}**. {self.bot.EMOJIS['HEART']}"
        else:
            action_feedback_msg = f"{self.bot.EMOJIS['HEART']} Successfully removed the last {removed_count} warnings for **{member.display_name}**. {self.bot.EMOJIS['HEART']}"

        # Log records returned by the atomic deletion, not an earlier snapshot.
        # Database IDs are explicitly labeled; command arguments remain display numbers.
        modlog_details_list = [
            f" - Record ID {warning.id} (Mod: <@{warning.moderator_id}>, "
            f"Reason: '{warning.reason or 'No reason provided.'}', Timestamp: {warning.timestamp})"
            for warning in removed_warnings
        ]

        # Send confirmation message to the channel
        await ctx.send(action_feedback_msg)

        # Send a log entry to the moderation log channel
        await send_modlog_embed(
            self.bot,
            ctx.guild,
            "Warnings Cleared", # Action type for the log
            member, # User who had warnings cleared
            ctx.author, # Moderator who cleared the warnings
            f"**Action:** {action_feedback_msg.replace(self.bot.EMOJIS['HEART'], '').strip()}\n\n" +
            "**Details:**\n" + "\n".join(modlog_details_list) # Combine details for the log
        )

    @clearwarnings.error
    async def clearwarnings_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(f"{self.bot.EMOJIS['CROWN']} You don't have permission to clear warnings. You need the 'Kick Members' permission. {self.bot.EMOJIS['CROWN']}")
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send(f"{self.bot.EMOJIS['SPARKLE']} Could not find that member. Please make sure you spelled the name correctly or provided a valid ID/mention. {self.bot.EMOJIS['SPARKLE']}")
        else:
            await ctx.send(f"{self.bot.EMOJIS['HEART']} An error occurred: {error} {self.bot.EMOJIS['HEART']}")
            print(f"Error in clearwarnings: {error}")

    # --- Kick Command ---
    @commands.command(name='kick')
    @commands.has_permissions(kick_members=True)
    async def kick_user(self, ctx, member: discord.Member, *, reason: str = "No reason provided."):
        """Kicks a member from the server. Usage: eli kick <@user> [reason]
        Requires 'Kick Members' permission."""

        if not await self._check_hierarchy(ctx, member, "kick"):
            return

        try:
            # Try to DM the user
            try:
                dm_embed = discord.Embed(
                    title=f"{self.bot.EMOJIS['HEART']} You have been Kicked! {self.bot.EMOJIS['HEART']}",
                    description=(
                        f"From **{ctx.guild.name}**:\n"
                        f"{self.bot.EMOJIS['SPARKLE']} **Reason:** {reason}\n"
                        f"{self.bot.EMOJIS['RIBBON']} **Moderator:** {ctx.author.mention}"
                    ),
                    color=0xFFB6C1
                )
                dm_embed.set_footer(text=f"Server: {ctx.guild.name} | Bot: {self.bot.user.name}")
                await member.send(embed=dm_embed)
                print(f"DM sent to {member.name} before kick.")
            except discord.Forbidden:
                print(f"Could not DM {member.name} before kick (DMs forbidden or no mutual guilds).")
            except Exception as dm_e:
                print(f"An unexpected error occurred while DMing {member.name} before kick: {dm_e}")

            await member.kick(reason=reason)
            await ctx.send(f'{member.mention} has been kicked. Reason: {reason}')
            print(f"Kicked {member.name} from {ctx.guild.name}. Reason: {reason}")

            await send_modlog_embed(
                self.bot, # Pass the bot instance
                ctx.guild,
                "Kick",
                member,
                ctx.author,
                reason
            )

        except discord.Forbidden:
            await ctx.send(f"I don't have permission to kick members. Please grant me 'Kick Members'.")
            print(f"Bot lacks permissions to kick {member.name}.")
        except discord.HTTPException as e:
            await ctx.send(f"An error occurred while trying to kick {member.mention}: {e}")
            print(f"Error kicking {member.name}: {e}")
        except Exception as e:
            await ctx.send(f"An unexpected error occurred: {e}")
            print(f"Unexpected error in kick: {e}")

    @kick_user.error
    async def kick_user_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(f"{self.bot.EMOJIS['CROWN']} You don't have permission to kick members. You need the 'Kick Members' permission. {self.bot.EMOJIS['CROWN']}")
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send(f"{self.bot.EMOJIS['SPARKLE']} Could not find that member. Please make sure you spelled the name correctly or provided a valid ID/mention. {self.bot.EMOJIS['SPARKLE']}")
        else:
            await ctx.send(f"{self.bot.EMOJIS['HEART']} An error occurred: {error} {self.bot.EMOJIS['HEART']}")
            print(f"Error in kick_user: {error}")

    # --- Ban Command ---
    @commands.command(name='ban')
    @commands.has_permissions(ban_members=True)
    async def ban_user(self, ctx, member: discord.Member, *, reason: str = "No reason provided."):
        """Bans a member from the server. Usage: eli ban <@user> [reason]
        Requires 'Ban Members' permission."""

        if not await self._check_hierarchy(ctx, member, "ban"):
            return

        try:
            # Try to DM the user
            try:
                dm_embed = discord.Embed(
                    title=f"{self.bot.EMOJIS['HEART']} You have been Banned! {self.bot.EMOJIS['HEART']}",
                    description=(
                        f"From **{ctx.guild.name}**:\n"
                        f"{self.bot.EMOJIS['SPARKLE']} **Reason:** {reason}\n"
                        f"{self.bot.EMOJIS['RIBBON']} **Moderator:** {ctx.author.mention}"
                    ),
                    color=0xFFB6C1
                )
                dm_embed.set_footer(text=f"Server: {ctx.guild.name} | Bot: {self.bot.user.name}")
                await member.send(embed=dm_embed)
                print(f"DM sent to {member.name} before ban.")
            except discord.Forbidden:
                print(f"Could not DM {member.name} before ban (DMs forbidden or no mutual guilds).")
            except Exception as dm_e:
                print(f"An unexpected error occurred while DMing {member.name} before ban: {dm_e}")

            await member.ban(reason=reason)
            await ctx.send(f'{member.mention} has been banned. Reason: {reason}')
            print(f"Banned {member.name} from {ctx.guild.name}. Reason: {reason}")

            await send_modlog_embed(
                self.bot, # Pass the bot instance
                ctx.guild,
                "Ban",
                member,
                ctx.author,
                reason
            )

        except discord.Forbidden:
            await ctx.send(f"I don't have permission to ban members. Please grant me 'Ban Members'.")
            print(f"Bot lacks permissions to ban {member.name}.")
        except discord.HTTPException as e:
            await ctx.send(f"An error occurred while trying to ban {member.mention}: {e}")
            print(f"Error banning {member.name}: {e}")
        except Exception as e:
            await ctx.send(f"An unexpected error occurred: {e}")
            print(f"Unexpected error in ban: {e}")

    @ban_user.error
    async def ban_user_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(f"{self.bot.EMOJIS['CROWN']} You don't have permission to ban members. You need the 'Ban Members' permission. {self.bot.EMOJIS['CROWN']}")
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send(f"{self.bot.EMOJIS['SPARKLE']} Could not find that member. Please make sure you spelled the name correctly or provided a valid ID/mention. {self.bot.EMOJIS['SPARKLE']}")
        else:
            await ctx.send(f"{self.bot.EMOJIS['HEART']} An error occurred: {error} {self.bot.EMOJIS['HEART']}")
            print(f"Error in ban_user: {error}")

    # --- Unban Command ---
    @commands.command(name='unban')
    @commands.has_permissions(ban_members=True)
    async def unban_user(self, ctx, user_id: int, *, reason: str = "No reason provided."):
        """Unbans a user by their ID. Usage: eli unban <user_id> [reason]
        Requires 'Ban Members' permission."""
        try:
            user = await self.bot.fetch_user(user_id)
            await ctx.guild.unban(user, reason=reason)
            await ctx.send(f'{user.name}#{user.discriminator} ({user.id}) has been unbanned. Reason: {reason}')
            print(f"Unbanned {user.name} from {ctx.guild.name}. Reason: {reason}")

            await send_modlog_embed(
                self.bot, # Pass the bot instance
                ctx.guild,
                "Unban",
                user, # Pass the user object here
                ctx.author,
                reason
            )

        except discord.NotFound:
            await ctx.send(f"{self.bot.EMOJIS['SPARKLE']} User with ID {user_id} not found in the ban list or is not a valid user ID. {self.bot.EMOJIS['SPARKLE']}")
        except discord.Forbidden:
            await ctx.send(f"I don't have permission to unban members. Please grant me 'Ban Members'.")
            print(f"Bot lacks permissions to unban user ID {user_id}.")
        except discord.HTTPException as e:
            await ctx.send(f"An error occurred while trying to unban user ID {user_id}: {e}")
            print(f"Error unbanning user ID {user_id}: {e}")
        except Exception as e:
            await ctx.send(f"An unexpected error occurred: {e}")
            print(f"Unexpected error in unban: {e}")

    @unban_user.error
    async def unban_user_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(f"{self.bot.EMOJIS['CROWN']} You don't have permission to unban members. You need the 'Ban Members' permission. {self.bot.EMOJIS['CROWN']}")
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"{self.bot.EMOJIS['SPARKLE']} Please provide a valid user ID to unban. Usage: `eli unban <user_id> [reason]` {self.bot.EMOJIS['SPARKLE']}")
        else:
            await ctx.send(f"{self.bot.EMOJIS['HEART']} An error occurred: {error} {self.bot.EMOJIS['HEART']}")
            print(f"Error in unmute_user: {error}")

    # --- Purge Command ---
    @commands.command(name='purge')
    @commands.has_permissions(manage_messages=True)
    async def purge_messages(self, ctx, amount: int):
        """Deletes a specified number of messages in the channel. Usage: eli purge <amount>
        Requires 'Manage Messages' permission."""
        if amount <= 0:
            await ctx.send(f"{self.bot.EMOJIS['SPARKLE']} Please provide a positive number of messages to delete. {self.bot.EMOJIS['SPARKLE']}")
            return
        if amount > 100:
            await ctx.send(f"{self.bot.EMOJIS['SPARKLE']} You can only purge up to 100 messages at a time. {self.bot.EMOJIS['SPARKLE']}")
            return

        try:
            # Add 1 to amount to delete the command message itself
            deleted = await ctx.channel.purge(limit=amount + 1)
            deleted_count = len(deleted) - 1 # Exclude the command message

            # Send confirmation message that auto-deletes
            confirm_msg = await ctx.send(f"{self.bot.EMOJIS['SPARKLE']} Purged {deleted_count} messages. {self.bot.EMOJIS['SPARKLE']}")
            await asyncio.sleep(5) # Wait for 5 seconds
            await confirm_msg.delete() # Delete confirmation message

            print(f"Purged {deleted_count} messages in {ctx.channel.name} by {ctx.author.name}.")

            await send_modlog_embed(
                self.bot, # Pass the bot instance
                ctx.guild,
                "Purge",
                ctx.author, # The actor is the one who purged
                ctx.author,
                f"Purged {deleted_count} messages in #{ctx.channel.name}",
                purge_count=deleted_count
            )

        except discord.Forbidden:
            await ctx.send(f"I don't have permission to manage messages in this channel. Please grant me 'Manage Messages'.")
            print(f"Bot lacks permissions to purge in {ctx.channel.name}.")
        except discord.HTTPException as e:
            await ctx.send(f"An error occurred while trying to purge messages: {e}")
            print(f"Error purging messages: {e}")
        except Exception as e:
            await ctx.send(f"An unexpected error occurred: {e}")
            print(f"Unexpected error in purge: {e}")

    @purge_messages.error
    async def purge_messages_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(f"{self.bot.EMOJIS['CROWN']} You don't have permission to purge messages. You need the 'Manage Messages' permission. {self.bot.EMOJIS['CROWN']}")
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"{self.bot.EMOJIS['SPARKLE']} Please provide a valid number of messages to delete. Usage: `eli purge <amount>` {self.bot.EMOJIS['SPARKLE']}")
        else:
            await ctx.send(f"{self.bot.EMOJIS['HEART']} An error occurred: {error} {self.bot.EMOJIS['HEART']}")
            print(f"Error in purge_messages: {error}")

    # --- Mute Command ---
    @commands.command(name='mute')
    @commands.has_permissions(moderate_members=True)
    async def mute_user(self, ctx, member: discord.Member, duration: str, *, reason: str = "No reason provided."):
        """Mutes (times out) a member for a specified duration. Usage: eli mute <@user> <duration> [reason]
        Duration examples: 30s, 5m, 1h, 2d, 1w. Requires 'Moderate Members' permission."""

        if not await self._check_hierarchy(ctx, member, "mute"):
            return

        if member.is_timed_out():
            await ctx.send(f"{member.mention} is already timed out.")
            return

        time_delta = parse_duration(duration)
        if time_delta is None:
            await ctx.send(f"{self.bot.EMOJIS['SPARKLE']} Invalid duration format. Use s, m, h, d, w (e.g., `30s`, `5m`, `1h`, `2d`, `1w`). {self.bot.EMOJIS['SPARKLE']}")
            return

        timeout_until = datetime.now(timezone.utc) + time_delta

        # Discord's timeout limit is 28 days (4 weeks)
        if time_delta.total_seconds() > 28 * 24 * 60 * 60:
            await ctx.send(f"{self.bot.EMOJIS['SPARKLE']} The maximum timeout duration is 28 days (4 weeks). {self.bot.EMOJIS['SPARKLE']}")
            return

        try:
            await member.timeout(timeout_until, reason=reason)

            # Try to DM the user
            try:
                dm_embed = discord.Embed(
                    title=f"{self.bot.EMOJIS['HEART']} You have been Timed Out! {self.bot.EMOJIS['HEART']}",
                    description=(
                        f"In **{ctx.guild.name}**:\n"
                        f"{self.bot.EMOJIS['SPARKLE']} **Duration:** {duration}\n"
                        f"{self.bot.EMOJIS['RIBBON']} **Reason:** {reason}\n"
                        f"{self.bot.EMOJIS['STAR']} **Moderator:** {ctx.author.mention}"
                    ),
                    color=0xFFB6C1
                )
                dm_embed.set_footer(text=f"Server: {ctx.guild.name} | Bot: {self.bot.user.name}")
                await member.send(embed=dm_embed)
                print(f"DM sent to {member.name} after mute.")
            except discord.Forbidden:
                print(f"Could not DM {member.name} after mute (DMs forbidden or no mutual guilds).")
            except Exception as dm_e:
                print(f"An unexpected error occurred while DMing {member.name} after mute: {dm_e}")

            await ctx.send(f'{member.mention} has been timed out for {duration}. Reason: {reason}')
            print(f"Timed out {member.name} in {ctx.guild.name} for {duration}. Reason: {reason}")

            await send_modlog_embed(
                self.bot, # Pass the bot instance
                ctx.guild,
                "Mute",
                member,
                ctx.author,
                reason,
                duration=duration
            )

        except discord.Forbidden:
            await ctx.send(f"I don't have permission to timeout members. Please grant me 'Moderate Members'.")
            print(f"Bot lacks permissions to timeout {member.name}.")
        except discord.HTTPException as e:
            await ctx.send(f"An error occurred while trying to timeout {member.mention}: {e}")
            print(f"Error timing out {member.name}: {e}")
        except Exception as e:
            await ctx.send(f"An unexpected error occurred: {e}")
            print(f"Unexpected error in mute: {e}")

    @mute_user.error
    async def mute_user_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(f"{self.bot.EMOJIS['CROWN']} You don't have permission to mute members. You need the 'Moderate Members' permission. {self.bot.EMOJIS['CROWN']}")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"{self.bot.EMOJIS['SPARKLE']} You are missing arguments. Usage: `eli mute <@user> <duration> [reason]` {self.bot.EMOJIS['SPARKLE']}")
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send(f"{self.bot.EMOJIS['SPARKLE']} Could not find that member. Please make sure you spelled the name correctly or provided a valid ID/mention. {self.bot.EMOJIS['SPARKLE']}")
        else:
            await ctx.send(f"{self.bot.EMOJIS['HEART']} An error occurred: {error} {self.bot.EMOJIS['HEART']}")
            print(f"Error in mute_user: {error}")

    # --- Unmute Command (removes Discord's native Timeout) ---
    @commands.command(name='unmute')
    @commands.has_permissions(moderate_members=True)
    async def unmute_user(self, ctx, member: discord.Member, *, reason: str = "No reason provided."):
        """Removes timeout from a member. Usage: eli unmute <@user> [reason]
        Requires 'Moderate Members' permission."""

        if not member.is_timed_out():
            await ctx.send(f"{member.mention} is not currently timed out.")
            return

        try:
            await member.timeout(None, reason=reason) # Setting timeout to None removes it

            # Try to DM the user with an embed
            try:
                dm_embed = discord.Embed(
                    title=f"{self.bot.EMOJIS['HEART']} Your Timeout has been Removed! {self.bot.EMOJIS['HEART']}",
                    description=(
                        f"In **{ctx.guild.name}**:\n"
                        f"{self.bot.EMOJIS['SPARKLE']} **Reason:** {reason}\n"
                        f"{self.bot.EMOJIS['RIBBON']} **Moderator:** {ctx.author.mention}"
                    ),
                    color=0xFFB6C1
                )
                dm_embed.set_footer(text=f"Server: {ctx.guild.name} | Bot: {self.bot.user.name}")
                await member.send(embed=dm_embed)
                print(f"DM sent to {member.name} after unmute.")
            except discord.Forbidden:
                print(f"Could not DM {member.name} after unmute (DMs forbidden or no mutual guilds).")
            except Exception as dm_e:
                print(f"An unexpected error occurred while DMing {member.name} after unmute: {dm_e}")

            await ctx.send(f'{member.mention} has been untimed out. Reason: {reason}')
            print(f"Untimed out {member.name} in {ctx.guild.name}. Reason: {reason}")

            await send_modlog_embed(
                self.bot, # Pass your bot instance here
                ctx.guild,
                "Unmute",
                member,
                ctx.author,
                reason
            )

        except discord.Forbidden:
            await ctx.send(f"I don't have permission to untimeout members. Please grant me 'Moderate Members'.")
            print(f"Bot lacks permissions to untimeout {member.name}.")
        except discord.HTTPException as e:
            await ctx.send(f"An error occurred while trying to untimeout {member.mention}: {e}")
            print(f"Error untiming out {member.name}: {e}")
        except Exception as e:
            await ctx.send(f"An unexpected error occurred: {e}")
            print(f"Unexpected error in unmute: {e}")

    @unmute_user.error
    async def unmute_user_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(f"{self.bot.EMOJIS['CROWN']} You don't have permission to unmute members. You need the 'Moderate Members' permission. {self.bot.EMOJIS['CROWN']}")
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send(f"{self.bot.EMOJIS['SPARKLE']} Could not find that member. Please make sure you spelled the name correctly or provided a valid ID/mention. {self.bot.EMOJIS['SPARKLE']}")
        else:
            await ctx.send(f"{self.bot.EMOJIS['HEART']} An error occurred: {error} {self.bot.EMOJIS['HEART']}")
            print(f"Error in unmute_user: {error}")

    # ----- SetModLogChannel command -----
    @commands.command(name='setmodlogchannel')
    @commands.has_permissions(manage_guild=True)
    async def set_modlog_channel(self, ctx, channel: discord.TextChannel):
        """Sets the channel for moderation logs. Usage: eli setmodlogchannel #channel-name
        Requires 'Manage Server' permission."""
        await db_settings.set_modlog_channel(self.bot.db_pool, ctx.guild.id, channel.id)

        embed = discord.Embed(
            title=f"{self.bot.EMOJIS['RIBBON']} Modlog Channel Set! {self.bot.EMOJIS['RIBBON']}",
            description=f"Moderation logs will now be sent to {channel.mention}.",
            color=0x98FB98 # Pale Green
        )
        embed.set_footer(text=f"Set by {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
        await ctx.send(embed=embed)
        print(f"Modlog channel set to {channel.name} ({channel.id}) for guild {ctx.guild.name}.")

    @set_modlog_channel.error
    async def set_modlog_channel_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(f"{self.bot.EMOJIS['CROWN']} You don't have permission to set the modlog channel. You need the 'Manage Server' permission. {self.bot.EMOJIS['CROWN']}")
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"{self.bot.EMOJIS['SPARKLE']} Please mention a valid text channel. Usage: `eli setmodlogchannel #channel-name` {self.bot.EMOJIS['SPARKLE']}")
        else:
            await ctx.send(f"{self.bot.EMOJIS['HEART']} An error occurred: {error} {self.bot.EMOJIS['HEART']}")
            print(f"Error in set_modlog_channel: {error}")

    # --- Blacklist Management Group Commands ---
    @commands.group(name='blacklist', aliases=['bl'], invoke_without_command=False)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def blacklist_group(self, ctx):
        """Manages blacklisted words and links for AutoMod.
        Use `eli help blacklist` for subcommands.
        """
        if ctx.invoked_subcommand is None:
            await ctx.send(f"{self.bot.EMOJIS['SPARKLE']} Please specify a subcommand like `addword`, `removeword`, `listwords`, `addlink`, `removelink`, or `listlinks`. For more info, type `eli help blacklist`. {self.bot.EMOJIS['SPARKLE']}")

    async def _change_blacklist(self, ctx, inputs, *, kind, remove=False):
        """Serialize guild mutations; publish each entry only after DB confirmation.

        A multi-entry command consists of individual commits. If one fails, stop
        and report partial progress; already committed entries remain cached.
        """
        entries = [word.lower().strip() for part in " ".join(inputs).split(',') for word in part.split()]
        if not entries:
            await ctx.send(f"Please provide at least one {kind} to {'remove' if remove else 'add'}.")
            return
        if any(len(entry) > 255 or "\x00" in entry for entry in entries):
            await ctx.send("Each blacklist entry must contain 1-255 characters and no NUL characters. No changes were made.")
            return

        helpers = {
            ("word", False): db_blacklists.add_word,
            ("word", True): db_blacklists.remove_word,
            ("link", False): db_blacklists.add_link,
            ("link", True): db_blacklists.remove_link,
        }
        mutate = helpers[kind, remove]
        key = "blacklisted_words" if kind == "word" else "blacklisted_links"
        changed = []
        skipped = []
        failed = False
        async with self._blacklist_lock(ctx.guild.id):
            for entry in entries:
                try:
                    did_change = await mutate(self.bot.db_pool, ctx.guild.id, entry)
                except Exception:
                    log.exception("Blacklist mutation failed for guild %s (%s)", ctx.guild.id, kind)
                    failed = True
                    break
                # No await between confirmed commit and cache update. A False
                # result also confirms presence (add) or absence (remove).
                guild_cache = self.all_blacklists_data.setdefault(
                    ctx.guild.id, {"blacklisted_words": [], "blacklisted_links": []},
                )
                cached = guild_cache[key]
                if remove:
                    guild_cache[key] = [value for value in cached if value != entry]
                elif entry not in cached:
                    guild_cache[key] = [*cached, entry]
                (changed if did_change else skipped).append(entry)

        verb = "Removed" if remove else "Added"
        feedback = f"{verb} {len(changed)} {kind}(s). Skipped {len(skipped)} {'not present' if remove else 'already present'}."
        if failed:
            feedback += " An update failed; stopped processing. The confirmed changes above were saved. Check the list before retrying."
        await ctx.send(feedback)
        if changed:
            await send_modlog_embed(
                self.bot, ctx.guild, "Blacklist Update", ctx.author, self.bot.user,
                f"{verb} {len(changed)} {kind}(s): " + ", ".join(changed),
            )

    async def _list_blacklist(self, ctx, *, kind):
        """Refresh this guild/type from PostgreSQL; never erase cache on failure."""
        key = "blacklisted_words" if kind == "word" else "blacklisted_links"
        getter = db_blacklists.get_words if kind == "word" else db_blacklists.get_links
        async with self._blacklist_lock(ctx.guild.id):
            try:
                entries = await getter(self.bot.db_pool, ctx.guild.id)
            except Exception:
                log.exception("Blacklist read failed for guild %s (%s)", ctx.guild.id, kind)
                await ctx.send("I couldn't load the blacklist. Please try again later.")
                return
            self.all_blacklists_data.setdefault(
                ctx.guild.id, {"blacklisted_words": [], "blacklisted_links": []},
            )[key] = entries
        if not entries:
            await ctx.send(f"There are no blacklisted {kind}s for this server currently.")
            return
        await ctx.send(embed=discord.Embed(
            title=f"{self.bot.EMOJIS['BUTTERFLY']} Blacklisted {kind.title()}s for {ctx.guild.name}",
            description="\n".join(f"- `{entry}`" for entry in entries), color=0xFFB6C1,
        ))

    @blacklist_group.command(name='addword')
    async def blacklist_addword(self, ctx, *words_input: str):
        """Add words, separated by commas or spaces, to this server's blacklist."""
        await self._change_blacklist(ctx, words_input, kind="word")

    @blacklist_group.command(name='removeword', aliases=['delword'])
    async def blacklist_removeword(self, ctx, *words_input: str):
        """Remove words, separated by commas or spaces, from this server's blacklist."""
        await self._change_blacklist(ctx, words_input, kind="word", remove=True)

    @blacklist_group.command(name='listwords')
    async def blacklist_listwords(self, ctx):
        """List this server's blacklisted words."""
        await self._list_blacklist(ctx, kind="word")

    @blacklist_group.command(name='addlink')
    async def blacklist_addlink(self, ctx, *links_input: str):
        """Add links, separated by commas or spaces, to this server's blacklist."""
        await self._change_blacklist(ctx, links_input, kind="link")

    @blacklist_group.command(name='removelink', aliases=['dellink'])
    async def blacklist_removelink(self, ctx, *links_input: str):
        """Remove links, separated by commas or spaces, from this server's blacklist."""
        await self._change_blacklist(ctx, links_input, kind="link", remove=True)

    @blacklist_group.command(name='listlinks')
    async def blacklist_listlinks(self, ctx):
        """List this server's blacklisted links."""
        await self._list_blacklist(ctx, kind="link")

    # --- NEW: /setconfessionchannel Slash Command ---
    @app_commands.command(name='setconfessionchannel', description='Sets the channel for anonymous confessions.')
    @app_commands.describe(channel='The channel where confessions will be sent.')
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_channels=True)
    async def set_confession_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)

        try:
            await db_settings.set_confession_channel(self.bot.db_pool, interaction.guild.id, channel.id)
        except Exception:
            log.exception("Failed to save confession channel for guild %s", interaction.guild.id)
            await interaction.followup.send("I couldn't save the confession channel. Please try again later.", ephemeral=True)
            return

        await interaction.followup.send(
            f"{self.bot.EMOJIS['HEART']} Confessions channel set to {channel.mention} for this server. {self.bot.EMOJIS['HEART']}"
        )
        await send_modlog_embed(
            self.bot,
            interaction.guild,
            "Confession Channel Set",
            interaction.user,
            self.bot.user,
            f"Confession channel set to {channel.mention}"
        )

    # --- NEW: /confess Slash Command ---
    @app_commands.command(name='confess', description='Send an anonymous confession.')
    @app_commands.describe(message='Your anonymous confession message.')
    @app_commands.guild_only()
    async def confess(self, interaction: discord.Interaction, message: str):
        await interaction.response.defer(ephemeral=True)

        guild_id = interaction.guild.id
        try:
            settings = await db_settings.get_settings(self.bot.db_pool, guild_id)
        except Exception:
            log.exception("Failed to load confession settings for guild %s", guild_id)
            await interaction.followup.send("I couldn't load the confession settings. Please try again later.", ephemeral=True)
            return
        confession_channel_id = settings.confession_channel_id

        if not confession_channel_id:
            return await interaction.followup.send(
                f"{self.bot.EMOJIS['SPARKLE']} A confession channel has not been set up for this server. "
                f"An admin needs to use `/setconfessionchannel` first. {self.bot.EMOJIS['SPARKLE']}",
                ephemeral=True
            )

        confession_channel = interaction.guild.get_channel(confession_channel_id)
        if not confession_channel or not isinstance(confession_channel, discord.TextChannel):
            # If the channel is gone or not a text channel, remove it from settings
            try:
                await db_settings.set_confession_channel(self.bot.db_pool, guild_id, None)
            except Exception:
                log.exception("Failed to clear invalid confession channel for guild %s", guild_id)
                await interaction.followup.send("I couldn't update the confession settings. Please try again later.", ephemeral=True)
                return
            return await interaction.followup.send(
                f"{self.bot.EMOJIS['SPARKLE']} The configured confession channel no longer exists or is not a text channel. "
                f"Please set a new one using `/setconfessionchannel`. {self.bot.EMOJIS['SPARKLE']}",
                ephemeral=True
            )

        embed = discord.Embed(
            title=f"{self.bot.EMOJIS['HEART']} Anonymous Confession {self.bot.EMOJIS['HEART']}",
            description=message,
            color=0xFFB6C1
        )
        embed.set_footer(text=f"Confession received at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")

        try:
            await confession_channel.send(embed=embed)
            await interaction.followup.send(
                f"{self.bot.EMOJIS['HEART']} Your confession has been sent anonymously! {self.bot.EMOJIS['HEART']}",
                ephemeral=True
            )
            print(f"Confession by {interaction.user} (ID: {interaction.user.id}) in {interaction.guild.name} (ID: {interaction.guild.id}): {message}")
            await send_modlog_embed(
                self.bot,
                interaction.guild,
                "New Anonymous Confession",
                interaction.user, # The actual user who confessed (for logging, not displayed publicly)
                self.bot.user, # The bot is the "moderator" for this action
                f"Confession: {message}\nChannel: {confession_channel.mention}"
            )
        except discord.Forbidden:
            await interaction.followup.send(
                f"{self.bot.EMOJIS['ERROR']} I don't have permission to send messages in {confession_channel.mention}. "
                f"Please check my permissions. {self.bot.EMOJIS['ERROR']}",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                f"{self.bot.EMOJIS['ERROR']} An error occurred while sending your confession: {e} {self.bot.EMOJIS['ERROR']}",
                ephemeral=True
            )

    # --- Cog Error Handler ---
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if hasattr(ctx.command, 'on_error'):
            return # Let the command's local error handler deal with it

        # This can catch permissions errors etc. if they aren't caught by specific @command.error decorators
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(f"{self.bot.EMOJIS['CROWN']} You don't have the necessary permissions to use this command. {self.bot.EMOJIS['CROWN']}")
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send(f"{self.bot.EMOJIS['SPARKLE']} Could not find that member. {self.bot.EMOJIS['SPARKLE']}")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"{self.bot.EMOJIS['SPARKLE']} Missing argument(s) for this command. Check `eli help {ctx.command.name}`. {self.bot.EMOJIS['SPARKLE']}")
        else:
            print(f"Unhandled error in Moderation cog: {error}")
            # You might want to send a generic error message or log it
            # await ctx.send(f"{self.bot.EMOJIS['HEART']} An unexpected error occurred in a moderation command: {error} {self.bot.EMOJIS['HEART']}")

# --- Setup function for the cog ---
# This function is REQUIRED for discord.py to load the cog
async def setup(bot):
    # This line loads the Moderation cog and automatically registers
    # all commands (prefix and slash) defined within it.
    await bot.add_cog(Moderation(bot))

    # IMPORTANT: Do NOT manually add app_commands that are already defined inside a cog.
    # bot.add_cog() handles this automatically.
    # If you have other slash commands in main.py that are NOT part of a cog,
    # you would add them to bot.tree there.
