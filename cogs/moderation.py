import discord
from discord.ext import commands
import asyncio # Needed for unmute/mute timing
import datetime # Needed for timestamps

# Import your helper functions from utils.py
from utils import load_warnings, save_warnings, load_modlog_settings, save_modlog_settings, send_modlog_embed, parse_duration

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # You can keep track of muted users if needed, though Discord's timeout handles most of it
        self.muted_users = {} 

        # --- Automod Configuration (PLACEHOLDERS) ---
        # IMPORTANT: For a real bot, you'd want to load these from a config file or database
        # rather than hardcoding them here. For now, replace these with your actual lists.
        self.BLACKLISTED_WORDS = ["asshole", "bitch", "fuck", "motherfucker" ,"pussy" , "slut" , "nigga" , "nigger" , "mofo" , "bokachoda" , "chut" , "behenchod" ,"cock" ,"dickhead" ,"dick" , "bkl" , "madarchod"] # Example words
        self.BLACKLISTED_LINKS = ["instagram.com", "discord.gg"] # Example links

    # --- Hierarchy Check Helper Method ---
    # This helper is specific to moderation commands, so it's a method of this cog
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

    # --- Warn Command ---
    @commands.command(name='warn')
    @commands.has_permissions(moderate_members=True)
    async def warn_user(self, ctx, member: discord.Member, *, reason: str = "No reason provided."):
        """Warns a member. Usage: eli warn <@user> [reason]
        Requires 'Moderate Members' permission."""

        if not await self._check_hierarchy(ctx, member, "warn"):
            return

        warnings = load_warnings()
        guild_id = str(ctx.guild.id)
        user_id = str(member.id)

        if guild_id not in warnings:
            warnings[guild_id] = {}
        if user_id not in warnings[guild_id]:
            warnings[guild_id][user_id] = []

        warnings[guild_id][user_id].append({
            'reason': reason,
            'moderator_id': ctx.author.id,
            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat()
        })
        save_warnings(warnings)

        warning_count = len(warnings[guild_id][user_id])

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
        warnings = load_warnings()
        guild_id = str(ctx.guild.id)
        user_id = str(member.id)

        if guild_id not in warnings or user_id not in warnings[guild_id] or not warnings[guild_id][user_id]:
            await ctx.send(f"{member.mention} has no warnings in this server.")
            return

        user_warnings = warnings[guild_id][user_id]
        embed = discord.Embed(
            title=f"{self.bot.EMOJIS['STAR']} Warnings for {member.display_name} {self.bot.EMOJIS['STAR']}",
            color=0xFFB6C1,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
        embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)

        for i, warning in enumerate(user_warnings):
            moderator = self.bot.get_user(warning['moderator_id'])
            mod_name = moderator.mention if moderator else "Unknown User"
            timestamp = datetime.datetime.fromisoformat(warning['timestamp'])
            embed.add_field(
                name=f"Warning #{i+1}",
                value=(
                    f"{self.bot.EMOJIS['SPARKLE']} **Reason:** {warning['reason']}\n"
                    f"{self.bot.EMOJIS['RIBBON']} **Moderator:** {mod_name}\n"
                    f"{self.bot.EMOJIS['FLOWER']} **Date:** {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}"
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
            print(f"Error in unban_user: {error}")

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

        timeout_until = datetime.datetime.now(datetime.timezone.utc) + time_delta

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
        modlog_settings = load_modlog_settings()
        modlog_settings[str(ctx.guild.id)] = str(channel.id)
        save_modlog_settings(modlog_settings)

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

    # --- Automod on_message event listener ---
    @commands.Cog.listener() # This decorator tells discord.py it's an event listener within a cog
    async def on_message(self, message):
        """Automod logic to delete blacklisted words and links."""
        # Ignore messages from bots themselves
        if message.author.bot:
            return

        # Ignore DMs
        if message.guild is None:
            return

        # Check for blacklisted words
        for word in self.BLACKLISTED_WORDS:
            if word.lower() in message.content.lower():
                try:
                    await message.delete()
                    await message.channel.send(f"{self.bot.EMOJIS['SPARKLE']} {message.author.mention}, that word is not allowed! {self.bot.EMOJIS['SPARKLE']}", delete_after=5)
                    print(f"Deleted message from {message.author.name} for blacklisted word in {message.channel.name}.")
                    await send_modlog_embed(
                        self.bot, # Pass the bot instance
                        message.guild,
                        "Automod",
                        message.author,
                        self.bot.user, # Bot is the moderator for automod
                        f"Used blacklisted word: '{word}'"
                    )
                    return # Stop processing after finding one blacklisted word
                except discord.Forbidden:
                    print(f"Bot lacks permissions to delete messages in {message.channel.name}.")
                    return
                except Exception as e:
                    print(f"Error deleting message for blacklisted word: {e}")
                    return

        # Check for blacklisted links
        for link in self.BLACKLISTED_LINKS:
            if link.lower() in message.content.lower():
                try:
                    await message.delete()
                    await message.channel.send(f"{self.bot.EMOJIS['SPARKLE']} {message.author.mention}, that link is not allowed! {self.bot.EMOJIS['SPARKLE']}", delete_after=5)
                    print(f"Deleted message from {message.author.name} for blacklisted link in {message.channel.name}.")
                    await send_modlog_embed(
                        self.bot, # Pass the bot instance
                        message.guild,
                        "Automod",
                        message.author,
                        self.bot.user,
                        f"Posted blacklisted link: '{link}'"
                    )
                    return # Stop processing after finding one blacklisted link
                except discord.Forbidden:
                    print(f"Bot lacks permissions to delete messages for links in {message.channel.name}.")
                    return
                except Exception as e:
                    print(f"Error deleting message for blacklisted link: {e}")
                    return
        
         # --- Interactive Responses (run these after automod) ---
        # Do not respond if the message is a command (starts with the bot's prefix)
        if message.content.lower().startswith(self.bot.command_prefix.lower()):
            return

        # Convert message content to lowercase for easier comparison
        msg_content = message.content.lower()

        if "thank you eli" in msg_content or "thanks eli" in msg_content or "ty eli" in msg_content:
                await message.channel.send(f"You're very welcome, {message.author.mention}! Glad I could help. {self.bot.EMOJIS['HEART']}")
                return

        if "love you eli" in msg_content or "ily eli" in msg_content :
                await message.channel.send(f"Aww, I love you too, {message.author.mention}! {self.bot.EMOJIS['MANYBUTTERFLIES']}")
                return
        
        if "hi" in msg_content:
                words = msg_content.split()
                if "hi" in words or any(word.startswith("hi") for word in words) or any(word.endswith("hi") for word in words):
                    await message.channel.send(f"Hi there, {message.author.mention}! {self.bot.EMOJIS['FLOWER']}")
                    return

        # Respond if someone says "hello"
        if "hello" in msg_content:
             words = msg_content.split()
             if "hello" in words or any(word.startswith("hello") for word in words) or any(word.endswith("hello") for word in words):
                await message.channel.send(f"Hello, {message.author.mention}! {self.bot.EMOJIS['SPARKLE']}")
                return # Stop here
        
        if "good morning" in msg_content or "gm" in msg_content:
                await message.channel.send(f"Good morning, {message.author.mention}! Hope you have a wonderful day. {self.bot.EMOJIS['STAR']}")
                return
        
        if "what can you do" in msg_content or "what are your commands" in msg_content:
                await message.channel.send(f"I can do quite a lot! Type `{self.bot.command_prefix}cmds` to see all my commands. {self.bot.EMOJIS['RIBBON']}")
                return
        
        if "bye" in msg_content or "goodbye" in msg_content:
                await message.channel.send(f"See you later, {message.author.mention}! {self.bot.EMOJIS['BUTTERFLY']}")
                return
        
        # Respond if someone says "eli"
        if "eli" in msg_content:
            # Add a check to prevent responding if "eli" is just part of a longer word
            # This simple check ensures "eli" is either a standalone word or at the start/end
            # For more robust checking, you'd use regex (but this is simpler for now)
            words = msg_content.split()
            if "eli" in words or any(word.startswith("eli") for word in words) or any(word.endswith("eli") for word in words):
                await message.channel.send(f"Hello {message.author.mention}, how may I help you? {self.bot.EMOJIS['HEART']}")
                return # Stop here to prevent multiple responses for one message

        # You can add more interactive responses here following the same pattern:
        # if "your_phrase" in msg_content:
        #     await message.channel.send(f"Your response!")
        #     return # Crucial to stop after one response

    # Add more error handlers if needed for moderation commands.
    # A general error handler for the cog can be implemented as shown in General cog.
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
    await bot.add_cog(Moderation(bot))