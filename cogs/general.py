import discord
from discord.ext import commands
import datetime
import os # Needed for os.getenv('BOT_OWNER_ID') if you still use it in botinfo

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot # This allows the cog to access the bot instance

    # You can access emojis via self.bot.EMOJIS['NAME'] now
    # For readability, let's create local references in __init__ or use them directly.
    # For consistency with prior examples, let's use direct access via self.bot.EMOJIS

    # --- ping Command ---
    @commands.command(name='ping')
    async def ping(self, ctx):
        """Checks the bot's latency."""
        latency = round(self.bot.latency * 1000) # Convert to milliseconds
        await ctx.send(f"Pong! {self.bot.EMOJIS['SPARKLE']} Latency: {latency}ms")

    # --- Say Command ---
    @commands.command(name='say')
    async def say_message(self, ctx, *, message: str = None):
        """Makes the bot say something in the current channel. If no message is provided,
        it will prompt the user to say something within 30 seconds.
        Usage: eli say <your message> or eli say (then type message)"""

        if message is None:
            await ctx.send(f"{self.bot.EMOJIS['SPARKLE']} What would you like me to say? You have 30 seconds to respond. {self.bot.EMOJIS['SPARKLE']}")

            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel

            try:
                msg = await self.bot.wait_for('message', check=check, timeout=30.0)
                message = msg.content
            except asyncio.TimeoutError: # Import asyncio if not already
                await ctx.send(f"{self.bot.EMOJIS['HEART']} You didn't say anything in time! {self.bot.EMOJIS['HEART']}")
                return

        # Delete the command message to make it look cleaner
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass # Bot doesn't have permission to delete messages

        await ctx.send(message)

    # --- serverinfo Command ---
    @commands.command(name='serverinfo', aliases=['guildinfo', 'server'])
    async def server_info(self, ctx):
        """Displays information about the server."""
        guild = ctx.guild

        embed = discord.Embed(
            title=f"{self.bot.EMOJIS['RIBBON']} Server Info: {guild.name} {self.bot.EMOJIS['RIBBON']}",
            color=0xFFB6C1 # Pinkish color
        )
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)

        embed.add_field(name=f"{self.bot.EMOJIS['SPARKLE']} Server Name", value=guild.name, inline=True)
        embed.add_field(name=f"{self.bot.EMOJIS['STAR']} Server ID", value=guild.id, inline=True)
        embed.add_field(name=f"{self.bot.EMOJIS['CROWN']} Owner", value=guild.owner.mention if guild.owner else "N/A", inline=True)
        embed.add_field(name=f"{self.bot.EMOJIS['FLOWER']} Members", value=guild.member_count, inline=True)
        embed.add_field(name=f"{self.bot.EMOJIS['HEART']} Channels", value=len(guild.channels), inline=True)
        embed.add_field(name=f"{self.bot.EMOJIS['RIBBON']} Roles", value=len(guild.roles), inline=True)
        embed.add_field(name=f"{self.bot.EMOJIS['SPARKLE']} Creation Date", value=guild.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"), inline=False)

        await ctx.send(embed=embed)

    # --- botinfo Command ---
    @commands.command(name='botinfo')
    async def get_bot_info(self, ctx):
        """Displays information and statistics about the bot."""

        # Access BOT_START_TIME from the bot instance
        uptime_delta = datetime.datetime.now(datetime.timezone.utc) - self.bot.BOT_START_TIME_REF

        # Format uptime nicely
        days, remainder = divmod(int(uptime_delta.total_seconds()), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        uptime_string_parts = []
        if days:
            uptime_string_parts.append(f"{days}d")
        if hours:
            uptime_string_parts.append(f"{hours}h")
        if minutes:
            uptime_string_parts.append(f"{minutes}m")
        if seconds or not uptime_string_parts:
            uptime_string_parts.append(f"{seconds}s")

        uptime_str = " ".join(uptime_string_parts)


        embed = discord.Embed(
            title=f"{self.bot.EMOJIS['CROWN']} Eli Bot Information {self.bot.EMOJIS['CROWN']}",
            description=f"{self.bot.EMOJIS['HEART']} All about your friendly moderation bot! {self.bot.EMOJIS['HEART']}",
            color=0xFFB6C1
        )
        embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else None)
        embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)

        # General Info
        embed.add_field(name=f"{self.bot.EMOJIS['RIBBON']} Name", value=self.bot.user.name, inline=True)
        embed.add_field(name=f"{self.bot.EMOJIS['STAR']} ID", value=self.bot.user.id, inline=True)
        embed.add_field(name=f"{self.bot.EMOJIS['FLOWER']} Prefix", value=f"`{self.bot.command_prefix}`", inline=True)

        # Stats
        embed.add_field(name=f"{self.bot.EMOJIS['STAR']} Servers", value=len(self.bot.guilds), inline=True)
        embed.add_field(name=f"{self.bot.EMOJIS['FLOWER']} Users Served", value=len(self.bot.users), inline=True)
        embed.add_field(name=f"{self.bot.EMOJIS['SPARKLE']} Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        embed.add_field(name=f"{self.bot.EMOJIS['RIBBON']} Uptime", value=uptime_str, inline=False)

        # Other Info
        embed.add_field(name=f"{self.bot.EMOJIS['SPARKLE']} Library", value=f"discord.py v{discord.__version__}", inline=True)
        embed.add_field(name=f"{self.bot.EMOJIS['CROWN']} Owner", value=f"<@{os.getenv('BOT_OWNER_ID') or 'Not Set'}>", inline=True)
        embed.add_field(name=f"{self.bot.EMOJIS['RIBBON']} Created On", value=self.bot.user.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"), inline=False)


        await ctx.send(embed=embed)

    # --- userinfo Command ---
    @commands.command(name='userinfo', aliases=['whois'])
    async def user_info(self, ctx, member: discord.Member = None):
        """Displays detailed information about a user.
        Usage: eli userinfo [member_mention_or_id]"""

        if member is None:
            member = ctx.author

        embed = discord.Embed(
            title=f"{self.bot.EMOJIS['FLOWER']} User Info: {member.display_name} {self.bot.EMOJIS['FLOWER']}",
            color=0xFFB6C1,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
        embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)

        # General User Information
        embed.add_field(name=f"{self.bot.EMOJIS['RIBBON']} User", value=member.mention, inline=False)

        if hasattr(member, 'discriminator') and member.discriminator != '0':
            embed.add_field(name=f"{self.bot.EMOJIS['SPARKLE']} Username", value=f"{member.name}#{member.discriminator}", inline=True)
        else:
            embed.add_field(name=f"{self.bot.EMOJIS['SPARKLE']} Username", value=member.name, inline=True)

        embed.add_field(name=f"{self.bot.EMOJIS['STAR']} User ID", value=member.id, inline=True)
        embed.add_field(name=f"{self.bot.EMOJIS['RIBBON']} Account Created", value=member.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"), inline=False)

        # Guild-Specific Information
        if isinstance(member, discord.Member):
            embed.add_field(name=f"{self.bot.EMOJIS['STAR']} Joined Server", value=member.joined_at.strftime("%Y-%m-%d %H:%M:%S UTC"), inline=False)

            # Roles
            roles = [role.mention for role in member.roles if role.name != "@everyone"]
            roles.reverse()
            embed.add_field(name=f"{self.bot.EMOJIS['RIBBON']} Roles ({len(roles)})", value="\n".join(roles) if roles else "No roles (except @everyone)", inline=False)
            embed.add_field(name=f"{self.bot.EMOJIS['CROWN']} Top Role", value=member.top_role.mention, inline=True)

            # Status
            status_map = {
                discord.Status.online: "Online",
                discord.Status.idle: "Idle",
                discord.Status.dnd: "Do Not Disturb",
                discord.Status.offline: "Offline"
            }
            embed.add_field(name=f"{self.bot.EMOJIS['HEART']} Status", value=status_map.get(member.status, "Unknown"), inline=True)

            # Activities
            activities = []
            for activity in member.activities:
                if isinstance(activity, discord.Game):
                    activities.append(f"Playing **{activity.name}**")
                elif isinstance(activity, discord.Streaming):
                    activities.append(f"Streaming **{activity.name}** on {activity.platform}")
                elif isinstance(activity, discord.Activity):
                    activities.append(f"{activity.name}")
                elif isinstance(activity, discord.CustomActivity):
                     activities.append(f"Custom Status: {activity.name}")

            if activities:
                embed.add_field(name=f"{self.bot.EMOJIS['BUTTERFLY']} Activities", value="\n".join(activities), inline=False)
            else:
                embed.add_field(name=f"{self.bot.EMOJIS['BUTTERFLY']} Activities", value="No current activity.", inline=False)

        else:
            embed.add_field(name="Note", value="This user is not currently in this server.", inline=False)

        await ctx.send(embed=embed)

    # --- Error Handling for General Commands (inside the cog) ---
    @user_info.error # Example error handler for user_info
    async def user_info_error(self, ctx, error):
        if isinstance(error, commands.MemberNotFound):
            await ctx.send(f"{self.bot.EMOJIS['SPARKLE']} Could not find that member. Please make sure you spelled the name correctly or provided a valid ID/mention. {self.bot.EMOJIS['SPARKLE']}")
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"{self.bot.EMOJIS['SPARKLE']} Invalid argument. Please mention a member or provide their ID. Usage: `eli userinfo [member_mention_or_id]` {self.bot.EMOJIS['SPARKLE']}")
        else:
            await ctx.send(f"{self.bot.EMOJIS['HEART']} An error occurred: {error} {self.bot.EMOJIS['HEART']}")
            print(f"Error in user_info: {error}")

    # Add more error handlers here if needed for ping, say, serverinfo, botinfo
    # For example:
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        # This is a general error handler for commands within this cog
        # Specific command error handlers (like user_info_error above) will take precedence
        if hasattr(ctx.command, 'on_error'):
            return # Let the command's local error handler deal with it

        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"{self.bot.EMOJIS['SPARKLE']} Missing argument(s) for this command. Check `eli help {ctx.command.name}`. {self.bot.EMOJIS['SPARKLE']}")
        # Add other common error types you want to handle globally for this cog
        # elif isinstance(error, commands.BadArgument):
        #     await ctx.send(...)
        # elif isinstance(error, commands.CommandNotFound):
        #     await ctx.send(f"{self.bot.EMOJIS['SPARKLE']} That's not a recognized command. Type `eli cmds` for a list of commands. {self.bot.EMOJIS['SPARKLE']}")
        # else:
        #     print(f"Unhandled error in General cog: {error}")
        #     await ctx.send(f"{self.bot.EMOJIS['HEART']} An unexpected error occurred: {error} {self.bot.EMOJIS['HEART']}")


# --- Setup function for the cog ---
# This function is REQUIRED for discord.py to load the cog
async def setup(bot):
    await bot.add_cog(General(bot))